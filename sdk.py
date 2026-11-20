#!/usr/bin/env python3
"""Create, inspect and prepare a source mod for local testing."""

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path, PurePosixPath

SDK = Path(__file__).resolve().parent
EXAMPLE = "example.copperbell"
STOCK = ("base", "tbc", "wotlk")
PACKAGE_ID = re.compile(r"[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+")
SAFE_PART = re.compile(r"[a-z0-9][a-z0-9_.-]*")


def package_id(value):
    if len(value) > 64 or not PACKAGE_ID.fullmatch(value) or value.startswith("azs."):
        raise ValueError("Choose a package id such as studio.my-mod (up to 64 characters).")
    return value


def new(target, namespace):
    package_id(namespace)
    target.mkdir(parents=True)
    shutil.copyfile(SDK / "LICENSE", target / "LICENSE")
    for source in sorted((SDK / "examples/copperbell").rglob("*")):
        if source.is_file():
            relative = source.relative_to(SDK / "examples/copperbell").as_posix()
            destination = target / relative.replace(EXAMPLE, namespace)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                source.read_text(encoding="utf-8").replace(EXAMPLE, namespace),
                encoding="utf-8", newline="\n",
            )


def input_file(root, relative):
    """Read paths using the same portable spelling on Windows and Unix."""
    path = PurePosixPath(relative)
    if (
        path.as_posix() != relative
        or not path.parts
        or any(not SAFE_PART.fullmatch(part) for part in path.parts if part != "LICENSE")
    ):
        raise ValueError(f"Invalid relative path: {relative}")
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise ValueError(f"Links are unsupported: {relative}")
    if not current.is_file() or not current.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Missing or unsafe file: {relative}")
    return current


def read_source(source):
    config = tomllib.loads(input_file(source, "mod.toml").read_text(encoding="utf-8"))
    namespace = package_id(config["id"])
    version = config["version"]
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Set a nonempty version string in mod.toml.")
    requires = config["requires"]
    if (
        not isinstance(requires, list)
        or "base" not in requires
        or any(dep not in STOCK for dep in requires)
        or len(requires) != len(set(requires))
    ):
        raise ValueError("requires must include base and may also include tbc and wotlk, once each.")
    manifest = f"packs/{namespace}/pack.toml"
    objects = []
    content_overrides = set()
    for file in sorted(source.rglob("*")):
        if file.is_dir() and not file.is_symlink() and not getattr(file, "is_junction", lambda: False)():
            continue
        path = file.relative_to(source).as_posix()
        if path in ("mod.toml", "LICENSE"):
            continue
        file = input_file(source, path)
        if path.startswith(f"packs/{namespace}/") and file.suffix == ".toml":
            kind = "gameplay"
        elif path.startswith(f"packs/{namespace}/scripts/") and file.suffix == ".lua":
            kind = "script"
        elif path.startswith(f"modes/{namespace}/") and len(file.relative_to(source).parts) == 3 and file.suffix == ".toml":
            kind = "mode"
        else:
            raise ValueError(f"Unsupported source file: {path}")
        if kind != "script":
            entry = tomllib.loads(file.read_text(encoding="utf-8"))
            if path == manifest:
                if entry["key"] != namespace or entry.get("requires", []) != requires:
                    raise ValueError("Keep the package id and requires in mod.toml and pack.toml in sync.")
            for override in entry.get("override", []):
                content_overrides.add(f'{override["kind"]}:{override["key"]}')
            if kind == "mode" and "replaces" in entry:
                content_overrides.add(f'mode:{entry["replaces"]}')
        objects.append({"path": path, "kind": kind, "hash": "0" * 64})
    input_file(source, manifest)
    overrides = config.get("overrides", [])
    if (
        any(item["dependency"] not in requires for item in overrides)
        or {item["entity"] for item in overrides} != content_overrides
    ):
        raise ValueError("Declare every override and its direct dependency in mod.toml.")
    return config, objects


def prepare(source, base, output, azs_release):
    config, objects = read_source(source)
    if output.exists() or output.resolve().is_relative_to(source.resolve()):
        raise ValueError("Choose a new output folder outside your mod sources.")
    base_profile = json.loads(input_file(base, "profile.json").read_text(encoding="utf-8"))
    stock = [package for package in base_profile["lock"]["packages"] if package["id"] in STOCK]
    versions = {package["id"]: package["version"] for package in stock}
    if len(stock) != len(STOCK) or set(versions) != set(STOCK):
        raise ValueError("The supplied profile must have exactly one base, tbc and wotlk package.")
    compatibility = base_profile["compatibility"]
    if any(obj["kind"] == "script" for obj in objects):
        caps = compatibility.setdefault("required_capabilities", [])
        if "scripts-v1" not in caps:
            caps.append("scripts-v1")
    profile = {
        "compatibility": compatibility,
        "lock": {"name": config["id"], "packages": stock + [{
            "id": config["id"],
            "version": config["version"],
            "kind": "gameplay",
            "variant": None,
            "dependencies": [{"id": dep, "version": versions[dep]} for dep in config["requires"]],
            "overrides": config.get("overrides", []),
            "required_assets": [],
            "objects": objects,
        }]},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="azs-sdk-", dir=output.parent) as temp:
        stage = Path(temp) / "profile"
        stage.mkdir()
        for directory, files in [(base, (obj for pack in stock for obj in pack["objects"])), (source, objects)]:
            for obj in files:
                relative = obj["path"]
                original = input_file(directory, relative)
                target = stage / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as handle:
                    handle.write(original.read_bytes())
        license_file = source / "LICENSE"
        if license_file.exists() or license_file.is_symlink():
            shutil.copyfile(input_file(source, "LICENSE"), stage / "LICENSE")
        (stage / "profile.json").write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8", newline="\n")
        subprocess.run([azs_release, "profile-lock", str(stage)], check=True)
        stage.rename(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("new", help="copy the starter and rename its namespace")
    create.add_argument("output", type=Path)
    create.add_argument("--id", default=EXAMPLE)
    check = commands.add_parser("check", help="check the source layout, TOML and override declarations")
    check.add_argument("source", type=Path)
    build = commands.add_parser("prepare", help="lock a local test profile using separately supplied game packs")
    build.add_argument("source", type=Path)
    build.add_argument("--base-profile", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--azs-release", default="azs-release")
    args = parser.parse_args()
    try:
        if args.command == "new":
            new(args.output, args.id)
            print(f"Created source mod at {args.output}")
        elif args.command == "check":
            config, objects = read_source(args.source)
            print(f'{config["id"]}: {len(objects)} source objects checked.')
        else:
            prepare(args.source, args.base_profile, args.output, args.azs_release)
            print(f"Local test profile: {args.output}")
    except (OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"SDK error: {error}\n")


if __name__ == "__main__":
    main()
