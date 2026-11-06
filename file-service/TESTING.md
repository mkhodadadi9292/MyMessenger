# file-service — what each test guarantees

Run everything: `uv run pytest` (needs Docker for the `redis` / `postgres` tests, or `TEST_REDIS_URL` / `TEST_POSTGRES_URL` pointing at disposable instances; without them those tests **fail** with a clear message instead of skipping).

| Folder | Isolation |
|---|---|
| `tests/unit` | pure Python, in-memory fakes (`tests/fakes.py`), no IO |
| `tests/integration` | HTTP via httpx ASGI, tmp media/chunk dirs, in-memory SQLite, fakeredis for `XADD`/`XRANGE` only |
| `tests/streams` | real `redis:7-alpine` container (testcontainers), `FLUSHDB` around every test |
| `tests/postgres` | real `postgres:17-alpine` container; each test creates and drops its own database |

## unit/test_chunk_plan.py
- `test_total_chunks_rounds_up` — chunk count is `ceil(size / chunk_size)`.
- `test_expected_length_is_chunk_size_except_last` — every chunk is full-size except a shorter last one.
- `test_exact_multiple_has_full_last_chunk` — a size that divides evenly has no short last chunk.
- `test_index_out_of_range_is_rejected` — negative or too-large chunk indices are a validation error.
- `test_missing_lists_absent_indices_in_order` — `missing()` reports exactly the indices not yet received.
- `test_non_positive_sizes_are_rejected` — zero/negative file size or chunk size cannot form a plan.

## unit/test_media_type.py
- `test_sniffs_each_supported_type` — magic bytes map to the right MIME for every allowed type.
- `test_unknown_content_is_not_sniffed` — unrecognised content gives no MIME (so it is rejected).
- `test_declared_type_must_match_content` — the declared MIME must match the sniffed content.
- `test_mp3_alias_matches_mpeg_content` — `audio/mp3` is accepted for MPEG audio content.

## unit/test_ticket_verifier.py
- `test_valid_ticket_yields_claims` — a correctly signed ticket exposes upload id, user, size and the raw token.
- `test_expired_ticket_is_rejected` — expired tickets are refused.
- `test_tampered_ticket_is_rejected` — any change to the payload breaks the signature.
- `test_ticket_signed_with_other_secret_is_rejected` — only the shared upload-ticket secret is trusted.
- `test_wrong_audience_issuer_or_type_is_rejected` — tickets for another audience/issuer, or user access tokens, are refused.
- `test_ticket_is_bound_to_its_upload` — a ticket cannot be used on a different `upload_id`.

## unit/test_upload_service.py
- `test_init_creates_session_with_chunk_plan` — init creates an active session with the server's chunk plan.
- `test_init_is_idempotent_for_active_session` — re-init returns the existing session and its received chunks (resume).
- `test_init_rejects_oversized_upload` — sizes above `MAX_UPLOAD_SIZE_BYTES` are refused (413).
- `test_init_rejects_unsupported_mime` — only the messenger's media MIME types can be uploaded.
- `test_resending_a_chunk_is_idempotent` — sending the same index twice keeps a single chunk.
- `test_out_of_order_chunks_complete_correctly` — chunk order does not matter; the assembled file is byte-identical.
- `test_chunk_length_must_match_plan` — over/under-length chunks and a missing Content-Length are rejected.
- `test_chunk_index_out_of_range_is_rejected` — indices beyond the plan are refused.
- `test_body_longer_than_declared_length_is_cut_off` — a body larger than its Content-Length is rejected and leaves no chunk.
- `test_complete_reports_missing_chunks` — complete lists missing indices and keeps the session active.
- `test_complete_rejects_content_that_differs_from_ticket` — size, sha256 or MIME mismatch fails the upload, keeps no file and publishes nothing.
- `test_complete_publishes_event_and_is_idempotent` — complete publishes exactly one `upload.completed` with ticket, checksum and safe path; repeating is a no-op.
- `test_failed_publish_is_retried_by_outbox_relay` — if Redis is down at completion, the outbox relay publishes later.
- `test_ticket_for_other_upload_is_rejected` — a valid ticket for upload A cannot read upload B.
- `test_abort_discards_chunks_and_blocks_further_chunks` — abort deletes chunks, is idempotent, and closes the session.
- `test_abort_after_complete_is_refused` — a completed upload cannot be aborted (a message may already exist).

## unit/test_cleanup_service.py
- `test_stale_active_sessions_lose_their_chunks` — only active sessions idle past the TTL are purged.
- `test_stuck_assembly_discards_partial_and_planned_file` — crashed assemblies lose their partial and planned file.
- `test_unattached_completed_upload_is_purged_once_streams_are_settled` — a never-attached file is removed only when streams prove no attach is coming.
- `test_unattached_upload_is_kept_while_streams_are_not_settled` — any doubt about stream state keeps the file.
- `test_unattached_upload_without_published_event_is_kept` — a completion not yet announced is never purged.
- `test_completed_upload_inside_grace_period_is_kept` — completed files inside the grace period are kept.
- `test_terminal_uploads_are_purged` — rejected/failed/aborted/expired uploads lose file and chunks.
- `test_attached_files_are_never_purged_by_any_rule` — **no rule ever deletes an attached (referenced) file.**
- `test_orphan_chunk_dirs_without_live_session_are_removed` — leftover chunk dirs go; dirs of live sessions stay.
- `test_chunk_dir_age_uses_utc_regardless_of_local_timezone` — chunk-dir age compares in UTC even when the host timezone is not UTC.

## unit/test_event_contract.py
- `test_default_stream_and_group_names_match_contract` — stream/group names match `contracts/upload-events.v1.json`.
- `test_published_completion_has_exactly_the_contract_fields` — `upload.completed` carries exactly the contract fields.
- `test_outcome_types_match_contract` — outcome types match what the backend publishes.

## integration/test_upload_protocol.py
- `test_full_protocol_stores_verified_file_and_announces_it` — init → out-of-order chunks → status → complete stores the exact file under `artifacts/` and announces it.
- `test_resume_reports_only_received_chunks` — re-init after a gap reports what is already on disk.
- `test_resending_a_chunk_overwrites_it` — retrying a chunk over HTTP is safe.
- `test_complete_with_missing_chunks_is_409_with_list` — the 409 body lists missing chunks for the client to resend.
- `test_checksum_mismatch_is_422_and_leaves_no_file` — a wrong checksum gives 422, no media file, no event, status `failed`.
- `test_mime_mismatch_is_422` — content that is not the declared type is refused.
- `test_chunk_with_wrong_length_is_rejected` — too-long chunk is 413, too-short is 400.
- `test_chunk_index_out_of_range_is_400` — HTTP maps out-of-range indices to 400.
- `test_bad_tickets_are_401` — missing, expired, foreign-upload and tampered tickets are 401.
- `test_upload_of_another_user_is_401` — a ticket for another user cannot touch an existing upload.
- `test_oversized_upload_is_413_at_init` — the size cap is enforced before any bytes are sent.
- `test_abort_removes_chunks` — DELETE removes chunks and further chunks get 409.
- `test_no_file_is_visible_in_media_before_verification` — nothing appears in the public media tree before complete.
- `test_internal_api_requires_key` — the internal cleanup API refuses requests without the right key.
- `test_internal_cleanup_purges_aborted_upload` — the cleaner's terminal rule works end to end over HTTP.
- `test_health` — `/health` answers for the compose healthcheck.

## streams/test_stream_consumer.py (real Redis)
- `test_published_event_is_consumed_and_acked` — a handled event is acked.
- `test_group_created_late_still_sees_earlier_events` — a consumer group created after publishing still receives old events.
- `test_failed_handler_leaves_event_pending` — **no ack when the handler (DB commit) fails.**
- `test_stale_event_is_redelivered_to_another_consumer` — XAUTOCLAIM hands a dead consumer's event to a live one.
- `test_event_goes_to_dead_letters_after_max_deliveries` — after max deliveries the event moves to `<stream>.dead` with its source id.
- `test_keep_pending_check_prevents_dead_lettering` — the keep-pending hook keeps retrying instead of dead-lettering.
- `test_permanent_error_dead_letters_immediately` — malformed events go straight to dead letters.
- `test_run_loop_stops_cleanly` — the worker loop exits promptly on shutdown.

## streams/test_outcome_and_settlement.py (real Redis)
- `test_outcome_event_updates_session` — `upload.attached` / `upload.rejected` move a completed upload to the right state, idempotently.
- `test_unknown_outcome_type_is_dead_lettered` — unknown outcome types are not silently dropped.
- `test_not_settled_before_backend_reads_the_event` — undelivered completions block purging.
- `test_not_settled_while_backend_has_it_pending` — completions the backend is still processing block purging.
- `test_not_settled_while_an_outcome_is_unprocessed` — unapplied outcomes block purging.
- `test_settled_when_backend_acked_and_outcomes_drained` — purging is allowed only when both streams are drained.
- `test_not_settled_when_upload_is_in_dead_letters` — uploads in either dead-letter stream are kept for manual handling.
- `test_settled_after_outcomes_were_applied_and_trimmed` — settlement still works after outcome entries are deleted/trimmed, and a new unprocessed outcome blocks purging again.

## postgres/test_migrations_and_repository.py (real Postgres)
- `test_upgrade_downgrade_upgrade` — the migration history upgrades, downgrades one step and upgrades again on an empty database.
- `test_compare_and_set_transition_on_postgres` — duplicate inserts are refused and status changes are compare-and-set on Postgres.
