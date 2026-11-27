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
import sys

# The guard is read-only even when called without python -B.
sys.dont_write_bytecode = True


class Invalid(Exception):
    pass


class InvalidContract(Invalid):
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


def section(lines, name, *, marked=False):
    heading = r'^ {0,3}#{1,2}[ \t]' if marked else r'^#{1,2}\s'
    found = [i for i, line in enumerate(lines)
             if line.strip() == '## ' + name and (not marked or re.match(heading, line))]
    if len(found) != 1:
        raise Invalid()
    start = found[0] + 1
    end = next((i for i in range(start, len(lines)) if re.match(heading, lines[i])), len(lines))
    values = [x for x in lines[start:end] if x.strip()]
    if marked and any(re.match(r'^(?: {4}| {0,3}\t)', x) for x in values):
        raise InvalidContract('verify.md: required sections must use visible Markdown, not indented code')
    return [x.strip() for x in values]


def nonempty(value):
    return isinstance(value, str) and bool(value.strip()) and not re.search(r'\b(?:fail(?:ed)?|not verified|blocked|pending)\b', value, re.I)


# A lexical prefix only selects the Markdown parser. That parser still decides
# visibility, valid syntax, duplicates and version. Ordinary prose is standalone.
TASK_PREFIX = re.compile(rb'^ {0,3}Bridge[ \t]+task[ \t]+contract[ \t]*:', re.I)
RULE_PREFIX = re.compile(rb'^ {0,3}(?:Bridge[ \t]+rule[ \t]+contract|(?:[-+*][ \t]+)?Rule[ \t]+(?:scenario|readiness))[ \t]*:', re.I)


def has_prefix(data, pattern):
    for line in data.removeprefix(b'\xef\xbb\xbf').replace(b'\r', b'\n').split(b'\n'):
        # A complete inline comment can separate tokens but never join them.
        if b'<!--' in line:
            parts = []
            start = 0
            while (pos := line.find(b'<!--', start)) >= 0:
                end = line.find(b'-->', pos + 4)
                if end < 0:
                    break
                parts.extend((line[start:pos], b' '))
                start = end + 3
            line = b''.join((*parts, line[start:]))
        if pattern.match(line):
            return True
    return False


def contract_inputs(plan_bytes, tasks_bytes, *, required=False):
    if not has_prefix(plan_bytes, TASK_PREFIX):
        if required:
            raise InvalidContract('plan.md: bridge task contract marker required for planning')
        return None
    from task_dag import ContractError, decode_artifact, marked_contract, read_contract

    try:
        if not marked_contract(decode_artifact(plan_bytes, errors='replace')):
            if required:
                raise InvalidContract('plan.md: bridge task contract marker required for planning')
            return None
        plan_text = decode_artifact(plan_bytes)
        _, checkboxes, _ = read_contract(plan_text, decode_artifact(tasks_bytes))
        return plan_text, checkboxes
    except ContractError as error:
        raise InvalidContract(str(error)) from error


def auxiliary_file_link(root, parent, parent_fd, name):
    """Classify metadata inside root without opening the link or reading its target."""
    target = root / parent / os.readlink(name, dir_fd=parent_fd)
    if not target.is_relative_to(root):
        return False
    parts = target.relative_to(root).parts
    if not parts or parts[-1] == '..' or len(parts) > 128:
        return False
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    stack = [os.open(root, flags)]
    try:
        for part in parts[:-1]:
            if part == '..':
                if len(stack) == 1:
                    return False
                os.close(stack.pop())
            else:
                stack.append(os.open(part, flags, dir_fd=stack[-1]))
        mode = os.stat(parts[-1], dir_fd=stack[-1], follow_symlinks=False).st_mode
        return stat.S_ISREG(mode)
    except FileNotFoundError:
        # A dangling auxiliary link, like an absent diagram, has no spec subtree.
        return True
    finally:
        for fd in reversed(stack):
            os.close(fd)


def spec_inputs(root, prefix):
    """Walk only specs/, using directory descriptors throughout (no symlink traversal)."""
    result = {}
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    entries = size = 0

    def walk(fd, path, depth):
        nonlocal entries, size
        with os.scandir(fd) as children:
            for child in children:
                entries += 1
                if entries > 8192 or depth > 32:
                    raise InvalidContract('specs/: directory search limit exceeded')
                name = path + '/' + child.name
                if child.is_symlink():
                    if child.name != 'spec.md' and auxiliary_file_link(root, path, fd, child.name):
                        continue
                    raise InvalidContract('specs/: linked specs, directories or unclassifiable targets are not supported')
                if child.is_dir(follow_symlinks=False):
                    sub = os.open(child.name, flags, dir_fd=fd)
                    try:
                        walk(sub, name, depth + 1)
                    finally:
                        os.close(sub)
                elif child.name == 'spec.md':
                    data = safe_read(root, name)
                    size += len(data)
                    if len(result) >= 512 or size > 32 * 1024 * 1024:
                        raise InvalidContract('specs/: spec input limit exceeded')
                    result[name] = data

    fd = os.open(root, flags)
    path = prefix + 'specs'
    try:
        for part in path.split('/'):
            if part in ('', '.', '..'):
                raise Invalid()
            try:
                sub = os.open(part, flags, dir_fd=fd)
            except FileNotFoundError:
                raise InvalidContract('specs/: missing spec.md') from None
            os.close(fd)
            fd = sub
        walk(fd, path, 0)
    finally:
        os.close(fd)
    if not result:
        raise InvalidContract('specs/: missing spec.md')
    return result


def rule_inputs(plan, marked, specs, load, planning_change=None):
    if not has_prefix(plan, RULE_PREFIX):
        return None
    from rule_contract import plan_marker, validate
    from task_dag import ContractError
    try:
        if not plan_marker(plan):
            return None
        if marked is None:
            raise ContractError('plan.md: Bridge task contract: 1 required with rule contract')
        if planning_change is not None:
            specs = spec_inputs(planning_change, '')
        return validate(*marked, specs, load)
    except ContractError as error:
        raise InvalidContract(str(error)) from error


def rule_loader(repo, change, external, manifest_data=None):
    total = 0
    root = None

    def load(path):
        nonlocal total, root
        if repo is None:
            raise InvalidContract('Rule reference requires planning --repo <repository root>')
        if root is None:
            root = Path(repo).absolute()
            if (root.resolve(strict=True) != root or root == change or not change.is_relative_to(root)
                    or Path(git(root, 'rev-parse', '--show-toplevel')) != root):
                raise InvalidContract('Rule reference requires the containing Git repository root')
        if (root / path).is_relative_to(change):
            raise InvalidContract('Rule reference must point outside the consuming change')
        try:
            if manifest_data is not None and path in manifest_data:
                entry = manifest_data[path]
                if entry[:1] != b'\x01':
                    raise Invalid()
                data = entry[1:]
            else:
                data = safe_read(root, path)
        except (OSError, Invalid):
            raise InvalidContract(f'Rule reference: cannot safely read {path}') from None
        total += len(data)
        if len(external) >= 64 or total > 16 * 1024 * 1024:
            raise InvalidContract('Rule reference input limit exceeded')
        external[path] = data
        return data
    return load


def planning(change, repo):
    root = Path(change).absolute()
    if root.resolve(strict=True) != root:
        raise Invalid()
    plan = safe_read(root, 'plan.md')
    marked = contract_inputs(plan, safe_read(root, 'tasks.md'), required=True)
    policy = rule_inputs(plan, marked, {}, rule_loader(repo, root, {}), planning_change=root)
    return {'status': 'ok', 'notice': 'structure only; not execution, authorization or acceptance',
            **(policy.result() if policy else {})}


def marked_verify_lines(plan_text, root, report_path):
    from task_dag import ContractError, contract_lines, decode_artifact, pending_checkbox

    try:
        for number, line in contract_lines(plan_text):
            if pending_checkbox(line):
                raise InvalidContract(f'plan.md:{number}: pending plan checkbox')
        report = decode_artifact(safe_read(root, report_path))
        return [line for _, line in contract_lines(report, 'verify.md')]
    except ContractError as error:
        raise InvalidContract(str(error)) from error


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
    specs = spec_inputs(root, rel + '/')
    contents = {p: safe_read(root, p) for p in required}
    contents.update(specs)
    contents[manifest_path] = manifest_bytes
    for entry in entries_manifest:
        path, state = entry['path'], entry['state']
        is_absent = absent(root, path)
        if args.command != 'preflight' and is_absent != (state == 'absent'):
            raise Invalid()
        contents[path] = b'\x00' if is_absent else b'\x01' + safe_read(root, path)
    if any(not contents[p].strip() for p in required + list(specs)):
        raise Invalid()
    plan_bytes, tasks_bytes = (contents[rel + '/' + name] for name in ('plan.md', 'tasks.md'))
    marked = contract_inputs(plan_bytes, tasks_bytes)
    external = {}
    policy = rule_inputs(plan_bytes, marked, specs, rule_loader(root, change, external, contents))
    for path, data in external.items():
        contents.setdefault(path, b'\x01' + data)
    if marked is not None:
        plan_text, checkboxes = marked
        ids = list(checkboxes)
        marks = [checkboxes[task_id][0] for task_id in ids]
    else:
        tasklines = visible(tasks_bytes.decode())
        entries = [re.fullmatch(r'\s*-\s*\[([ xX~])\]\s+(\d+\.\d+)\s+\S.*', line) for line in tasklines if re.match(r'^\s*-\s*\[', line)]
        if not entries or any(x is None for x in entries):
            raise Invalid()
        ids = [x.group(2) for x in entries]
        if len(ids) != len(set(ids)):
            raise Invalid()
        marks = [x.group(1).lower() for x in entries]
    digest = hashlib.sha256((base + '\0' + head + '\0').encode())
    for path, data in sorted(contents.items()):
        raw = path.encode()
        digest.update(len(raw).to_bytes(8, 'big') + raw + len(data).to_bytes(8, 'big') + data)
    candidate = digest.hexdigest()
    if args.command == 'verify':
        if policy and policy.blocked:
            raise InvalidContract('verify: rule-blocked tasks: ' + ', '.join(policy.blocked))
        if any(mark != 'x' for mark in marks):
            raise Invalid()
        if marked is not None:
            lines = marked_verify_lines(plan_text, root, rel + '/verify.md')
        else:
            plan_lines = visible(plan_bytes.decode())
            plan_ids = re.findall(r'^## Task (\d+\.\d+)(?=[:\s]|$)', '\n'.join(plan_lines), re.M)
            if sorted(plan_ids) != sorted(ids) or any(re.match(r'^\s*-\s*\[\s*[~ ]\s*\]', x) for x in plan_lines):
                raise Invalid()
            lines = visible(safe_read(root, rel + '/verify.md').decode())
        strict_report = marked is not None
        if (section(lines, 'Candidate', marked=strict_report) != [candidate]
                or section(lines, 'Mandatory checks', marked=strict_report) != ['- [x] structural', '- [x] tests', '- [x] review']
                or section(lines, 'Overall Decision', marked=strict_report) != ['- [x] PASS']):
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
            if not isinstance(record, dict) or not isinstance(record.get('id'), str):
                raise Invalid()
            if policy:
                from task_dag import ContractError
                try:
                    extra = policy.evidence(record)
                except ContractError as error:
                    raise InvalidContract(str(error)) from error
            else:
                extra = set()
            if set(record) != {'id', 'plan', 'red', 'green'} | extra or record['id'] != record['plan']:
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
            'notice': 'self-reported records are not independent proof', **(policy.result() if policy else {})}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['planning', 'preflight', 'candidate', 'verify'])
    for name in ('repo', 'base', 'change'):
        parser.add_argument('--' + name, required=name == 'change')
    args = parser.parse_args()
    if args.command != 'planning' and (args.repo is None or args.base is None):
        parser.error('the following arguments are required: --repo, --base')
    try:
        result = planning(args.change, args.repo) if args.command == 'planning' else run(args)
    except InvalidContract as error:
        print(json.dumps({'status': 'error', 'message': str(error)}))
        return 1
    except (Invalid, OSError, UnicodeError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
        print(json.dumps({'status': 'error', 'message': 'invalid, missing, incomplete or stale input'}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
