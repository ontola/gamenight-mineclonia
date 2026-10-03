# Windows candidate verification — 3 October 2026

Engine: dd6057695478ff562b5d409f3f5254e2bde0cac6.
Adapter used by local candidate: d8e41fd.
Mineclonia: 0.123.1. Embedded Python: 3.13.7.

## Passed

- 31 adapter unit tests.
- Native controller binding, stale-frame and directional-focus tests.
- Clean Windows engine CI build:
  https://github.com/ontola/luanti/actions/runs/37150848986
- Packaged embedded Python launch self-test.
- Real server plus two rendered clients, driven through the adapter with scripted host frames.
- The former fixed prototype seed now selects dry ground at (0,17,65) and
  (2,17,65). Both players remained standing at y=17.5 after joining.
- Test process completed with exit code zero and save-aware shutdown.

The local candidate archive is 54,986,492 bytes (about 55 MB).
SHA-256: cdb828a20a01622265755ba4841ca02c1d67af67789474f8bb067d2e4f895d43.

## Required before store publication

- Visually inspect focus navigation, A/B actions, inventory movement and crafting
  at two-player screen size. Computer Use app approval timed out, so no screenshot
  or visual pass is claimed.
- Physical controller check: each player independent; reconnect; menus; inventory;
  camera feel; controller drift and neutral input on resume.
- Verify the final CI package through the installer and current host contract.
- Capture and review the required gameplay montage and store artwork.
- Publish a checksummed release, add package-matched catalog evidence, and verify
  the live listing.

The source repositories exist and the package builds. The public store listing
is not published. Scripted input and a successful build do not establish the
quality of a physical controller playtest.
