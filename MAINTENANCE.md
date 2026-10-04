# Reliability work

- Separate view/process ownership and controller routing from session orchestration.
- Use explicit idle, preparing, ready, playing, paused and closed states.
- Bind saved accounts to profile IDs. Claim legacy couch accounts once without
  rewriting player databases or mod keys; keep the registry in world checkpoints.
- Test profile changes, seat changes, partial launch and cleanup failures.
- Measure 1–4 clients with render-frame timestamps, CPU and working set after a
  fixed warmup. Keep physical controller observations separate from scripted input.
- Cache engine artifacts using the complete pinned engine specification and build
  recipe; validate archive checksums on every reuse. Ship an explicit runtime list.
- Format Python glue and automate package smoke evidence. Publish only after
  real Windows package validation; report missing hardware observations honestly.
