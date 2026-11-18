# The mod kit: templates for Azeroth Survivors Reborn mods

This folder is a set of **templates**: text files to copy, rename and change. It holds no program,
no tool and no file of World of Warcraft. Everything in it is TOML, Lua, JSON or Markdown that the
project wrote, plus copies of the game's own content packs (also text) in `starter-mod/`.

```text
templates/
  README.md               this file
  registry-entry.toml     your packages/<id>.toml for the pull request, every key explained
  snippets/               one small, checked example per task, each naming the file it goes in
    spell-override.toml     change a spell the game has
    talent-add.toml         add a talent to a shipped class
    talent-rework.toml      change a talent the game has
    boss-kit.toml           a boss kit of your own (what the boss does)
    zone.toml               a zone of your own, with its enemies, an elite and its boss
    enemy.toml              more enemies for that zone (a ranged one, a second elite)
    mode.toml               a game mode on top of the Campaign
    class/                  a new class: class.toml, spells.toml, talents.toml
    script-boss/            a boss kit that calls a Lua script, and the script
  starter-mod/            a complete mod folder that passes the game's check
```

The guides that go with the kit are on the game's site, under **Guides** (they go online with the
site's next update): **Mods** (`/guides/mods`), **Making mods** (`/guides/making-mods`, the
tutorial), **Mod scripts** (`/guides/mod-scripts`) and **Content reference**
(`/guides/content-reference`, every field of every entry).

## Getting the tools

Three author tools check and pack a mod: `azs-content` (the game's content check),
`azs-release` (lock and pack) and `azs-script` (the script check). They come from the game's
private repository and are **not** part of the game download or of this kit. To get them, ask in the
community Discord: <https://discord.gg/PAkjPpryPP>. You can read, copy and change every template
without them; you need them to check a mod before you share it, and to pack its release zip.

## What the starter is

`starter-mod/` is a **locked content profile**, the folder a player imports:

```text
starter-mod/
  profile.json                 the lock: every package, its version, every file and its BLAKE3 hash
  LICENSE                      a placeholder: replace it with your licence
  packs/base/ packs/tbc/ packs/wotlk/   copies of the game's own packs
  modes/*.toml                 copies of the game's own game modes (the base package's)
  packs/yourname.example/      YOUR package: pack.toml and overrides.toml (the worked example)
```

- The worked example is one override: the mage's Fireball hits for 60 instead of 51 and comes every
  1.1 seconds instead of 1.3 (`packs/yourname.example/overrides.toml`, declared in `profile.json`
  as `{ "dependency": "base", "entity": "spell:fireball" }`).
- A profile carries every pack it plays, so the starter carries the game's packs `base`, `tbc` and
  `wotlk`. They are copies of the game's content, made on 2026-11-18 while the game was at 0.7.1
  (the game repository at commit `8ed6ae8e5`). A mod plays the copy it locked: a later update of the
  game's own content does not reach it until you copy the newer files in and lock again.
- The game's Cataclysm pack is not in the kit, and no mod may carry it. Its one trace was in the
  Campaign mode: the game's own `modes/standard.toml` lists `packs = ["base", "tbc", "wotlk",
  "cata"]`; the starter's copy lists `["base", "tbc", "wotlk"]`, with a comment above the line.
  Every other file of the three packs and the modes is the game's file as it is.
- Size: 390 files (388 locked TOML files, `profile.json`, `LICENSE`), about 3.2 MB; its release
  zip is about 1.3 MB.
- It passes `azs-content profile-check` (`"ok": true`, 4 gameplay packages) and
  `azs-release profile-lock` (`388 objects locked, 0 rehashed; the game's preflight passes`). That check reads
  the sources and the registry; the game's full mode check (`runtime_modes_validated` in its JSON
  is `false`) and an import into a running game were not run on it.
- Line endings: every file is stored with LF line endings, and the repository keeps them so on every
  checkout (`.gitattributes`). The lock's hashes are of those bytes: an editor or a git setting that
  turns them into CRLF changes every hash, and the check then says "TOML source hash differs from
  the profile lock". `azs-release profile-lock` writes the new hashes after any edit.

## Making your mod from the starter

1. **Copy** `starter-mod/` to a folder of your own (the folder's name is up to you).
2. **Name your package.** Pick `<you>.<mod>`: lower-case letters, digits, `_` and `-`, two parts or
   more, never starting with `azs.`. Rename the folder `packs/yourname.example/`, and replace
   `yourname.example` by your name in `packs/<yours>/pack.toml` and everywhere in `profile.json`
   (a plain search and replace: the package's `id` and its objects' paths). Give the lock a
   `name` of your own in `profile.json` (lower-case letters, digits, `.`, `_` and `-`).
3. **Write your changes** into your package folder, starting from a snippet. Each snippet's first
   lines say which file it goes in, what the lock must declare, and the rules that bite.
4. **Add each new file to the lock.** In `profile.json`, under your package's `objects`, add
   `{ "path": "packs/<yours>/<file>", "hash": "<any 64 hex digits>", "kind": "gameplay" }` (a mode
   file: `"kind": "mode"`, a script: `"kind": "script"`). `azs-release profile-lock` writes the
   real hash; it does not add a file for you, it names it (`not locked: <path>`).
5. **Declare each override.** A change to an entry the game has (an `[[override]]`) needs
   `{ "dependency": "base", "entity": "<kind>:<key>" }` in your package's `overrides`. The
   dependency is a pack your package requires directly (`requires` in `pack.toml`, `dependencies`
   in `profile.json`, the same list) that defines the entry or requires the pack that does: to
   change a `wotlk` entry, require `wotlk` and name it. A new entry needs nothing there.
6. **Lock and check** (the test loop below). Repeat 3 to 6 until it passes.
7. **Replace `LICENSE`** with your licence, saying which files it covers (your own package only).

## The test loop

```text
azs-release profile-lock <folder>                  rehash, name unlocked files, run the check
azs-content profile-check --profile <folder> --json   the check alone, as JSON
azs-script check <folder>                          only for a mod with scripts
```

Messages you will meet, as the tools print them:

| Message | What to do |
| --- | --- |
| `TOML source hash differs from the profile lock` | run `azs-release profile-lock` after your edit |
| `not locked: packs/<yours>/<file>` | add the file to your package's `objects` (step 4) |
| `the lock must declare this override` | add the override to your package's `overrides` (step 5) |
| ``entity key must use its package namespace `<yours>:` `` | a new entry's key is `<yours>:<name>` |
| ``talent <key>: `name` has no `ko` string`` | write the text in all twelve languages |
| `a zone needs normal enemies and elites` | a zone has at least one `[[zone.enemy]]` and one `[[zone.elite]]` |
| `a zone needs exactly one final boss` | mark one `[[zone.boss]]` with `final = true` |
| `gameplay TOML must be under packs/<id>/, its package owner` | the package id, its folder and `pack.toml` `key` must agree |

Then play it: put the folder into `UserData\mods\import\` of your game, open **MENU**, **Mods**,
press **Import**, then **Choose** on your mod, and restart the game. Import again after every
change; the newer import replaces the older one of the same mod.

## Before you publish: the checklist

- [ ] `azs-release profile-lock` passes, and no file is reported `not locked`.
- [ ] `azs-script check` passes, if your mod has scripts.
- [ ] Every name, text and yell a player reads is in all twelve languages
      (`en de fr es pt ru it pl tr ja zh ko`), and the translations say the same thing.
- [ ] Your package's id is `<you>.<mod>`, and it is your registry entry's `namespace`.
- [ ] Every override is declared, and each one is a change you mean to make.
- [ ] Your mod imported, was chosen and played a run in your own game.
- [ ] `LICENSE` is your licence and says which files it covers.
- [ ] The zip holds no file of World of Warcraft or anything taken out of one (no archives, models,
      textures, sounds or DBC tables), and no art, music or sound you may not share.
- [ ] `azs-release profile-pack <folder> --out <id>-<version>.zip` printed the zip's size and
      SHA-256, and that zip is the asset of a GitHub release (not a draft, not a prerelease) whose
      name fits your entry's `[source] asset`.
- [ ] `registry-entry.toml`, filled in, is your `packages/<id>.toml`.

## The notice

Azeroth Survivors Reborn is a fan project. It is not affiliated with or endorsed by Blizzard
Entertainment. "World of Warcraft", "Warcraft" and "Azeroth" are trademarks of Blizzard
Entertainment. A mod must not contain Blizzard's game files or anything extracted from them
(archives, models, textures, sounds, DBC tables): only text and files its author may share. A mod
may name files of the player's own game client by their id or path, as these templates do (spell
ids, display ids, icon names). The full rule is `docs/LEGAL.md` of the registry; rights holders
reach us through <https://azreborn.com/contact>.
