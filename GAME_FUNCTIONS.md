# Documented game functions

A game publishes a callable API and the assistant invokes it through one
`call_game_function(name, arguments)` interface. New functions belong to the
game's registry and handlers; the private service does not need a new action
for each ability. Mineclonia is the first adapter using this development path.
Other adapters must implement the same discovery and execution contract before
the assistant can call their functions.

## Discover and call

`controls.game_api` has version `gamenight-functions-v1` and a `functions` object.
The initial documentation is [functions.json](mods/gamenight_bridge/functions.json).
The runtime adds trusted installed mods' registrations to that same registry.
Every entry contains a description, parameters, return description, and whether
the call changes game state. The model receives the actual registry and the last
observed result. Its output schema is built from those declarations.

```json
{
  "action": "call",
  "game": "mineclonia",
  "values": {
    "name": "inventory.give",
    "arguments": {"target": "self", "item": "mcl_tools:sword_diamond", "count": 2}
  }
}
```

The relay command also carries the selected session ID, expected world revision,
request ID and bound controller seat. The host injects the requesting player's
saved world account; the model cannot supply `caller`. `self` follows that
account when the controller seat changes. A target can also be `all`, an exact
connected world account, or an unambiguous profile display name.

The host validates again, invokes the registered handler, and returns observed
data in its receipt. Item grants report delivered and leftover counts. A full
inventory is not reported as a complete delivery. Read calls leave the revision
unchanged; mutating calls reserve a new persisted revision before executing.
Retries with the same request ID return the stored receipt. A different payload
cannot reuse the ID. A failed mutating handler may have partial effects; read
the new state before another call. There is no automatic retry with a new ID.

These are live calls and do not restart the world. They are distinct from adding
new Lua item/node registrations, which still require validation and reconnect.
The current assistant performs one proposed call per request. Returned data and
`last_result` support a follow-up request; automatic sequences of dependent calls
remain future agent orchestration work.

## Initial functions

| Function | Arguments | Use |
| --- | --- | --- |
| `players.list` | none | Connected accounts, profile names, health and positions |
| `items.search` | query | Find up to ten registered item IDs by ID or description |
| `inventory.list` | target | Observe up to eight nonempty slots per player |
| `inventory.give` | target, item, count | Grant an existing item and report actual delivery |
| `players.heal` | target | Restore configured maximum health |
| `players.teleport` | target, x, y, z | Move connected players to explicit coordinates |

Exact item IDs are preferred. A readable name works only when it matches one
description. Ambiguous names fail with an instruction to call `items.search`.
Unknown function names, missing/extra arguments, wrong types and out-of-range
values are refused. Function calls currently use the existing host-owner authority.

## Extend without changing the assistant

A trusted installed game mod registers its documentation and implementation:

```lua
core.gamenight_register_function("rounds.set_mode", {
    description = "Choose the mode for the next round.",
    parameters = {
        mode = {type="string", description="Exact game mode",
                enum={"free_for_all", "waves"}, max_length=32},
    },
    returns = "Observed mode and when it applies.",
    mutates = true,
}, function(arguments, caller)
    -- Call this game's own implementation and return the observed state.
    return my_game.set_next_mode(arguments.mode)
end)
```

Register after the bridge loads (declare it as a dependency). The SDK exposes a
registry of callable game capabilities; it does not automatically export every
engine global. The dispatcher resolves an exact registered handler and never
evaluates a model-provided function path or source code.

Version 1 uses named scalar parameters: `string`, `boolean`, `number`, `integer`.
Parameters are required unless `required:false`; number limits use `min`/`max`,
strings use byte `max_length` and optional exact string `enum`. Maximums are 64
functions, 16 parameters per function, 1,000 bytes per description/return
description, 1,024 bytes per string argument and 8,192 bytes per result. Function
names use lowercase letters, numbers, underscores and dots (up to 64 bytes).
Nested inputs require another contract version; structured return data is allowed.

Trusted handlers own their apply timing and partial-failure behavior. Generated
Lua's restricted SDK and validation lifecycle remain separate. Publishing this
contract does not grant raw engine, shell or filesystem access to the agent.

## Verify

`python -m unittest test_game_functions test_relay` checks dynamic registration,
types, identities, argument rejection and relay results. LuaJIT executes the
trusted handlers against an explicit engine fixture. Real engine observations
are recorded separately under `verification/` and distinguish controller/model
fixtures from real players and inventories. Store packages remain unchanged.
