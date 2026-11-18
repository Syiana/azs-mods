-- slam.lua: a nova on every cast, and on every third cast a combo of three novas and a yell.
local function nova(radius)
  return { nova = { spell = 905193, radius = radius, warn = 1.5 } }
end

function fire(ctx, state)
  local casts = (state.casts or 0) + 1
  state.casts = casts
  local radius = (ctx.params.reach or 4) + 2 + ctx.roll() * 2
  if casts % 3 == 0 then
    local steps = { nova(radius), nova(radius + 2), nova(radius + 4) }
    return { { ability = { combo = { steps, 1.5 } } }, { say = "slam" } }, state
  end
  return { { ability = nova(radius), delay = 0.5 } }, state
end

function death(ctx, state)
  return { { say = "slam" } }
end
