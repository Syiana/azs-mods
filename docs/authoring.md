# Authoring recipes

Start each recipe with `python sdk.py new copperbell` from the SDK folder, or work in a copy of
your current sources. The paths below are relative to the resulting `copperbell` directory.
Prepare a fresh local profile after you finish each change so the game sees the new version.

## Build a workshop yard

In `packs/example.copperbell/zones/workshop.toml`, the zone's `center` and `radius` define the
play area. `map_bounds` places the overview map. Check spawn paths and the ring around the arena
in the native client. Give the player room to dodge, at least two ways around obstacles and a
boss arena with a clear center. Increasing the radius alone can move spawns behind geometry.

The Tin Runner joins from minute zero, the slower Loose Rivet from minute two, and the Broken
Press guards lairs from minute three. Their `cost` affects what the encounter director can afford
to spawn. Change one variable at a time. For example, increase the Tin Runner's `speed` to
`7.4`, then play until minute three with a short-range starter and observe the difference.

The Shiftkeeper appears at minute eight. Edit `bosses/shiftkeeper.toml` to adjust how often its
attacks come due. The default nova gives a two-second warning. The charge combo makes players
reposition before the stomp. The occasional adds keep them moving between attacks.

## Create a mode

Copy `modes/example.copperbell/closing_shift.toml` to `opening_shift.toml` in the same directory.
Set `name` to `Opening Shift`, update `[card]` to describe its rules, and set
`[horde].enemy_health` to `0.85`. Both definitions inherit `standard`, so the player can choose
either mode from its own card. Changes in both modes apply to the campaign the profile loads.
The Workshop itself can also be selected in Campaign. Modded runs stay in the mod's scope.

## Add a class, a spell and a talent

Copy `recipes/class/coilwright/` into `packs/example.copperbell/classes/`. This demonstrates
three linked files. `class.toml` links the Coilwright to its starting spell and equipment.
`spells.toml` declares Spring Snap, a physical single-target strike. `talents.toml` defines
three trees and a three-rank physical damage talent in Brasswork.

When you adapt the recipe, reserve a free class ID and a free spell ID in the profile. Keep the
`starter` pointing at a spell on the class. In a published class, preserve talent order and
positions when possible so a new version makes existing builds predictable. The example is a
minimal class to extend with more unlocks and full talent trees.

## Override a shipped entry

Copy `recipes/overrides/overrides.toml` into `packs/example.copperbell/`. Add this to
`mod.toml`. The recipe references a stock key and supplies only a new cooldown value.

```toml
[[overrides]]
dependency = "base"
entity = "spell:fireball"
```

An override changes fields in an existing entry. A new entry gets a namespaced key and needs no
override declaration. Two independent packages that override the same entry can conflict.

## Script the boss

Replace `packs/example.copperbell/bosses/shiftkeeper.toml` with `recipes/script/shiftkeeper.toml`.
Copy `recipes/script/warning_bells.lua` to `packs/example.copperbell/scripts/warning_bells.lua`.
Prepare the profile normally. The SDK registers the Lua file as a script and adds the
`scripts-v1` capability. The game also asks players to consent to scripted mods.

The boss passes two numeric parameters to `fire`. It schedules two rings with a gap, then adds
a third ring on alternate casts using per-boss state. The [Mod scripts guide](
https://azreborn.com/guides/mod-scripts) covers hooks, command limits and how to dry-run a script
with `azs-script`. Use a native client that supports that capability.

## Design and share a Map Builder project

Use Map Builder for terrain and layout work. `recipes/map-builder/copperbell_trial.toml` gives
you a separate practice-map draft with a spawn point and two terrain brush strokes. It inherits
its encounters from a stock campaign zone. Copy it to `maps/copperbell_trial.toml` beside your
account save and open `copperbell_trial` in the editor. The [Map Builder section](
https://azreborn.com/guides/content-reference#the-map-editor) describes the controls.

| Phase | Plan | What to playtest |
| --- | --- | --- |
| Entry | Give the entrance a clear view of the yard and two routes out. | A fresh hero can leave the spawn without walking into a funnel. |
| First waves | Use the wide side routes for quick enemies. | Both routes remain reachable as the horde grows. |
| Lair | Leave room around the Broken Press for one full dodge. | The warning and the escape route are visible together. |
| Finale | Keep the center open for the Shiftkeeper's staggered rings. | Four or five players can spread out without leaving the arena. |

Run `azs-content check-map recipes/map-builder/copperbell_trial.toml` to check the source without
launching the editor. Playtest terrain and then use **Export package** in the editor's Share maps
panel. The [map package reference](https://azreborn.com/guides/content-reference#map-packages)
describes the export. Inspect the exported files before distributing them. See
[Releasing](releasing.md) for the distribution checklist.
