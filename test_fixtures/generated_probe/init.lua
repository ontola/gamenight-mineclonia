-- Test-only fixture. Never included in a game package.
local dir = core.get_worldpath() .. "/gamenight"
core.set_timeofday(0.5)
core.settings:set("time_speed", "0")
local elapsed = 0
core.register_globalstep(function(dt)
    elapsed = elapsed + dt
    if elapsed < 0.05 then return end
    elapsed = 0
    local command = io.open(dir .. "/generated-probe-command.json", "rb")
    if command then
        command:close()
        os.remove(dir .. "/generated-probe-command.json")
        for x = -4, 4 do for z = 66, 78 do
            core.set_node({x=x,y=17,z=z}, {name="mcl_core:stone"})
        end end
        for i, name in ipairs({"Couch1", "Couch2"}) do
            local p = core.get_player_by_name(name)
            if p then
                p:set_pos({x=0,y=17.5,z=70+(i-1)*3})
                p:add_velocity(vector.multiply(p:get_velocity(), -1))
                p:set_look_horizontal(0)
                p:set_look_vertical(0)
                local inventory = p:get_inventory()
                for slot, stack in ipairs(inventory:get_list("main")) do
                    if stack:get_name() == "gamenight_custom:rally" then
                        local selected = p:get_wield_index()
                        local previous = inventory:get_stack("main", selected)
                        inventory:set_stack("main", selected, stack)
                        inventory:set_stack("main", slot, previous)
                        break
                    end
                end
            end
        end
    end
    local out = {players={}, generated=rawget(_G, "gamenight_generated_status") or false}
    for _, p in ipairs(core.get_connected_players()) do
        out.players[p:get_player_name()] = {position=p:get_pos(), velocity=p:get_velocity(), wielded=p:get_wielded_item():get_name()}
    end
    core.safe_file_write(dir .. "/generated-probe.json", core.write_json(out))
end)
