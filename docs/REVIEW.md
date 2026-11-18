# Reviewing a package

A pin's pull request ("Pin: packages serial N") adds a release to `packages.json`. The pin script
has already checked the zip's structure (the launcher's rules, see the README); merging the pull
request is the human review. This file is what a reviewer reads, and what makes a version blocked.

A review is distribution approval, never a promise: it checks that a package is what it says it is
and plays by the rules, not that it is fun or balanced. A reviewed mod still plays as **Modded**.

## What to read

Read the diff of the author's repository between the old pinned tag and the new one (for a new
package: the whole package folder). The game's own packs in a profile are copies of the game's
content: compare them with the game's files rather than reading them line by line, and treat any
difference there as a change the author must explain.

1. **The numbers.** What the package changes: health, damage, cooldowns, chances, rewards. A mod
   may change balance as it likes, but its description should say what it does, and nothing should
   be hidden in it that its description does not cover.
2. **The texts, in all twelve languages** (`en de fr es pt ru it pl tr ja zh ko`). Every name, text
   and yell a player reads. The game's check makes sure every language is there, not what it says:
   read them (with a translation tool where needed) for insults, hate, advertising, links, and
   texts that say something other than the English.
3. **What it asks of the game.** `profile.json`: the packages it locks and their versions, the
   `overrides` it declares (each one an entry of the game it changes), and `compatibility`,
   above all `required_capabilities` (`scripts-v1` for scripts, `authored-map-v1` for maps).
   `required_assets` and any object of the kinds `texture` or `audio` (files the package brings for
   the game to show or play).
4. **Scripts, as source.** A package with scripts (`"scripts": true` in its pin, `.lua` objects of
   kind `script`) runs code on the player's computer. Read every `.lua` file whole, not only the
   diff: what each hook does, that it returns commands the kit allows, and that nothing in it is
   built to stall the host (deep loops that end only by running out of fuel, tables filled with keys
   chosen to collide, very long strings). The sandbox limits a script, but its known limits
   (the script guide, <https://azreborn.com/guides/mod-scripts>, "Known limits") leave this to the
   review.
   Run `azs-script check` on the unpacked profile.
5. **Licence and rights.** The zip's `LICENSE` names a licence and says which files it covers, and
   the entry's `license` agrees. Every picture or sound the package ships is the author's own or
   one they may share, with its source named.
6. **No game files.** Nothing in the zip is a file of World of Warcraft or extracted from one:
   no archives, models, textures, sounds or DBC tables, under any name or extension
   ([LEGAL.md](LEGAL.md)). Naming the player's own client files by id or path is fine.

## The checklist

- [ ] The pin's pull request says the zip passed the pin script (no "Not pinned" line for it).
- [ ] The description says what the package does, and the diff does no more than that.
- [ ] Every text a player reads is fit to read, in every language.
- [ ] `overrides` and `required_capabilities` are what the package needs, and no more.
- [ ] Every script read whole; `azs-script check` passes.
- [ ] `LICENSE` is there and covers the author's own files; the author may share every file.
- [ ] No file of World of Warcraft, and nothing extracted from one.
- [ ] The game's packs in the profile are unchanged, or every change is explained.
- [ ] The namespace belongs to this author (a first entry), and the repository is the same as before
      (an update).

## When a version is blocked

A version is blocked (in its entry: `status = "blocked"` with a `reason` for the newest version, or
`blocked = [{ version, reason }]` for an older one) when it:

- breaks saves, or keeps players from playing (a crash, a profile that no longer starts);
- carries a file of World of Warcraft or anything extracted from one, or a file its author may not
  share;
- carries a script that is built to harm, to stall the host, or to do anything other than what the
  package says;
- misleads players: a description, name or text that hides what the package does, or impersonates
  another author or the game;
- holds texts with hate, harassment or advertising;
- its author asks for it to be withdrawn.

Blocking is not a punishment for a bug: an author who fixes one ships a new version, and the bad
version alone stays blocked: list its tag under `blocked`, keep `status = "active"`, and the fix's
new release is pinned as usual (a blocked package's pin does not move on). A blocked version stays
listed (the launcher must learn of the block); a launcher does not install it any more and turns a
chosen profile of it off at its first start after it has read a catalog that names the block
(opening **GET MORE** reads it), saves kept.
