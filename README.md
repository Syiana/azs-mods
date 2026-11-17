# Azeroth Survivors Reborn: the package catalog

The list of community **packages** (mods and maps) that the game's MODS tab offers to install: locked
content profiles (the game's `profile.json` and the sources it locks) that the game imports as a local
mod and always plays as Modded. It holds no package: every package stays in its author's repository.
This repository only says which release of each one the game may install, and pins that release's zip
by size and SHA-256. The addons of the AddOns window are another repository
([`Syiana/azs-addons`](https://github.com/Syiana/azs-addons)); this one never lists an addon and that
one never lists a package, so that an older launcher, which installs every row of an addon index as a
Lua addon, never sees one.

```text
packages/<id>.toml    one entry per package, changed by pull request
packages.json         generated: the entries plus each package's pinned release
tools/packages.py     checks the entries and the zips, writes packages.json (Python, standard library)
tools/common.py       the rules it shares with the addon index's pin script
tools/test_packages.py  its tests (tools/test_support.py: their stand-ins)
.github/workflows/    check (pull requests), pin (daily), drift (nightly)
```

An entry names `kind` (`mod` or `map`), the `namespace` it owns (`author.name`; no entry may own a
namespace inside another's), the packages it `requires`, and `status` (`active`, `deprecated` or
`blocked`, with a `reason`) for its newest version. `mirrors` lists `https://` folders that serve
the pinned zip as `<sha256>.zip`. A package zip holds `profile.json` at the top, optionally
`LICENSE`, and exactly the objects the profile locks, by the game's content paths; the profile may
hold the game's own packs, its namespace, and a required package's packages exactly as some version
of that package pins them.

`packages.json` keeps every pinned version of a package, oldest first, up to 16: the newest is the
one the game offers, the older ones stay so that a package shipping them stays valid and so that a
version can be blocked after a newer one came out:

```toml
blocked = [{ version = "v1", reason = "Breaks saves." }]
```

A blocked newest version is not moved on, so launchers learn of the block. A `kind = "map"` package
is a Map Builder export: its zip locks exactly one package of its namespace holding only `map`
objects under `maps/<package>/`, with no edges to other packages and the `authored-map-v1`
capability; the launcher installs it beside the game's content (see the game's
`docs/HOWTO-CONTENT.md`, "Map packages"). Past 16 versions the
oldest go, never a blocked one or one another package ships. The launcher (`Catalog::parse` in
`azs-update/src/packages.rs`) holds the same rules, so a `packages.json` this script writes is one
the signing step accepts. `check --assets` falls back to the mirrors as the launcher does, and
reports a GitHub asset that no longer serves the pinned bytes either way. Run
`python tools/test_packages.py`, `python tools/packages.py check [--assets]` and
`python tools/packages.py pin [--offline]`.

Python has no BLAKE3, the game's object hash, so the maintainers' signing step checks every object
of every kept version (the assets folder holds each pinned zip by its SHA-256) and signs the
catalog under its own domain, so that no signature over it is one over a content release or the
addon index:

```bash
azs-release packages-sign --packages packages.json --assets <folder of <sha256>.zip> --store <the update store> --key <the release key>
```

### Adding a package

1. Make the profile folder: `profile.json` and the sources it locks, as the game's
   `docs/HOWTO-CONTENT.md` ("Local mod profiles") describes. Give your package an id and namespace of
   the form `author.name`.
2. `azs-release profile-lock <folder>` hashes the locked objects again after every edit, names the
   files the lock does not list, and runs the game's source preflight. Every name in your content
   needs all twelve languages (`en de fr es pt ru it pl tr ja zh ko`); a missing one is reported
   with its file and key.
3. `azs-release profile-pack <folder> --out <id>-<version>.zip` writes the release zip (the same
   bytes every time) and prints its size and SHA-256.
4. Publish a GitHub release of your repository with that zip as its asset.
5. Open a pull request with one new file, `packages/<id>.toml`:

```toml
id = "frostmage"                    # lower-case letters, digits and -; never changes afterwards
kind = "mod"                        # or "map"
name = "Frost Mage"
author = "someone"
repo = "someone/frostmage"          # the GitHub repository whose releases hold the zip
description = "One line on what it does."
license = "MIT"
namespace = "author.frostmage"      # the package id the profile's lock names
requires = []                       # ids of packages that are installed first

[source]
type = "release"
asset = "frostmage-*.zip"           # the release asset's name; * stands for the version
```

The pin workflow pins the release, a maintainer reads what the package changes (its balance, its
texts, what it asks of the game) and merges. To stop offering a version, set `status = "blocked"`
with a `reason`; a launcher turns a chosen profile of a blocked version off at its next start.

## Running it

Python 3.11 or newer, nothing to install.

```bash
python tools/test_packages.py
```

```bash
python tools/packages.py check
```

```bash
python tools/packages.py check --assets
```

```bash
python tools/packages.py pin
```

`check` reads only this repository. `check --assets` also fetches every pinned zip; `pin` asks
GitHub for the releases (set `GITHUB_TOKEN` to raise the API's rate limit; the token is sent to
the API only, never to a download). `pin --offline` brings `packages.json` up to the entries without
the network (a reverted pin must be re-pinned this way, so that the serial rises).

## Setting the repository up

- Settings > Actions > General > "Allow GitHub Actions to create and approve pull requests": the
  pin workflow opens its pull requests with the workflow's own token.
- A pull request opened with that token does not start the check workflow. The pin script has
  checked each zip before pinning it; to see the check run on such a pull request, close and reopen
  it.
- Protect the default branch, so that `packages.json` changes only through a reviewed pull request.

## Publishing (the game's maintainers)

After a pin is merged, `tools/publish-addons.ps1` in the game's repository does the rest, in the same
scheduled task that publishes the addon index (the release key stays on the maintainer's PC; CI never
holds it): its `packages` section looks at this repository's `main` every 30 minutes (`-PackagesRepo`),
and when `packages.json` has a higher serial than the live `packages/catalog.json` it fetches every
pinned zip into a folder as `<sha256>.zip` (a zip whose bytes differ from the pin stops it), signs the
catalog with `azs-release packages-sign` and uploads `packages/catalog.json.sig` before
`packages/catalog.json`. The launcher reads it only from the MODS tab's "Community packages".
