local ID = 'rally'
local COOLDOWN = 1.0
local BOOST_Y = 12
local RADIUS = 4
local now = 0

gn.check(function()
    assert(ID == 'rally', 'ID mismatch')
    assert(COOLDOWN > 0, 'Cooldown must be positive')
    assert(BOOST_Y > 0, 'Boost Y must be positive')
end)

gn.on_tick(function(dt)
    now = now + dt
end)

-- Report initial counter at startup
local initial_boosts = gn.get('boosts', 0)
gn.emit('boosts', initial_boosts)

gn.tool(ID, {
    description = 'Rally Wand: Boosts nearby teammates up.',
    color = '#00FFFF'
}, function(player)
    local last_use = gn.get('rally_last_' .. player, 0)
    if now < last_use then
        return
    end
    
    gn.set('rally_last_' .. player, now + COOLDOWN)
    
    local p_pos = gn.pos(player)
    if not p_pos then return end
    
    local nearby = gn.near(p_pos, RADIUS)
    local boosted_count = 0
    
    for _, other in ipairs(nearby) do
        if other ~= player then
            local vel = gn.velocity(other)
            if vel then
                gn.push(other, {x=vel.x, y=BOOST_Y, z=vel.z})
                boosted_count = boosted_count + 1
            end
        end
    end
    
    local total_boosts = gn.get('boosts', 0)
    total_boosts = total_boosts + boosted_count
    gn.set('boosts', total_boosts)
    gn.emit('boosts', total_boosts)
end)

gn.on_join(function(player)
    gn.give_once(player, ID, 1)
end)