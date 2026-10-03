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
