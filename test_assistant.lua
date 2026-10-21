-- Engine-free checks for chat request parsing and item lookup.
core = {}
local A = dofile(arg[1])
local function p(text, names) return A.parse(text, names) end
local function one(r) assert(r and #r.items == 1); return r.items[1] end
local r = p("geef me 10 crystal")
assert(one(r).count == 10 and r.items[1].query == "crystal" and r.target == "me" and r.lang == "nl" and r.strong)
r = p("Give me 5 diamonds please!")
assert(one(r).count == 5 and r.items[1].query == "diamonds" and r.lang == "en")
r = p("kan ik twee ijzeren zwaarden krijgen?")
assert(one(r).count == 2 and r.items[1].query == "ijzeren zwaarden" and not r.strong)
r = p("geef iedereen 3 brood"); assert(r.target == "all" and one(r).count == 3)
r = p("geef anna een stack fakkels", {anna = "GN_1"})
assert(r.target == "GN_1" and one(r).count.stacks == 1 and r.items[1].query == "fakkels")
r = p("geef Anna 2 stacks hout", {anna = "GN_1"})
assert(r.target == "GN_1" and one(r).count.stacks == 2 and r.items[1].query == "hout")
r = p("assistent, ik wil 64x zand"); assert(one(r).count == 64 and r.items[1].query == "zand" and r.strong)
r = p("geef me een diamanten houweel"); assert(one(r).count == 1 and r.items[1].query == "diamanten houweel")
r = p("geef me 10 brood, 5 appels en een boog")
assert(#r.items == 3 and r.items[1].count == 10 and r.items[2].query == "appels" and r.items[3].count == 1)
assert(p("hallo allemaal") == nil and p("geef") == nil and p("ik wil naar huis") ~= nil)
assert(p(("a"):rep(201)) == nil and p(nil) == nil)

local function T(s) return s end
local reg = {
    ["mcl_end:crystal"] = {description = "End Crystal"},
    ["mcl_ocean:prismarine_crystals"] = {description = "Prismarine Crystals"},
    ["mcl_core:diamond"] = {description = "Diamond"},
    ["mcl_core:diamondblock"] = {description = "Block of Diamond"},
    ["mcl_tools:sword_diamond"] = {description = "Diamond Sword\nDamage: 7"},
    ["mcl_tools:sword_iron"] = {description = "\27(T@mcl_tools)Iron Sword\27E"},
    ["mcl_tools:pick_diamond"] = {description = "Diamond Pickaxe"},
    ["mcl_torches:torch"] = {description = "Torch"},
    ["mcl_farming:bread"] = {description = "Bread"},
    ["mcl_core:sand"] = {description = "Sand"},
    ["mcl_core:sandstone"] = {description = "Sandstone"},
    ["mcl_core:secret"] = {description = "Diamond", groups = {not_in_creative_inventory = 1}},
    ["mcl_beds:bed_black_bottom"] = {description = "Black Bed"},
    ["mcl_beds:bed_white_bottom"] = {description = "White Bed"},
    ["mcl_trees:wood_acacia"] = {description = "Acacia Planks"},
    ["mcl_trees:wood_oak"] = {description = "Oak Planks"},
    [""] = {description = "Hand"},
}
local idx = A.index(reg, T)
local function find(q) local item, alt = A.find(idx, q); return item and item.name, alt end
local name, alt = find("fakkels"); assert(#alt == 0)
name, alt = find("crystal")
assert(name == "mcl_end:crystal", name); assert(alt[1] == "Prismarine Crystals")
assert(find("kristallen") == "mcl_end:crystal")
assert(find("diamonds") == "mcl_core:diamond")
assert(find("diamant") == "mcl_core:diamond")
assert(find("ijzeren zwaarden") == "mcl_tools:sword_iron")
assert(find("diamanten houweel") == "mcl_tools:pick_diamond")
assert(find("fakkels") == "mcl_torches:torch")
assert(find("torches") == "mcl_torches:torch")
assert(find("zand") == "mcl_core:sand")
assert(find("prismarine crystals") == "mcl_ocean:prismarine_crystals")
assert(find("naar huis") == nil)
assert(find("bed") == "mcl_beds:bed_white_bottom")
assert(find("planken") == "mcl_trees:wood_oak" and find("planks") == "mcl_trees:wood_oak")
print("PASS assistant: Dutch/English requests, counts, targets and item lookup")
