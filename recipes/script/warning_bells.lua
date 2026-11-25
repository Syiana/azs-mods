-- Two warning rings, with an extra ring on alternate casts.
local function ring(radius, delay)
  return { ability = { nova = { spell = 8078, radius = radius, warn = 1.6 } }, delay = delay }
end

function fire(ctx, state)
  local radius = ctx.params.radius
  local extra = ctx.params.extra
  state.wide = state.wide == 1 and 0 or 1
  local actions = { ring(radius, 0), ring(radius + extra, 2) }
  if state.wide == 1 then
    actions[3] = ring(radius + extra * 2, 4)
  end
  return actions, state
end
