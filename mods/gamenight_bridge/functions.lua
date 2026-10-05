-- Trusted game-owned handlers. Documentation and argument validation share one registry.
local M, handlers = {}, {}
local f = assert(io.open(core.get_modpath("gamenight_bridge") .. "/functions.json", "rb"))
local api = assert(core.parse_json(f:read("*a"))); f:close()
local specs = api.functions
local function accepts(spec, value)
    if spec.type == "string" then
        if type(value) ~= "string" or #value == 0 or #value > (spec.max_length or 1024) then return false end
        if spec.enum and #spec.enum > 0 then for _, v in ipairs(spec.enum) do if v == value then return true end end; return false end
        return true
    elseif spec.type == "boolean" then return type(value) == "boolean"
    elseif spec.type == "number" or spec.type == "integer" then
        return type(value) == "number" and value == value and value > -math.huge and value < math.huge
            and (spec.type ~= "integer" or value == math.floor(value))
            and (not spec.min or value >= spec.min) and (not spec.max or value <= spec.max)
    end
    return false
end
function M.register(name, spec, handler)
    assert(type(name) == "string" and #name <= 64 and name:match("^[a-z][a-z0-9_.]*$") and not handlers[name], "invalid or duplicate game function")
    assert(type(spec.description) == "string" and type(spec.parameters) == "table" and type(spec.returns) == "string" and type(spec.mutates) == "boolean" and type(handler) == "function", "missing function documentation")
    specs[name], handlers[name] = spec, handler
end
local function targets(value, caller)
    local matches = {}
    for _, player in ipairs(core.get_connected_players()) do
        local name = player:get_player_name()
        local profile = M.describe and M.describe(player)
        if value == "all" or (value == "self" and name == caller) or name == value or (profile and profile.name == value) then
            table.insert(matches, player)
        end
    end
    table.sort(matches, function(a,b) return a:get_player_name() < b:get_player_name() end)
    assert(#matches > 0, "Target player is not connected")
    assert(value == "all" or #matches == 1, "Player name is ambiguous; use a player account")
    return matches
end
local function item_description(item)
    local description = item.description or ""
    description = core.strip_escapes and core.strip_escapes(description)
        or description:gsub("\27%([^)]*%)", ""):gsub("\27.", "")
    return (description:match("[^\n]+") or ""):sub(1,128)
end
local function registered_items(query, exact)
    local matches = {}
    local q = query:lower()
    for id, item in pairs(core.registered_items) do
        if id ~= "air" and id ~= "ignore" and type(item.description) == "string" and item.description ~= "" then
            local description = item_description(item)
            local match = exact and (id == query or description:lower() == q)
            if not exact then
                match = true
                local text = (id .. " " .. description):lower():gsub("_", " ")
                for word in q:gmatch("%S+") do if not text:find(word, 1, true) then match = false; break end end
            end
            if match then table.insert(matches, {id=id, description=description}) end
        end
    end
    table.sort(matches, function(a,b) return a.id < b.id end)
    return matches
end
local function register(name, handler) M.register(name, specs[name], handler) end
register("players.list", function()
    local result = {}
    for _,p in ipairs(core.get_connected_players()) do
        local profile = M.describe and M.describe(p)
        table.insert(result, {player=p:get_player_name(), name=profile and profile.name or p:get_player_name(), hp=p:get_hp(), position=p:get_pos()})
    end
    table.sort(result, function(a,b) return a.player < b.player end)
    return result
end)
register("items.search", function(args)
    local matches = registered_items(args.query, false)
    local more = #matches > 10
    while #matches > 10 do table.remove(matches) end
    local labels = {}
    for _,item in ipairs(matches) do table.insert(labels, item.description .. " (" .. item.id .. ")") end
    return {items=matches, more=more, summary=#matches > 0 and table.concat(labels, "; ") or "No matching items found."}
end)
register("inventory.give", function(args, caller)
    local item = core.registered_items[args.item] and args.item or nil
    if not item then
        local matches = registered_items(args.item, true)
        assert(#matches == 1, #matches == 0 and "Item not found; call items.search" or "Item name is ambiguous; use items.search and an exact ID")
        item = matches[1].id
    end
    assert(item ~= "air" and item ~= "ignore", "Item cannot be granted")
    local players = targets(args.target, caller)
    local result = {item=item, players={}, summary=""}
    local summaries = {}
    for _,p in ipairs(players) do
        local remaining, delivered = args.count, 0
        while remaining > 0 do
            -- ItemStack clamps a nonstackable tool to one. Grant in real
            -- stack-sized chunks and count the constructed stack, not input.
            local stack = ItemStack({name=item, count=math.min(remaining, core.registered_items[item].stack_max or 99)})
            local amount = stack:get_count()
            assert(amount > 0 and amount <= remaining, "Item stack could not be constructed")
            local left = p:get_inventory():add_item("main", stack):get_count()
            delivered = delivered + amount - left
            remaining = remaining - amount
            if left > 0 then break end
        end
        local left = args.count - delivered
        table.insert(result.players, {player=p:get_player_name(), delivered=delivered, leftover=left})
        local profile = M.describe and M.describe(p)
        table.insert(summaries, (profile and profile.name or p:get_player_name()) .. ": " .. (args.count-left) .. " received" .. (left > 0 and (", " .. left .. " did not fit") or ""))
    end
    result.summary = item_description(core.registered_items[item]) .. " — " .. table.concat(summaries, "; ")
    return result
end)
register("inventory.list", function(args, caller)
    local result = {players={}}
    for _,p in ipairs(targets(args.target, caller)) do
        local entry = {player=p:get_player_name(), items={}, more=false}
        for slot,stack in ipairs(p:get_inventory():get_list("main") or {}) do
            if not stack:is_empty() then
                if #entry.items < 8 then table.insert(entry.items, {slot=slot,item=stack:get_name(),count=stack:get_count()})
                else entry.more = true end
            end
        end
        table.insert(result.players, entry)
    end
    return result
end)
register("players.heal", function(args, caller)
    local result = {}
    for _,p in ipairs(targets(args.target, caller)) do
        p:set_hp(p:get_properties().hp_max or 20, {type="set_hp", from="gamenight"})
        table.insert(result, {player=p:get_player_name(), hp=p:get_hp()})
    end
    return result
end)
register("players.teleport", function(args, caller)
    local result = {players={}, position={x=args.x,y=args.y,z=args.z}}
    for _,p in ipairs(targets(args.target, caller)) do
        p:set_pos(result.position); table.insert(result.players,p:get_player_name())
    end
    return result
end)
function M.contract() return api end
function M.call(values, before_mutation)
    assert(type(values) == "table", "Missing function call")
    for k in pairs(values) do assert(k == "name" or k == "arguments" or k == "caller", "Unexpected function call field") end
    local name, args = values.name, values.arguments
    local spec = type(name) == "string" and specs[name]
    assert(spec and handlers[name], "Function is not exposed by this game")
    assert(type(values.caller) == "string" and core.get_player_by_name(values.caller), "Caller is not connected")
    assert(type(args) == "table", "Missing function arguments")
    for key, value in pairs(args) do assert(spec.parameters[key] and accepts(spec.parameters[key], value), "Arguments do not match documented function") end
    for key, param in pairs(spec.parameters) do assert(param.required == false or args[key] ~= nil, "Missing required function argument") end
    if spec.mutates and before_mutation then before_mutation() end
    local result = handlers[name](args, values.caller)
    local encoded = core.write_json(result)
    assert(encoded and #encoded <= 8192, "Function result exceeds supported size")
    api.last_result = {name=name,result=result}
    return result, spec.mutates
end
-- Other trusted installed mods may register documented functions without cloud changes.
core.gamenight_register_function = M.register
return M
