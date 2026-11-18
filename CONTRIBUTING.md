# Contributing a package

Thank you for making something for Azeroth Survivors Reborn. This file is how a mod or a map gets
into the game's Mods window. The rules themselves are in the [README](README.md) ("The rules"); the
mod kit is [`templates/`](templates/README.md).

## Proposing a new package

1. Publish the package first: a GitHub repository of your own, and a release (not a draft, not a
   prerelease) whose asset is the zip `azs-release profile-pack` wrote. See the README's
   "Publishing a mod".
2. Fork this repository and add one file, `packages/<id>.toml`, made from
   [`templates/registry-entry.toml`](templates/registry-entry.toml). Change nothing else: in
   particular not `packages.json`, which the pin workflow writes.
3. Run the check if you have Python 3.11 or newer (nothing to install):

   ```bash
   python tools/packages.py check
   ```

   It prints `the package entries and packages.json are in order`, or what is wrong and in which
   file.
4. Open the pull request. The template asks what the package does, what it changes, whether it
   has scripts, and that it holds no game files.

You may also open a "New package" issue first, to ask whether an idea fits before you build it.

## Writing the entry

- `id`: the package's name in the catalog, lower-case letters, digits and `-`. It never changes, so
  pick it with care. The file is `packages/<id>.toml`.
- `namespace`: `<you>.<mod>`, the id of your package in `profile.json` and its folder
  `packs/<namespace>/`. It is yours from then on; no one else's entry may use it or a name inside it.
- `repo`: `owner/name` of the repository whose releases hold the zip.
- `[source] asset`: the asset's file name, with one `*` for the version, for example
  `example-*.zip`. Exactly one asset of a release may match.
- `license`: your licence's name, and ship its text as `LICENSE` in the zip.
- `description`: one line on what the package does, in English.

Every key is explained in the template, with its limits.

## Proposing an update

A new version needs no pull request of yours: publish a new release with a new tag, and the next
pin run (once a day) pins it and opens its own pull request for the review. Change your entry by
pull request only when the entry itself changes: a new description, a mirror, a block.

The repository, the kind and the namespace stay the same for every version of a package. A package
that moves to another repository is a new entry.

## What we read in a review

The review is described in full in [docs/REVIEW.md](docs/REVIEW.md). In short: what the package
changes (its numbers and its texts in all twelve languages), what it asks of the game, every script
line by line, its licence and its right to every file it ships, and that it holds no file of World
of Warcraft ([docs/LEGAL.md](docs/LEGAL.md)).

## How long it takes

The reviewers are volunteers, and there is no fixed time. A small, clear package with a clear
description is the quickest to read; a package with scripts takes longest, since every line is
read. If a pull request has waited a long time without an answer, ask in the community Discord.

## Conduct

Be kind and patient with authors, reviewers and players; criticise work, never people. Harassment,
hate and content that targets a person get a pull request or issue closed and its author blocked.

## Reporting a broken or harmful package

Open a "Problem with a package" issue: which package and version, what happens, and how to see it.
A version that breaks saves, misleads players, or carries files it must not is blocked: the
launcher stops installing it and, at its first start after it has read a catalog that names the
block (opening **GET MORE** reads it), turns it off, saves kept.

Do not post an exploit or a harmful file in an issue. Send it privately through
<https://azreborn.com/contact>, which is also the way for rights holders to reach us.
