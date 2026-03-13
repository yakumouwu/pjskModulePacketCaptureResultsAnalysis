# Receiver Roadmap (Security / Performance / Feature Expansion)

## 0. Current status
- [x] Capture `suite` / `mysekai` responses
- [x] Decode API payloads
- [x] Render suite card image
- [x] Diamond (`id=12`) detection for mysekai full packet
- [x] Push notification via NapCat HTTP API
- [x] Log rotation and file retention
- [x] Health check endpoint (`/healthz`)

## 1. Security hardening
- [ ] Add shared-secret verification on `/upload` requests (header signature), reject unknown source
- [ ] Move `BOT_TOKEN` / sensitive envs to `.env` or secret manager (avoid shell history exposure)
- [ ] Add optional IP allowlist for upload source
- [ ] Place receiver behind reverse proxy (Nginx/Caddy) with HTTPS
- [ ] Add request size guardrail and explicit 413 response for oversized payloads

## 2. Reliability and resilience
- [ ] Persist dedup cache with periodic flush + graceful shutdown flush
- [ ] Add failed-push retry queue file (`/data/alerts/retry_queue.jsonl`) and background retry worker
- [ ] Add startup self-check: validate NapCat endpoint and token, print clear status
- [ ] Add structured error codes in logs for quick triage
- [ ] Add container readiness endpoint (`/readyz`) in addition to `/healthz`

## 3. Performance and storage
- [ ] Optimize prune strategy (batch prune every N writes instead of every write)
- [ ] Add optional gzip for archived hit JSON
- [ ] Separate retention policy by type:
  - [ ] `suite_raw_keep`
  - [ ] `mysekai_raw_keep`
  - [ ] `suite_json_keep`
  - [ ] `mysekai_json_keep`
  - [ ] `suite_card_keep`
- [ ] Add daily size cap warning (log warning when `/data` usage over threshold)

## 4. Notification features
- [ ] Group push support with optional `@` mention (CQ code or message segment)
- [ ] Push rendered Mysekai map image (in addition to text), with switchable modes: text-only / image-only / text+image
- [ ] Align image push payload with NapCat v4.17.48 action/message format
- [ ] Template system for notification text (single-line / multi-line / compact)
- [ ] Add map label from config file instead of hard-coded mapping
- [ ] Add optional cooldown per `siteId` to reduce spam
- [ ] Add secondary channel fallback (e.g., webhook) when NapCat fails

## 5. Observability
- [ ] Add counters in logs:
  - [ ] total uploads
  - [ ] decode success/fail
  - [ ] alert hit count
  - [ ] push success/fail
- [ ] Add daily summary log task
- [ ] Add simple `/metrics` endpoint (Prometheus text format, optional)

## 6. Config consistency
- [ ] Keep only one canonical variable name: `BOT_PUSH_URL` (deprecate alias warning for `BOT_PUSH_BASE_URL`)
- [ ] Add config validation at startup (missing/invalid env values fail fast)
- [ ] Document all env vars in `README_DOCKER.md` with defaults and examples

## 7. Test plan
- [ ] Unit test for `find_diamond_hits` (multiple sites, multiple drops)
- [ ] Unit test for dedup behavior across restart (with persisted cache)
- [ ] Integration test: mock NapCat endpoint and verify payload
- [ ] Regression test for retention pruning

## 8. Open decisions
- [ ] Primary push target mode by default: `private` or `group`
- [ ] Whether to include source file name in end-user notification
- [ ] Keep alert event logs forever or rotate by days
- [ ] Whether to require HTTPS before production rollout
