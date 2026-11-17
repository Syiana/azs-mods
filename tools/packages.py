#!/usr/bin/env python3
"""The package catalog's pin bot: declarative mods and maps. Standard library only.

    packages.py check             every packages/<id>.toml is well-formed and packages.json is what they generate
    packages.py check --assets    also fetch every pinned zip: still the pinned bytes, still within the rules
    packages.py pin               pin each package's newest release beside its kept ones; packages.json changes only when a pin does
    packages.py pin --offline     bring packages.json up to the entries without the network

A package is a locked content profile in a release zip: the game's `profile.json` and the sources it
locks, nothing else. It never holds a program and nothing in it is run here: the game's own
validator (`--import-profile`) checks it on the player's machine. A pin is what this script adds to
an entry: the newest release's tag, its zip's address, size and SHA-256, and what the zip's
`profile.json` says (its packages, their versions, its compatibility). packages.json keeps every
pinned version of a package (at most MAX_VERSIONS), oldest first: the newest is the one offered, an
older one can still be blocked (`blocked = [{ version, reason }]` in the entry), and a package that
ships another's sources may ship any version of them the other keeps. The launcher's
`azs-update/src/packages.rs` (`Catalog::parse`) holds the same rules: a set this script writes is
one the signing tool accepts.

Python has no BLAKE3, the game's object hash: the maintainers' `azs-release packages-sign` reads the
merged packages.json and the pinned zips, checks every object against its locked hash, binds the
profile's lock digest and signs the catalog the launcher installs from. A signature there is
distribution approval only: an installed package always plays as Modded.

packages.json lives in this repository and never in the addon index's: older launchers install every
row of an addon index as a Lua addon, so a package must never appear there.
"""

import argparse
import hashlib
import io
import json
import re
import sys
import tomllib
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402  (the addon index's rules are the packages' too)
    ASSET_LIMIT,
    PROGRAMS,
    Refused,
    ascii_lower,
    check_path,
    check_text,
    entry_name,
    http_api,
    http_fetch,
    is_control,
    is_id,
    need,
    newest_release,
)

SCHEMA = 1
KINDS = ("mod", "map")
STATUSES = ("active", "deprecated", "blocked")
# The launcher's bounds on unpacking a package zip (azs-update/src/packages.rs, the same numbers).
MAX_FILES, MAX_BYTES, MAX_DEPTH, MAX_PATH = 5000, 256 << 20, 12, 240
# profile.json, as the game bounds a manifest.
PROFILE_LIMIT = 8 << 20
MAX_PACKAGES, MAX_CAPABILITIES, MAX_MIRRORS = 128, 256, 4
# packages.json: all versions together, and the versions of one package (packages.rs, the same).
MAX_ROWS, MAX_VERSIONS = 1024, 16
OBJECT_KINDS = ("gameplay", "mode", "collision", "navigation", "asset", "texture", "audio", "release_notes", "generated_ui", "generation_manifest", "map")
# A map package (kind = "map", survivors-content `mappackage`): one package of Map Builder maps
# and their manifests only, which the game plays beside its content.
MAP_CAPABILITY = "authored-map-v1"
# Files a zip may hold beside the locked objects; the launcher does not install them.
EXTRA_FILES = ("profile.json", "LICENSE")

ENTRY_KEYS = {"id", "kind", "name", "author", "repo", "description", "license", "namespace", "requires", "status", "reason", "mirrors", "blocked", "source"}
TEXTS = {"name": 80, "author": 80, "description": 400, "license": 40, "reason": 400, "version": 40}


# --- names --------------------------------------------------------------------------------------


def is_namespace(text):
    """A package namespace: `author.name`, lower-case parts of letters, digits, `_` and `-`. The
    game reserves `azs.` and the unqualified names of its own packs."""
    return (
        isinstance(text, str)
        and len(text) <= 64
        and re.fullmatch(r"[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+", text) is not None
        and not text.startswith("azs.")
    )


def owns(namespace, package_id):
    """Whether `package_id` lies in `namespace`: the namespace itself or below it."""
    return package_id == namespace or package_id.startswith(namespace + ".")


def check_object_path(path):
    """A locked object's path as the game takes one (survivors-content `check_object_path`):
    relative, `/`-separated parts of letters, digits, `.`, `_` and `-`, none ending in `.`, no
    reserved name, at most 240 bytes and the launcher's depth."""
    need(isinstance(path, str) and 0 < len(path.encode("utf-8")) <= MAX_PATH, f"{path!r} is too long for a content path")
    check_path(path)
    parts = path.split("/")
    need(len(parts) <= MAX_DEPTH, f"{path} lies more than {MAX_DEPTH} folders deep")
    for part in parts:
        need(re.fullmatch(r"[A-Za-z0-9._-]+", part) is not None and not part.endswith("."), f"{path!r} is not a normalized content path")


# --- entries ------------------------------------------------------------------------------------


def check_fields(package):
    """What a person writes of a package: the fields an entry and a packages.json row share."""
    need(is_id(package.get("id")), f"id {package.get('id')!r} is not lower-case letters, digits and -")
    need(package.get("kind") in KINDS, f"kind {package.get('kind')!r} is not mod or map")
    for field, limit in TEXTS.items():
        if field != "version":
            check_text(field, package.get(field), limit)
    need(package["name"].strip() and package["author"].strip(), "name and author must not be empty")
    repo = package.get("repo")
    plain = r"(?!\.{1,2}$)[A-Za-z0-9_.-]+"
    need(isinstance(repo, str) and re.fullmatch(f"{plain}/{plain}", repo) is not None, f"repo {repo!r} is not owner/name")
    need(is_namespace(package.get("namespace")), f"namespace {package.get('namespace')!r} is not author.name (and not azs.)")
    requires = package.get("requires")
    need(isinstance(requires, list) and all(is_id(r) for r in requires), "requires is not a list of ids")
    need(package.get("status") in STATUSES, f"status {package.get('status')!r} is not active, deprecated or blocked")
    need(package["status"] == "active" or package["reason"].strip(), "a deprecated or blocked package says why (reason)")
    mirrors = package.get("mirrors")
    need(isinstance(mirrors, list) and len(mirrors) <= MAX_MIRRORS, f"mirrors is not a list of at most {MAX_MIRRORS}")
    for mirror in mirrors:
        # A mirror serves exact bytes by their SHA-256: <mirror><sha256>.zip, checked like GitHub's.
        need(
            isinstance(mirror, str) and len(mirror) <= 200 and re.fullmatch(r"https://[A-Za-z0-9.-]+(?::[0-9]+)?/[A-Za-z0-9._~/-]*/", mirror) is not None,
            f"mirror {mirror!r} is not an https:// folder address ending in /",
        )


def load_entry(path):
    """One packages/<id>.toml, checked."""
    try:
        entry = tomllib.loads(path.read_text(encoding="utf-8"))
        need(set(entry) <= ENTRY_KEYS, f"unknown key {', '.join(sorted(set(entry) - ENTRY_KEYS))}")
        for key in ("description", "license", "reason"):
            entry.setdefault(key, "")
        entry.setdefault("requires", [])
        entry.setdefault("mirrors", [])
        entry.setdefault("status", "active")
        entry.setdefault("blocked", [])
        check_fields(entry)
        blocked = entry["blocked"]
        need(isinstance(blocked, list) and len(blocked) <= MAX_VERSIONS, f"blocked is not a list of at most {MAX_VERSIONS}")
        for item in blocked:
            need(isinstance(item, dict) and set(item) == {"version", "reason"}, "a blocked item is not { version, reason }")
            check_text("blocked version", item["version"], TEXTS["version"])
            check_text("blocked reason", item["reason"], TEXTS["reason"])
            need(item["version"].strip() and item["reason"].strip(), "a blocked version says which and why")
        need(len({item["version"] for item in blocked}) == len(blocked), "blocked lists a version twice")
        need(path.name == f"{entry['id']}.toml", f"its file is not named {entry['id']}.toml")
        source = entry.get("source")
        need(isinstance(source, dict) and set(source) == {"type", "asset"}, "source is not { type, asset }")
        need(source["type"] == "release", "source.type is not release")
        asset = source["asset"]
        need(
            isinstance(asset, str)
            and re.fullmatch(r"[A-Za-z0-9_.+*-]+", asset) is not None
            and asset.count("*") <= 1
            and ascii_lower(asset).endswith(".zip"),
            f"source.asset {asset!r} is not a .zip file name with at most one * for the version",
        )
        return entry
    except (Refused, tomllib.TOMLDecodeError, UnicodeError) as e:
        raise Refused(f"{path.name}: {e}") from None


def check_set(packages):
    """What entries must hold together: an id and a namespace belong to one package, no namespace
    lies inside another's (that would take its packages over), and what a package requires is
    another package of the set, without a circle."""
    ids = set()
    for package in packages:
        need(package["id"] not in ids, f"{package['id']} is listed twice")
        ids.add(package["id"])
    check_relations(packages)


def check_relations(packages):
    """The rules entries and packages.json rows share, over packages that may list one id several
    times (its versions): namespaces apart, requires inside the set, no circle."""
    first = {}
    for package in packages:
        if package["id"] in first:
            continue
        for other in first.values():
            need(
                not owns(other["namespace"], package["namespace"]) and not owns(package["namespace"], other["namespace"]),
                f"{package['id']}: namespace {package['namespace']} overlaps {other['namespace']} of {other['id']}",
            )
        first[package["id"]] = package
    requires = {}
    for package in packages:
        for required in package["requires"]:
            need(required in first and required != package["id"], f"{package['id']} requires {required}, which is not another package here")
        requires.setdefault(package["id"], []).extend(package["requires"])

    def visit(package_id, path):
        need(package_id not in path, f"{package_id} requires itself through {', '.join(path)}")
        for required in requires[package_id]:
            visit(required, path + [package_id])

    for package_id in first:
        visit(package_id, [])


def check_rows(rows):
    """packages.json's rows together, as the launcher parses them (packages.rs `Catalog::parse`): each
    version once, at most MAX_VERSIONS of a package and MAX_ROWS in all, every version keeps the
    package's kind, namespace and repository, and a foreign package in a profile is exactly what
    some version of a required package pins."""
    need(len(rows) <= MAX_ROWS, f"packages.json lists more than {MAX_ROWS} versions")
    by_id = {}
    for row in rows:
        versions = by_id.setdefault(row["id"], [])
        need(all(r["version"] != row["version"] for r in versions), f"packages.json lists {row['id']} {row['version']} twice")
        if versions:
            need(
                (versions[0]["kind"], versions[0]["namespace"], versions[0]["repo"]) == (row["kind"], row["namespace"], row["repo"]),
                f"{row['id']} {row['version']}: every version keeps the package's kind, namespace and repository",
            )
        versions.append(row)
        need(len(versions) <= MAX_VERSIONS, f"packages.json keeps more than {MAX_VERSIONS} versions of {row['id']}")
    check_relations(rows)
    for row in rows:
        for pinned in row["profile"]["packages"]:
            if "." not in pinned["id"] or owns(row["namespace"], pinned["id"]):
                continue
            owner = next((r for r in row["requires"] if owns(by_id[r][0]["namespace"], pinned["id"])), None)
            need(owner is not None, f"{row['id']} {row['version']}: {pinned['id']} lies in no namespace it owns or requires")
            need(
                any(pinned in version["profile"]["packages"] for version in by_id[owner]),
                f"{row['id']} {row['version']}: {pinned['id']} {pinned['version']} conflicts with what every version of {owner} pins",
            )


def load_entries(root):
    folder = root / "packages"
    entries = [load_entry(path) for path in sorted(folder.glob("*.toml"))] if folder.is_dir() else []
    check_set(entries)
    return entries


# --- a package zip ------------------------------------------------------------------------------


def check_profile(text, namespace, required_rows, package_kind="mod"):
    """profile.json of a package of `namespace`: a locked profile whose every package is the game's
    own (an unqualified name), the package's own (inside its namespace) or exactly what a required
    package pins (same id, version and kind). Returns the summary a pin keeps and the object paths
    the zip must hold."""
    try:
        profile = json.loads(text)
    except (json.JSONDecodeError, UnicodeError) as e:
        raise Refused(f"profile.json is not JSON: {e}") from None
    need(isinstance(profile, dict) and set(profile) == {"lock", "compatibility"}, "profile.json is not { lock, compatibility }")
    lock, compatibility = profile["lock"], profile["compatibility"]
    need(isinstance(lock, dict) and isinstance(lock.get("name"), str) and isinstance(lock.get("packages"), list), "profile.json has no lock { name, packages }")
    check_text("lock.name", lock["name"], 80)
    need(0 < len(lock["packages"]) <= MAX_PACKAGES, f"the lock holds no package or more than {MAX_PACKAGES}")
    need(
        isinstance(compatibility, dict)
        and set(compatibility) == {"content_schema", "simulation_abi", "protocol_abi", "required_capabilities"}
        and all(type(compatibility[k]) is int and 0 <= compatibility[k] < 1 << 32 for k in ("content_schema", "simulation_abi", "protocol_abi")),
        "compatibility is not { content_schema, simulation_abi, protocol_abi, required_capabilities }",
    )
    capabilities = compatibility["required_capabilities"]
    need(
        isinstance(capabilities, list) and len(capabilities) <= MAX_CAPABILITIES
        and all(isinstance(c, str) and re.fullmatch(r"[a-z0-9][a-z0-9._:-]{0,127}", c) for c in capabilities),
        "required_capabilities is not a short list of capability names",
    )
    # What the required packages pin of their own, over every version they keep.
    provided = {}
    for row in required_rows:
        for pinned in row["profile"]["packages"]:
            if owns(row["namespace"], pinned["id"]):
                provided.setdefault(pinned["id"], []).append((row["id"], pinned))
    summary, paths, own = [], set(), False
    for package in lock["packages"]:
        need(isinstance(package, dict), "a locked package is no object")
        package_id, version, kind = package.get("id"), package.get("version"), package.get("kind")
        need(isinstance(package_id, str) and re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", package_id), f"package id {package_id!r} is not a package name")
        need(isinstance(version, str) and 0 < len(version) <= 40 and not any(is_control(c) for c in version), f"{package_id}: version {version!r} is not a version")
        need(kind in ("gameplay", "presentation"), f"{package_id}: kind {kind!r} is not gameplay or presentation")
        need(not package_id.startswith("azs."), f"{package_id} is reserved for the game")
        if owns(namespace, package_id):
            own = True
        elif "." in package_id:
            # Another author's package: only as some version of a required package pins it.
            need(package_id in provided, f"{package_id} lies in no namespace this package owns or requires")
            pins = provided[package_id]
            need(
                any((pinned["version"], pinned["kind"]) == (version, kind) for _, pinned in pins),
                f"{package_id} {version} conflicts with {', '.join(sorted({p['version'] for _, p in pins}))} that {pins[0][0]} pins",
            )
        objects = package.get("objects")
        need(isinstance(objects, list), f"{package_id} lists no objects")
        for item in objects:
            need(isinstance(item, dict) and set(item) == {"path", "hash", "kind"}, f"{package_id}: an object is not {{ path, hash, kind }}")
            check_object_path(item["path"])
            need(isinstance(item["hash"], str) and re.fullmatch(r"[0-9a-f]{64}", item["hash"]), f"{item['path']}: hash is not 64 lower-case hex digits")
            need(item["kind"] in OBJECT_KINDS, f"{item['path']}: kind {item['kind']!r} is not one the game knows")
            need(item["path"] not in EXTRA_FILES, f"{item['path']} is reserved beside the objects")
            need(ascii_lower(item["path"]) not in {ascii_lower(p) for p in paths}, f"{item['path']} is locked twice")
            paths.add(item["path"])
        summary.append({"id": package_id, "version": version, "kind": kind})
    need(own, f"the profile holds no package in its namespace {namespace}")
    if package_kind == "map":
        # The launcher's `mappackage::check_package_lock`: one package of maps, nothing else.
        need(len(lock["packages"]) == 1 and owns(namespace, lock["packages"][0]["id"]),
             "a map package locks exactly one package, its own")
        package = lock["packages"][0]
        need(all(o["kind"] == "map" and o["path"].startswith(f"maps/{package['id']}/") for o in package["objects"]),
             "a map package holds only maps and their manifests, under maps/<package>/")
        need(not package["dependencies"] and not package["overrides"] and not package["required_assets"],
             "a map package has no edges to other packages")
        need(MAP_CAPABILITY in capabilities, f"a map package requires the {MAP_CAPABILITY} capability")
    return {"name": lock["name"], "packages": summary, "compatibility": compatibility}, paths


def check_package_zip(entry, data, required_rows=(), max_files=MAX_FILES, max_bytes=MAX_BYTES):
    """The launcher's rules for a package's release zip, `data`: `profile.json` at the top, beside
    it at most a LICENSE, and exactly the objects the profile locks, by safe content paths. Each
    file is named once, is a plain file (no link, no encryption, no program) stored or deflated,
    unpacks to the size it announces, and all stay within the bounds (an archive bomb meets one of
    them before it is unpacked further). Returns the profile summary the pin keeps."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, ValueError, NotImplementedError) as e:
        raise Refused(f"it is no zip: {e}") from None
    infos = archive.infolist()
    need(len(infos) <= max_files, f"it holds {len(infos)} entries, more than {max_files}")
    names = [info.orig_filename for info in infos]
    need(len(set(names)) == len(names), "it lists a name twice")
    files, seen, total, profile = set(), set(), 0, None
    for info in infos:
        name = entry_name(info)
        is_dir = name.endswith(("/", "\\"))
        path = name[:-1] if name.endswith("/") else name
        check_path(path)
        need(not any(is_control(c) or c in '<>"|?*' for c in path), f"{name!r} holds a character Windows takes in no file name")
        need(len(path.split("/")) <= MAX_DEPTH, f"{name} lies more than {MAX_DEPTH} folders deep")
        mode = info.external_attr >> 16 if info.create_system == 3 else 0
        need(mode & 0o120000 != 0o120000, f"{name} is a symbolic link")
        if is_dir:
            continue
        need(not info.flag_bits & 1, f"{name} is encrypted")
        need(info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), f"{name} is packed with method {info.compress_type}, not stored or deflated")
        extension = ascii_lower(path.rsplit(".", 1)[1]) if "." in path else ""
        need(extension not in PROGRAMS, f"{name} is a program")
        need(ascii_lower(path) not in seen, f"it lists {name} twice")
        seen.add(ascii_lower(path))
        total += info.file_size
        need(total <= max_bytes, f"it unpacks to more than {max_bytes} bytes")
        need(path != "profile.json" or info.file_size <= PROFILE_LIMIT, f"profile.json is larger than {PROFILE_LIMIT} bytes")
        try:
            with archive.open(info) as member:
                content = member.read(info.file_size + 1)
        except (zipfile.BadZipFile, OSError, EOFError, ValueError, NotImplementedError, RuntimeError) as e:
            raise Refused(f"{name} does not unpack: {e}") from None
        need(len(content) == info.file_size, f"{name} unpacks to another size than the {info.file_size} bytes it announces")
        if path == "profile.json":
            profile = content
        files.add(path)
    need(profile is not None, "it has no profile.json at its top")
    summary, locked = check_profile(profile, entry["namespace"], required_rows, entry.get("kind", "mod"))
    extra = sorted(files - locked - set(EXTRA_FILES))
    need(not extra, f"it holds {extra[:1]}, which profile.json does not lock")
    missing = sorted(locked - files)
    need(not missing, f"it lacks {missing[:1]}, which profile.json locks")
    return summary


# --- packages.json ------------------------------------------------------------------------------


def package_row(entry, pin, newest=True):
    """A packages.json row: the entry's fields and a pin's. The entry's status is the newest
    version's; an older version is blocked when the entry's `blocked` names it, else active. What a
    version requires stays as it was pinned."""
    status, reason = entry["status"], entry["reason"]
    if not newest:
        blocked = {item["version"]: item["reason"] for item in entry["blocked"]}
        status, reason = ("blocked", blocked[pin["version"]]) if pin["version"] in blocked else ("active", "")
    return {
        "id": entry["id"],
        "kind": entry["kind"],
        "name": entry["name"],
        "author": entry["author"],
        "repo": entry["repo"],
        "description": entry["description"],
        "license": entry["license"],
        "namespace": entry["namespace"],
        "requires": list(pin.get("requires", entry["requires"])),
        "status": status,
        "reason": reason,
        "mirrors": list(entry["mirrors"]),
        "version": pin["version"],
        "asset_url": pin["asset_url"],
        "size": pin["size"],
        "sha256": pin["sha256"],
        "profile": pin["profile"],
    }


def check_pin(row):
    """What this script adds to a row: the pinned release and what its profile says."""
    check_text("version", row.get("version"), TEXTS["version"])
    need(row["version"].strip(), "version must not be empty")
    url, releases = row.get("asset_url"), f"https://github.com/{row['repo']}/releases/download/"
    need(isinstance(url, str) and url.startswith(releases), f"asset_url is not under {releases}")
    parts = url[len(releases):].split("/")
    need(
        len(parts) >= 2 and ascii_lower(parts[-1]).endswith(".zip")
        and all(re.fullmatch(r"(?!\.{1,2}$)[A-Za-z0-9_.+~%-]+", part) for part in parts),
        f"asset_url {url} is not <tag>/<file>.zip under the repository's releases",
    )
    size = row.get("size")
    need(isinstance(size, int) and not isinstance(size, bool) and 1 <= size <= ASSET_LIMIT, f"size {size!r} is not between 1 byte and {ASSET_LIMIT}")
    need(isinstance(row.get("sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is not None, "sha256 is not 64 lower-case hex digits")
    profile = row.get("profile")
    need(isinstance(profile, dict) and set(profile) == {"name", "packages", "compatibility"}, "profile is not { name, packages, compatibility }")
    need(any(owns(row["namespace"], p["id"]) for p in profile["packages"]), "the pinned profile holds no package of its namespace")


def check_catalog(catalog):
    """packages.json as the signing tool and the launcher parse it."""
    need(isinstance(catalog, dict) and set(catalog) == {"schema", "serial", "packages"}, "packages.json is not { schema, serial, packages }")
    need(type(catalog["schema"]) is int and catalog["schema"] >= 1, "packages.json has no schema number")
    need(type(catalog["serial"]) is int and catalog["serial"] >= 0, "packages.json has no serial")
    need(isinstance(catalog["packages"], list), "packages.json lists no packages")
    for row in catalog["packages"]:
        try:
            need(isinstance(row, dict), "it is no object")
            check_fields(row)
            check_pin(row)
        except Refused as e:
            raise Refused(f"packages.json, package {row.get('id') if isinstance(row, dict) else '?'}: {e}") from None
    check_rows(catalog["packages"])


def load_catalog(root):
    path = root / "packages.json"
    if not path.exists():
        return {"schema": SCHEMA, "serial": 0, "packages": []}
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as e:
        raise Refused(f"packages.json is not JSON: {e}") from None
    check_catalog(catalog)
    return catalog


def write_catalog(root, catalog):
    """packages.json, the same bytes on every machine: the signing tool reads them."""
    text = json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"
    (root / "packages.json").write_bytes(text.encode("utf-8"))


def fetch_pinned(row, fetch):
    """The zip a row pins, from GitHub or, as the launcher falls back, from a mirror that serves the
    exact bytes by their SHA-256. Returns the bytes and a problem line when GitHub no longer serves
    them (a replaced or removed asset), or refuses when no source does."""
    sources = [row["asset_url"]] + [f"{mirror}{row['sha256']}.zip" for mirror in row["mirrors"]]
    failures = []
    for url in sources:
        try:
            data = fetch(url, row["size"] + 1)
        except (OSError, Refused, KeyError, ValueError) as e:
            failures.append(f"{url}: {e}")
            continue
        if len(data) == row["size"] and hashlib.sha256(data).hexdigest() == row["sha256"]:
            changed = None if url == row["asset_url"] else (
                f"source_changed: {row['asset_url']} no longer serves the pinned bytes ({failures[0]}); {url} still does")
            return data, changed
        failures.append(f"{url}: not the {row['size']} bytes with SHA-256 {row['sha256']}")
    raise Refused(f"source_changed: no source serves the pinned zip any more: {'; '.join(failures)}")


def pin_entry(entry, old, required_rows, api, fetch):
    """The pin of `entry`'s newest release, or None when `old` (its newest kept pin) is that release
    already. A blocked package is not moved: launchers must learn of the block on the version they
    have. `required_rows` are every kept version of what it requires."""
    if entry["status"] == "blocked":
        need(old is not None, "a blocked package without a pin has nothing to block")
        return None
    tag, asset = newest_release(entry, api)
    url, size = asset["browser_download_url"], asset["size"]
    if old is not None and (old["version"], old["asset_url"]) == (tag, url):
        return None
    if old is not None:
        need(old["version"] != tag, f"the release {tag} is pinned already with another asset; a new version needs a new tag")
    need(type(size) is int and 1 <= size <= ASSET_LIMIT, f"{asset['name']} weighs {size} bytes, not between 1 and {ASSET_LIMIT}")
    data = fetch(url, size + 1)
    need(len(data) == size, f"{url} is not the {size} bytes GitHub lists")
    profile = check_package_zip(entry, data, required_rows)
    pin = {"version": tag, "asset_url": url, "size": size, "sha256": hashlib.sha256(data).hexdigest(), "profile": profile,
           "requires": list(entry["requires"])}
    check_pin(package_row(entry, pin))
    return pin


def in_order(entries):
    """The entries, each after what it requires (check_set has ruled out circles)."""
    by_id, done, out = {e["id"]: e for e in entries}, set(), []

    def place(entry):
        if entry["id"] in done:
            return
        for required in entry["requires"]:
            place(by_id[required])
        done.add(entry["id"])
        out.append(entry)

    for entry in entries:
        place(entry)
    return out


def needed(rows):
    """The rows another package's row ships a package of: (id, version) of every version that is
    the only one of its package to pin what the other ships."""
    by_id = {}
    for row in rows:
        by_id.setdefault(row["id"], []).append(row)
    keep = set()
    for row in rows:
        for required in row["requires"]:
            for pinned in row["profile"]["packages"]:
                pins = [v for v in by_id.get(required, []) if pinned in v["profile"]["packages"]]
                if len(pins) == 1:
                    keep.add((required, pins[0]["version"]))
    return keep


def prune(rows, entries):
    """At most MAX_VERSIONS of a package: the oldest go first, but never a blocked version (its
    block must reach launchers) nor one another package ships."""
    blocked = {(e["id"], item["version"]) for e in entries for item in e["blocked"]}
    while True:
        counts = {}
        for row in rows:
            counts[row["id"]] = counts.get(row["id"], 0) + 1
        over = [i for i, n in counts.items() if n > MAX_VERSIONS]
        if not over:
            return rows
        keep = needed(rows) | blocked
        newest = {row["id"]: row["version"] for row in rows}
        drop = next((row for row in rows if row["id"] in over and row["version"] != newest[row["id"]]
                     and (row["id"], row["version"]) not in keep), None)
        need(drop is not None, f"{over[0]} keeps {MAX_VERSIONS} versions that are blocked or shipped by another package")
        rows = [row for row in rows if row is not drop]


def render(entry, versions):
    """An entry's kept versions as rows, the last the newest."""
    return [package_row(entry, row, newest=(i == len(versions) - 1)) for i, row in enumerate(versions)]


def pin(root, api, fetch, offline=False):
    """Bring packages.json up to the entries and, unless `offline`, to each package's newest
    release, beside the versions it keeps. A package whose pin fails keeps what it has. A package
    without a pin is not offered, and neither is one that requires it. The serial grows by one
    when anything changed."""
    entries, catalog = in_order(load_entries(root)), load_catalog(root)
    kept = {}
    for row in catalog["packages"]:
        kept.setdefault(row["id"], []).append(row)
    versions, failed = {}, {}
    for entry in entries:
        before = kept.get(entry["id"], [])
        required = [row for r in entry["requires"] for row in versions.get(r, [])]
        try:
            need(all(r in versions for r in entry["requires"]), "it requires a package that has no pin")
            known = {row["version"] for row in before}
            for item in entry["blocked"]:
                need(item["version"] in known, f"blocked names {item['version']}, which is no pinned version")
            need(entry["status"] != "blocked" or before, "a blocked package without a pin has nothing to block")
            new = None if offline else pin_entry(entry, before[-1] if before else None, required, api, fetch)
        except (Refused, OSError, KeyError, TypeError, ValueError) as e:
            failed[entry["id"]] = str(e) or type(e).__name__
            new = None
        rows = list(before) if before and all(r in versions for r in entry["requires"]) else []
        if new is not None:
            rows.append(new)
        if rows:
            versions[entry["id"]] = render(entry, rows)
    listed = []
    for entry in entries:
        if entry["id"] in versions:
            listed += render(entry, versions[entry["id"]])
    try:
        listed = prune(listed, entries)
        listed = [row for e in entries for row in render(e, [r for r in listed if r["id"] == e["id"]])]
    except Refused as e:
        failed["packages.json"] = str(e)
        listed = catalog["packages"]
    if listed != catalog["packages"]:
        new = {"schema": SCHEMA, "serial": catalog["serial"] + 1, "packages": listed}
        check_catalog(new)
        write_catalog(root, new)
        print(f"packages.json: serial {new['serial']}, {len(listed)} versions of {len({r['id'] for r in listed})} packages")
        old = {(r["id"], r["version"]): r for r in catalog["packages"]}
        for row in listed:
            before = old.get((row["id"], row["version"]))
            if before is None:
                print(f"  pinned {row['id']} {row['version']} ({row['size']} bytes, sha256 {row['sha256']})")
            if row["status"] != "active" and (before is None or before["status"] != row["status"]):
                print(f"  {row['status']} {row['id']} {row['version']}: {row['reason']}")
        for gone in sorted(set(old) - {(r["id"], r["version"]) for r in listed}):
            print(f"  dropped {gone[0]} {gone[1]}")
    else:
        print(f"packages.json is current: serial {catalog['serial']}, {len(listed)} versions")
    return failed


def check(root, fetch=None):
    """What is wrong with the entries and packages.json, as a list of lines; with `fetch`, also
    with the pinned zips as GitHub (or, failing that, a mirror) serves them now."""
    try:
        entries, catalog = load_entries(root), load_catalog(root)
    except Refused as e:
        return [str(e)]
    by_id, problems = {e["id"]: e for e in entries}, []
    kept = {}
    for row in catalog["packages"]:
        kept.setdefault(row["id"], []).append(row)
    for package_id, versions in kept.items():
        entry = by_id.get(package_id)
        if entry is None:
            problems.append(f"packages.json lists {package_id}, which has no entry: run tools/packages.py pin --offline")
            continue
        known = {row["version"] for row in versions}
        stray = [item["version"] for item in entry["blocked"] if item["version"] not in known]
        if stray or render(entry, versions) != versions:
            problems.append(f"packages.json is not what packages/{package_id}.toml says: run tools/packages.py pin --offline")
            continue
        if fetch is None:
            continue
        for row in versions:
            try:
                required = [r for need_id in row["requires"] for r in kept[need_id]]
                data, changed = fetch_pinned(row, fetch)
                if changed:
                    problems.append(f"{row['id']} {row['version']}: {changed}")
                profile = check_package_zip(entry, data, required)
                need(profile == row["profile"], "its profile.json says other than the pin")
            except (Refused, OSError, KeyError) as e:
                problems.append(f"{row['id']} {row['version']}: {e}")
    return problems


def main(argv=None, api=http_api, fetch=http_fetch):
    parser = argparse.ArgumentParser(description="Validate and pin the package catalog.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent, help="the index repository")
    commands = parser.add_subparsers(dest="command", required=True)
    checking = commands.add_parser("check", help="validate the entries and packages.json")
    checking.add_argument("--assets", action="store_true", help="also fetch and check every pinned zip")
    pinning = commands.add_parser("pin", help="pin each package's newest release")
    pinning.add_argument("--offline", action="store_true", help="only bring packages.json up to the entries")
    args = parser.parse_args(argv)
    if args.command == "check":
        problems = check(args.root, fetch if args.assets else None)
        for line in problems:
            print(line, file=sys.stderr)
        if not problems:
            print("the package entries and packages.json are in order" + (", the pinned zips too" if args.assets else ""))
        return 1 if problems else 0
    try:
        failed = pin(args.root, api, fetch, args.offline)
    except Refused as e:
        print(e, file=sys.stderr)
        return 1
    for package_id, why in failed.items():
        print(f"{package_id}: {why}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
