# Design and preview mods with MCP

The Mod Kit MCP runs locally over stdio. It can search the supplied game's packs, create and edit
a draft, check and package it for import, and start the installed client on explicit request.
Drafts contain editable content TOML. The packaging tools use the same profile format as manual mods.

Start with the [Modding SDK releases](https://github.com/Syiana/azs-mods/releases) and the
[starter profile](https://github.com/Syiana/azs-mods/tree/main/templates/starter-mod). The SDK
release must include `mod_mcp.py`. Use the starter profile and Windows authoring tools attached
to the same release if available. See [Getting the tools](https://azreborn.com/guides/making-mods#getting-the-tools)
for other versions.

## Connect it once

Install Python 3.13 or newer and run `python -m pip install -r requirements-mcp.txt` from the SDK
directory. Use `azs-content` and `azs-release` versions that match the stock profile you supply.
The preview command also needs a game installation with the matching preview-enabled launcher and
client. Close the game before starting a new preview. Building a ZIP only needs the SDK and profile.

Register a local MCP server in Claude Desktop with the following configuration. Replace the
example paths with absolute paths. Use the same command and arguments in any stdio MCP client.

```json
{
  "mcpServers": {
    "azs-mod-kit": {
      "command": "C:/Python313/python.exe",
      "args": [
        "C:/AZS-SDK/mod_mcp.py",
        "--workspace", "C:/AZS-Mods",
        "--base-profile", "C:/AZS-SDK/starter-mod",
        "--azs-content", "C:/AZS-Tools/azs-content.exe",
        "--azs-release", "C:/AZS-Tools/azs-release.exe",
        "--launcher", "C:/AzerothSurvivors/AzerothSurvivorsLauncher.exe"
      ]
    }
  }
}
```

With Codex CLI, register `codex mcp add azs-mod-kit -- <python> <mod_mcp.py> ...` with the same
arguments. Omit `--launcher` on a machine used only for content authoring. A browser session needs
a local MCP host to start an application on your machine.

## Make a playable draft

> Create a new class in `studio.stormcaller`. Start from the class recipe and add spells for a
> lightning bolt and a ground pulse using visual IDs from the stock packs. Add a four-piece
> and an eight-piece bonus, validate the mod, and give me the ZIP.

> Search the stock Warlock spells and set bonuses for a suitable fire impact. Make a draft which
> overrides the existing epic eight-piece bonus and adds a class-specific four-piece. Preview the
> Warlock in Elwynn wearing the epic set at five stars.

The `class` recipe supplies the class, a starter spell and the talent trees. Rename entity keys
together and check class and spell IDs against the pinned profile. In a set for a new class, use
explicit `class = "studio.stormcaller:stormcaller"` in each bonus when the class key is namespaced.
Use `draft_text` for every new localized name and tooltip. It fills the required locale keys with
English draft text wherever a translation is missing.
For a class/tier/piece-count combination that already exists, override that entry by its key and
declare its stock dependency in `mod.toml`. A second bonus with the same combination fails the
profile check. An existing tier also supplies the actual gear. `search_stock` and `read_stock`
give examples of the supported mechanics, triggers, visual references and gear tiers in the supplied
profile. If a mechanic needs a new engine capability, the profile checker will reject an unknown field.
Cataclysm content is available when the supplied stock profile includes `cata`. Add it to both
draft manifests when the mod directly depends on that pack.

`build_mod` writes the checked profile and ZIP under the workspace's `output` directory, with a
new location for each revision. Share the ZIP or extract it into a new subfolder under
`UserData/mods/import` and use **Menu → Mods → Import** in the game.

`launch_preview` checks the current draft and imports that revision through the installed launcher.
It opens a disposable hero in Elwynn's Proving Grounds with the selected set equipped and the
first available class spells on the bar. Omit `stars` to activate both set bonuses with the profile's
normal star thresholds. A preview class must be available in the profile's Proving Grounds mode.
Pass `spells` to give specific class abilities priority on the starting bar. Pick other spells,
targets or training settings from the Proving Grounds panel. `preview_status` reports server world entry and recent startup logs while
the client loads. Every preview gets a fresh account in the installation's `UserData/mods/previews`
folder. The normal game and mod saves and the normal mod selection are separate from that folder.
Changes to a draft take effect in a fresh preview after closing the current client.
