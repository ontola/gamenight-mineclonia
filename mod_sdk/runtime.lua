-- Trusted adapter around generated Lua. Only gn's copied values cross the boundary.
local source_path = core.get_modpath("gamenight_custom")
local file = assert(io.open(source_path .. "/program.lua", "rb"))
local source = file:read(12001); file:close()
assert(#source <= 12000 and source:byte(1) ~= 27, "Source must be bounded Lua text")
local storage = core.get_mod_storage()
local saved_data=storage:get_string("sdk_values")
local data = saved_data~="" and core.parse_json(saved_data) or {}
local saved_definitions=storage:get_string("sdk_definitions")
local definitions = saved_definitions~="" and core.parse_json(saved_definitions) or {}
local active, ticks, joins, checks, registered = true, {}, {}, {}, {}
local status = {api="gamenight-lua-v1", enabled=true, definitions={}, events={}, error=false}
gamenight_generated_status = status
local operations, initialized, dirty = 0, false, false
local function number(v,lo,hi)
    assert(type(v)=="number" and v==v and v>=lo and v<=hi, "Number outside SDK range")
    return v
end
local function text(v,max)
    assert(type(v)=="string" and #v<=max, "Text outside SDK limit")
    return v
end
local function id(v)
    text(v,32); assert(string.match(v,"^[a-z][a-z0-9_]*$"), "Invalid item ID")
    return "gamenight_custom:" .. v
end
local function count(t) local n=0; for _ in pairs(t) do n=n+1 end; return n end
local function op() operations=operations+1; assert(operations<=32,"SDK operation budget exceeded") end
local function player(name)
    text(name,64); return assert(core.get_player_by_name(name), "Player disconnected")
end
local function vec(p,limit)
    assert(type(p)=="table", "Expected position")
    return {x=number(p.x,-limit,limit), y=number(p.y,-limit,limit), z=number(p.z,-limit,limit)}
end
local function nearby(p,radius)
    local out={}
    for _,p2 in ipairs(core.get_connected_players()) do
        local q=p2:get_pos(); local dx,dy,dz=q.x-p.x,q.y-p.y,q.z-p.z
        if dx*dx+dy*dy+dz*dz<=radius*radius then out[#out+1]=p2:get_player_name() end
    end
    return out
end
local function location(p)
    p=vec(p,31000); assert(#nearby(p,8)>0,"Content must stay within 8 blocks of a player")
    return vector.round(p)
end
local safe_string={}
for _,name in ipairs({"len","sub","lower","upper"}) do
    safe_string[name]=function(s,...) text(s,12000); return string[name](s,...) end
end
safe_string.byte=function(s,i) text(s,12000); return string.byte(s,i or 1) end
safe_string.find=function(s,needle,start) text(s,12000);text(needle,128);return string.find(s,needle,start or 1,true) end
-- Strings have a VM-wide metatable; hide the full library while generated code runs.
-- The generated environment cannot access or change this metatable.
local string_meta=getmetatable("")
local function guarded(fn,...)
    if not active then return false end
    local old_hook,old_mask,old_count=debug.gethook()
    local old_index=string_meta.__index
    local budget=100000
    local memory_before=collectgarbage("count")
    operations=0
    if jit then jit.off(fn,true) end
    string_meta.__index=safe_string
    debug.sethook(function()
        budget=budget-1000
        if budget<=0 or collectgarbage("count")-memory_before>8192 then
            error("Generated Lua resource budget exceeded",0)
        end
    end,"",1000)
    local ok,result=pcall(fn,...)
    debug.sethook(old_hook,old_mask,old_count)
    string_meta.__index=old_index
    if not ok then
        active=false;status.enabled=false;status.error=tostring(result):sub(1,500)
        core.log("error","[GameNight generated mod] "..status.error)
    end
    if dirty then storage:set_string("sdk_values",core.write_json(data));dirty=false end
    return ok,result
end
local function add(list,fn)
    assert(not initialized and type(fn)=="function" and #list<8,"Invalid callback registration")
    list[#list+1]=fn
end
local gn={}
local function definition(kind,key,spec,callback)
    assert(not initialized,"Definitions require a restart")
    local name=id(key); assert(not registered[name] and count(registered)<16,"Duplicate/too many definitions")
    assert(type(spec)=="table","Expected item definition")
    local desc=text(spec.description,80);local color=text(spec.color,7)
    assert(string.match(color,"^#%x%x%x%x%x%x$"),"Expected #RRGGBB color")
    local light=number(spec.light or 0,0,14)
    local d={kind=kind,description=desc,color=color,light=math.floor(light)}
    assert(not definitions[name] or definitions[name].kind==kind,"Keep the existing item kind or use a new ID")
    assert(definitions[name] or count(definitions)<128,"World content definition limit reached")
    definitions[name]=d;registered[name]=true;status.definitions[#status.definitions+1]=name
    local texture="default_steel_block.png^[colorize:"..color..":210"
    if kind=="node" then
        core.register_node(name,{description=desc,tiles={texture},light_source=d.light,
            groups={dig_immediate=3,pickaxey=1},_mcl_hardness=0.3,_mcl_blast_resistance=1})
    else
        assert(type(callback)=="function","A tool needs a use callback")
        core.register_craftitem(name,{description=desc,inventory_image="default_stick.png^[colorize:"..color..":210",stack_max=1,
            on_use=function(stack,p,pointed)
                local pos=pointed and pointed.above
                guarded(callback,p:get_player_name(),pos and vector.new(pos) or nil)
                return stack
            end})
    end
end
function gn.node(key,spec) definition("node",key,spec) end
function gn.tool(key,spec,fn) definition("tool",key,spec,fn) end
function gn.on_tick(fn) add(ticks,fn) end
function gn.on_join(fn) add(joins,fn) end
function gn.check(fn) add(checks,fn) end
function gn.players()
    local out={};for _,p in ipairs(core.get_connected_players()) do out[#out+1]=p:get_player_name() end;return out
end
function gn.pos(name) return vector.new(player(name):get_pos()) end
function gn.look(name) return vector.new(player(name):get_look_dir()) end
function gn.velocity(name) return vector.new(player(name):get_velocity()) end
function gn.controls(name)
    local c=player(name):get_player_control();return {jump=c.jump,sneak=c.sneak,aux1=c.aux1,dig=c.dig,place=c.place}
end
function gn.wielded(name) return player(name):get_wielded_item():get_name() end
function gn.push(name,v) op();player(name):add_velocity(vec(v,20)) end
function gn.near(p,radius) return nearby(vec(p,31000),number(radius,0,8)) end
function gn.node_at(p) return core.get_node(location(p)).name end
function gn.place(p,key)
    op();p=location(p);local name=id(key)
    assert(registered[name] and definitions[name].kind=="node","Unknown own node")
    local old=core.get_node(p).name
    if old=="air" or old:sub(1,17)=="gamenight_custom:" then core.set_node(p,{name=name});return true end
    return false
end
function gn.remove(p)
    op();p=location(p);if core.get_node(p).name:sub(1,17)=="gamenight_custom:" then core.remove_node(p);return true end
    return false
end
function gn.give_once(name,key,n)
    op();local item=id(key);assert(registered[item],"Unknown own item");number(n,1,16)
    local p=player(name);local meta=p:get_meta();local marker="gamenight:given:"..item
    local given=meta:get_int(marker);local amount=math.floor(n)-given
    if amount>0 then
        local left=p:get_inventory():add_item("main",item.." "..amount):get_count()
        meta:set_int(marker,math.floor(n)-left)
    end
end
function gn.get(key,default) text(key,64);local v=data[key];if v==nil then return default end;return v end
function gn.set(key,value)
    op();text(key,64);assert(data[key]~=nil or count(data)<128,"Persistent state is full")
    if type(value)=="string" then text(value,1024)
    elseif type(value)=="number" then number(value,-1e12,1e12)
    else assert(type(value)=="boolean","State values must be scalar") end
    data[key]=value;dirty=true
end
function gn.say(name,message) op();core.chat_send_player(player(name):get_player_name(),text(message,160)) end
function gn.emit(label,value) op();text(label,64);number(value,-1e12,1e12)
    assert(status.events[label]~=nil or count(status.events)<32,"Too many diagnostic counters")
    status.events[label]=value
end
local env={gn=gn,assert=assert,error=error,type=type,tonumber=tonumber,tostring=tostring,
    ipairs=ipairs,pairs=pairs,next=next,string=safe_string,table={insert=table.insert,remove=table.remove},math={}}
for _,k in ipairs({"abs","min","max","floor","ceil","sqrt","sin","cos","pi","random"}) do env.math[k]=math[k] end
local fn,err=loadstring(source,"@gamenight-generated")
assert(fn,err);setfenv(fn,env)
local ok,message=guarded(fn);assert(ok,message)
initialized=true
assert(count(registered)>0 or #source==0,"A generated mod must define new content")
for _,check in ipairs(checks) do local passed,why=guarded(check);assert(passed,why) end
-- Retain inert definitions after edits/undo so placed nodes and inventories survive.
for name,d in pairs(definitions) do
    if not registered[name] then
        local texture="default_steel_block.png^[colorize:"..d.color..":210"
        if d.kind=="node" then core.register_node(name,{description=d.description.." (inactive)",tiles={texture},groups={dig_immediate=3}})
        else core.register_craftitem(name,{description=d.description.." (inactive)",inventory_image="default_stick.png^[colorize:"..d.color..":210"}) end
    end
end
storage:set_string("sdk_definitions",core.write_json(definitions))
core.register_on_joinplayer(function(p) for _,fn in ipairs(joins) do guarded(fn,p:get_player_name()) end end)
local elapsed=0
core.register_globalstep(function(dt)
    elapsed=elapsed+dt;if elapsed<0.1 or not active then return end
    local step=math.min(elapsed,0.5);elapsed=0
    for _,fn in ipairs(ticks) do guarded(fn,step) end
end)
-- Validation can exercise callback registration and a player-free update in real Luanti.
function gamenight_generated_validate()
    for _,fn in ipairs(ticks) do local passed,why=guarded(fn,0.1);assert(passed,why) end
    assert(active,status.error)
end
