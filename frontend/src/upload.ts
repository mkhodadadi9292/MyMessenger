import { sha256 } from '@noble/hashes/sha2.js'
import { bytesToHex } from '@noble/hashes/utils.js'

import { api } from './api'
import type { ArtifactKind } from './types'

const HASH_READ_SIZE = 1024 * 1024
const CHUNK_CONCURRENCY = 3
const MAX_CHUNK_ATTEMPTS = 5
const MAX_RESUME_ROUNDS = 3
const BACKOFF_BASE_MS = 500
const BACKOFF_MAX_MS = 8000

export type UploadPhase = 'hashing' | 'uploading' | 'finishing'

export interface UploadProgress {
  phase: UploadPhase
  loaded: number
  total: number
}

export interface UploadRequest {
  chatId: number
  file: File
  kind: ArtifactKind
  replyToId: number | null
  onProgress?: (progress: UploadProgress) => void
}

export interface UploadHandle {
  done: Promise<void>
  cancel: () => void
}

interface UploadTicket {
  upload_id: string
  ticket: string
  upload_url: string
}

interface UploadState {
  upload_id: string
  status: string
  chunk_size: number
  total_chunks: number
  size_bytes: number
  received_chunks: number[]
}

export class UploadCancelledError extends Error {
  constructor() {
    super('upload cancelled')
  }
}

export class FileServiceError extends Error {
  constructor(
    public status: number,
    message: string,
    public missingChunks: number[] = [],
  ) {
    super(message)
  }
}

class ChunkRetriesExhaustedError extends Error {}

const RETRYABLE_STATUSES = new Set([408, 429, 500, 502, 503, 504])

function backoffDelay(attempt: number): number {
  const exponential = Math.min(BACKOFF_MAX_MS, BACKOFF_BASE_MS * 2 ** attempt)
  return exponential / 2 + Math.random() * (exponential / 2)
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(new UploadCancelledError())
    const timer = setTimeout(resolve, ms)
    signal.addEventListener(
      'abort',
      () => {
        clearTimeout(timer)
        reject(new UploadCancelledError())
      },
      { once: true },
    )
  })
}

async function readError(response: Response): Promise<FileServiceError> {
  let detail = response.statusText || `upload failed (${response.status})`
  let missing: number[] = []
  try {
    const body = await response.json()
    detail = body.detail ?? detail
    missing = body.missing_chunks ?? []
  } catch {
    detail = `upload failed (${response.status})`
  }
  return new FileServiceError(response.status, detail, missing)
}

export async function sha256OfFile(
  file: Blob,
  signal: AbortSignal,
  onProgress?: (loaded: number) => void,
): Promise<string> {
  const hasher = sha256.create()
  for (let offset = 0; offset < file.size; offset += HASH_READ_SIZE) {
    if (signal.aborted) throw new UploadCancelledError()
    const piece = await file.slice(offset, offset + HASH_READ_SIZE).arrayBuffer()
    hasher.update(new Uint8Array(piece))
    onProgress?.(Math.min(file.size, offset + HASH_READ_SIZE))
  }
  return bytesToHex(hasher.digest())
}

class ChunkedUpload {
  private readonly controller = new AbortController()
  private ticket: UploadTicket | null = null
  private uploadedBytes = 0

  constructor(private readonly request: UploadRequest) {}

  cancel(): void {
    if (this.controller.signal.aborted) return
    this.controller.abort()
    const ticket = this.ticket
    if (ticket) {
      void fetch(`${ticket.upload_url}/${ticket.upload_id}`, {
        method: 'DELETE',
        headers: this.headers(ticket),
      }).catch(() => undefined)
    }
  }

  async run(): Promise<void> {
    const { file, chatId, kind, replyToId } = this.request
    const signal = this.controller.signal
    const digest = await sha256OfFile(file, signal, (loaded) =>
      this.report('hashing', loaded, file.size),
    )
    if (signal.aborted) throw new UploadCancelledError()
    const ticket = await api<UploadTicket>(`/chats/${chatId}/uploads`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file_name: file.name,
        size_bytes: file.size,
        mime_type: file.type,
        kind,
        sha256: digest,
        reply_to_id: replyToId,
      }),
    })
    this.ticket = ticket
    if (signal.aborted) {
      this.cancel()
      throw new UploadCancelledError()
    }
    let state = await this.call<UploadState>(ticket.upload_url, { method: 'POST' })
    for (let round = 0; round < MAX_RESUME_ROUNDS; round++) {
      this.uploadedBytes = this.bytesOf(state, state.received_chunks)
      this.report('uploading', this.uploadedBytes, file.size)
      const missing = this.missingChunks(state)
      try {
        await this.uploadChunks(state, missing)
        this.report('finishing', file.size, file.size)
        await this.call(`${ticket.upload_url}/${ticket.upload_id}/complete`, { method: 'POST' })
        return
      } catch (err) {
        const resumable =
          err instanceof ChunkRetriesExhaustedError ||
          (err instanceof FileServiceError && err.missingChunks.length > 0)
        if (!resumable || round === MAX_RESUME_ROUNDS - 1) throw err
        await sleep(backoffDelay(round + 2), signal)
        state = await this.call<UploadState>(`${ticket.upload_url}/${ticket.upload_id}`, {
          method: 'GET',
        })
      }
    }
  }

  private headers(ticket: UploadTicket): Record<string, string> {
    return { Authorization: `Bearer ${ticket.ticket}` }
  }

  private report(phase: UploadPhase, loaded: number, total: number): void {
    this.request.onProgress?.({ phase, loaded, total })
  }

  private missingChunks(state: UploadState): number[] {
    const received = new Set(state.received_chunks)
    return Array.from({ length: state.total_chunks }, (_, i) => i).filter((i) => !received.has(i))
  }

  private chunkBounds(state: UploadState, index: number): [number, number] {
    const start = index * state.chunk_size
    return [start, Math.min(state.size_bytes, start + state.chunk_size)]
  }

  private bytesOf(state: UploadState, indices: number[]): number {
    return indices.reduce((sum, i) => {
      const [start, end] = this.chunkBounds(state, i)
      return sum + (end - start)
    }, 0)
  }

  private async call<T>(url: string, init: RequestInit): Promise<T> {
    const ticket = this.ticket
    if (!ticket) throw new Error('upload has no ticket')
    let response: Response
    try {
      response = await fetch(url, {
        ...init,
        headers: { ...this.headers(ticket), ...(init.headers as Record<string, string>) },
        signal: this.controller.signal,
      })
    } catch (err) {
      if (this.controller.signal.aborted) throw new UploadCancelledError()
      throw err
    }
    if (!response.ok) throw await readError(response)
    return (await response.json()) as T
  }

  private async uploadChunks(state: UploadState, indices: number[]): Promise<void> {
    const queue = [...indices]
    const worker = async () => {
      for (let index = queue.shift(); index !== undefined; index = queue.shift()) {
        await this.uploadChunkWithRetry(state, index)
      }
    }
    await Promise.all(Array.from({ length: Math.min(CHUNK_CONCURRENCY, queue.length) }, worker))
  }

  private async uploadChunkWithRetry(state: UploadState, index: number): Promise<void> {
    const ticket = this.ticket!
    const signal = this.controller.signal
    const [start, end] = this.chunkBounds(state, index)
    const body = this.request.file.slice(start, end)
    for (let attempt = 0; attempt < MAX_CHUNK_ATTEMPTS; attempt++) {
      if (signal.aborted) throw new UploadCancelledError()
      let response: Response | null = null
      try {
        response = await fetch(`${ticket.upload_url}/${ticket.upload_id}/chunks/${index}`, {
          method: 'PUT',
          headers: { ...this.headers(ticket), 'Content-Type': 'application/octet-stream' },
          body,
          signal,
        })
      } catch {
        if (signal.aborted) throw new UploadCancelledError()
      }
      if (response?.ok) {
        this.uploadedBytes += end - start
        this.report('uploading', this.uploadedBytes, this.request.file.size)
        return
      }
      if (response && !RETRYABLE_STATUSES.has(response.status)) throw await readError(response)
      await sleep(backoffDelay(attempt), signal)
    }
    throw new ChunkRetriesExhaustedError(`chunk ${index} failed after ${MAX_CHUNK_ATTEMPTS} attempts`)
  }
}

export function startUpload(request: UploadRequest): UploadHandle {
  const upload = new ChunkedUpload(request)
  return { done: upload.run(), cancel: () => upload.cancel() }
}
