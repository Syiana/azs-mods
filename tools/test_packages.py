#!/usr/bin/env python3
"""packages.py's tests: `python tools/test_packages.py`. No network: GitHub is the stand-in of
test_support.py, and the package zips are built here."""

import contextlib
import hashlib
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import packages  # noqa: E402
from test_support import Hub, Repo, file, raw_zip  # noqa: E402

HASH = "ab" * 32


def locked(package_id, version="1", kind="gameplay", paths=()):
    return {"id": package_id, "version": version, "kind": kind, "variant": None, "dependencies": [], "overrides": [],
            "required_assets": [], "objects": [{"path": p, "hash": HASH, "kind": "gameplay"} for p in paths]}


def profile(*packages_, name="frost"):
    return {"lock": {"name": name, "packages": list(packages_)},
            "compatibility": {"content_schema": 1, "simulation_abi": 1, "protocol_abi": 1, "required_capabilities": ["generated-ui-v1"]}}


def package_zip(*packages_, extra=(), drop=(), descriptor=None):
    """A release zip as an author ships it: profile.json and every locked object."""
    descriptor = descriptor or profile(*packages_)
    entries = [file("profile.json", json.dumps(descriptor).encode())]
    for package in descriptor["lock"]["packages"]:
        entries += [file(o["path"], b"key = 'x'\n", deflated=True) for o in package["objects"] if o["path"] not in drop]
    return raw_zip(entries + list(extra))


def frost_zip(version="1", **kw):
    return package_zip(locked("base", paths=["packs/base/pack.toml"]),
                       locked("author.frost", version, paths=["packs/author.frost/pack.toml", "packs/author.frost/archetype.toml"]), **kw)


PACKAGE = """\
id = "{id}"
kind = "mod"
name = "Frost Mage"
author = "someone"
repo = "someone/{id}"
description = "One line."
license = "MIT"
namespace = "{namespace}"
requires = {requires}

[source]
type = "release"
asset = "{id}-*.zip"
"""

ENTRY = {"id": "frost", "namespace": "author.frost", "requires": [], "status": "active", "reason": "", "mirrors": []}


class Packages(Repo):
    def __init__(self, case):
        super().__init__(case)
        (self.root / "packages").mkdir()

    def package(self, package_id, namespace, requires=(), **changes):
        text = PACKAGE.format(id=package_id, namespace=namespace, requires=json.dumps(list(requires)))
        for old, new in changes.items():
            text = text.replace(old, new)
        (self.root / "packages" / f"{package_id}.toml").write_text(text, encoding="utf-8")

    def catalog(self):
        return json.loads((self.root / "packages.json").read_text(encoding="utf-8"))


def quiet(function, *args, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return function(*args, **kw)


class ZipRules(unittest.TestCase):
    def test_a_package_zip_passes_and_says_what_its_profile_holds(self):
        summary = packages.check_package_zip(ENTRY, frost_zip())
        self.assertEqual(summary["name"], "frost")
        self.assertEqual([p["id"] for p in summary["packages"]], ["base", "author.frost"])
        self.assertEqual(summary["compatibility"]["required_capabilities"], ["generated-ui-v1"])
        # A LICENSE beside profile.json is allowed and never an object.
        packages.check_package_zip(ENTRY, frost_zip(extra=[file("LICENSE", b"MIT")]))

    def test_what_the_launcher_refuses_is_refused_here(self):
        cases = {
            "a program": frost_zip(extra=[file("packs/author.frost/run.exe")]),
            "symbolic link": frost_zip(extra=[file("packs/author.frost/link", mode=0o120777)]),
            "encrypted": frost_zip(extra=[file("packs/author.frost/x.toml", flags=1)]),
            "method 12": frost_zip(extra=[file("packs/author.frost/x.toml", method=12)]),
            "leaves its folder": frost_zip(extra=[file("packs/../evil.toml")]),
            "relative /-path": frost_zip(extra=[file("/etc/passwd")]),
            "twice": frost_zip(extra=[file("PACKS/base/pack.toml")]),
            "does not lock": frost_zip(extra=[file("packs/author.frost/stray.toml")]),
            "which profile.json locks": frost_zip(drop=["packs/author.frost/archetype.toml"]),
            "no profile.json": raw_zip([file("packs/author.frost/pack.toml")]),
            "no zip": b"not a zip",
            "does not unpack": frost_zip(extra=[file("packs/author.frost/lie.toml", b"x" * 100, deflated=True, announces=10)]),
        }
        for why, data in cases.items():
            with self.subTest(why), self.assertRaises(common.Refused) as caught:
                packages.check_package_zip(ENTRY, data)
            self.assertIn(why, str(caught.exception))

    def test_an_archive_bomb_meets_a_bound_before_it_is_unpacked(self):
        # Deflated zeros: a few kilobytes that announce (and unpack to) far more than the bound.
        bomb = frost_zip(extra=[file("packs/author.frost/zeros.toml", b"\0" * (1 << 20), deflated=True)])
        self.assertLess(len(bomb), 8 << 10)
        with self.assertRaises(common.Refused) as caught:
            packages.check_package_zip(ENTRY, bomb, max_bytes=1 << 19)
        self.assertIn("unpacks to more than", str(caught.exception))
        # One that lies about its size is stopped one byte past what it announces.
        liar = frost_zip(extra=[file("packs/author.frost/zeros.toml", b"\0" * (1 << 20), deflated=True, announces=16)])
        with self.assertRaises(common.Refused) as caught:
            packages.check_package_zip(ENTRY, liar)
        # Python's reader stops at the announced size and finds the checksum wrong; either way refused.
        self.assertRegex(str(caught.exception), "another size|does not unpack")
        many = frost_zip(extra=[file(f"packs/author.frost/{n}.toml") for n in range(40)])
        with self.assertRaises(common.Refused) as caught:
            packages.check_package_zip(ENTRY, many, max_files=20)
        self.assertIn("entries, more than 20", str(caught.exception))

    def test_a_profile_may_hold_only_its_own_the_games_and_what_it_requires(self):
        takeover = package_zip(locked("base", paths=["packs/base/pack.toml"]), locked("other.author", paths=["packs/other.author/pack.toml"]))
        with self.assertRaises(common.Refused) as caught:
            packages.check_package_zip(ENTRY, takeover)
        self.assertIn("other.author lies in no namespace", str(caught.exception))
        reserved = package_zip(locked("author.frost", paths=["packs/author.frost/pack.toml"]), locked("azs.generated-ui", paths=["presentation/x.lua"]))
        with self.assertRaises(common.Refused) as caught:
            packages.check_package_zip(ENTRY, reserved)
        self.assertIn("reserved for the game", str(caught.exception))
        foreign_only = package_zip(locked("base", paths=["packs/base/pack.toml"]))
        with self.assertRaises(common.Refused) as caught:
            packages.check_package_zip(ENTRY, foreign_only)
        self.assertIn("no package in its namespace", str(caught.exception))

    def test_a_required_package_must_be_a_version_its_owner_pins(self):
        lib = {"id": "frost-lib", "namespace": "author.frostlib",
               "profile": {"packages": [{"id": "author.frostlib", "version": "2", "kind": "gameplay"}]}}
        uses = lambda version: package_zip(  # noqa: E731
            locked("author.frostlib", version, paths=["packs/author.frostlib/pack.toml"]), locked("author.frost", paths=["packs/author.frost/pack.toml"]))
        summary = packages.check_package_zip(ENTRY, uses("2"), [lib])
        self.assertEqual(summary["packages"][0], {"id": "author.frostlib", "version": "2", "kind": "gameplay"})
        with self.assertRaises(common.Refused) as caught:
            packages.check_package_zip(ENTRY, uses("1"), [lib])
        self.assertIn("author.frostlib 1 conflicts with 2 that frost-lib pins", str(caught.exception))
        with self.assertRaises(common.Refused) as caught:
            packages.check_package_zip(ENTRY, uses("2"))
        self.assertIn("lies in no namespace this package owns or requires", str(caught.exception))

    def test_object_paths_follow_the_games_content_path_rules(self):
        for path in ["packs/a b.toml", "packs/x./y.toml", "packs/con.toml", ".azs/x", "a/" * 13 + "x"]:
            with self.subTest(path), self.assertRaises(common.Refused):
                packages.check_object_path(path)
        packages.check_object_path("packs/author.frost/classes/mage/spells.toml")


class MapPackages(unittest.TestCase):
    MAP = {"id": "castle-keep", "kind": "map", "namespace": "author.castle", "requires": [], "status": "active", "reason": "", "mirrors": []}

    def map_zip(self, *extra_packages, capabilities=("authored-map-v1",), objects=None):
        package = locked("author.castle", "2")
        package["objects"] = objects or [
            {"path": "maps/author.castle/castle_keep.toml", "hash": HASH, "kind": "map"},
            {"path": "maps/author.castle/castle_keep.json", "hash": HASH, "kind": "map"},
        ]
        descriptor = profile(*extra_packages, package)
        descriptor["compatibility"]["required_capabilities"] = list(capabilities)
        return package_zip(descriptor=descriptor)

    def test_a_map_package_holds_one_package_of_maps(self):
        summary = packages.check_package_zip(self.MAP, self.map_zip())
        self.assertEqual(summary["packages"], [{"id": "author.castle", "version": "2", "kind": "gameplay"}])
        cases = {
            "exactly one package, its own": self.map_zip(locked("base", paths=["packs/base/pack.toml"])),
            "requires the authored-map-v1 capability": self.map_zip(capabilities=()),
            "only maps and their manifests": self.map_zip(objects=[{"path": "packs/author.castle/pack.toml", "hash": HASH, "kind": "gameplay"}]),
        }
        for why, data in cases.items():
            with self.subTest(why), self.assertRaises(common.Refused) as caught:
                packages.check_package_zip(self.MAP, data)
            self.assertIn(why, str(caught.exception))
        # The same zip as a mod is fine: the rule is the map kind's.
        packages.check_package_zip(dict(self.MAP, kind="mod"), self.map_zip(locked("base", paths=["packs/base/pack.toml"])))


class Entries(unittest.TestCase):
    def test_entries_must_hold_together(self):
        repo = Packages(self)
        repo.package("frost", "author.frost")
        repo.package("frost-plus", "author.frost.plus")
        with self.assertRaises(common.Refused) as caught:
            packages.load_entries(repo.root)
        self.assertIn("overlaps author.frost", str(caught.exception))
        (repo.root / "packages" / "frost-plus.toml").unlink()
        repo.package("needs", "author.needs", requires=["absent"])
        with self.assertRaises(common.Refused) as caught:
            packages.load_entries(repo.root)
        self.assertIn("requires absent", str(caught.exception))
        repo.package("needs", "author.needs", requires=["frost"])
        repo.package("frost", "author.frost", requires=["needs"])
        with self.assertRaises(common.Refused) as caught:
            packages.load_entries(repo.root)
        self.assertIn("requires itself", str(caught.exception))

    def test_an_entry_that_breaks_a_rule_is_refused(self):
        cases = {
            'kind = "mod"': ('kind = "addon"', "not mod or map"),
            'namespace = "author.frost"': ('namespace = "azs.frost"', "not author.name"),
            'license = "MIT"': ('license = "MIT"\nstatus = "blocked"', "says why"),
            'requires = []': ('requires = []\nmirrors = ["http://plain.example/"]', "https://"),
        }
        for old, (new, why) in cases.items():
            repo = Packages(self)
            repo.package("frost", "author.frost", **{old: new})
            with self.subTest(why), self.assertRaises(common.Refused) as caught:
                packages.load_entries(repo.root)
            self.assertIn(why, str(caught.exception))


class Pinning(unittest.TestCase):
    def setUp(self):
        self.repo, self.hub = Packages(self), Hub()

    def pin(self, offline=False):
        return quiet(packages.pin, self.repo.root, self.hub.api, self.hub.fetch, offline)

    def test_the_newest_release_is_pinned_with_its_profile(self):
        self.repo.package("frost", "author.frost")
        data = frost_zip()
        self.hub.release("someone/frost", "v1", {"frost-1.zip": data})
        self.assertEqual(self.pin(), {})
        row = self.repo.catalog()["packages"][0]
        self.assertEqual((row["version"], row["size"], row["sha256"]), ("v1", len(data), hashlib.sha256(data).hexdigest()))
        self.assertEqual(row["profile"]["packages"][1]["id"], "author.frost")
        self.assertEqual((row["status"], self.repo.catalog()["serial"]), ("active", 1))
        self.assertEqual(self.pin(), {})
        self.assertEqual(self.repo.catalog()["serial"], 1, "nothing new: the serial stays")
        self.assertEqual(packages.check(self.repo.root), [])

    def test_a_replaced_asset_under_the_same_tag_is_reported_and_never_repinned(self):
        self.repo.package("frost", "author.frost")
        self.hub.release("someone/frost", "v1", {"frost-1.zip": frost_zip()})
        self.pin()
        pinned = self.repo.catalog()["packages"][0]["sha256"]
        url = self.repo.catalog()["packages"][0]["asset_url"]
        self.hub.files[url] = frost_zip(version="9")
        self.assertEqual(self.pin(), {})
        self.assertEqual(self.repo.catalog()["packages"][0]["sha256"], pinned, "the same tag keeps its pin")
        problems = packages.check(self.repo.root, self.hub.fetch)
        self.assertTrue(any("source_changed" in p for p in problems), problems)

    def lib_and_mod(self):
        self.repo.package("frost-lib", "author.frostlib")
        self.repo.package("frost", "author.frost", requires=["frost-lib"])
        lib = lambda v: package_zip(locked("author.frostlib", v, paths=["packs/author.frostlib/pack.toml"]))  # noqa: E731
        mod = lambda v: package_zip(locked("author.frostlib", v, paths=["packs/author.frostlib/pack.toml"]),  # noqa: E731
                                    locked("author.frost", paths=["packs/author.frost/pack.toml"]))
        return lib, mod

    def test_a_library_moves_on_and_the_packages_that_ship_it_keep_their_versions(self):
        lib, mod = self.lib_and_mod()
        self.hub.release("someone/frost-lib", "v1", {"frost-lib-1.zip": lib("1")})
        self.hub.release("someone/frost", "v1", {"frost-1.zip": mod("1")})
        self.assertEqual(self.pin(), {})
        self.assertEqual([(r["id"], r["version"]) for r in self.repo.catalog()["packages"]], [("frost-lib", "v1"), ("frost", "v1")])
        # The library moves on: its v1 stays kept, so the mod that ships it stays valid.
        self.hub.release("someone/frost-lib", "v2", {"frost-lib-2.zip": lib("2")})
        self.assertEqual(self.pin(), {})
        rows = self.repo.catalog()["packages"]
        self.assertEqual([(r["id"], r["version"]) for r in rows], [("frost-lib", "v1"), ("frost-lib", "v2"), ("frost", "v1")])
        packages.check_rows(rows)
        self.assertEqual(packages.check(self.repo.root), [])
        # A mod release that ships a library version no version pins is refused; the mod keeps v1.
        self.hub.release("someone/frost", "v2", {"frost-2.zip": mod("3")})
        failed = self.pin()
        self.assertIn("author.frostlib 3 conflicts with 1, 2 that frost-lib pins", failed["frost"])
        # One built on the new library is pinned beside it.
        self.hub.release("someone/frost", "v3", {"frost-3.zip": mod("2")})
        self.assertEqual(self.pin(), {})
        rows = self.repo.catalog()["packages"]
        self.assertEqual([(r["id"], r["version"]) for r in rows if r["id"] == "frost"], [("frost", "v1"), ("frost", "v3")])
        self.assertEqual(packages.check(self.repo.root), [])

    def test_the_rows_hold_the_launchers_rules(self):
        lib, mod = self.lib_and_mod()
        self.hub.release("someone/frost-lib", "v1", {"frost-lib-1.zip": lib("1")})
        self.hub.release("someone/frost", "v1", {"frost-1.zip": mod("1")})
        self.pin()
        rows = self.repo.catalog()["packages"]
        # What the signing tool refuses is refused here: a dependency no version of its owner pins,
        # a version twice, a version that moves the package's namespace, too many versions.
        orphan = [dict(rows[0], profile=dict(rows[0]["profile"], packages=[{"id": "author.frostlib", "version": "9", "kind": "gameplay"}])), rows[1]]
        twice = [rows[0], rows[0], rows[1]]
        moved = [rows[0], dict(rows[0], version="v2", namespace="author.frostlib2"), rows[1]]
        many = [dict(rows[0], version=f"v{n}") for n in range(packages.MAX_VERSIONS + 1)]
        cases = {"conflicts with what every version of frost-lib pins": orphan, "lists frost-lib v1 twice": twice,
                 "keeps the package's kind, namespace and repository": moved, "more than 16 versions": many}
        for why, broken in cases.items():
            with self.subTest(why), self.assertRaises(common.Refused) as caught:
                packages.check_rows(broken)
            self.assertIn(why, str(caught.exception))

    def test_an_older_version_is_blocked_after_a_newer_one_is_pinned(self):
        self.repo.package("frost", "author.frost")
        self.hub.release("someone/frost", "v1", {"frost-1.zip": frost_zip()})
        self.pin()
        self.hub.release("someone/frost", "v2", {"frost-2.zip": frost_zip(version="2")})
        self.pin()
        self.repo.package("frost", "author.frost", **{'license = "MIT"': 'license = "MIT"\nblocked = [{ version = "v1", reason = "Breaks saves." }]'})
        self.assertEqual(self.pin(), {})
        rows = self.repo.catalog()["packages"]
        self.assertEqual([(r["version"], r["status"], r["reason"]) for r in rows], [("v1", "blocked", "Breaks saves."), ("v2", "active", "")])
        self.assertEqual(packages.check(self.repo.root), [])
        self.repo.package("frost", "author.frost", **{'license = "MIT"': 'license = "MIT"\nblocked = [{ version = "v0", reason = "No." }]'})
        self.assertIn("no pinned version", self.pin()["frost"])

    def test_a_package_keeps_at_most_its_newest_versions_and_every_blocked_one(self):
        self.addCleanup(setattr, packages, "MAX_VERSIONS", packages.MAX_VERSIONS)
        packages.MAX_VERSIONS = 2
        self.repo.package("frost", "author.frost")
        for n in (1, 2):
            self.hub.release("someone/frost", f"v{n}", {f"frost-{n}.zip": frost_zip(version=str(n))})
            self.pin()
        self.repo.package("frost", "author.frost", **{'license = "MIT"': 'license = "MIT"\nblocked = [{ version = "v1", reason = "Breaks saves." }]'})
        self.hub.release("someone/frost", "v3", {"frost-3.zip": frost_zip(version="3")})
        self.assertEqual(self.pin(), {})
        self.assertEqual([r["version"] for r in self.repo.catalog()["packages"]], ["v1", "v3"], "the blocked v1 stays, v2 goes")

    def test_a_replaced_release_asset_falls_back_to_a_mirror_by_hash(self):
        self.repo.package("frost", "author.frost", **{'requires = []': 'requires = []\nmirrors = ["https://mirror.example.org/packages/"]'})
        data = frost_zip()
        self.hub.release("someone/frost", "v1", {"frost-1.zip": data})
        self.pin()
        row = self.repo.catalog()["packages"][0]
        self.hub.files[f"https://mirror.example.org/packages/{row['sha256']}.zip"] = data
        self.hub.files[row["asset_url"]] = frost_zip(version="9")
        problems = packages.check(self.repo.root, self.hub.fetch)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("source_changed", problems[0])
        self.assertIn("mirror.example.org", problems[0])
        del self.hub.files[f"https://mirror.example.org/packages/{row['sha256']}.zip"]
        problems = packages.check(self.repo.root, self.hub.fetch)
        self.assertIn("no source serves the pinned zip", problems[0])

    def test_a_blocked_package_keeps_its_pin_and_says_why(self):
        self.repo.package("frost", "author.frost")
        self.hub.release("someone/frost", "v1", {"frost-1.zip": frost_zip()})
        self.pin()
        self.repo.package("frost", "author.frost", **{'license = "MIT"': 'license = "MIT"\nstatus = "blocked"\nreason = "Breaks saves."'})
        self.hub.release("someone/frost", "v2", {"frost-2.zip": frost_zip(version="2")})
        self.assertEqual(self.pin(), {})
        self.assertEqual(len(self.repo.catalog()["packages"]), 1, "a blocked package is not moved on")
        row = self.repo.catalog()["packages"][0]
        self.assertEqual((row["status"], row["reason"], row["version"]), ("blocked", "Breaks saves.", "v1"))
        self.assertEqual(self.repo.catalog()["serial"], 2)
        self.repo.package("new", "author.new", **{'license = "MIT"': 'license = "MIT"\nstatus = "blocked"\nreason = "No."'})
        self.assertIn("nothing to block", self.pin()["new"])

    def test_the_catalog_is_packages_json_and_no_addon_index(self):
        # Older launchers install every row of an addon index into Interface/AddOns: this repository writes none.
        self.repo.package("frost", "author.frost")
        self.hub.release("someone/frost", "v1", {"frost-1.zip": frost_zip()})
        self.pin()
        self.assertTrue((self.repo.root / "packages.json").exists())
        self.assertFalse((self.repo.root / "index.json").exists())
        self.assertEqual(packages.check(self.repo.root), [])

    def test_the_command_line_says_whether_all_is_in_order(self):
        self.repo.package("frost", "author.frost")
        self.hub.release("someone/frost", "v1", {"frost-1.zip": frost_zip()})
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(packages.main(["--root", str(self.repo.root), "pin"], self.hub.api, self.hub.fetch), 0)
            self.assertEqual(packages.main(["--root", str(self.repo.root), "check", "--assets"], self.hub.api, self.hub.fetch), 0)
            (self.repo.root / "packages" / "frost.toml").write_text("id = 1\n", encoding="utf-8")
            self.assertEqual(packages.main(["--root", str(self.repo.root), "check"], self.hub.api, self.hub.fetch), 1)


class Seed(unittest.TestCase):
    def test_this_repositorys_package_entries_are_in_order(self):
        self.assertEqual(packages.check(Path(__file__).resolve().parent.parent), [])


if __name__ == "__main__":
    unittest.main()
