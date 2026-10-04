-- Test spawn migration and returning-player behavior without a game process.
local file = assert(arg[1], "path to safe_spawn.lua required")
for _,saved_count in ipairs({0,2,4}) do
    local saved = {}
    for i=1,saved_count do saved[i]={x=(i-1)*2,y=0,z=0} end
    local stored, loaded, newplayer, joined
    core = {
        settings={get_bool=function() return true end, set=function() end},
        registered_nodes={stone={walkable=true},air={walkable=false},water={walkable=false,liquidtype="source"}},
        get_mod_storage=function() return {
            get_string=function() return saved_count>0 and "saved" or "" end,
            set_string=function(_,_,value) stored=value end,
        } end,
        get_item_group=function(name,group) return name=="water" and group=="water" and 1 or 0 end,
        get_node=function(p) return {name=p.y==0 and (p.x<0 and "water" or "stone") or "air"} end,
        write_json=function(v) return v end, parse_json=function() return saved end,
        pos_to_string=function() return "pos" end, log=function() end,
        get_spawn_level=function() return 0 end,
        emerge_area=function(_,_,callback) callback(nil,nil,0) end,
        find_nodes_in_area_under_air=function() return {{x=0,y=0,z=0}} end,
        register_on_mods_loaded=function(cb) loaded=cb end,
        after=function(_,cb) cb() end, load_area=function() end,
        register_on_newplayer=function(cb) newplayer=cb end,
        register_on_joinplayer=function(cb) joined=cb end,
    }
    vector={subtract=function(v) return v end,add=function(v) return v end}
    local spawn=dofile(file)
    assert(not spawn.ready)
    loaded()
    assert(spawn.ready and #stored==4)
    local seen={}
    for i,p in ipairs(stored) do
        assert(p.x>=0, "water was accepted")
        local key=p.x..","..p.y..","..p.z
        assert(not seen[key], "spawn positions overlap");seen[key]=true
        local pending,position=0,nil
        local meta={get_int=function() return pending end,set_int=function(_,_,v) pending=v end}
        local player={get_meta=function() return meta end,get_player_name=function() return "Couch"..i end,
                      set_pos=function(_,v) position=v end}
        core.get_player_by_name=function() return player end
        joined(player);assert(position==nil, "returning player was relocated")
        newplayer(player);joined(player)
        assert(position.x==p.x and position.z==p.z and position.y==p.y+0.6)
        assert(pending==0)
    end
end
print("Spawn search, two-position migration, four-position reuse and returning positions passed")
