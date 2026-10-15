#!/usr/bin/env python3
"""Private, local music-server snapshots. Import stages data; it never deploys it."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile
import time


def run(args):
    return subprocess.check_output(args, text=True).strip()


def digest(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def inventory(roots):
    files = {}
    for label, root in roots.items():
        paths = [root] if root.is_file() else [root, *root.rglob('*')]
        for p in paths:
            if p.is_symlink() or not (p.is_file() or p.is_dir()):
                raise ValueError(f'Unsupported link or special file: {p}. Nothing exported.')
            if p.is_file():
                name = str(PurePosixPath('data', label) / p.relative_to(root)) if root.is_dir() else f'data/{label}'
                files[name] = p
    return files


def export_profile(compose, output):
    compose = compose.resolve(strict=True)
    output = output.absolute()
    if output.exists():
        raise ValueError('Output already exists; choose a new filename.')
    document = json.loads(compose.read_text())
    services = document.get('services', {})
    required = {'gluetun', 'slskd', 'qbittorrent', 'droppedneedle'}
    if not required <= services.keys():
        raise ValueError('This exporter expects the inspected four-service music Compose stack.')
    base = compose.parent
    roots = {'compose.json': compose}
    mapping = {}
    # Keep service state, not the separate music/download disks.
    targets = {'slskd': {'/app'}, 'qbittorrent': {'/config'},
               'droppedneedle': {'/app/config', '/app/cache', '/app/plugins', '/app/imports'}}
    for service, expected in targets.items():
        found = set()
        for mount in services[service].get('volumes', []):
            if isinstance(mount, str):
                parts = mount.split(':')
                source, target = parts[:2]
            else:
                if mount.get('type') != 'bind':
                    continue
                source, target = mount['source'], mount['target']
            if target in expected:
                path = Path(source)
                path = (base / path).resolve(strict=True) if not path.is_absolute() else path.resolve(strict=True)
                label = service + '-' + target.strip('/').replace('/', '-')
                roots[label] = path
                mapping[label] = {'service': service, 'target': target, 'original_source': str(path)}
                found.add(target)
        if found != expected:
            raise ValueError(f'Missing expected bind mounts for {service}: {expected - found}')
    for service, settings in services.items():
        envs = settings.get('env_file', [])
        if isinstance(envs, (str, dict)):
            envs = [envs]
        for i, env in enumerate(envs):
            source = env['path'] if isinstance(env, dict) else env
            p = (base / source).resolve(strict=True)
            label = f'{service}-env-{i}'
            roots[label] = p
            mapping[label] = {'service': service, 'env_file': source}
    if not (roots['droppedneedle-app-config'] / '.env').is_file():
        raise ValueError('Dropped Needle encryption-key file is missing.')
    if not (roots['droppedneedle-app-cache'] / 'library.db').is_file():
        raise ValueError('Dropped Needle database is missing.')
    for p in roots.values():
        if p.is_dir() and output.is_relative_to(p):
            raise ValueError('Save the archive outside the service data folders.')
    files = inventory(roots)
    size = sum(p.stat().st_size for p in files.values())
    print(f'Profile data: {size / 1024**2:.1f} MiB before compression.')
    print('Includes credentials, account database, cache, plugins and imports.')
    print('The music stack will stop while the archive is made, then previously running services restart.')
    if input('Type EXPORT to continue: ').strip() != 'EXPORT':
        return
    command = ['docker', 'compose', '-f', str(compose)]
    running = run(command + ['ps', '--status', 'running', '--services']).splitlines()
    if not running:
        running = []
    ids = run(command + ['ps', '-aq']).splitlines()
    metadata = json.loads(run(['docker', 'inspect', *ids])) if ids else []
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.profile-', dir=output.parent)
    os.close(fd)
    try:
        try:
            if running:
                subprocess.run(command + ['stop', *running], check=True)
            files = inventory(roots)
            manifest = {'format': 'optiplex-now-music-profile', 'version': 1,
                        'created': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                        'mounts': mapping, 'files': {n: digest(p) for n, p in files.items()},
                        'directories': [f'data/{label}' for label,p in roots.items() if p.is_dir()],
                        'original_compose': str(compose), 'deployment': False}
            with tempfile.TemporaryDirectory() as tmp:
                info = Path(tmp)
                (info / 'manifest.json').write_text(json.dumps(manifest, indent=2))
                (info / 'containers.json').write_text(json.dumps(metadata, indent=2))
                with tarfile.open(temporary, 'w:gz') as archive:
                    archive.add(info / 'manifest.json', arcname='manifest.json')
                    archive.add(info / 'containers.json', arcname='containers.json')
                    for name, path in files.items():
                        archive.add(path, arcname=name, recursive=False)
            # Hard link commits without replacing another snapshot.
            os.link(temporary, output)
        finally:
            if running:
                subprocess.run(command + ['start', *running], check=True)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print(f'Saved private profile: {output}')
    print('Keep this archive private. It is not encrypted. Media/download mounts are not included.')


def import_profile(source, destination):
    destination = destination.absolute()
    if destination.exists():
        raise ValueError('Destination must be a new folder. Existing files will not be overwritten.')
    with tarfile.open(source, 'r:gz') as archive:
        members = archive.getmembers()
        names = set()
        for m in members:
            p = PurePosixPath(m.name)
            if (not m.isfile() or p.is_absolute() or '..' in p.parts or
                    str(p) != m.name or m.name in names):
                raise ValueError('Archive contains an unsafe or duplicate member.')
            names.add(m.name)
        if 'manifest.json' not in names or archive.getmember('manifest.json').size > 10*1024**2:
            raise ValueError('Missing or oversized profile manifest.')
        manifest = json.load(archive.extractfile('manifest.json'))
        if manifest.get('format') != 'optiplex-now-music-profile' or manifest.get('version') != 1:
            raise ValueError('Unsupported profile format.')
        expected = manifest['files']
        if names != set(expected) | {'manifest.json', 'containers.json'}:
            raise ValueError('Archive does not match its manifest.')
        directories = manifest.get('directories', [])
        for name in directories:
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or str(p) != name or len(p.parts) != 2 or p.parts[0] != 'data':
                raise ValueError('Invalid profile directory.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        required = sum(m.size for m in members)
        if shutil.disk_usage(destination.parent).free < required + 100*1024**2:
            raise ValueError('Not enough free space to import this profile.')
        with tempfile.TemporaryDirectory(prefix='.profile-import-', dir=destination.parent) as tmp:
            staging = Path(tmp) / 'profile'
            staging.mkdir(mode=0o700)
            for name in directories:
                (staging / name).mkdir(parents=True, exist_ok=True)
            for m in members:
                path = staging / m.name
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(m) as src, open(path, 'xb') as dst:
                    shutil.copyfileobj(src, dst)
                path.chmod(0o600)
                if m.name in expected and digest(path) != expected[m.name]:
                    raise ValueError(f'Checksum mismatch: {m.name}')
            # Destination is new, but recheck immediately before rename.
            if destination.exists():
                raise ValueError('Destination appeared during import; refusing to overwrite.')
            staging.rename(destination)
    print(f'Profile verified and staged: {destination}')
    print('No services installed or started. Paths, permissions and networking still need deployment setup.')


def main():
    os.umask(0o077)
    print('OptiPlex Now — music server profiles (THIS COMPUTER)')
    print('1. Export existing music server\n2. Import profile into a new folder\nEnter to cancel')
    choice = input('Choose: ').strip()
    if choice == '1':
        if os.geteuid() != 0:
            raise ValueError('Export requires sudo on the server.')
        compose = input('Compose JSON path: ').strip()
        output = input('Save archive as (full path ending .tar.gz): ').strip()
        if not compose or not output:
            return
        export_profile(Path(compose), Path(output))
    elif choice == '2':
        source = input('Profile archive path: ').strip()
        dest = input('New destination folder: ').strip()
        if source and dest:
            import_profile(Path(source), Path(dest))


if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print(f'Not completed: {exc}')
    finally:
        input('Press Enter to close.')
