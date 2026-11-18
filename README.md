# Azeroth Survivors Reborn: the community mods and maps

This repository is the list of community **packages**, mods and maps, that the game's Mods window
offers to install (its **GET MORE** tab). It holds no package itself: every package stays in its
author's own GitHub repository. An entry here says which repository a package comes from, and the
registry pins each release it offers by the zip's size and SHA-256, so a player's game installs
exactly the bytes that were reviewed.

- A **mod** is a locked content profile: the game's `profile.json` and the content files it locks.
  It changes spells, talents, enemies, bosses, zones, game modes or classes, and always plays as
  **Modded** (heroes and progress of its own, no ranks, co-op only with players on the same lock).
- A **map** is a Map Builder export: one map and its manifest, played as a practice map.

New to mods? The guides on the game's site are the place to start (they are its home; they go
online with the site's next update):

- **Mods**, <https://azreborn.com/guides/mods>: what mods are, playing them, what they can and
  cannot do.
- **Making mods**, <https://azreborn.com/guides/making-mods>: the tutorial, from nothing to a
  published mod.
- **Mod scripts**, <https://azreborn.com/guides/mod-scripts>: Lua boss scripts.
- **Content reference**, <https://azreborn.com/guides/content-reference>: every field of every
  entry.

## Getting a mod (players)

1. In the game's hero menu, open **MENU**, then **Mods**, then the **GET MORE** tab.
2. Press **Install** on a row (or **Update** when an older version is installed).
3. On the **INSTALLED** tab, press **Choose** on the mod, and restart the game.

The game downloads only the pinned zip, checks every file, and imports it. The catalog it reads is
signed by the game's maintainers, so a launcher knows it comes from them. A mod from a folder (not
from this list) is imported with **Import** instead; see the Mods guide.

## Publishing a mod (authors)

1. **Make the mod**: a profile folder (`profile.json` and the files it locks). Start from the kit in
   [`templates/`](templates/README.md): a complete starter mod that passes the game's check, one
   small checked example per task, and this registry's entry, every key explained.
2. **Check it** with the author tools: `azs-release profile-lock <folder>` and, for a mod with
   scripts, `azs-script check <folder>`. The tools are not part of the game download; ask for them in
   the community Discord, <https://discord.gg/PAkjPpryPP>.
3. **Play it** in your own game: import it from `UserData\mods\import\` (MENU, Mods, Import),
   choose it, restart, play a run.
4. **Pack it**: `azs-release profile-pack <folder> --out <id>-<version>.zip` writes the release zip
   (`profile.json`, an optional `LICENSE` and exactly the locked files, the same bytes every time)
   and prints its size and SHA-256.
5. **Release it**: a GitHub release of your repository (not a draft, not a prerelease) with that zip
   as its asset. The release's tag is the version players see.
6. **Register it**: a pull request on this repository with one new file, `packages/<id>.toml`
   (copy [`templates/registry-entry.toml`](templates/registry-entry.toml)). See
   [CONTRIBUTING.md](CONTRIBUTING.md).

## What a pull request goes through

1. **The check.** Every pull request runs `python tools/test_packages.py` and
   `python tools/packages.py check --assets` (`.github/workflows/check.yml`): the entries are
   well-formed, together they break no rule below, and every pinned zip is still the pinned bytes.
   It is read-only, so it runs on a pull request from a fork too.
2. **The entry review.** A maintainer reads the entry: who you are, what the package is, its
   namespace and licence, and merges it.
3. **The pin.** Once a day (and on request) the pin workflow (`.github/workflows/pin.yml`) fetches
   each package's newest release, checks the zip against the launcher's rules (below) and opens a
   pull request "Pin: packages serial N" that adds it to `packages.json` by size and SHA-256. A
   release that breaks a rule is not pinned; the pull request says why, and the package keeps the
   pin it had.
4. **The review.** Merging the pin's pull request is the review: a maintainer reads what changed in
   your repository between the old and the new tag, as [docs/REVIEW.md](docs/REVIEW.md) describes.
   Nothing reaches players before it is merged and signed.
5. **Signing.** The maintainers' publisher signs the merged `packages.json` into the catalog the
   launcher reads (see "For maintainers"). A game shows the new version after its next catalog
   refresh.

Every night the drift workflow (`.github/workflows/drift.yml`) fetches every pinned zip again and
opens an issue when one is no longer the pinned bytes (its release asset was replaced or removed)
or no longer passes the rules. Players are safe either way: the launcher installs only the pinned
bytes.

## The rules

These are the rules `tools/packages.py` checks; the game's launcher holds the same ones.

- **Ids.** An entry's `id` is lower-case letters, digits and `-`, at most 64 characters, and its
  file is `packages/<id>.toml`. An id is listed once and never changes.
- **Namespaces.** An entry owns a `namespace` of the form `author.name`: two or more lower-case
  parts of letters, digits, `_` and `-`, at most 64 characters. Names that start with `azs.` are
  the game's and are refused. No namespace may lie inside another entry's (`a.b` and `a.b.c`
  overlap). Your profile holds packages of three sorts only: the game's own packs (an unqualified
  name like `base`), packages of your namespace, and packages of a package you `require`, exactly
  as some version of that package pins them (same id, version and kind).
- **Kinds.** `kind = "mod"` or `"map"`. A map package's zip locks exactly one package of its
  namespace, holding only `map` objects under `maps/<package>/`, with no edges to other packages,
  and requires the `authored-map-v1` capability.
- **The zip.** `profile.json` at the top, beside it at most a `LICENSE`, and exactly the files the
  profile locks, by normalized content paths. No program (`.exe`, `.dll`, `.bat`, `.ps1`, `.sh`,
  `.jar`, ... are refused by name), no link, no encryption, only stored or deflated entries, each
  unpacking to the size it announces. At most 5,000 files, 256 MiB unpacked, 12 folders deep, 240
  bytes a path; the zip itself at most 64 MiB, `profile.json` at most 8 MiB.
- **Licences.** `license` names your licence (at most 40 characters). Ship its text as `LICENSE` in
  the zip and say which files it covers: your own package only, since the game's packs in your
  profile are the game's.
- **No game files.** A package must not contain Blizzard's game files or anything extracted from
  them; see [docs/LEGAL.md](docs/LEGAL.md).
- **Status.** `status` is the newest version's: `active` (offered), `deprecated` (still installs,
  with a notice giving the `reason`) or `blocked` (not installed any more). A deprecated or blocked
  package says why in `reason`. An older version is blocked with `blocked = [{ version, reason }]`,
  where `version` is a pinned release tag:

  ```toml
  blocked = [{ version = "v1", reason = "Breaks saves." }]
  ```

  A launcher turns a chosen profile of a blocked version off at its first start after it has read a
  catalog that names the block (opening the Mods window's **GET MORE** tab reads it), and keeps the
  saves; a game that never reads the catalog again keeps playing it.
  A blocked newest version is not moved on to a newer release, so that launchers learn of the block.
- **Versions.** `packages.json` keeps every pinned version of a package, oldest first, up to 16: the
  newest is the one offered, the older ones stay so that a package shipping them stays valid and so
  that a version can be blocked after a newer one came out. Past 16 the oldest go, never a blocked
  one or one another package ships. A version is a release tag: a new version needs a new tag, and
  a tag pinned already with another asset is refused.
- **Mirrors.** `mirrors` lists up to 4 `https://` folders (ending in `/`) that serve the pinned zip
  as `<sha256>.zip`, exact bytes. The launcher falls back to them when GitHub no longer serves the
  pinned bytes.

## FAQ

**Why was my pull request refused?** The check prints the reason with the file it is about, for
example `example.toml: namespace 'azs.example' is not author.name (and not azs.)` or
`other.toml: its file is not named example.toml`. Fix the entry and push again. A reviewer may also
ask for changes (see [docs/REVIEW.md](docs/REVIEW.md)), and may refuse a package that breaks the
rules here or in [docs/LEGAL.md](docs/LEGAL.md).

**What does the pin do?** It ties your entry to one exact zip: the release's tag, the asset's
address, its size and SHA-256, and what its `profile.json` says (its packages, their versions, its
compatibility, whether it has scripts). A player's game installs only those bytes; a zip you
replace later is not installed, and the drift check reports it.

**How do I ship an update?** Lock and pack the new version, and publish a new GitHub release with a
new tag and a zip whose name fits your `[source] asset`. The next pin run pins it beside the old
versions and opens its pull request; after the review it is the version offered, and a player's
**Update** keeps the old version and its progress. You need no pull request of your own unless the
entry itself changes.

**How do I withdraw a version?** Open a pull request that changes your entry: `status = "blocked"`
with a `reason` for the newest version, or `blocked = [{ version = "<tag>", reason = "..." }]` for
an older one. A blocked package's pin does not move on, so to withdraw the newest version and ship a
fixed one, list the bad tag under `blocked`, keep `status = "active"`, and publish the fix as a new
release. Deleting the release alone does not
withdraw it: the pin stays, and a mirror may still serve it.

**May I use art or sounds from World of Warcraft?** No. A package must not contain the game's files
or anything taken out of them: archives, models, textures, sounds, DBC tables. A mod may name files
of the player's own client by their id or path (a spell id, a display id, an icon name, a model
path), which is how the game's own content works. Pictures you made yourself, or may share, can
ship as files of your package (a PNG zone icon or a painting behind a class's talents; see the
content reference). A mod cannot play sounds of its own today. [docs/LEGAL.md](docs/LEGAL.md) has the full rule.

## Layout

```text
packages/<id>.toml      one entry per package, changed by pull request
packages.json           generated: the entries plus each package's pinned releases
templates/              the mod kit: starter mod, snippets, the entry template
docs/REVIEW.md          what a reviewer reads
docs/LEGAL.md           the notice and the rule on game files
tools/packages.py       checks the entries and the zips, writes packages.json (Python, standard library)
tools/common.py         the rules it shares with the addon index's pin script
tools/test_packages.py  its tests (tools/test_support.py: their stand-ins)
.github/workflows/      check (pull requests), pin (daily), drift (nightly)
```

The addons of the AddOns window are another repository
([`Syiana/azs-addons`](https://github.com/Syiana/azs-addons)): this one never lists an addon and
that one never lists a package, so that an older launcher, which installs every row of an addon
index as a Lua addon, never sees one.

## For maintainers

### Running the scripts

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

`check` reads only this repository. `check --assets` also fetches every pinned zip, falling back to
the mirrors as the launcher does, and reports a GitHub asset that no longer serves the pinned bytes
either way; `pin` asks GitHub for the releases (set `GITHUB_TOKEN` to raise the API's rate limit; the
token is sent to the API only, never to a download). `pin --offline` brings `packages.json` up to
the entries without the network (a reverted pin must be re-pinned this way, so that the serial
rises).

Python has no BLAKE3, the game's object hash, so the maintainers' signing step checks every object
of every kept version (the assets folder holds each pinned zip by its SHA-256) and signs the
catalog under its own domain, so that no signature over it is one over a content release or the
addon index:

```bash
azs-release packages-sign --packages packages.json --assets <folder of <sha256>.zip> --store <the update store> --key <the release key>
```

### Setting the repository up

- Settings > Actions > General > "Allow GitHub Actions to create and approve pull requests": the
  pin workflow opens its pull requests with the workflow's own token.
- A pull request opened with that token does not start the check workflow. The pin script has
  checked each zip before pinning it; to see the check run on such a pull request, close and reopen
  it.
- Protect the default branch, so that `packages.json` changes only through a reviewed pull request.

### Publishing

After a pin is merged, `tools/publish-addons.ps1` in the game's repository does the rest, in the same
scheduled task that publishes the addon index (the release key stays on the maintainer's PC; CI never
holds it): its `packages` section looks at this repository's `main` every 30 minutes (`-PackagesRepo`),
and when `packages.json` has a higher serial than the live `packages/catalog.json` it fetches every
pinned zip into a folder as `<sha256>.zip` (a zip whose bytes differ from the pin stops it), signs the
catalog with `azs-release packages-sign` and uploads `packages/catalog.json.sig` before
`packages/catalog.json`. The launcher reads it only from the Mods window's **GET MORE** tab.
