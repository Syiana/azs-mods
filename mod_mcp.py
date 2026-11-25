#!/usr/bin/env python3
"""Azeroth Survivors mod authoring over local MCP stdio."""

import argparse
import sys
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

sys.dont_write_bytecode = True

from authoring import Studio, localized_text
from sdk import SDK


def server(studio):
    mcp = FastMCP('Azeroth Survivors Mod Kit', instructions=(
        'Use search_stock and read_stock to find spell keys, set definitions, effects, talents and visual fields. '
        'Start a new class with the class recipe or an existing-class set with a blank project. '
        'Use draft_text for all required locale fields in a new tooltip or name. '
        'Read an existing file before editing it. Use the Mod Kit guides and existing pack examples for mechanics. '
        'Build and report diagnostic failures accurately. Preview only when the user asks to launch the local game.'
    ))

    @mcp.tool()
    def search_stock(query: str, path_contains: str = '') -> list[dict]:
        """Find text, IDs, spell visuals, effects, triggers and gear tiers in stock gameplay TOML."""
        return studio.stock_search(query, path_contains)

    @mcp.tool()
    def read_stock(path: str) -> str:
        """Read a stock content file returned by search_stock. Use its real fields as design examples."""
        return studio.stock_read(path)

    @mcp.tool()
    def authoring_guide(topic: Literal['authoring', 'reference', 'releasing'] = 'authoring') -> str:
        """Read the SDK instructions on classes, profiles, overrides and release packaging."""
        return (SDK / f'docs/{topic}.md').read_text(encoding='utf-8')

    @mcp.tool()
    def draft_text(english: str, translations: dict[str, str] | None = None) -> str:
        """Return a TOML localization table. Missing draft translations use the supplied English text."""
        return localized_text(english, translations or {})

    @mcp.tool()
    def create_project(project: str, recipe: Literal['blank', 'class'] = 'blank') -> list[str]:
        """Create a namespaced mod such as studio.stormcaller. The class recipe includes a class, spell and talents."""
        return studio.create(project, recipe)

    @mcp.tool()
    def list_files(project: str) -> list[str]:
        """List a mod project's editable source files."""
        return studio.files(project)

    @mcp.tool()
    def read_file(project: str, path: str) -> str:
        """Read a mod project's source file."""
        return studio.read(project, path)

    @mcp.tool()
    def write_content(project: str, path: str, toml: str) -> str:
        """Replace or add one TOML file. Class-scoped sets use packs/<project>/classes/<class>/set_bonuses.toml."""
        return studio.write(project, path, toml)

    @mcp.tool()
    def build_mod(project: str) -> dict[str, Any]:
        """Assemble, validate and package this mod. Return the local importable ZIP and profile paths."""
        return studio.build(project)

    @mcp.tool()
    def launch_preview(project: str, class_id: int, tier: str = 'epic', stars: int | None = None,
                       spells: list[str] | None = None) -> dict[str, Any]:
        """Launch an equipped hero in Elwynn. Prioritize the given spells and default to active set bonuses."""
        return studio.preview(project, class_id, tier, stars, spells or ())

    @mcp.tool()
    def preview_status(pid: int) -> dict[str, Any]:
        """Check a just-launched preview for world entry and startup errors."""
        return studio.preview_status(pid)

    return mcp


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--base-profile', required=True, type=Path)
    parser.add_argument('--azs-content', default='azs-content')
    parser.add_argument('--azs-release', default='azs-release')
    parser.add_argument('--launcher', type=Path)
    args = parser.parse_args()
    studio = Studio(args.workspace, args.base_profile, args.azs_content, args.azs_release,
                    args.launcher.resolve() if args.launcher else None)
    server(studio).run()
