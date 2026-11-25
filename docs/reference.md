# Source and profile reference

## SDK source project

```text
my-mod/
  LICENSE
  mod.toml
  packs/myname.my-mod/
    pack.toml
    zones/workshop.toml
    bosses/shiftkeeper.toml
    classes/coilwright/{class,spells,talents}.toml
    scripts/warning_bells.lua
  modes/myname.my-mod/closing_shift.toml
```

Namespaced gameplay keys use `myname.my-mod:entry_name`. Mode keys use the TOML filename
under the mode's namespace directory. Keep package IDs portable and stable across versions.
The SDK requires a lower-case dotted id such as `myname.my-mod`, a version string, and the
same `requires` list in `mod.toml` and `pack.toml`. `base` is required for these examples.
Add `tbc` or `wotlk` when your content directly depends on those packs.

| Source path | Generated lock object |
| --- | --- |
| `packs/<id>/**/*.toml` | `gameplay` |
| `packs/<id>/scripts/**/*.lua` | `script`, enables the `scripts-v1` capability |
| `modes/<id>/*.toml` | `mode` |
| `LICENSE` | Copied to the local profile beside its lock |
| `mod.toml` | SDK metadata used to build the profile lock |

Keep design documents and images beside the source folder. This source builder handles one
gameplay package and the three stock dependencies. To add a separately licensed texture,
cosmetic pack or another community dependency, use the full game profile format described in
[Making mods](https://azreborn.com/guides/making-mods). There you can set `required_assets`,
add other packages and use their licensed resource files.

## From source to a locked profile

`prepare` copies the three stock packages from the profile you supply, adds the source mod,
and registers every included object. It takes the schema and ABI from your base profile.
`azs-release profile-lock` fills the BLAKE3 hashes and checks the assembled content. The final
directory appears at the requested path only after that check passes. Keep the source directory
as the place where you edit. The local profile contains its own copies of the dependencies.

For structured diagnostics, use `azs-content profile-check --profile <local-profile> --json`.
The native client's import performs its own checks, including mode settings. Run a playtest
for terrain, art references, timing, balance and scripted attacks. A successful import is
a good time to start those checks.

## Localized text and presentation

For localized names, subtitles and dialogue, use the twelve keys `en`, `de`, `fr`, `es`,
`pt`, `ru`, `it`, `pl`, `tr`, `ja`, `zh` and `ko`. Save as UTF-8. Keep placeholders
like `{v}` in every version of a talent tooltip. Mode cards can use the English fields as a
fallback and add `[i18n.<language>]` sections.

Choose distinct entity keys and NPC entry IDs. Creature `display` refers to the presentation
data mounted by the client. It is an independent number from the encounter's `entry`. For
maps, keep `map`, `map_name`, `area`, `center` and `map_bounds` consistent with the client's
coordinates. For spells, the numeric ID refers to the local presentation and also needs to be
unique in the assembled spell registry. Test these references in the game.

## Diagnose a problem

| Message or symptom | Check |
| --- | --- |
| Unsupported source file | Keep only the source files in the paths above. |
| Declare every override | Put the referenced stock pack in `requires` and the entity in `[[overrides]]`. |
| Hash mismatch | Re-run `prepare` from the sources into a fresh output folder. |
| Missing locale or tooltip placeholder | Compare all twelve text fields and the tokens in the English string. |
| Duplicate class, spell or key | Choose a free ID and keep your keys namespaced. |
| Unknown mode or invalid setting | Check the filename, `extends` and game mode fields against the content reference. |
| Diagnostic points to a stock package | Run the same tool on the original base profile. Use a base profile and author tools from the same release. |
| Missing or unsupported script capability | Use a current native client and check that the script lives below your package's `scripts/` directory. |
| Profile imports and zone looks wrong | Check the four terrain references, then inspect the arena and NPCs in a run. |

The full [content field reference](https://azreborn.com/guides/content-reference) covers spells,
boss mechanics, mode parameters and all other content types. The [script API reference](
https://azreborn.com/guides/mod-scripts) covers Lua hooks. These are maintained with the game.
