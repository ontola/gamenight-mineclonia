# Windows v0.1.3 verification — 4 October 2026

Exact package SHA-256: `f194308f4ca66fe03ce199cd421718fec7e623d60ee2437348c65e3fca12c30b`.
Adapter: `6ccef67fbc19ec5f488dbd0bf177c8f3ef99a51f`.
Engine: `956935bea670ef529a80dbe35f37b80271b0ae60`.
Later harness-only commit `2e78137` moves control checks before camera sweeps and
waits for profile acknowledgements. It changes no packaged runtime files.

- 54 Python tests, Lua profile/paused-reconnect/safe-spawn tests, native binding,
  navigation, layout and host-frame tests passed. Ruff format/check passed.
- The exact Windows package passed one-, two-, three- and four-player readiness,
  dry spawn, independent scripted input, pause/resume, live profile updates and
  host-disconnect process cleanup checks.
- Four-player seat shuffle preserved every named carried/crafting/equipment item
  slot and saved position. A replacement profile received a separate account and
  left the former owner's save intact. Mineclonia's regenerated virtual hand list
  is excluded; inventory IDs are compared by stable list name.
- The first four-player fixture had empty carried inventories for some players.
  A new copy seeded with distinct stacks (11/12/13/14 cobblestone) passed every
  ownership assertion. Both reports are retained in `verification/v0.1.3.json`.
- Live mod install and undo each validated, checkpointed, restarted the server,
  reconnected all four profiles and returned the expected receipt/settings.
- Real rendered frame-time and memory observations for all player counts are in
  [PERFORMANCE.md](PERFORMANCE.md). Active unfocused views now use the same FPS
  cap as the focused view. Four players still show frame-time spikes.
- CI engine caching reduced an adapter-only build step from 4m39s to 10s.

**Upgrade:** join the old seats once so legacy Couch1–Couch4 saves are associated
with the right profiles. Preserve the identity registry with the world and its
connection settings. Later seat changes retain ownership automatically.

Physical controller feel, audio audibility and cross-game switching remain
unverified. The read-only physical input observer later found zero devices;
scripted checks cannot substitute for the [hands-on checklist](CONTROLLER-CHECK.md).
The existing v0.1.2 store montage is retained with its original provenance.

## Previous releases

# Windows v0.1.2 profile verification — 4 October 2026

Package SHA-256: `b99021db59007c7728100029d8eb2baa92d61d71caa6f255dab7c81090d62657`.
Adapter: `dede8113ea45b120bb23cd63b402936025f4dd96`. Engine source remains `b7903f56996069669d14ec1b06246cfef8c1f6a9`.

- 42 Python tests passed, including avatar v1/legacy decoding, transparency, shared head anchors, sparse/reordered profile mapping, invalid input and PNG/skin output.
- Lua profile tests passed: HUD updates, reconnect, validation and armor-layer preservation. Dry-spawn migration tests also passed.
- The exact CI package passed native-entrypoint checks with 1 and 4 players: profile names/colors and skin application, independent scripted input, pause/resume, profile updates while paused, and complete child cleanup on host disconnect. Reports: `verification/v0.1.2.json`.
- Visually inspected four synthetic profiles in the real Windows renderer, including character faces, clothing colors, personal skin colors, overhead names and viewport badges.
- The release preview uses the final package engine binary and unchanged shipped bridge/game code. Four staged gameplay cuts were reviewed at desktop and 390px phone widths. See `verification/v0.1.2-preview.json` for source, timestamps and hashes.

Current and legacy profile artwork is supported. Oversized/malformed artwork falls back to a simple face. Profile changes use the existing host `party_updated` message, without restarting the world.

Cosmetics follow profile IDs; inventories and saved positions still follow Couch1–Couch4 seat slots. Upstream chat/death messages can still show internal names. Physical pads, audio, cross-game switching and performance on other hardware remain unverified for this release. Two-/three-player layout coverage remains in the adapter/native tests and the prior v0.1.1 package playtests below.

## Previous release

# Windows v0.1.1 verification — 4 October 2026

Engine: b7903f56996069669d14ec1b06246cfef8c1f6a9.
Adapter: 30fea66835fd34f2e752de38528b32ccf21de8fb. Mineclonia: 0.123.1.

- 36 Python tests passed, including occupied-seat filtering, sparse seats, controller isolation and waiting for every renderer.
- Native viewport tests cover 1–4 players, complete screen coverage, no overlap and odd screen dimensions. Binding, stale-frame and navigation tests also passed in the package build.
- The exact Windows package passed native-entrypoint checks with 1, 2, 3 and 4 players: authentication, connected player count, rendered views, separate scripted movement for each player, pause/resume and host-disconnect cleanup. See verification/v0.1.1.json.
- Lua checks cover finding four dry spawn positions, migrating the old two-position record, reusing four positions and preserving returning players.
- Visually checked full-screen solo, the three-player arrangement and the four-player grid on a 3840×2160 desktop.
- An idle local four-player run used approximately 2.3 GB of combined client/server working-set memory. This was not a frame-rate benchmark.
- First-load testing under concurrent activity exceeded the former 90-second client startup timeout. The package now allows 180 seconds. Preloading and cached subsequent launches remain important.

Player count is chosen before launch; the host prepares a changed lobby roster again. This version does not add or remove viewports during active play.
Physical-controller feel, audio audibility, couch-distance readability and frame rates on other hardware remain unverified. Keep the experimental status.

## Earlier v0.1.0 checks

# Windows candidate verification — 4 October 2026

Engine: 528e03c03ce1a33c8586a96aeda2e4cbe28e9945.
Mineclonia: 0.123.1. Embedded Python: 3.13.7.

## Observed

- 31 adapter unit tests passed.
- Native controller binding, stale-frame and directional-focus tests passed.
- Actual native package entrypoint completed authenticated preparation, two rendered
  views, separate scripted input, world pause/resume, and host-disconnect cleanup.
  The release includes a package-specific report; these are synthetic host checks.
- Reopening a saved world passed after moving spawn validation to the first server tick.
- The former fixed prototype seed selected dry ground at (0,17,65) and (2,17,65).
  New players stood at y=17.5; existing player positions are preserved.
- Visually inspected two-player menu and inventory at a 3840×2160 desktop.
  D-pad and left stick move focus directly. A selects; B closes.
- Selecting Steady look speed persisted in the per-player config.
- Inventory X split and A placement produced two server-side stacks of 32.
  Y transferred the selected stack into the hotbar; item totals remained 64.
- The test worlds use scripted host controller frames, not physical controllers.

## Remaining hardware checks

Physical controller camera feel, reconnect, drift, and comfortable couch-distance
readability need a hands-on playtest. Audio audibility and cross-game switching
have not been certified. The initial store listing must retain experimental status.

## Gameplay capture

The optional renderer recorder and capture/mod stage a separate scratch world.
Recording uses actual Mineclonia rendering, input, mining, building, TNT and
the integration's bounce-pad physics. The staging mod is excluded from packages.
See capture/SHOTS.md for the shot plan and the release media provenance for the
final frame ranges, checksums and encoding checks.
