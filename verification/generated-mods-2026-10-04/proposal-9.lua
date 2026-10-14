local ID = 'rally'
local COOLDOWN = 1.0
local BOOST_Y = 6
local BOOST_H_MULTIPLIER = 8
local RADIUS = 4
local now = 0

gn.check(function()
    assert(ID == 'rally', 'ID mismatch')
    assert(COOLDOWN > 0, 'Cooldown must be positive')
    assert(BOOST_Y >= 0, 'Boost Y must be non-negative')
end)

gn.on_tick(function(dt)
    now = now + dt
end)

-- Report initial counter at startup
local initial_boosts = gn.get('boosts', 0)
gn.emit('boosts', initial_boosts)

-- Tool definition for Rally Wand
gn.tool(ID, {
    description = 'Rally Wand: Boosts nearby teammates up.',
    color = '#FFA500' -- Orange color
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
                -- Calculate horizontal boost based on wielder's look direction
                local look_dir = gn.look(player)
                local horizontal_boost = {x = look_dir.x * BOOST_H_MULTIPLIER, y = 0, z = look_dir.z * BOOST_H_MULTIPLIER}
                
                -- Combine vertical boost (6) with calculated horizontal boost
                local final_boost = {x = horizontal_boost.x, y = BOOST_Y, z = horizontal_boost.z}
                
                gn.push(other, final_boost)
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
end}