-- Profile appearances are host-owned, transient, and independent of world saves.
local M = {}
local profiles, last_json, huds = {}, nil, {}
local path = core.get_worldpath() .. "/gamenight/profiles.json"
local function apply(player)
    local name = player:get_player_name()
    local profile = profiles[name]
    if not profile then return end
    -- Use Mineclonia's skin API: armor, invisibility and inventory models retain
    -- their own texture layers. Never write skin metadata back to the world.
    mcl_player.player_set_skin(player, profile.skin)
    mcl_player.player_set_model(player, "mcl_armor_character.b3d")
    -- Animation owns nametag alpha (sneaking hides it). Embed the accent in the
    -- text rather than repeatedly overriding its visibility/color properties.
    player:set_properties({nametag = core.colorize(profile.color, profile.name)})
    local background = "[fill:" .. math.min(388, math.max(128, #profile.name*9+76)) .. "x56:#151b25d9"
    local ids = huds[name]
    if ids then
        player:hud_change(ids.background, "text", background)
        player:hud_change(ids.face, "text", profile.face)
        player:hud_change(ids.name, "text", profile.name)
        player:hud_change(ids.name, "number", tonumber(profile.color:sub(2),16))
    else
        huds[name] = {
            background = player:hud_add({type="image",position={x=1,y=0},offset={x=-8,y=8},
                alignment={x=-1,y=1},scale={x=1,y=1},text=background,z_index=9}),
            face = player:hud_add({type="image",position={x=1,y=0},offset={x=-12,y=12},
                alignment={x=-1,y=1},scale={x=1,y=1},text=profile.face,z_index=10}),
            name = player:hud_add({type="text",position={x=1,y=0},offset={x=-68,y=36},
                alignment={x=-1,y=0},text=profile.name,number=tonumber(profile.color:sub(2),16),z_index=10}),
        }
    end
end
function M.poll()
    local f = io.open(path,"rb")
    if not f then return end
    local text = f:read(524289); f:close()
    if text == last_json or #text > 524288 then return end
    local value = core.parse_json(text)
    if type(value) ~= "table" then return end
    for name,p in pairs(value) do
        if not (name:match("^Couch[1-4]$") or (#name == 19 and name:match("^GN_%x+$")) or name == "Preview") or type(p) ~= "table" or type(p.name) ~= "string"
            or #p.name > 128 or type(p.color) ~= "string" or not p.color:match("^#%x%x%x%x%x%x$")
            or type(p.skin) ~= "string" or #p.skin > 65536 or not p.skin:match("^%[png:[%w+/=]+$")
            or type(p.face) ~= "string" or #p.face > 32768 or not p.face:match("^%[png:[%w+/=]+$") then return end
    end
    profiles, last_json = value, text
    for _,player in ipairs(core.get_connected_players()) do apply(player) end
end
function M.seat(name)
    M.poll()
    local seat = profiles[name] and profiles[name].seat
    if type(seat) == "number" and seat >= 1 and seat <= 4 and seat == math.floor(seat) then return seat end
    return tonumber(name:match("^Couch([1-4])$")) or 1
end
function M.describe(player)
    local p = profiles[player:get_player_name()]
    return p and {name=p.name,color=p.color,skin_applied=mcl_player.players[player].textures[1] == p.skin,
        nametag=player:get_properties().nametag,hud=huds[player:get_player_name()] ~= nil} or nil
end
core.register_on_joinplayer(function(player)
    core.after(0,function() if player and player:is_player() then M.poll(); apply(player) end end)
end)
core.register_on_leaveplayer(function(player) huds[player:get_player_name()] = nil end)
return M
