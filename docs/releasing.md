# Releasing the SDK and your own mods

## Distribute this SDK

Publish `survivors-modding-sdk-<version>.zip` with its companion `.zip.sha256` on a public
release page. A download link can point directly to that release asset. Keep the ZIP's
`LICENSE`, `NOTICE.md` and `CONTENTS.sha256` intact. The ZIP is the source SDK. It can be
unpacked with a standard ZIP tool.

On Windows, use `Get-FileHash -Algorithm SHA256 <sdk-zip>` in PowerShell. On Linux use
`sha256sum <sdk-zip>`; on macOS use `shasum -a 256 <sdk-zip>`. Compare with the published
checksum. These hashes let users check the bytes against the accompanying manifest.

## Test a mod locally

Run `sdk.py prepare` and import the result on your own machine. If your release review requires
an install test, you can use `azs-release profile-pack <local-profile> --out local-test.zip`
and import that ZIP into the native client. The packed profile includes every locked object,
including the copies of the stock packs. Keep the generated profile and test ZIP local unless
you have confirmed distribution rights for every file in them.

Before release, check setup from a fresh mod save, new character creation, the mode card and
zone selection, the encounter through its finale, and co-op with the same package versions on
each client. For scripts, first check the source with the script tooling, then test the encounter
in the native client with script consent enabled.

## Review a mod's distribution contents

- Write the mod's license and identify all third-party materials alongside it. For contributed
  media, keep the origin, license, author and applicable attribution. Record the source of
  third-party dependency files and the scope of any redistribution permission.
- Check the whole package, including nested archives and the stock packs assembled from your
  local base profile. A local copy or a compatibility requirement does not confer a license.
  Keep game archives, client extracts and unauthorized franchise art, dialogue and audio out
  of shared packages. Use original creative content.
- Check the community package guidelines and review process before proposing an upload.
  A registry acceptance describes the project review; it does not confer third-party rights.
  [Community package rules](https://github.com/Syiana/azs-mods/blob/main/docs/LEGAL.md)

## Submit a distributable mod

Once distribution rights for your runtime ZIP are confirmed, keep the filename and bytes
stable for its version. For registry submissions, use `recipes/registry-entry.toml` to
propose an entry in `packages/` of the community registry. Change its ID, namespace,
repository and author before opening a pull request. The registry pins the release by
version, size and SHA-256. Use a new version if any byte changes. The
[registry contribution guide](https://github.com/Syiana/azs-mods/blob/main/CONTRIBUTING.md)
explains how to request a review, update a pin or withdraw a release.
