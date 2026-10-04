# Reliability work — v0.1.3

Completed:

- Split session orchestration, view/process ownership, input routing, persistent
  identities and mod coordination into focused modules.
- Explicit idle, preparing, ready, playing, paused and closed states. Readiness
  requires every renderer and expected connected profile; cleanup handles partial
  launch, validator cancellation and failed bridge writes.
- Profile-owned saves, one-time legacy account claims and atomic ownership records
  included in checkpoints. Real package tests cover seat shuffle and replacement.
- Opt-in renderer timing and CPU/memory observations for 1–4 players. Fixed the
  accidental background FPS cap on active split-screen views.
- Hash-checked engine/download caches, an explicit runtime file list and package
  lifecycle/identity/mod tests. Measured adapter-only build step: 10 seconds.
- Formatted Python glue and CI format/lint checks.

Evidence: [VERIFICATION.md](VERIFICATION.md), [PERFORMANCE.md](PERFORMANCE.md),
`verification/v0.1.3.json`.

Remaining: hands-on controller feel/reconnect, audio, cross-game switching,
extended/heavy-world performance and lower-powered PCs. Use
[CONTROLLER-CHECK.md](CONTROLLER-CHECK.md) for the physical playtest.
