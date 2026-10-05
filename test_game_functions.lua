local api = dofile(arg[1])
local oldopen = io.open
io.open = function() return {read=function() return "contract" end,close=function() end} end
local players = {}
local function player(name,display)
    local p={name=name,display=display,count=0,hp=5,pos={x=0,y=1,z=0},left=0}
    function p:get_player_name() return self.name end
    function p:get_pos() return self.pos end
    function p:set_pos(pos) self.pos=pos end
    function p:get_hp() return self.hp end
    function p:set_hp(hp) self.hp=hp end
    function p:get_properties() return {hp_max=20} end
    function p:get_inventory() return {add_item=function(_,_,stack) self.count=self.count+stack.count-self.left; return {get_count=function() return self.left end} end} end
    players[#players+1]=p; return p
end
local a,b=player("Couch1","Alex"),player("Couch2","Bea")
core={
    get_modpath=function() return "fixture" end,
    parse_json=function() return api end,
    write_json=function() return "{}" end,
    get_connected_players=function() return players end,
    get_player_by_name=function(name) for _,p in ipairs(players) do if p.name==name then return p end end end,
    registered_items={air={description="Air"},["mcl_tools:sword_diamond"]={description="Diamond Sword",stack_max=1},["mcl_core:diamond"]={description="Diamond"}},
}
ItemStack=function(v) v.count=math.min(v.count,core.registered_items[v.name].stack_max or 99);function v:get_count() return self.count end;return v end
local functions=dofile(arg[2]);io.open=oldopen
functions.describe=function(p) return {name=p.display} end
local admitted=0
local function call(name,args)
    return functions.call({name=name,arguments=args,caller="Couch1"},function() admitted=admitted+1 end)
end
local result=call("players.list",{});assert(#result==2 and result[2].name=="Bea" and admitted==0)
result=call("items.search",{query="diamond sword"});assert(#result.items==1 and result.items[1].id=="mcl_tools:sword_diamond")
result=call("inventory.give",{target="self",item="Diamond Sword",count=2});assert(a.count==2 and b.count==0 and result.players[1].delivered==2)
b.left=1
result=call("inventory.give",{target="Bea",item="mcl_core:diamond",count=3});assert(a.count==2 and b.count==2 and result.players[1].leftover==1)
assert(admitted==2)
for _,args in ipairs({{target="self",item="Diamond Sword",count=true},{target="self",item="Diamond Sword",count=300},{target="self",item="Diamond Sword",count=1.5},{target="self",item="Diamond Sword",count=2,caller="Couch2"}}) do
    assert(not pcall(call,"inventory.give",args))
end
assert(admitted==2 and a.count==2)
assert(not pcall(functions.call,{name="players.list",arguments={},caller="gone"}))
assert(not pcall(call,"engine.eval",{}))
core.registered_items["other:sword"]={description="Diamond Sword"}
assert(not pcall(call,"inventory.give",{target="self",item="Diamond Sword",count=1}))
assert(a.count==2)
call("players.heal",{target="all"});assert(a.hp==20 and b.hp==20)
call("players.teleport",{target="self",x=2,y=3,z=4});assert(a.pos.x==2 and b.pos.x==0)
core.gamenight_register_function("game.extra",{description="Custom registered function",parameters={},returns="Value",mutates=false},function() return {value=42} end)
assert(call("game.extra",{}).value==42)
core.gamenight_register_function("game.failure",{description="Partial mutating failure",parameters={},returns="Value",mutates=true},function() a.count=a.count+1;error("failed after effect") end)
local before=admitted;assert(not pcall(call,"game.failure",{}));assert(admitted==before+1)
assert(functions.contract().last_result.name=="game.extra")
print("Game function routing, validation, identity, inventory, returns and extension passed")
