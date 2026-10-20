-- The same wordmark used by the store cover greets each joining player.
-- Remove it after the introduction so it never obscures ongoing play.
core.register_on_joinplayer(function(player)
    local name = player:get_player_name()
    local id = player:hud_add({
        type = "image",
        position = {x = 0.5, y = 0.06},
        alignment = {x = 0, y = 1},
        scale = {x = 0.4, y = 0.4},
        text = "gamenight_logo.png",
        z_index = 100,
    })
    core.after(6, function()
        local current = core.get_player_by_name(name)
        if current == player then current:hud_remove(id) end
    end)
end)
