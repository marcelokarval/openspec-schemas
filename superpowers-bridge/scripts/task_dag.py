#!/usr/bin/env python3
"""Project declared dependencies and checkboxes without changing a change directory."""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
from dataclasses import dataclass, field
import errno
import os
from pathlib import Path
import re
import stat
import sys
import unicodedata


ID = r"[0-9]+\.[0-9]+"
PLAN_TASK = re.compile(rf"##[ \t]+Task[ \t]+({ID})(?:[ \t]*:[ \t]*(.*))?[ \t]*$")
CHECKBOX = re.compile(rf"-[ \t]+\[([ xX~])\][ \t]+({ID})(?:[ \t]+(.*))?[ \t]*$")
LIST_ITEM = r"[-+*]|[0-9]+[.)]"
CHECKBOX_CANDIDATE = re.compile(rf"^\s*(?:(?:{LIST_ITEM})\s+|>\s*)*(?:{LIST_ITEM})\s*\[")
PENDING_STATE = re.compile(r"([ \t~]+)\](?=[ \t]|$)")
SECTION = re.compile(r"^ {0,3}#{1,2}(?:[ \t]|$)")
SETEXT_UNDERLINE = re.compile(r" {0,3}(?:-+|=+)[ \t]*")
NON_PARAGRAPH = re.compile(r"^ {0,3}(?:#{1,6}(?:[ \t]|$)|>|(?:[-+*]|[0-9]{1,9}[.)])[ \t])")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
RAW_HTML = re.compile(r"^[ \t]*<(?:[!?]|/?[A-Za-z][A-Za-z0-9-]*(?=[ \t/>]|$))")
INLINE_COMMENT_TOKEN = re.compile(r"`+|<!--|-->")
DEPENDS_ON = "- Depends on:"
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024
NOTE = ("[x] is not acceptance; [~] does not prove execution or satisfy dependencies. "
        "Readiness does not imply authorization or safe parallelism.")
CONTRACT_MARKER = "Bridge task contract: 1"
MARKER_PREFIX = re.compile(r"^ {0,3}Bridge[ \t]+task[ \t]+contract[ \t]*:", re.I | re.ASCII)
PROSE_FIELDS = ("Outcome", "Owner/resolver", "Inputs", "Acceptance", "Stop", "Resume")
LIST_FIELDS = ("Write paths", "Exclusions", "Shared resources")
CONTRACT_FIELDS = frozenset((*PROSE_FIELDS, *LIST_FIELDS, "Needs", "Produces", "Depends on"))
FIELD_PREFIX = re.compile(rf"^([ \t]*)({LIST_ITEM})[ \t]+")
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*")
PATH_PART = re.compile(r"[A-Za-z0-9_.@+-]+")
PLACEHOLDER = re.compile(r"\b(?:TBD|TODO|TBA|FIXME)\b|<[^<>]*>|\{\{[^{}]*\}\}", re.I)
MAX_CLAIM_LENGTH = 1024


class ContractError(ValueError):
    """A structural error safe to report without echoing raw content."""


@dataclass
class PlannedTask:
    title: str
    parents: tuple[str, ...] | None = None
    fields: dict[str, list[str]] = field(default_factory=dict)
    output: str = ""
    needs: dict[str, str] = field(default_factory=dict)
    writes: tuple[str, ...] = ()
    resources: tuple[str, ...] = ()


def id_key(task_id):
    # Sort numerically without converting untrusted decimal strings to integers.
    parts = [part.lstrip("0") for part in task_id.split(".")]
    return tuple((len(part), part) for part in parts), task_id


def is_escaped(line, start):
    backslash_start = start
    while backslash_start > 0 and line[backslash_start - 1] == "\\":
        backslash_start -= 1
    return (start - backslash_start) % 2 == 1


def strip_comments(line, *, strict, allow_block):
    # Strict artifacts never carry inline syntax into a subsequent line.
    # Marker discovery still skips legacy comment blocks used as examples.
    parts = []
    scan = keep_from = code_width = 0
    ambiguity = None
    while (match := INLINE_COMMENT_TOKEN.search(line, scan)) is not None:
        token = match[0]
        scan = match.end()
        start = match.start()
        if token.startswith("`"):
            width = len(token)
            if not code_width:
                # A backslash can escape the first backtick outside code only.
                code_width = width - is_escaped(line, start)
            elif code_width == width:
                code_width = 0
            continue
        if is_escaped(line, start):
            ambiguity = ambiguity or "escaped comment delimiter"
            continue
        if code_width:
            ambiguity = ambiguity or "comment delimiter in inline code or after an unmatched backtick run"
            continue
        if token == "<!--":
            end = line.find("-->", scan)
            if end == -1 and (strict or not allow_block or not re.match(r"^ {0,3}\S", line)):
                ambiguity = ambiguity or "comment must close on the same line"
                # Keep this opener literal even during marker discovery.
                break
            # A space prevents joining fragments into a structural token.
            parts.extend((line[keep_from:start], " "))
            if end == -1:
                return "".join(parts), True, ambiguity
            scan = keep_from = end + 3
    if strict and code_width:
        ambiguity = ambiguity or "inline code must close on the same line"
    return "".join((*parts, line[keep_from:])), False, ambiguity


def valid_fence_opener(marker):
    return marker is not None and (marker[1][0] == "~" or "`" not in marker[2])


def content_lines(text, *, contract=False, strict=False, artifact="plan.md"):
    """Recognize only our Markdown subset, skipping fenced examples and block comments."""
    fence = None
    comment = False

    def check_markup(line, number, *, allow_block=True):
        comment_open = False
        if "<!--" in line or "-->" in line or (strict and "`" in line):
            line, comment_open, ambiguity = strip_comments(line, strict=strict, allow_block=allow_block)
            if strict and ambiguity:
                raise ContractError(f"{artifact}:{number}: {ambiguity}; use a fenced example")
        if strict and RAW_HTML.match(line):
            raise ContractError(f"{artifact}:{number}: raw HTML blocks are not supported; use a fenced example")
        return line, comment_open

    # Text files are read with universal newlines. Unicode separators in titles
    # must not turn into structural line breaks.
    for number, line in enumerate(text.split("\n"), 1):
        marker = FENCE.match(line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                if not marker[2].strip(" \t"):
                    fence = None
            continue
        if not contract and (comment or line.lstrip(" \t").startswith("<!--")):
            comment = "-->" not in line
            continue
        if contract and comment:
            _, close, suffix = line.partition("-->")
            if close:
                _, comment = check_markup(suffix, number, allow_block=False)
            continue
        if strict and line.startswith((" ", "\t")) and valid_fence_opener(FENCE.match(line.lstrip(" \t"))):
            raise ContractError(f"{artifact}:{number}: indented fence opener; start examples in column 0")
        if valid_fence_opener(marker):
            fence = marker[1]
            continue
        if contract:
            # Keep source line numbers; an inline comment cannot supply a field value.
            line, comment = check_markup(line, number)
        yield number, line
    if strict and (fence or comment):
        raise ContractError(f"{artifact}: unclosed fence or comment")


def marked_contract(text):
    markers = [line for _, line in content_lines(text, contract=True) if MARKER_PREFIX.match(line)]
    if len(markers) > 1 or (markers and markers[0].strip(" \t") != CONTRACT_MARKER):
        raise ContractError("plan.md: unknown, malformed or duplicate bridge task contract marker")
    return bool(markers)


def contract_lines(text, artifact="plan.md"):
    return content_lines(text, contract=True, strict=True, artifact=artifact)


def pending_checkbox(line):
    prefix = CHECKBOX_CANDIDATE.match(line)
    state = PENDING_STATE.match(line, prefix.end()) if prefix else None
    if not state:
        return False
    mark = state[1].strip(" \t")
    return mark == "~" or (not mark and " " in state[1])


def marked_field(line, number, task_id):
    prefix = FIELD_PREFIX.match(line)
    if not prefix:
        return None
    name, colon, value = line[prefix.end():].partition(":")
    name = " ".join(name.split())
    if not colon or name not in CONTRACT_FIELDS:
        return None
    if prefix[1] or prefix[2] != "-":
        raise ContractError(f"plan.md:{number}: task {task_id}: {name} requires an unindented '-' list item")
    return name, value.strip(" \t")


def read_plan(text, *, marked=False):
    tasks = {}
    current = None
    previous_number, previous_paragraph = 0, False
    source = contract_lines(text) if marked else content_lines(text)
    for number, line in source:
        underline = SETEXT_UNDERLINE.fullmatch(line)
        setext_heading = underline and previous_paragraph and number == previous_number + 1
        previous_number = number
        previous_paragraph = (bool(line.strip(" \t")) and not underline
                              and not line.startswith(("    ", "\t"))
                              and not NON_PARAGRAPH.match(line))
        match = PLAN_TASK.fullmatch(line)
        if match:
            current, title = match.groups()
            if current in tasks:
                raise ValueError(f"plan.md:{number}: duplicate task ID {current}")
            tasks[current] = PlannedTask(title or "")
        elif SECTION.match(line) or setext_heading:
            current = None
        elif current is not None:
            if marked:
                field_decl = marked_field(line, number, current)
            else:
                field_decl = (("Depends on", line[len(DEPENDS_ON):].strip(" \t"))
                              if line.startswith(DEPENDS_ON) else None)
            if field_decl is None:
                continue
            name, value = field_decl
            task = tasks[current]
            if name != "Depends on":
                task.fields.setdefault(name, []).append(value)
                continue
            location = f"plan.md:{number}: task {current}"
            if task.parents is not None:
                raise ValueError(f"{location}: duplicate Depends on declaration")
            parents = () if value == "none" else tuple(
                parent.strip(" \t") for parent in value.split(",")
            )
            if not all(re.fullmatch(ID, parent) for parent in parents):
                raise ValueError(f"{location}: invalid Depends on value; expected none or task IDs")
            if len(set(parents)) != len(parents):
                raise ValueError(f"{location}: duplicate dependency")
            task.parents = tuple(sorted(parents, key=id_key))
    return tasks


def read_checkboxes(text, *, marked=False):
    tasks = {}
    source = contract_lines(text, "tasks.md") if marked else content_lines(text)
    for number, line in source:
        match = CHECKBOX.fullmatch(line)
        if marked and CHECKBOX_CANDIDATE.match(line) and (not match or not match[3] or not prose(match[3])):
            raise ContractError(f"tasks.md:{number}: expected a top-level checkbox with a task ID and description")
        if match:
            mark, task_id, title = match.groups()
            if task_id in tasks:
                raise ValueError(f"tasks.md:{number}: duplicate task ID {task_id}")
            tasks[task_id] = (mark.lower(), title or "")
    return tasks


def prose(value):
    return (any(char.isalnum() for char in value) and not PLACEHOLDER.search(value)
            and value.strip(" `*_[]().").lower() not in {"none", "n/a", "na", "pending", "placeholder"})


def token(value):
    return len(value) <= MAX_CLAIM_LENGTH and TOKEN.fullmatch(value) and prose(value)


def exact_path(value):
    return (len(value) <= MAX_CLAIM_LENGTH and value.lower() != "none" and not PLACEHOLDER.search(value)
            and all(part not in {".", ".."} and PATH_PART.fullmatch(part) for part in value.split("/")))


def path_prefixes(path):
    return (path[:match.start()] for match in re.finditer("/", path))


def validate_task(task_id, task):
    def invalid(message):
        raise ContractError(f"plan.md: task {task_id}: {message}")

    def required(name):
        values = task.fields.get(name, [])
        if len(values) != 1 or not values[0]:
            invalid(f"expected one nonempty {name} declaration")
        return values[0]

    def claims(name, valid):
        value = required(name)
        items = () if value == "none" else tuple(item.strip(" \t") for item in value.split(","))
        if len(items) != len(set(items)) or not all(valid(item) for item in items):
            invalid(f"invalid {name}; expected unique exact entries or none")
        return items

    if task.parents is None:
        invalid("missing Depends on declaration")
    for name in PROSE_FIELDS:
        value = required(name)
        if not (name == "Inputs" and value == "none") and not prose(value):
            invalid(f"{name} needs a concrete value")
    task.output = required("Produces")
    if not token(task.output):
        invalid("Produces needs an exact output identifier")
    task.writes = claims("Write paths", exact_path)
    exclusions = set(claims("Exclusions", exact_path))
    writes = set(task.writes)
    if (exclusions & writes or any(exclusions.intersection(path_prefixes(p)) for p in writes)
            or any(writes.intersection(path_prefixes(p)) for p in exclusions)):
        invalid("Write paths overlap Exclusions")
    task.resources = claims("Shared resources", token)

    values = task.fields.get("Needs", [])
    if not task.parents and values == ["none"]:
        return
    for value in values:
        match = re.fullmatch(rf"({ID})[ \t]+=>[ \t]+({TOKEN.pattern})", value)
        if not match or not token(match[2]) or match[1] in task.needs:
            invalid("Needs requires one exact output per dependency (or none for a root)")
        task.needs[match[1]] = match[2]
    if not task.parents or task.needs.keys() != set(task.parents):
        invalid("Needs must name exactly the IDs in Depends on (or none for a root)")


def read_contract(plan_text, tasks_text):
    """Validate marked content and return the same graph model used by the DAG CLI."""
    try:
        plan = read_plan(plan_text, marked=True)
        boxes = read_checkboxes(tasks_text, marked=True)
        graph = derive_graph(plan, boxes)
        for task_id in graph[0]:
            validate_task(task_id, plan[task_id])
        for task_id in graph[0]:
            for parent, output in plan[task_id].needs.items():
                if output != plan[parent].output:
                    raise ContractError(f"plan.md: task {task_id}: Needs output does not match task {parent} Produces")
    except ContractError:
        raise
    except ValueError as error:
        raise ContractError(str(error)) from error
    return plan, boxes, graph


def derive_graph(plan, checkboxes):
    if plan.keys() != checkboxes.keys():
        plan_only = ", ".join(sorted(plan.keys() - checkboxes.keys(), key=id_key)) or "none"
        tasks_only = ", ".join(sorted(checkboxes.keys() - plan.keys(), key=id_key)) or "none"
        raise ValueError(f"ID mismatch: only in plan.md: {plan_only}; only in tasks.md: {tasks_only}")

    if not plan:
        raise ValueError("no task IDs in plan.md or tasks.md")

    ids = sorted(plan, key=id_key)
    children = {task_id: [] for task_id in ids}
    indegree = {}
    for task_id in ids:
        parents = plan[task_id].parents or ()
        indegree[task_id] = len(parents)
        for parent in parents:
            if parent == task_id:
                raise ValueError(f"plan.md: task {task_id}: self-dependency")
            if parent not in plan:
                raise ValueError(f"plan.md: task {task_id}: unknown dependency {parent}")
            children[parent].append(task_id)

    # Topological evaluation: only a consistent checked predecessor can
    # satisfy an edge. A checkbox alone cannot hide an unmet ancestor.
    queue = deque(task_id for task_id in ids if not indegree[task_id])
    states = {}
    while queue:
        task_id = queue.popleft()
        parents = plan[task_id].parents
        mark, _ = checkboxes[task_id]
        if parents is None:
            state = "unknown"
        elif mark == "~":
            state = "marked"
        elif all(states[parent] == "checked" for parent in parents):
            state = "checked" if mark == "x" else "ready"
        else:
            state = "inconsistent" if mark == "x" else "blocked"
        states[task_id] = state
        for child in children[task_id]:
            indegree[child] -= 1
            if not indegree[child]:
                queue.append(child)
    if len(states) != len(ids):
        affected = ", ".join(task_id for task_id in ids if indegree[task_id])
        raise ValueError(f"plan.md: dependency cycle prevents ordering: {affected}")
    return ids, children, states


def clean_title(text):
    # No entities, directives, HTML, escapes or Markdown syntax from input.
    text = re.sub(r"<!--.*?-->", "", text)
    safe = "".join(
        char if unicodedata.category(char)[0] in "LMN" or char in " .,:()/+-" else " "
        for char in text
    )
    return " ".join(safe.split()).strip(" .")


def render_ascii(ids, plan, checkboxes, children, states, titles, claims=None):
    def endpoints(members):
        return members[0] if len(members) == 1 else "{" + ", ".join(members) + "}"

    lines = ["Task DAG (declared edges; prerequisite --> dependent)"]
    for task_id in ids:
        parents = plan[task_id].parents
        if children[task_id]:
            lines.append(f"  {task_id} --> {endpoints(children[task_id])}")
        elif not parents:
            lines.append(f"  {task_id} ({'unknown' if parents is None else 'no edges'})")
        if parents and len(parents) > 1:
            lines.append(f"  {endpoints(parents)} --> {task_id} (join)")

    rows = [("ID", "Box", "Status", "Depends on", "Title")]
    for task_id in ids:
        parents = plan[task_id].parents
        depends = "unknown" if parents is None else ", ".join(parents) or "none"
        rows.append((task_id, f"[{checkboxes[task_id][0]}]",
                     states[task_id], depends, titles[task_id]))
    # Cap alignment padding without truncating any cell.
    widths = [min(24, max(map(len, column))) for column in zip(*(row[:-1] for row in rows))]
    lines.append("")
    for row in rows:
        lines.append("  ".join(value.ljust(width) for value, width in zip(row[:-1], widths))
                     + "  " + row[-1])
    if claims is None:
        ready = ", ".join(task_id for task_id in ids if states[task_id] == "ready")
        claims = [f"Next front: {ready or 'none'}"]
    lines.extend(("", *claims, NOTE))
    return "\n".join(lines)


def render_mermaid(ids, checkboxes, children, states, titles):
    node = {task_id: "task_" + task_id.replace(".", "_") for task_id in ids}
    lines = ["flowchart LR", f"    %% {NOTE}"]
    for task_id in ids:
        mark = " [~]" if checkboxes[task_id][0] == "~" else ""
        label = f"{task_id} {titles[task_id]}{mark} ({states[task_id]})"
        lines.append(f'    {node[task_id]}["{label}"]')
    lines.extend(f"    {node[i]} --> {node[child]}" for i in ids for child in children[i])
    return "\n".join(lines)


def project_claims(ids, plan, states):
    """Show declared overlaps; reserve marked claims before greedily selecting ready IDs."""
    paths = defaultdict(set)
    resources = defaultdict(set)
    ready = [task_id for task_id in ids if states[task_id] == "ready"]
    for task_id in ids:
        for path in plan[task_id].writes:
            paths[path].add(task_id)
        for resource in plan[task_id].resources:
            resources[resource].add(task_id)
    path_groups = {path: owners.copy() for path, owners in paths.items()}
    for path, owners in paths.items():
        for prefix in path_prefixes(path):
            if prefix in path_groups:
                path_groups[prefix].update(owners)

    locked_paths, locked_prefixes, locked_resources = set(), set(), set()

    def reserve(task):
        locked_paths.update(task.writes)
        for path in task.writes:
            locked_prefixes.update(prefix for prefix in path_prefixes(path) if prefix in paths)
        locked_resources.update(task.resources)

    for task_id in ids:
        if states[task_id] == "marked":
            reserve(plan[task_id])
    front = []
    for task_id in ready:
        task = plan[task_id]
        if locked_resources.intersection(task.resources) or any(
            path in locked_paths or path in locked_prefixes
            or locked_paths.intersection(path_prefixes(path)) for path in task.writes
        ):
            continue
        front.append(task_id)
        reserve(task)

    conflicts = [f"  {kind} {claim}: {', '.join(sorted(owners, key=id_key))}"
                 for kind, groups in (("path", path_groups), ("resource", resources))
                 for claim, owners in sorted(groups.items()) if len(owners) > 1]
    return [f"Dependency ready: {', '.join(ready) or 'none'}",
            "Declared conflicts (not edges):", *(conflicts or ["  none"]),
            f"Next front: {', '.join(front) or 'none'}",
            "Projection covers declared conflicts only; [~] reserves claims without proving execution."]


def decode_artifact(data, *, errors="strict"):
    return data.decode("utf-8-sig", errors).replace("\r\n", "\n").replace("\r", "\n")


def read_artifact(change_fd, name):
    try:
        mode = os.stat(name, dir_fd=change_fd, follow_symlinks=False).st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f"{name}: symbolic links are not allowed")
        if not stat.S_ISREG(mode):
            raise ValueError(f"{name}: expected a regular file")
        # Recheck the opened descriptor: the directory entry may have changed.
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=change_fd)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError(f"{name}: expected a regular file")
            if before.st_size > MAX_ARTIFACT_BYTES:
                raise ValueError(f"{name}: exceeds 4 MiB")
            with os.fdopen(fd, "rb", closefd=False) as source:
                data = source.read(before.st_size + 1)
            if len(data) > MAX_ARTIFACT_BYTES:
                raise ValueError(f"{name}: exceeds 4 MiB")
            after = os.fstat(fd)
            if (len(data) != before.st_size or before.st_size != after.st_size
                    or before.st_mtime_ns != after.st_mtime_ns
                    or before.st_ctime_ns != after.st_ctime_ns):
                raise ValueError(f"{name}: changed during read")
        finally:
            os.close(fd)
    except OSError as error:
        reason = ("symbolic links are not allowed" if error.errno == errno.ELOOP
                  else error.strerror)
        raise ValueError(f"cannot read {name}: {reason}") from error
    try:
        return decode_artifact(data)
    except UnicodeError as error:
        raise ValueError(f"cannot read {name}: not valid UTF-8") from error


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--change", required=True, type=Path, help="directory with plan.md and tasks.md")
    parser.add_argument("--format", choices=("ascii", "mermaid"), default="ascii")
    args = parser.parse_args(argv)

    try:
        if not all(hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")):
            raise ValueError("safe artifact reads are not supported on this platform")
        try:
            change_fd = os.open(args.change, os.O_RDONLY | os.O_DIRECTORY)
        except OSError as error:
            raise ValueError(f"cannot open change directory: {error.strerror}") from error
        try:
            plan_text = read_artifact(change_fd, "plan.md")
            marked = marked_contract(plan_text)
            if not marked:
                plan = read_plan(plan_text)
            tasks_text = read_artifact(change_fd, "tasks.md")
        finally:
            os.close(change_fd)
        if marked:
            plan, checkboxes, (ids, children, states) = read_contract(plan_text, tasks_text)
        else:
            checkboxes = read_checkboxes(tasks_text)
            ids, children, states = derive_graph(plan, checkboxes)
    except ValueError as error:
        print(f"task_dag: {error}", file=sys.stderr)
        return 2

    titles = {task_id: clean_title(plan[task_id].title) or clean_title(checkboxes[task_id][1])
              or "Task" for task_id in ids}
    claims = project_claims(ids, plan, states) if marked else None
    if args.format == "ascii":
        rendered = render_ascii(ids, plan, checkboxes, children, states, titles, claims)
    else:
        rendered = render_mermaid(ids, checkboxes, children, states, titles)
        if claims is not None:
            rendered += "\n" + "\n".join(f"    %% {line}" for line in claims)
    print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
