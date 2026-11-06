# file-cleaner — what each test guarantees

Run: `uv run pytest` (no Docker needed). The cleaner owns no database and no broker: it only calls file-service's internal API, so the integration tests run the **real file-service app** in-process (dev-only path dependency `../file-service`, httpx ASGI transport, in-memory SQLite, tmp media/chunk dirs, fakeredis for stream state).

The deletion rules themselves live in file-service (`file_service/application/cleanup_service.py`) and are also unit-tested there; these tests prove the cleaner drives them correctly and safely.

## unit/test_scheduler.py
- `test_default_policy_covers_every_rule_with_configured_thresholds` — every rule is scheduled and its age threshold comes from settings.
- `test_attach_grace_must_exceed_backend_event_max_age` — the cleaner refuses to start with a grace period that a late backend attach could outlive.
- `test_each_rule_runs_with_its_threshold_and_batch_limit` — each rule is sent with its own threshold and the batch limit.
- `test_rules_respect_their_own_intervals` — each rule runs on its own interval, and the next wake-up time is correct.
- `test_failure_of_one_rule_does_not_stop_the_others` — one failing rule is logged and skipped; others still run.
- `test_http_api_sends_rule_threshold_and_internal_key` — the HTTP call hits `/internal/v1/cleanup/<rule>` with the internal key and JSON body.
- `test_http_errors_surface_so_nothing_is_assumed_deleted` — non-2xx responses raise instead of being treated as success.

## integration/test_against_file_service.py
- `test_stale_incomplete_session_loses_its_chunks` — incomplete sessions older than the TTL lose their chunks; fresh ones are untouched.
- `test_completed_but_never_attached_file_is_removed_after_grace` — a completed file with no attach after the grace period is deleted once the streams are settled.
- `test_unattached_file_is_kept_while_streams_are_unsettled` — when the backend may still attach, the file is kept.
- `test_rejected_upload_file_is_removed` — files of rejected uploads are deleted and the session becomes `purged`.
- `test_leftover_chunk_directories_are_removed` — chunk directories without a live session are removed after their minimum age.
- `test_stuck_assembly_is_cleaned` — crashed assemblies lose their partial/planned file.
- `test_cleaner_never_deletes_referenced_files` — **with every threshold at zero, an attached file, an untracked legacy artifact and an avatar all survive.**
- `test_cleaner_keeps_everything_when_file_service_is_unreachable` — if file-service is down, nothing is reported deleted and the cleaner keeps running.
