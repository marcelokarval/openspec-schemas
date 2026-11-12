#!/usr/bin/env python3
"""Validate bounded local records, not the truth of self-reported evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess


class Invalid(Exception):
    pass


def git(root, *args):
    env = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LC_ALL': 'C',
           'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
           'GIT_OPTIONAL_LOCKS': '0'}
    result = subprocess.run(['git', '-C', str(root), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, env=env, timeout=5)
    if result.returncode or len(result.stdout) > 4096:
        raise Invalid()
    return result.stdout.decode('ascii').strip()


def safe_read(root, relative):
    if not isinstance(relative, str) or not relative or '\x00' in relative:
        raise Invalid()
    parts = relative.split('/')
    if any(part in ('', '.', '..') for part in parts):
        raise Invalid()
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            before = os.fstat(file_fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size > 4 * 1024 * 1024:
                raise Invalid()
            chunks = []
            remaining = before.st_size + 1
            while remaining:
                chunk = os.read(file_fd, min(remaining, 65536))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            after = os.fstat(file_fd)
            data = b''.join(chunks)
            if len(data) != before.st_size or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise Invalid()
            return data
        finally:
            os.close(file_fd)
    finally:
        os.close(fd)


def absent(root, relative):
    parts = relative.split('/')
    if not relative or any(p in ('', '.', '..') or '\x00' in p for p in parts):
        raise Invalid()
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            try:
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                return True
            os.close(fd)
            fd = nxt
        try:
            os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
            return False
        except FileNotFoundError:
            return True
    finally:
        os.close(fd)


def visible(text):
    out, fence = [], None
    for line in text.splitlines():
        if re.match(r'^ {4,}(`{3,}|~{3,})', line):
            raise Invalid()
        match = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if match:
            marker, suffix = match.groups()
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not suffix.strip():
                fence = None
            continue
        if fence is None:
            out.append(line)
    if fence:
        raise Invalid()
    return out


def section(lines, name):
    found = [i for i, line in enumerate(lines) if line.strip() == '## ' + name]
    if len(found) != 1:
        raise Invalid()
    start = found[0] + 1
    end = next((i for i in range(start, len(lines)) if re.match(r'^#{1,2}\s', lines[i])), len(lines))
    return [x.strip() for x in lines[start:end] if x.strip()]


def nonempty(value):
    return isinstance(value, str) and bool(value.strip()) and not re.search(r'\b(?:fail(?:ed)?|not verified|blocked|pending)\b', value, re.I)


def run(args):
    root = Path(args.repo).absolute()
    if root.resolve(strict=True) != root or Path(git(root, 'rev-parse', '--show-toplevel')) != root:
        raise Invalid()
    head = git(root, 'rev-parse', '--verify', 'HEAD^{commit}')
    base = git(root, 'rev-parse', '--verify', '--end-of-options', args.base + '^{commit}')
    git(root, 'merge-base', '--is-ancestor', base, head)
    change = Path(args.change).absolute()
    rel = change.relative_to(root).as_posix()
    if rel == '.':
        raise Invalid()
    required = [rel + '/' + name for name in ('brainstorm.md', 'proposal.md', 'design.md', 'tasks.md', 'plan.md')]
    manifest_path = rel + '/candidate-manifest.json'
    manifest_bytes = safe_read(root, manifest_path)
    manifest = json.loads(manifest_bytes)
    entries_manifest = manifest.get('paths') if isinstance(manifest, dict) and set(manifest) == {'paths'} else None
    if not isinstance(entries_manifest, list) or not entries_manifest or len(entries_manifest) > 512 or any(not isinstance(x, dict) or set(x) != {'path', 'state'} or not isinstance(x['path'], str) or x['state'] not in ('present', 'absent') for x in entries_manifest):
        raise Invalid()
    paths = [x['path'] for x in entries_manifest]
    if len(paths) != len(set(paths)):
        raise Invalid()
    if any(p.startswith(rel + '/') or p == rel for p in paths):
        raise Invalid()
    specs_dir = root / rel / 'specs'
    specs = []
    for parent, dirs, files in os.walk(specs_dir, followlinks=False):
        if any((Path(parent) / d).is_symlink() for d in dirs):
            raise Invalid()
        if 'spec.md' in files:
            specs.append((Path(parent) / 'spec.md').relative_to(root).as_posix())
    if not specs or len(specs) > 512:
        raise Invalid()
    contents = {p: safe_read(root, p) for p in set(required + specs + [manifest_path])}
    for entry in entries_manifest:
        path, state = entry['path'], entry['state']
        is_absent = absent(root, path)
        if args.command != 'preflight' and is_absent != (state == 'absent'):
            raise Invalid()
        contents[path] = b'\x00' if is_absent else b'\x01' + safe_read(root, path)
    if any(not contents[p].strip() for p in required + specs):
        raise Invalid()
    tasklines = visible(contents[rel + '/tasks.md'].decode())
    entries = [re.fullmatch(r'\s*-\s*\[([ xX~])\]\s+(\d+\.\d+)\s+\S.*', line) for line in tasklines if re.match(r'^\s*-\s*\[', line)]
    if not entries or any(x is None for x in entries):
        raise Invalid()
    ids = [x.group(2) for x in entries]
    if len(ids) != len(set(ids)):
        raise Invalid()
    digest = hashlib.sha256((base + '\0' + head + '\0').encode())
    for path, data in sorted(contents.items()):
        raw = path.encode()
        digest.update(len(raw).to_bytes(8, 'big') + raw + len(data).to_bytes(8, 'big') + data)
    candidate = digest.hexdigest()
    if args.command == 'verify':
        if any(x.group(1).lower() != 'x' for x in entries):
            raise Invalid()
        plan = visible(contents[rel + '/plan.md'].decode())
        plan_ids = re.findall(r'^## Task (\d+\.\d+)(?=[:\s]|$)', '\n'.join(plan), re.M)
        if sorted(plan_ids) != sorted(ids) or any(re.match(r'^\s*-\s*\[\s*[~ ]\s*\]', x) for x in plan):
            raise Invalid()
        lines = visible(safe_read(root, rel + '/verify.md').decode())
        if section(lines, 'Candidate') != [candidate] or section(lines, 'Mandatory checks') != ['- [x] structural', '- [x] tests', '- [x] review'] or section(lines, 'Overall Decision') != ['- [x] PASS']:
            raise Invalid()
        if any(re.search(r'\b(?:FAIL|NOT VERIFIED|BLOCKED|PENDING)\b', line, re.I) for line in lines):
            raise Invalid()
        evidence = json.loads(safe_read(root, rel + '/evidence.json'))
        if not isinstance(evidence, dict) or set(evidence) != {'candidate', 'tasks', 'structural', 'review', 'unresolved'} or evidence['candidate'] != candidate or evidence['unresolved'] != []:
            raise Invalid()
        records = evidence['tasks']
        if not isinstance(records, list) or len(records) != len(ids):
            raise Invalid()
        for record in records:
            if not isinstance(record, dict) or set(record) != {'id', 'plan', 'red', 'green'} or record['id'] != record['plan']:
                raise Invalid()
            for kind in ('red', 'green'):
                item = record[kind]
                if not isinstance(item, dict) or set(item) != {'command', 'outcome', 'details'} or item['outcome'] != ('expected_failure' if kind == 'red' else 'passed') or not nonempty(item['command']) or not nonempty(item['details']):
                    raise Invalid()
                if kind == 'green' and re.search(r'\b(?:error|skipped|skip|failure|expected failure)\b', item['details'], re.I):
                    raise Invalid()
        if sorted(x['id'] for x in records) != sorted(ids):
            raise Invalid()
        structural, review = evidence['structural'], evidence['review']
        if not isinstance(structural, dict) or set(structural) != {'command', 'result'} or not nonempty(structural['command']) or structural['result'] != 'pass':
            raise Invalid()
        if not isinstance(review, dict) or set(review) != {'reviewer', 'status', 'candidate'} or not nonempty(review['reviewer']) or review['status'] != 'pass' or review['candidate'] != candidate:
            raise Invalid()
    return {'status': 'ok', 'base': base, 'head': head, 'candidate': candidate,
            'notice': 'self-reported records are not independent proof'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['preflight', 'candidate', 'verify'])
    for name in ('repo', 'base', 'change'):
        parser.add_argument('--' + name, required=True)
    try:
        result = run(parser.parse_args())
    except (Invalid, OSError, UnicodeError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
        print(json.dumps({'status': 'error', 'message': 'invalid, missing, incomplete or stale input'}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
