export const REACTION_EMOJI = {
  like: '👍',
  heart: '❤️',
  laugh: '😂',
  wow: '😮',
  sad: '😢',
  fire: '🔥',
} as const

export type ReactionCode = keyof typeof REACTION_EMOJI

export const REACTION_CODES = Object.keys(REACTION_EMOJI) as ReactionCode[]