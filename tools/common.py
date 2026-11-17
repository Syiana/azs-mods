"""The rules the package script shares with the addon index's pin script (the addon registry's tools/pin.py):
copied from it verbatim, so a package zip is checked by the same rules as an addon zip and a bound the
launcher reads is one number here and there. When pin.py changes one of these, change it here too.
Standard library only."""

import json
import os
import re
import unicodedata
import urllib.request


# The most a pinned zip may weigh, and the launcher's bounds on unpacking one.
ASSET_LIMIT = 64 << 20


# File types no addon needs and Windows runs.
PROGRAMS = {"exe", "dll", "com", "scr", "pif", "msi", "bat", "cmd", "ps1", "vbs", "jar", "sh", "lnk", "hta"}


class Refused(Exception):
    """An entry, a zip or an index that breaks a rule."""


def need(ok, message):
    if not ok:
        raise Refused(message)


def ascii_lower(text):
    """Lower case as Windows folds file names for our purposes: A to Z only, as the launcher does."""
    return text.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))


def is_control(char):
    return unicodedata.category(char) == "Cc"


def is_id(text):
    """An addon id: lower-case letters, digits and `-` inside, at most 64 characters."""
    return isinstance(text, str) and re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?", text) is not None


def is_device(part):
    """A Windows device name, alone or with an extension, in any case: con, NUL.txt, com1."""
    stem = ascii_lower(part.split(".")[0].rstrip(" "))
    return re.fullmatch(r"con|prn|aux|nul|com[1-9]|lpt[1-9]", stem) is not None


def check_path(path):
    """A path that stays inside the install: relative, `/`-separated, no empty, `.` or `..` part,
    no drive or backslash, no name Windows rewrites or reserves, outside the launcher's state."""
    need(path and "\\" not in path and ":" not in path and not path.startswith("/"), f"{path!r} is not a relative /-path")
    parts = path.split("/")
    for part in parts:
        need(part not in ("", ".", ".."), f"{path!r} leaves its folder")
        need(
            not part.endswith((".", " ")) and not re.search(r"~[0-9]", part) and not is_device(part),
            f"{path!r} has a name Windows rewrites or reserves",
        )
    need(ascii_lower(parts[0].rstrip(". ")) != ".azs", f"{path!r} is inside the launcher's state")


def check_text(field, text, limit):
    need(
        isinstance(text, str) and len(text) <= limit and not any(is_control(c) or c == "|" for c in text),
        f"{field} is too long or holds a control character or |",
    )


def entry_name(info):
    """A zip entry's name as the launcher's zip reader decodes it: UTF-8 when the bytes are, CP437
    otherwise, whatever the entry's flag says, and not cut or rewritten as Python's reader does."""
    name = info.orig_filename
    if not info.flag_bits & 0x800:
        try:
            name = name.encode("cp437").decode("utf-8")
        except UnicodeError:
            pass
    return name


def newest_release(entry, api):
    """The entry's newest release with an asset its `source.asset` names: (tag, the asset). A draft
    or a prerelease is no release; two assets of one release matching is an entry to fix."""
    pattern = re.compile(re.escape(entry["source"]["asset"]).replace(r"\*", ".*"))
    releases = api(f"https://api.github.com/repos/{entry['repo']}/releases?per_page=30")
    need(isinstance(releases, list), "GitHub lists no releases")
    for release in releases:
        if release.get("draft") or release.get("prerelease"):
            continue
        found = [asset for asset in release.get("assets", []) if pattern.fullmatch(asset["name"])]
        need(len(found) <= 1, f"release {release['tag_name']} has {len(found)} assets matching {entry['source']['asset']}")
        if found:
            return release["tag_name"], found[0]
    raise Refused(f"no release has an asset matching {entry['source']['asset']}")


AGENT = "azs-addons-pin"


def http_api(url):
    """A GitHub API answer. The workflow's token goes to the API alone, for its rate limit."""
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": AGENT})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def http_fetch(url, limit):
    """At most `limit` bytes of a release asset, without the token: GitHub redirects to a file
    host, and a request's headers travel with the redirect."""
    need(url.startswith("https://github.com/"), f"{url} is not on GitHub")
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read(limit)
