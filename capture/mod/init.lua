-- Scratch-world staging for real renderer footage. Never shipped in the game.
local folder = core.get_worldpath() .. "/gamenight"
local busy, tick, last = false, 0, nil
local function node(x,y,z,name) core.set_node({x=x,y=y,z=z},{name=name}) end
local function report(value)
    core.safe_file_write(folder .. "/capture-status.json",core.write_json(value))
end
local function stage(shot)
    for _,obj in ipairs(core.get_objects_inside_radius({x=0,y=20,z=68},24)) do
        if not obj:is_player() then obj:remove() end
    end
    for x=-10,10 do for z=59,77 do for y=16,27 do
        node(x,y,z,y<=17 and (shot=="mine" or shot=="blast") and "mcl_core:stone"
            or y<=17 and "mcl_core:dirt_with_grass" or "air")
    end end end
    if shot=="mine" or shot=="blast" then
        for x=-8,8 do for y=18,23 do for z=73,75 do node(x,y,z,"mcl_core:stone") end end end
        for x=-2,2 do for y=18,21 do node(x,y,70,"mcl_core:stone_with_coal") end end
    else
        for y=18,21 do node(-6,y,72,"mcl_core:tree") end
        for x=-8,-4 do for z=70,74 do for y=22,23 do node(x,y,z,"mcl_core:leaves") end end end
        for x=5,8 do node(x,18,73,"mcl_flowers:poppy") end
    end
    local p1,p2=core.get_player_by_name("Couch1"),core.get_player_by_name("Couch2")
    assert(p1 and p2,"Both players must be connected")
    for _,p in ipairs({p1,p2}) do
        p:get_inventory():set_list("main",{})
        p:set_look_vertical(0.06)
        p:set_look_horizontal(0)
    end
    p1:set_pos({x=0,y=17.6,z=66})
    p2:set_pos({x=4,y=17.6,z=65})
    p2:set_look_horizontal(0.67)
    p2:set_look_vertical(0.05)
    if shot=="mine" then
        p1:get_inventory():add_item("main","mcl_tools:pick_diamond")
        node(0,19,69,"mcl_core:stone_with_coal")
    elseif shot=="build" then
        p1:get_inventory():add_item("main","mcl_core:wood 64")
        p1:set_look_vertical(0.55)
        node(0,18,69,"mcl_core:wood")
    elseif shot=="blast" then
        node(0,18,70,"mcl_tnt:tnt")
        p1:set_pos({x=0,y=17.6,z=63})
        p2:set_pos({x=5,y=17.6,z=64})
        p2:set_look_horizontal(0.69)
    elseif shot=="bounce" then
        node(0,18,69,"gamenight_bridge:bounce_pad")
        p2:set_look_vertical(-0.2)
    else error("Unknown shot") end
    core.set_timeofday(0.45)
    core.settings:set("time_speed","0")
    busy=false
    report({ok=true,shot=shot,ready=true})
end
core.register_globalstep(function(dt)
    tick=tick+dt
    if tick<0.1 or busy then return end
    tick=0
    local f=io.open(folder.."/capture-command.json","rb")
    if not f then return end
    local raw=f:read("*a");f:close()
    if raw==last then return end
    local c=core.parse_json(raw)
    if not c then return end
    last=raw
    if c.action=="stage" then
        busy=true
        core.emerge_area({x=-10,y=16,z=59},{x=10,y=27,z=77},function(_,_,remaining)
            if remaining==0 then
                local ok,err=pcall(stage,c.shot)
                if not ok then busy=false;report({ok=false,error=tostring(err)}) end
            end
        end)
    elseif c.action=="inventory" then
        local inventories={}
        for _,p in ipairs(core.get_connected_players()) do
            local items={}
            for _,stack in ipairs(p:get_inventory():get_list("main")) do
                table.insert(items,stack:to_string())
            end
            inventories[p:get_player_name()]=items
        end
        report({ok=true,inventories=inventories})
    elseif c.action=="ignite" then
        mcl_tnt.ignite({x=0,y=18,z=70})
        report({ok=true,action="ignite"})
    elseif c.action=="bounce" then
        local p=core.get_player_by_name("Couch1")
        if p then p:set_pos({x=0,y=18.6,z=69}) end
        report({ok=true,action="bounce"})
    end
end)
