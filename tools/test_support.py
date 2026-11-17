"""The stand-ins the package tests share (copied from the addon registry's test_pin.py): hand-built zips,
GitHub as a dictionary, and a registry in a temporary folder. No network."""

import struct
import tempfile
import zlib
from pathlib import Path


def file(name, data=b"x", deflated=False, announces=None, mode=0o100644, flags=0, method=None):
    """One entry of a hand-built zip: any name, a size the headers lie about, a link's mode."""
    return (name, data, deflated, announces, mode, flags, method)


def raw_zip(entries):
    """A zip of `entries`: a local header and the data per entry, the central directory, its end."""
    out, central = bytearray(), bytearray()
    for name, data, deflated, announces, mode, flags, method in entries:
        if deflated:
            packer = zlib.compressobj(6, zlib.DEFLATED, -15)
            packed = packer.compress(data) + packer.flush()
        else:
            packed = data
        method = method if method is not None else (8 if deflated else 0)
        size = announces if announces is not None else len(data)
        raw = name.encode("utf-8")
        shared = struct.pack("<5H3I2H", 20, flags, method, 0, 0x21, zlib.crc32(data), len(packed), size, len(raw), 0)
        offset = len(out)
        out += struct.pack("<I", 0x04034B50) + shared + raw + packed
        central += struct.pack("<IH", 0x02014B50, (3 << 8) | 20) + shared
        central += struct.pack("<3HII", 0, 0, 0, (mode << 16) & 0xFFFFFFFF, offset) + raw
    out += central + struct.pack("<I4H2IH", 0x06054B50, 0, 0, len(entries), len(entries), len(central), len(out), 0)
    return bytes(out)


class Hub:
    """A stand-in for GitHub: each repository's releases, newest first, and the bytes behind each
    asset's address."""

    def __init__(self):
        self.releases, self.files, self.asked, self.fetched = {}, {}, [], []

    def release(self, repo, tag, assets, prerelease=False, draft=False):
        listed = []
        for name, data in assets.items():
            url = f"https://github.com/{repo}/releases/download/{tag}/{name}"
            self.files[url] = data
            listed.append({"name": name, "size": len(data), "browser_download_url": url})
        self.releases.setdefault(repo, []).insert(0, {"tag_name": tag, "prerelease": prerelease, "draft": draft, "assets": listed})

    def api(self, url):
        self.asked.append(url)
        repo = url.removeprefix("https://api.github.com/repos/").split("/releases")[0]
        return self.releases.get(repo, [])

    def fetch(self, url, limit):
        self.fetched.append(url)
        return self.files[url][:limit]


class Repo:
    """A registry repository in a temporary folder."""

    def __init__(self, case):
        folder = tempfile.TemporaryDirectory()
        case.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
