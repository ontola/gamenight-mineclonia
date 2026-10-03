-- SPDX-License-Identifier: MIT
-- Dry shared starting ground for NEW players; returning positions are preserved.
local M = {ready = not core.settings:get_bool("gamenight_safe_spawn", false)}
if M.ready then return M end
local storage = core.get_mod_storage()
local positions
local function dry(name, floor)
    local def = core.registered_nodes[name]
    if not def or name == "ignore" then return false end
    if (def.liquidtype and def.liquidtype ~= "none") or (def.damage_per_second or 0) > 0 then return false end
    if core.get_item_group(name, "water") > 0 or core.get_item_group(name, "lava") > 0
        or core.get_item_group(name, "fire") > 0 then return false end
    return floor and def.walkable or (not floor and not def.walkable)
end
local function safe(p)
    return dry(core.get_node(p).name, true)
        and dry(core.get_node({x=p.x,y=p.y+1,z=p.z}).name, false)
        and dry(core.get_node({x=p.x,y=p.y+2,z=p.z}).name, false)
end
local function pair(p)
    if not safe(p) then return end
    for _, d in ipairs({{2,0},{-2,0},{0,2},{0,-2}}) do
        local q = {x=p.x+d[1],y=p.y,z=p.z+d[2]}
        if safe(q) then return {p,q} end
    end
end
local function accept(found)
    positions = found
    storage:set_string("safe_spawn_ground", core.write_json(found))
    core.settings:set("static_spawnpoint", core.pos_to_string({x=found[1].x,y=found[1].y+1,z=found[1].z}))
    M.positions = found
    M.ready = true
    core.log("action", "[GameNight] Dry shared spawn: " .. core.pos_to_string(found[1]))
end
local centers = {{0,0},{64,0},{-64,0},{0,64},{0,-64},{128,128},{-128,-128},{256,0},{0,256}}
local index = 0
local function search()
    local center, height
    repeat
        index = index + 1
        center = centers[index]
        if center then height = core.get_spawn_level(center[1],center[2]) end
    until not center or height
    if not center then
        M.error = "No dry starting area found. Preserve this world and choose another seed."
        core.log("error", "[GameNight] " .. M.error)
        return
    end
    local x,z = center[1],center[2]
    core.log("action", "[GameNight] Checking dry spawn near " .. x .. "," .. height .. "," .. z)
    local lo,hi = {x=x-4,y=height-8,z=z-4}, {x=x+4,y=height+4,z=z+4}
    core.emerge_area(lo,hi,function(_,_,remaining)
        if remaining ~= 0 or M.ready then return end
        local candidates = core.find_nodes_in_area_under_air(lo,hi,{"group:soil","group:stone","group:sand"})
        table.sort(candidates,function(a,b)
            return (a.x-x)^2+(a.z-z)^2 < (b.x-x)^2+(b.z-z)^2
        end)
        for _,p in ipairs(candidates) do
            local found = pair(p)
            if found then accept(found); return end
        end
        search()
    end)
end
core.register_on_mods_loaded(function()
    local saved = core.parse_json(storage:get_string("safe_spawn_ground"))
    if type(saved) == "table" and #saved == 2 then
        core.load_area(vector.subtract(saved[1],4),vector.add(saved[1],4))
        if safe(saved[1]) and safe(saved[2]) then accept(saved); return end
    end
    core.after(0,search)
end)
core.register_on_newplayer(function(player)
    player:get_meta():set_int("gamenight:first_spawn_pending",1)
end)
core.register_on_joinplayer(function(player)
    if player:get_meta():get_int("gamenight:first_spawn_pending") ~= 1 then return end
    local name = player:get_player_name()
    core.after(0.1,function()
        local current = core.get_player_by_name(name)
        if not current or not positions then return end
        local p = positions[name == "Couch2" and 2 or 1]
        current:set_pos({x=p.x,y=p.y+0.6,z=p.z})
        current:get_meta():set_int("gamenight:first_spawn_pending",0)
    end)
end)
return M
