-- In-game assistant: players type a plain request in chat ("geef me 10 crystal",
-- "give everyone 5 bread") and receive the items. Parsing and item lookup are
-- local and deterministic; no text is evaluated as code and nothing leaves the
-- world. `handle` is also the entry point for requests that arrive from the host.
local M = {}

-- Dutch words players use for Mineclonia's (English) item names.
local dutch = {
    diamant="diamond", diamanten="diamond", ijzer="iron", ijzeren="iron", goud="gold",
    gouden="golden", koper="copper", koperen="copper", smaragd="emerald", smaragden="emerald",
    kolen="coal", steenkool="coal", houtskool="charcoal", hout="oak log", boomstam="oak log", houten="wooden",
    plank="oak planks", planken="oak planks", steen="stone", stenen="stone", keisteen="cobblestone",
    keien="cobblestone", zand="sand", zandsteen="sandstone", grind="gravel", glas="glass",
    aarde="dirt", gras="grass", klei="clay", sneeuw="snow", ijs="ice", obsidiaan="obsidian",
    kwarts="quartz", kristal="crystal", kristallen="crystal", amethist="amethyst",
    zwaard="sword", zwaarden="sword", houweel="pickaxe", houwelen="pickaxe",
    pikhouweel="pickaxe", bijl="axe", bijlen="axe", schep="shovel", schoffel="hoe",
    boog="bow", kruisboog="crossbow", pijl="arrow", pijlen="arrow", schild="shield",
    drietand="trident", helm="helmet", harnas="chestplate", borstplaat="chestplate",
    broek="leggings", beenstukken="leggings", laarzen="boots", fakkel="torch",
    fakkels="torch", brood="bread", appel="apple", appels="apple", wortel="carrot",
    wortels="carrot", aardappel="potato", aardappels="potato", aardappelen="potato",
    biefstuk="steak", kip="chicken", vis="fish", zalm="salmon", taart="cake", koekje="cookie",
    koekjes="cookie", meloen="melon", pompoen="pumpkin", suiker="sugar", melk="milk",
    ei="egg", eieren="egg", veer="feather", veren="feather", touw="string", draad="string",
    bot="bone", botten="bone", buskruit="gunpowder", parel="pearl", enderparel="ender pearl",
    kist="chest", kisten="chest", werkbank="crafting table", oven="furnace", bed="bed",
    deur="door", deuren="door", ladder="ladder", emmer="bucket", water="water",
    wol="wool", staaf="ingot", staven="ingot", baar="ingot", baren="ingot", blok="block",
    blokken="block", erts="ore", rood="red", rode="red", blauw="blue", blauwe="blue",
    groen="green", groene="green", geel="yellow", gele="yellow", zwart="black",
    zwarte="black", wit="white", witte="white", paars="purple", paarse="purple",
    oranje="orange", roze="pink", grijs="grey", grijze="grey", bruin="brown", bruine="brown",
    lichtblauw="light blue", boot="boat", mijnkar="minecart", rails="rail", spoor="rail",
    zadel="saddle", kompas="compass", klok="clock", kaart="map", boek="book",
    boeken="book", papier="paper", stok="stick", stokken="stick", stokjes="stick",
    lantaarn="lantern", bloem="flower", bloemen="flower", zaad="seeds", zaden="seeds",
    tarwe="wheat", suikerriet="sugar cane", cactus="cactus", vuurwerk="firework",
    drankje="potion", toverdrank="potion", ervaringsfles="experience bottle",
}
local numbers = {
    een=1, ["één"]=1, twee=2, drie=3, vier=4, vijf=5, zes=6, zeven=7, acht=8, negen=9,
    tien=10, elf=11, twaalf=12, twintig=20, dertig=30, veertig=40, vijftig=50, honderd=100,
    a=1, an=1, one=1, two=2, three=3, four=4, five=5, six=6, seven=7, eight=8, nine=9,
    ten=10, eleven=11, twelve=12, twenty=20, thirty=30, forty=40, fifty=50, hundred=100,
}
-- Words that start a request. Longest phrases first. Only the explicit "give"
-- verbs answer when no item matches; "ik wil ..." may be ordinary chat.
local triggers = {
    {"kan ik", "nl"}, {"mag ik", "nl"}, {"ik wil graag", "nl"}, {"ik wil", "nl"},
    {"geef", "nl", true}, {"gimme", "en", true}, {"give", "en", true}, {"get", "en"},
    {"can i have", "en"}, {"can i get", "en"}, {"i want", "en"}, {"i need", "en"},
}
local everyone = {iedereen=true, allemaal=true, ons=true, everyone=true, everybody=true,
    all=true, us=true}
local me = {me=true, mij=true, ik=true, mn=true, myself=true}
local filler = {graag=true, alsjeblieft=true, alstublieft=true, aub=true, pls=true,
    please=true, stuks=true, stuk=true, keer=true, x=true, of=true, van=true, some=true,
    wat=true, de=true, het=true, the=true, krijgen=true, hebben=true, nog=true, even=true,
    ["for"]=true, voor=true, ["to"]=true, aan=true, have=true}
M.MAX = 640

local function words(text)
    local out = {}
    for w in text:lower():gsub("[^%w%sé',]", " "):gsub(",", " , "):gmatch("%S+") do out[#out+1] = w end
    return out
end

-- Strip trailing plural forms so "crystals" matches "Crystal".
local function stem(w)
    if #w > 4 and w:sub(-3) == "ies" then return w:sub(1, -4) .. "y" end
    if #w > 4 and (w:sub(-4) == "ches" or w:sub(-4) == "shes" or w:sub(-3) == "xes") then
        return w:sub(1, -3)
    end
    if #w > 3 and w:sub(-1) == "s" and w:sub(-2) ~= "ss" then return w:sub(1, -2) end
    return w
end

--- Parse chat text into {items = {{count, query}, ...}, target, lang, strong},
-- or nil when it is no request. "geef me 10 brood en 5 appels" has two items.
-- `names` maps lowercase display names to account names, for "geef Anna 5 brood".
function M.parse(text, names)
    if type(text) ~= "string" or #text > 200 then return nil end
    local w = words(text)
    local i = 1
    -- Optional address: "assistent, ...", "hey gamenight ...".
    while w[i] == "," or w[i] == "hey" or w[i] == "hoi" or w[i] == "assistent" or w[i] == "assistant"
        or w[i] == "gamenight" do i = i + 1 end
    local lang, strong = nil, i > 1
    for _, t in ipairs(triggers) do
        local phrase = words(t[1])
        local ok = true
        for k, p in ipairs(phrase) do if w[i + k - 1] ~= p then ok = false break end end
        if ok then lang = t[2]; strong = strong or t[3] or false; i = i + #phrase; break end
    end
    if not lang then return nil end
    local target, items, count, rest = "me", {}, nil, {}
    local function close()
        if #rest > 0 then
            items[#items + 1] = {count = count or 1, query = table.concat(rest, " ")}
        end
        count, rest = nil, {}
    end
    for k = i, #w do
        local word = w[k]
        if word == "en" or word == "and" or word == "," then
            close()
        elseif me[word] then
            -- "geef me", "kan ik ... krijgen": the speaker.
        elseif everyone[word] then
            target = "all"
        elseif names and names[word] then
            target = names[word]
        elseif tonumber(word) and not count then
            count = math.floor(tonumber(word))
        elseif word:match("^%d+x$") and not count then
            count = tonumber(word:sub(1, -2))
        elseif word == "stack" or word == "stacks" or word == "stapel" or word == "stapels" then
            -- "een stack", "2 stacks": whole stacks of whatever item follows.
            count = {stacks = type(count) == "number" and count or 1}
        elseif numbers[word] and not count and #rest == 0 then
            count = numbers[word]
        elseif not filler[word] then
            rest[#rest + 1] = word
        end
    end
    close()
    if #items == 0 or #items > 8 then return nil end
    return {items = items, target = target, lang = lang, strong = strong}
end

local function tokens(text)
    local out = {}
    for _, w in ipairs(words(text)) do
        if w == "," then goto continue end
        local en = dutch[w] or dutch[stem(w)]
        if en then
            for part in en:gmatch("%S+") do out[#out + 1] = part end
        else
            out[#out + 1] = stem(w)
        end
        ::continue::
    end
    return out
end

local function same(a, b)
    if a == b then return true end
    local short, long = a, b
    if #short > #long then short, long = b, a end
    return #short >= 4 and long:sub(1, #short) == short
end

--- Index items as {name, label, words} once their descriptions are final.
function M.index(registered, translate)
    local list = {}
    for name, def in pairs(registered) do
        local desc = type(def.description) == "string" and def.description or ""
        if translate then desc = translate(desc) end
        desc = desc:gsub("\27%([^)]*%)", ""):gsub("\27.", ""):match("^[^\n]*") or ""
        if desc ~= "" and name ~= "" and not name:find("^:") and name ~= "air"
            and name ~= "ignore" and name ~= "unknown" then
            local groups = def.groups or {}
            list[#list + 1] = {name = name, label = desc, words = tokens(desc),
                id = stem(name:match(":(.*)$") or name),
                hidden = (groups.not_in_creative_inventory or 0) > 0}
        end
    end
    table.sort(list, function(a, b) return a.name < b.name end)
    return list
end

--- Best item for a query, plus up to two alternatives.
function M.find(index, query)
    local want = tokens(query)
    if #want == 0 then return nil end
    local joined = table.concat(want, "_")
    local scored = {}
    for _, item in ipairs(index) do
        local matched = 0
        for _, q in ipairs(want) do
            for _, w in ipairs(item.words) do
                if same(q, w) then matched = matched + 1 break end
            end
        end
        if matched == #want then
            -- Fewer extra words is closer: "crystal" prefers "End Crystal" over a
            -- "Crystal Block Slab". Exact item ids and visible items rank higher.
            local score = matched / #item.words
            if item.id == joined or item.id:match("_" .. joined .. "$") then score = score + 0.3 end
            if table.concat(item.words, "_") == joined then score = score + 1 end
            if item.hidden then score = score - 1 end
            -- Among colour/wood variants, prefer the usual one (Oak Planks, White Bed).
            for _, w in ipairs(item.words) do
                if w == "oak" or w == "white" then score = score + 0.05 end
            end
            scored[#scored + 1] = {item = item, score = score}
        end
    end
    table.sort(scored, function(a, b)
        if a.score ~= b.score then return a.score > b.score end
        return a.item.label < b.item.label
    end)
    if not scored[1] then return nil end
    -- An exact name needs no "did you mean"; a loose match lists close ones.
    local alternatives = {}
    if table.concat(scored[1].item.words, "_") == joined then return scored[1].item, alternatives end
    for k = 2, math.min(3, #scored) do
        if scored[k].item.label ~= scored[1].item.label then
            alternatives[#alternatives + 1] = scored[k].item.label
        end
    end
    return scored[1].item, alternatives
end

local text = {
    nl = {
        given = "Alsjeblieft: %s.", given_all = "Iedereen krijgt %s.", given_to = "%s krijgt %s.",
        unknown = "Ik weet niet welk voorwerp je bedoelt met '%s'.",
        also = " Bedoelde je iets anders? Probeer: %s.", dropped = " Je inventaris is vol; de rest ligt naast je.",
        offline = "Die speler is er nu niet.",
    },
    en = {
        given = "Here you go: %s.", given_all = "Everyone gets %s.", given_to = "%s gets %s.",
        unknown = "I don't know which item you mean by '%s'.",
        also = " Something else? Try: %s.", dropped = " Your inventory is full; the rest is next to you.",
        offline = "That player is not here right now.",
    },
}

local function give(player, name, count)
    local def = core.registered_items[name]
    local max = math.max(1, (def and def.stack_max) or 64)
    local inv, dropped = player:get_inventory(), false
    local left = count
    while left > 0 do
        local stack = ItemStack(name .. " " .. math.min(left, max))
        left = left - stack:get_count()
        local rest = inv:add_item("main", stack)
        if not rest:is_empty() then
            core.add_item(player:get_pos(), rest)
            dropped = true
        end
    end
    return dropped
end

local index
local function items()
    if not index then
        index = M.index(core.registered_items, function(s) return core.get_translated_string("en", s) end)
    end
    return index
end

--- Fulfil a request from `name`. Returns true when the text was a request
-- (so chat does not show it twice), plus the reply that was sent.
function M.handle(name, message, display)
    local names = {}
    for _, p in ipairs(core.get_connected_players()) do
        local account = p:get_player_name()
        local shown = display and display(account) or account
        names[shown:lower()] = account
        names[account:lower()] = account
    end
    local request = M.parse(message, names)
    if not request then return false end
    local t = text[request.lang]
    local found, missing = {}, {}
    for _, want in ipairs(request.items) do
        local item, alternatives = M.find(items(), want.query)
        if item then
            local def = core.registered_items[item.name]
            local count = want.count
            if type(count) == "table" then count = count.stacks * ((def and def.stack_max) or 64) end
            found[#found + 1] = {item = item, alternatives = alternatives,
                count = math.max(1, math.min(M.MAX, count))}
        else
            missing[#missing + 1] = want.query
        end
    end
    if #found == 0 and not request.strong then return false end
    local targets = {}
    if request.target == "all" then
        targets = core.get_connected_players()
    else
        local p = core.get_player_by_name(request.target == "me" and name or request.target)
        if p then targets = {p} end
    end
    local parts, dropped, alternatives = {}, false, {}
    if #targets > 0 then
        for _, f in ipairs(found) do
            for _, p in ipairs(targets) do dropped = give(p, f.item.name, f.count) or dropped end
            parts[#parts + 1] = ("%d× %s"):format(f.count, f.item.label)
            for _, a in ipairs(f.alternatives) do alternatives[#alternatives + 1] = a end
        end
    end
    local reply = ""
    if #targets == 0 then
        reply = t.offline
    elseif #parts > 0 then
        local list = table.concat(parts, ", ")
        if request.target == "all" then
            reply = t.given_all:format(list)
        elseif request.target == "me" then
            reply = t.given:format(list)
        else
            reply = t.given_to:format(display and display(request.target) or request.target, list)
        end
        if dropped then reply = reply .. t.dropped end
    end
    if #missing > 0 then
        reply = reply .. (reply == "" and "" or " ") .. t.unknown:format(table.concat(missing, "', '"))
    end
    if #alternatives > 0 and #alternatives <= 3 then
        reply = reply .. t.also:format(table.concat(alternatives, ", "))
    end
    if request.target ~= "me" and #parts > 0 then
        core.chat_send_all(core.colorize("#ad6cfa", reply))
        return true, reply
    end
    core.chat_send_player(name, core.colorize("#ad6cfa", reply))
    return true, reply
end

return M
