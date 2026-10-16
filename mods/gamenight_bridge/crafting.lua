-- Prepare recipes through Mineclonia's inventory API. The native result slot
-- performs the craft, preserving material costs, replacements and callbacks.
local F = core.formspec_escape
local function explain(player, message)
    core.show_formspec(player:get_player_name(), "gamenight_bridge:recipe_status",
        "formspec_version[4]size[10,4]label[0.5,0.6;Recipe book]" ..
        "textarea[0.5,1.1;9,1.7;;;" .. F(message) .. "]" ..
        "button[2.5,3;5,0.7;recipes;Back to recipes]")
end
local function prepare(player, data)
    local recipe = data.recipes and data.recipes[data.rnum]
    if not recipe then return end
    if recipe.type ~= "normal" then
        explain(player, "This recipe uses a furnace or another workstation. It cannot be made in the crafting grid.")
        return
    end
    local count, last = 0, 0
    for i, item in pairs(recipe.items) do
        if item ~= "" then count = count + 1; last = math.max(last, i) end
    end
    local width = recipe.width or 0
    local small = width == 0 and count <= 4 or width > 0 and width <= 2 and last <= width * 2
    local table_nearby = mcl_crafting_table.has_crafting_table(player)
    if not small and not table_nearby then
        explain(player, "This recipe needs a crafting table. Stand near one, then prepare the recipe again.")
        return
    end
    if not mcl_inventory.get_recipe_groups(player, recipe, table_nearby and 3 or 2, table_nearby and 3 or 2) then
        explain(player, "You do not have all the ingredients. Check the recipe icons and collect the missing materials first.")
        return
    end
    mcl_inventory.to_craft_grid(player, recipe)
    -- Explicit marker lets the controller client focus the result after the
    -- server sends its inventory update (which may arrive after the formspec).
    local form = table_nearby and mcl_crafting_table.formspec or player:get_inventory_formspec()
    form = form .. "label[0,0;]button[100,100;1,1;gamenight_craft_result;]"
    if table_nearby then mcl_crafting_table.show_crafting_form(player) end
    core.show_formspec(player:get_player_name(), table_nearby and "main" or "", form)
end
mcl_craftguide.add_formspec_element("gamenight_prepare", {
    type = "button",
    element = function(data)
        if data.recipes and data.recipes[data.rnum] then
            return {0, data.iX - 1.8, 3.3, 0.7, F("Prepare recipe")}
        end
    end,
    action = prepare,
})
core.register_on_player_receive_fields(function(player, formname, fields)
    if formname == "gamenight_bridge:recipe_status" and fields.recipes then
        mcl_craftguide.show(player:get_player_name())
        return true
    end
end)
return {prepare = prepare}
