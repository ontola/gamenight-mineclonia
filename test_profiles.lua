-- Engine-free contract checks for profile polling and Mineclonia texture layers.
local file_text, parsed = 'first', {}
local joins, leaves, changes, ids = {}, {}, {}, 0
local player = {props={},huds={}}
function player:get_player_name() return 'Couch4' end
function player:is_player() return true end
function player:set_properties(p) for k,v in pairs(p) do self.props[k]=v end end
function player:get_properties() return self.props end
function player:hud_add(h) ids=ids+1; self.huds[ids]=h; return ids end
function player:hud_change(id,k,v) self.huds[id][k]=v; changes[#changes+1]={id,k,v} end
core = {
    get_worldpath=function() return '/scratch' end,
    parse_json=function() return parsed end,
    get_connected_players=function() return {player} end,
    colorize=function(c,n) return c..n end,
    after=function(_,f) f() end,
    register_on_joinplayer=function(f) joins[#joins+1]=f end,
    register_on_leaveplayer=function(f) leaves[#leaves+1]=f end,
}
io.open=function() return {read=function() return file_text end,close=function() end} end
mcl_player={players={[player]={textures={'old','armor','extra'}}}}
function mcl_player.player_set_skin(p,s) mcl_player.players[p].textures[1]=s end
function mcl_player.player_set_model(p,m) p.model=m end
local profiles=dofile(arg[1])
parsed={Couch4={name='Dev',color='#123456',skin='[png:AAAA',face='[png:BBBB'}}
profiles.poll()
assert(player.props.nametag=='#123456Dev')
assert(ids==3 and profiles.describe(player).skin_applied)
assert(mcl_player.players[player].textures[2]=='armor')
profiles.poll();assert(#changes==0) -- unchanged file does not resend textures/HUD
file_text='second';parsed.Couch4.name='New name';parsed.Couch4.color='#654321';parsed.Couch4.skin='[png:CCCC'
profiles.poll()
assert(ids==3 and #changes==4 and profiles.describe(player).name=='New name')
assert(player.props.nametag=='#654321New name')
file_text='bad';parsed={Couch4={name='x',color='red',skin='file.png',face='bad'}}
profiles.poll();assert(player.props.nametag=='#654321New name')
leaves[1](player);joins[1](player);assert(ids==6)
print('Profile bridge: name, HUD updates, validation, reconnect, armor preservation passed')

-- A paused reconnect must apply the profile without waiting for core.after,
-- because the simulation and its delayed callbacks are intentionally frozen.
local account = "GN_0123456789abcdef"
function player:get_player_name() return account end
core.after = function() end
core.get_connected_players = function() return {} end
file_text = "new account"
parsed = {[account]={name="New player",seat=3,color="#112233",skin="[png:DDDD",face="[png:EEEE"}}
profiles.poll()
core.get_connected_players = function() return {player} end
joins[1](player)
profiles.poll()
assert(profiles.describe(player).name == "New player")
assert(profiles.describe(player).hud and profiles.describe(player).skin_applied)
assert(profiles.seat(account) == 3)
print("Paused profile reconnect and generated account passed")
