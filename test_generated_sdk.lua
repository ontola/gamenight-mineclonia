local folder=assert(arg[1])
local memory={};local callbacks={};local players={}
local function store() return {get_string=function(_,k)return memory[k] or "" end,set_string=function(_,k,v)memory[k]=v end} end
core={registered_nodes={},registered_items={}}
function core.get_modpath() return folder end
function core.get_mod_storage()return store()end
function core.parse_json(v)return v end
function core.write_json(v)return v end
function core.log()end
function core.register_node(n,d)core.registered_nodes[n]=d;core.registered_items[n]=d end
function core.register_craftitem(n,d)core.registered_items[n]=d end
function core.register_on_joinplayer(fn)callbacks.join=fn end
function core.register_globalstep(fn)callbacks.tick=fn end
function core.get_connected_players()local out={};for _,p in pairs(players)do out[#out+1]=p end;return out end
function core.get_player_by_name(n)return players[n]end
function core.get_node()return {name="air"}end
function core.set_node()end
function core.remove_node()end
function core.chat_send_player()end
vector={new=function(v)return {x=v.x,y=v.y,z=v.z}end,round=function(v)return {x=math.floor(v.x+.5),y=math.floor(v.y+.5),z=math.floor(v.z+.5)}end}
local function person(n,x)
 local p={name=n,pos={x=x,y=20,z=0},velocity={x=0,y=0,z=0},given={},metadata={}}
 function p:get_player_name()return self.name end
 function p:get_pos()return self.pos end
 function p:get_look_dir()return {x=1,y=0,z=0}end
 function p:get_velocity()return self.velocity end
 function p:add_velocity(v)for k,num in pairs(v)do self.velocity[k]=self.velocity[k]+num end end
 function p:get_player_control()return {jump=false}end
 function p:get_wielded_item()return {get_name=function()return ""end}end
 function p:get_meta()return {get_int=function(_,k)return self.metadata[k] or 0 end,set_int=function(_,k,v)self.metadata[k]=v end}end
 function p:get_inventory()return {add_item=function(_,_,item)self.given[#self.given+1]=item;return {get_count=function()return 0 end}end}end
 return p
end
players.A=person("A",0);players.B=person("B",2)
local ok,err=pcall(dofile,folder.."/init.lua")
if arg[2]=="reject" then assert(not ok,"Expected rejection");print("Rejected: "..tostring(err));return end
assert(ok,err)
assert(gamenight_generated_status.enabled)
callbacks.join(players.A);callbacks.join(players.B)
if callbacks.tick then callbacks.tick(.2)end
if arg[2]=="runtime_reject" then assert(not gamenight_generated_status.enabled);assert(gamenight_generated_status.error);return end
assert(gamenight_generated_status.enabled,gamenight_generated_status.error)
local wand=core.registered_items["gamenight_custom:rally"]
if wand then
 wand.on_use({},players.A,{type="nothing"})
 assert(players.B.velocity.y==12,"Generated tool should launch teammate")
 assert(players.A.velocity.y==0,"Wielder must remain unaffected")
 assert(memory.sdk_values.boosts==1,"Counter should persist")
 assert(#players.A.given==1)
 callbacks.join(players.A);assert(#players.A.given==1,"Grant should be idempotent")
end
print("SDK checks passed")
