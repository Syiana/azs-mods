<!-- A new package or a change to an entry. Pin pull requests ("Pin: packages serial N") are opened by the pin workflow and do not use this template. -->

## The package

- Entry: `packages/<id>.toml`
- Repository: `owner/name`
- Kind: mod / map
- What it does, in a few lines:

## What it changes

<!-- The entries of the game it overrides (the "overrides" of profile.json), what it adds, and any game mode it brings. -->

## Checklist

- [ ] The pull request changes only `packages/<id>.toml` (not `packages.json`).
- [ ] `python tools/packages.py check` passes.
- [ ] The release named by `[source] asset` exists, is not a draft or a prerelease, and its zip was written by `azs-release profile-pack`.
- [ ] `azs-release profile-lock` passes on the package folder, and the mod was imported and played in my own game.
- [ ] Every name and text a player reads is in all twelve languages (`en de fr es pt ru it pl tr ja zh ko`).
- [ ] The package has scripts: yes / no. If yes, `azs-script check` passes.
- [ ] The zip holds a `LICENSE` that says which files it covers.
- [ ] The package holds no file of World of Warcraft and nothing extracted from one, and only files I may share ([docs/LEGAL.md](https://github.com/Syiana/azs-mods/blob/main/docs/LEGAL.md)).
