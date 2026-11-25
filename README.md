# Survivors Modding SDK

[Design classes and sets with MCP](docs/mcp.md) and launch them in an equipped Elwynn preview.

Build maps, enemies, bosses, game modes and classes for Azeroth Survivors Reborn. The SDK includes
source tools and an original example called **Copperbell Workshop**. The example takes place in
a small yard with two enemy types, an elite and a final boss. Its Closing Shift mode lets you
raise the challenge across the campaign. Optional recipes add a class, a spell override or a
scripted boss.

## Start here

Use Python 3.11 or newer in a terminal opened in this folder. On Windows, use `py -3` if
`python` is unavailable.

```sh
python sdk.py new copperbell
python sdk.py check copperbell
```

Open `copperbell/packs/example.copperbell/zones/workshop.toml` and change the final boss's
`minute` from `8` to `6`. Run `check` again. This checks the source layout, TOML syntax and
override declarations. The game checks ability fields and cross-references when you prepare
and import a local profile.

Before starting your own project, use `python sdk.py new my-mod --id myname.my-mod` to get a
fresh copy with your package id. The optional recipes use `example.copperbell` in their keys.
Replace it with your id when you copy them into your project.

## Try it in the game

The next step needs the native client, a separately obtained starter profile with the game's
`base`, `tbc` and `wotlk` packages, and a matching `azs-release` tool. Read **Getting the tools**
in the [Making mods guide](https://azreborn.com/guides/making-mods) for access to the tools.
Use a base profile you trust and keep it unmodified.

```sh
python sdk.py prepare copperbell --base-profile /path/to/starter-mod --output copperbell-local
```

If `azs-release` is outside your PATH, add `--azs-release /path/to/azs-release`. The output folder
must be new, beside or outside the source folder. In the native client open **Mods → Import**,
select `copperbell-local`, and select the imported profile. Copperbell Workshop is available as
a zone. Closing Shift is a separate mode card. The client uses local game data to render the
example; the package supplies its gameplay rules.

To iterate, edit `copperbell` and prepare a fresh output folder. Import that version into the
game. Gameplay edits can create a new save scope. Vanilla progression stays in the game's
official profile.

## Learn and publish

- [Authoring](docs/authoring.md) walks through the workshop, difficulty tuning, three talent trees,
  a balance override, Lua boss phases and the Map Builder workflow.
- [Reference](docs/reference.md) describes source layout, dependency declarations, text localization
  and diagnosing build and import errors.
- [Releasing](docs/releasing.md) covers the SDK archive, the local test profile and the repository
  entry you can use when you are ready to submit a mod.
- [Notices and provenance](NOTICE.md) describes exactly what the SDK license covers. The SDK
  archive includes `CONTENTS.sha256` for inspecting its contents.
