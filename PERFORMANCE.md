# Windows performance observations — 4 October 2026

Tested release candidate: v0.1.3, SHA-256
`f194308f4ca66fe03ce199cd421718fec7e623d60ee2437348c65e3fca12c30b`.
Engine `956935bea670ef529a80dbe35f37b80271b0ae60`; adapter
`6ccef67fbc19ec5f488dbd0bf177c8f3ef99a51f`.

## Results

Each range spans the active views. Peak working set includes clients and server.

| Players | Scene | Mean FPS per view | Frame time p95 | Peak working set |
| --- | --- | --- | --- | --- |
| 1 | stationary | 53.5–53.5 | 34.8–34.8 | 0.90 GB |
| 1 | camera_pan | 54.0–54.0 | 34.7–34.7 | 1.01 GB |
| 2 | stationary | 53.9–54.2 | 30.3–31.3 | 1.33 GB |
| 2 | camera_pan | 54.0–54.1 | 28.6–29.1 | 1.38 GB |
| 3 | stationary | 52.9–53.0 | 30.4–32.3 | 1.78 GB |
| 3 | camera_pan | 50.8–51.1 | 37.2–39.6 | 1.94 GB |
| 4 | stationary | 50.9–51.4 | 36.8–38.2 | 2.19 GB |
| 4 | camera_pan | 45.9–48.2 | 48.8–58.0 | 2.35 GB |

Four players are playable in these short scenes, but the camera sweep has visible
frame-time spikes; this is not a locked-60-FPS result. Keep the experimental label.

## Method and limits

- Windows, AMD Ryzen 9 5900X (12 cores/24 threads), NVIDIA RTX 5070 Ti
  (16,303 MiB reported VRAM), driver 617.14, approximately 64 GiB system RAM.
- 3840×2160 desktop. Solo: 3840×2160; two: 1920×2160 each;
  three: one 1920×2160 plus two 1920×1080; four: 1920×1080 each.
- 60 FPS cap, viewing range 60, cached assets and a shared starting-area world.
  Each scene warmed up for 10 seconds and measured for 20 seconds.
- Opt-in buffered renderer-completion timestamps measure elapsed frame intervals,
  including pacing and operating-system scheduling. They do not measure GPU time.
  No image capture ran during measurement. CPU and memory came from psutil.
- Normal desktop apps and an unrelated older Luanti process remained open.
  Combined working set can count shared pages more than once.
- The one-/two-player runs measured before scripted input checks; the three-/four-
  player runs measured afterwards. The world fixture is shared, but exact player
  poses differ. These observations are not a controlled scaling benchmark.
- Heavy mobs, large builds, extended sessions, arbitrary mods and slower hardware
  need separate measurements. Physical controller feel is not measured here.

## Fixed background frame cap

The previous engine treated all but the Windows-focused view as background and
capped them at 30 FPS. Every active GameNight viewport now uses the foreground cap;
paused hidden views keep the background cap. On the same two-player fixture:

| Engine | Stationary mean FPS | Camera-pan mean FPS |
| --- | --- | --- |
| Before (`0d789169`) | 54.2 / 28.1 | 53.4 / 28.0 |
| After (`956935be`) | 53.9 / 54.2 | 54.1 / 54.0 |

## Build cache

GitHub Actions build step: 4m39s for a cold engine build (run 37215658111),
10s for the next adapter-only build (run 37216107186). The latter reports
`engine_cache_hit: true`. The cache key includes the complete pinned engine source
and build recipe, and cache archive hashes are checked before use. Engine changes
correctly trigger a new build.

Machine-readable reports, including the initial four-player fixture precondition
failure and its independently seeded repeat, are in `verification/v0.1.3.json`.
