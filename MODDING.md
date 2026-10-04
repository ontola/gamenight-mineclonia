# Generated Lua mods for Mineclonia

The session assistant can write original Lua through the public
[GameNight Lua SDK](mod_sdk/API.txt). It can create new usable items and blocks,
combine player queries with timed callbacks, apply velocity, place its own content
near players, and retain small amounts of state. This is separate from the
existing scalar settings and legacy bounce-pad recipe.

## Request and edit

The host advertises `controls.mod_sdk` with version `gamenight-lua-v1`, the API,
installed source and the latest failed candidate/error. A model proposal uses
`action: mod` and `values: {title, code}`. Source is a complete Lua 5.1 program.
`gn` is injected; scripts do not import it. Follow-up requests receive the actual
installed source. A repair request also receives the rejected candidate.

Text and the existing voice transcription UI use the same session-agent route.
The phone/lobby assistant explains the reconnect and displays the installed title.
Only the session owner can apply a shared change. Hosted generation uses the
existing credit reservation/settlement path; local inference spends no hosted
credits. Generation is bounded to 4096 output tokens, 240 seconds for hosted
inference and 600 seconds for the optional local provider. Local generation can
take several minutes on consumer hardware; the UI shows the shared request state.

## Apply and recover

1. Stage source alongside the trusted SDK runtime, identified by SHA-256.
2. Start a separate Mineclonia server/world. Compile and register the content,
   run `gn.check` tests and a player-free tick. Rejection leaves the game running.
3. Recheck session, requesting seat, expiry and world revision.
4. Stop clients and save the server, then checkpoint the entire world.
5. Install the staged source and restart. Reconnect the existing profile accounts
   and controller seats. An initial callback failure restores the checkpoint.
6. Report completion only after every view and profile is ready. A crash during
   installation leaves a recovery marker for the next launch.

New item/node registration currently always uses a restart. Existing scalar
settings still apply live. Later callback errors disable generated behavior and
are shown to the assistant; the world remains available for an edit or undo.

Undo restores the previous source, preserving play since installation. It does
not rewind positions, inventories, terrain or persistent counters. Removed item
and node definitions remain inert so saved content does not become unknown.
Automatic failed-install rollback restores the checkpoint, including world data.

## Execution boundary

Generated code has no filesystem, network, shell, module loading, raw engine
objects or access to `core`. It receives copied values and a bounded facade over
Luanti APIs. Each callback has instruction, allocation-growth and game-operation
budgets. Runtime errors are contained. Text/bytecode/path/size checks apply again
on the host. This is an experimental Lua execution boundary, not an independently
audited OS sandbox; persistent heap growth and extended malicious-code workloads
need further hardening before accepting untrusted shared mod libraries.

The first SDK does not expose arbitrary entities, meshes, external assets, damage,
ordinary terrain replacement, or every Luanti API. It is designed to grow without
turning new mechanics into predefined numeric recipes.

## Test

- `python -m unittest test_generated_mods test_mod_lifecycle` (LuaJIT enables the
  execution tests). Covers original callbacks, grants, persistent data, disallowed
  APIs/bytecode, runaway loops, failed validation and restart recovery.
- `test_package_live.py --generated-fixture PRIVATE_FIXTURE ...` drives a real
  local model, authenticated cloud, public relay, packaged adapter and two engine
  clients. The host protocol frames are scripted. The test-only world probe only
  arranges players/selects the wand; use goes through the controller input path.
- Keep private credentials and provider/account orchestration outside this repo.
  `mod_sdk`, staging, execution, relay integration and recovery remain public.

See `verification/` for observed runs. Voice microphone capture, physical pad feel,
production deployment and arbitrary third-party mod compatibility require their
own checks; do not infer them from a scripted controller test.
