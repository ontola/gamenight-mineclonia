"""Validate documented game calls without knowledge of individual functions."""

import copy
import json
import math
from identities import ACCOUNT
from prototype import command, read_json


def contract(api):
    if not isinstance(api, dict):
        return None
    api = copy.deepcopy(api)
    # Luanti serializes an empty Lua table as JSON null. Parameterless
    # functions still publish an object, matching the call schema.
    for spec in api.get("functions", {}).values():
        if spec.get("parameters") is None:
            spec["parameters"] = {}
    return api


def accepts(spec, value):
    kind = spec.get("type")
    if kind in ("number", "integer"):
        return (
            type(value) in (int, float)
            and math.isfinite(value)
            and (kind != "integer" or value == int(value))
            and spec.get("min", -math.inf) <= value <= spec.get("max", math.inf)
        )
    if kind == "boolean":
        return type(value) is bool
    if kind == "string":
        return (
            isinstance(value, str)
            and 0 < len(value.encode("utf8")) <= spec.get("max_length", 1024)
            and (not spec.get("enum") or value in spec["enum"])
        )
    return False


def validate(api, values):
    if (
        not isinstance(api, dict)
        or api.get("version") != "gamenight-functions-v1"
        or not isinstance(values, dict)
        or set(values) != {"name", "arguments"}
    ):
        raise ValueError("Missing documented game function call")
    name, arguments = values["name"], values["arguments"]
    spec = api.get("functions", {}).get(name) if isinstance(name, str) else None
    if not spec or not isinstance(arguments, dict):
        raise ValueError("Function is not exposed by this game")
    parameters = spec["parameters"]
    if (
        any(k not in parameters for k in arguments)
        or any(
            p.get("required", True) and k not in arguments
            for k, p in parameters.items()
        )
        or any(not accepts(parameters[k], v) for k, v in arguments.items())
    ):
        raise ValueError("Arguments do not match the documented function")
    return spec


def caller_account(root, seat):
    registry = root / "world/gamenight/identities.json"
    if registry.exists():
        name = read_json(registry).get("profiles", {}).get(seat["player"])
    else:
        name = seat["player"]
    if not isinstance(name, str) or not ACCOUNT.fullmatch(name):
        raise ValueError("Requesting player has no world account")
    return name


def execute(root, selection, controls):
    c = selection["command"]
    validate(controls.get("game_api"), c.get("values"))
    if c["expected_revision"] != controls["revision"]:
        raise ValueError("World changed before the function call")
    values = dict(c["values"], caller=caller_account(root, selection["seat"]))
    result = command(
        root,
        "call",
        values,
        expected=c["expected_revision"],
        request_id=selection["id"],
    )
    data = result.get("result")
    text = data.get("summary") if isinstance(data, dict) else None
    if not isinstance(text, str):
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return {
        "id": selection["id"],
        "ok": result["ok"],
        "message": text.encode("utf8")[:1000].decode("utf8", errors="ignore")
        if result["ok"]
        else result.get("error", "Game function failed"),
        "data": data if result["ok"] else None,
    }
