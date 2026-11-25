"""Local workspace for the mod authoring MCP."""

import json
import ntpath
import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path
from uuid import uuid4

from sdk import BASE_STOCK, SDK, STOCK, input_file, package_id, prepare, read_source


def command(*args):
    # A GUI launched by a tool can keep inherited pipe handles open after the tool exits.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        result = subprocess.run(args, stdout=stdout, stderr=stderr, timeout=180)
        stdout.seek(0)
        output = stdout.read().decode('utf-8', errors='replace').strip()
        stderr.seek(0)
        errors = stderr.read().decode('utf-8', errors='replace').strip()
    if result.returncode:
        raise ValueError((output + '\n' + errors).strip() or f'{args[0]} exited {result.returncode}')
    return output


def localized_text(english, translations):
    recipe = SDK / 'recipes/class/coilwright/class.toml'
    locales = tomllib.loads(recipe.read_text(encoding='utf-8'))['name']
    if not english.strip() or set(translations) - (locales.keys() - {'en'}):
        supported = ', '.join(locale for locale in locales if locale != 'en')
        raise ValueError(f'Provide English text and optional translations for {supported}.')
    words = ', '.join(f'{locale} = {json.dumps(translations.get(locale, english), ensure_ascii=False)}' for locale in locales)
    return '{ ' + words + ' }'


class Studio:
    def __init__(self, root, base, content, release, launcher=None):
        self.root = root.resolve()
        self.base = base.resolve()
        self.content = content
        self.release = release
        self.launcher = launcher
        self.preview_logs = {}

    def project(self, name):
        project = self.root / package_id(name)
        if not project.is_dir() or project.is_symlink() or project.is_junction():
            raise ValueError(f'Unknown project: {name}')
        return project

    def create(self, name, recipe):
        package_id(name)
        if recipe not in ('blank', 'class'):
            raise ValueError('Choose blank or class.')
        if (self.root / name).exists() or (self.root / name).is_symlink():
            raise ValueError(f'Project already exists: {name}')
        self.root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.root) as temp:
            source = Path(temp) / name
            pack = source / 'packs' / name
            pack.mkdir(parents=True)
            deps = json.dumps(BASE_STOCK)
            (source / 'mod.toml').write_text(f'id = "{name}"\nversion = "0.1.0"\nrequires = {deps}\n', encoding='utf-8')
            (pack / 'pack.toml').write_text(f'key = "{name}"\nrequires = {deps}\n', encoding='utf-8')
            if recipe == 'class':
                dest = pack / 'classes/coilwright'
                dest.mkdir(parents=True)
                for item in (SDK / 'recipes/class/coilwright').glob('*.toml'):
                    dest.joinpath(item.name).write_text(item.read_text(encoding='utf-8').replace('example.copperbell', name), encoding='utf-8')
            shutil.copyfile(SDK / 'LICENSE', source / 'LICENSE')
            source.rename(self.root / name)
        return self.files(name)

    def files(self, name):
        project = self.project(name)
        files = sorted(path.relative_to(project).as_posix() for path in project.rglob('*.toml'))
        for path in files:
            input_file(project, path)
        return files

    def read(self, name, path):
        return input_file(self.project(name), path).read_text(encoding='utf-8')

    def write(self, name, path, body):
        project = self.project(name)
        if not re.fullmatch(r'[a-z0-9_.-]+(?:/[a-z0-9_.-]+)*\.toml', path) or any(
            part in ('.', '..') or part.endswith('.') or ntpath.isreserved(part) for part in path.split('/')
        ):
            raise ValueError('Use a portable relative TOML path.')
        if path != 'mod.toml' and not path.startswith((f'packs/{name}/', f'modes/{name}/')):
            raise ValueError('Write inside the project pack, mode directory or mod.toml.')
        if path.startswith(f'modes/{name}/') and len(path.split('/')) != 3:
            raise ValueError('Put mode files directly under their namespace directory.')
        if len(body.encode('utf-8')) > 256 * 1024:
            raise ValueError('Split the content into files smaller than 256 KiB.')
        tomllib.loads(body)
        target = project / path
        for current in [target, *target.parents][:len(path.split('/'))]:
            if current.is_symlink() or current.is_junction():
                raise ValueError('Links are unsupported in project files.')
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.root) as temp:
            pending = Path(temp) / target.name
            pending.write_text(body, encoding='utf-8', newline='\n')
            pending.replace(target)
        return path

    def build(self, name, package=True):
        source = self.project(name)
        config, objects = read_source(source)
        if config['id'] != name or any(obj['kind'] == 'script' for obj in objects):
            raise ValueError('Use the project namespace and data-only content for MCP builds.')
        revision = self.root / 'output' / name / uuid4().hex
        profile = revision / 'profile'
        prepare(source, self.base, profile, self.release, lock=command)
        diagnostics = json.loads(command(self.content, 'profile-check', '--profile', str(profile), '--json'))
        if not diagnostics.get('ok'):
            raise ValueError(json.dumps(diagnostics))
        result = {'profile': str(profile), 'validation': diagnostics}
        if package:
            archive = revision / f'{name}.zip'
            command(self.release, 'profile-pack', str(profile), '--out', str(archive))
            result['zip'] = str(archive)
        return result

    def preview(self, name, class_id, tier, stars, spells=()):
        if not self.launcher or not self.launcher.is_file():
            raise ValueError('Configure --launcher with the installed Azeroth Survivors launcher.')
        if not 1 <= class_id <= 255 or (stars is not None and not 0 <= stars <= 255) or not re.fullmatch(r'[a-z][a-z0-9_:-]{0,63}', tier):
            raise ValueError('Provide a class ID, gear tier key and valid star count.')
        if len(spells) > 6 or not all(re.fullmatch(r'[a-z0-9_.:-]{1,128}', spell) for spell in spells):
            raise ValueError('Provide up to six spell keys to prioritize on the preview bar.')
        result = self.build(name, package=False)
        star_arg = 'awake' if stars is None else str(stars)
        launch = json.loads(command(str(self.launcher), '--mods', 'preview', result['profile'], str(class_id), tier, star_arg, *spells))
        self.preview_logs[launch['pid']] = Path(launch['log'])
        return {**result, 'launch': launch, 'zone': 'elwynn'}

    def preview_status(self, pid):
        log = self.preview_logs.get(pid)
        if log is None:
            raise ValueError('Use a process ID returned by launch_preview in this MCP session.')
        with log.open('rb') as handle:
            entered = any(line.startswith(b'mod preview entered ') for line in handle)
            handle.seek(max(0, log.stat().st_size - 8192))
            tail = handle.read(8192).decode('utf-8', errors='replace')
        return {'entered_world': entered, 'recent_log': tail, 'log': str(log)}

    def stock_search(self, query, kind):
        """Search the exact TOML files from the pinned stock profile."""
        if not query.strip() or len(query) > 100:
            raise ValueError('Search for a name, ID or mechanic field (1–100 characters).')
        profile = json.loads(input_file(self.base, 'profile.json').read_text(encoding='utf-8'))
        matches = []
        for pack in profile['lock']['packages']:
            if pack['id'] not in STOCK:
                continue
            for obj in pack['objects']:
                path = obj['path']
                if obj['kind'] != 'gameplay' or not path.endswith('.toml') or kind not in path:
                    continue
                for index, line in enumerate(input_file(self.base, path).read_text(encoding='utf-8').splitlines(), 1):
                    if query.casefold() in line.casefold():
                        matches.append({'path': path, 'line': index, 'text': line.strip()[:350]})
                        if len(matches) == 30:
                            return matches
        return matches

    def stock_read(self, path):
        if not path.startswith(tuple(f'packs/{pack}/' for pack in STOCK)) or not path.endswith('.toml'):
            raise ValueError('Choose a stock TOML path returned by search_stock.')
        return input_file(self.base, path).read_text(encoding='utf-8')
