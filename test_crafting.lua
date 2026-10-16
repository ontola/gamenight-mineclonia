local extension, receiver, shown, prepared, checked = nil,nil,nil,0,0
local nearby,ingredients=false,true
core={formspec_escape=function(s)return s end,show_formspec=function(_,name,fs) shown={name=name,fs=fs} end,
register_on_player_receive_fields=function(f) receiver=f end}
mcl_craftguide={add_formspec_element=function(_,d)extension=d end,show=function(name)shown={name=name}end}
mcl_crafting_table={has_crafting_table=function()return nearby end,formspec="table",show_crafting_form=function()end}
mcl_inventory={get_recipe_groups=function(_,_,w,h)checked=checked+1;assert(w==h);return ingredients and {} end,
to_craft_grid=function()prepared=prepared+1 end}
local player={get_player_name=function()return "test"end,get_inventory_formspec=function()return "inventory"end}
dofile(arg[1])
local function recipe(kind,width,items) return {recipes={{type=kind,width=width,items=items}},rnum=1,iX=12} end
assert(extension.element({})==nil)
assert(extension.element(recipe("normal",2,{"wood","wood","wood","wood"}))[5]=="Prepare recipe")
extension.action(player,recipe("normal",2,{"wood","wood","wood","wood"}))
assert(prepared==1 and shown.name=="" and shown.fs:find("gamenight_craft_result"))
nearby=false;extension.action(player,recipe("normal",3,{"wood","wood","wood"}))
assert(prepared==1 and shown.fs:find("needs a crafting table"))
-- A narrow but tall shaped recipe also requires a table.
extension.action(player,recipe("normal",1,{"a","b","c"}))
assert(prepared==1 and shown.fs:find("needs a crafting table"))
nearby=true;extension.action(player,recipe("normal",3,{"wood","wood","wood"}))
assert(prepared==2 and shown.name=="main")
ingredients=false;extension.action(player,recipe("normal",2,{"wood"}))
assert(prepared==2 and shown.fs:find("do not have all"))
local previous=checked
extension.action(player,recipe("cooking",1,{"ore"}))
assert(prepared==2 and checked==previous and shown.fs:find("furnace"))
receiver(player,"gamenight_bridge:recipe_status",{recipes=true});assert(shown.name=="test")
print("PASS recipe preparation: ingredients, table reach, shaped sizes, workstation, result focus and return")
