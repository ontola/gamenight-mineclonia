# Documented game functions: 5 October 2026

The isolated Windows Mineclonia test connected two real engine clients. It
observed item lookup, two diamond swords delivered to Bo's mapped world account,
unchanged inventory for Alex, and a duplicate request returning the original
receipt without another grant. Healing and teleporting were observed through a
subsequent player query. The same server process stayed alive throughout.

`engine-report.json` records the returned data and inventory observations.
`run-engine.py` reproduces this check against a supplied native engine:

```powershell
python verification/functions-2026-10-05/run-engine.py --root E:/fresh-test-world --engine E:/package/game/engine
```

The directory must be new. The test retains its world and evidence and closes
its player views and server on exit. It uses a known dry-spawn seed. The engine
is the existing patched native GameNight build; the runtime prepares the pinned
Mineclonia sources as normal.

The host seats and controller frames are scripted. This does not test a physical
controller, microphone or real language model. The separate phone preview uses
real cloud handlers with an explicit disposable host/provider fixture. Nothing
was deployed or added to the published store package by this check.

The engine check caught a nonstackable tool count issue: constructing a stack of
two swords yielded one. The handler now grants stack-sized chunks, observes the
actual stack count and reports delivered/leftover amounts. The Lua fixture also
models this clamp so the regression is covered.
