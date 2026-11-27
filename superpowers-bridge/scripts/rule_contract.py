"""Structural business-rule contract. No semantic inference or external resolver."""
from dataclasses import dataclass, field
import re

from task_dag import (ContractError, FENCE, NON_PARAGRAPH, PLAN_TASK, SECTION, SETEXT_UNDERLINE,
                      content_lines, contract_lines, decode_artifact, exact_path, id_key, valid_fence_opener)

MARKER = 'Bridge rule contract: 1'
DECISIONS = ('approved', 'proposed', 'blocked')
MARKER_PREFIX = re.compile(r'^ {0,3}Bridge[ \t]+rule[ \t]+contract[ \t]*:', re.I | re.ASCII)
SUFFIX = r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}'
BR, AC = 'BR-' + SUFFIX, 'AC-' + SUFFIX
PAIR = re.compile(rf'({BR}) => ({AC})')
ANCHOR = r'[A-Za-z][A-Za-z0-9_-]{0,95}'
REFERENCE = re.compile(rf'({BR}) => ([^#\s]+)#({ANCHOR})')
FIELD = re.compile(r'^(Rule reference|Rule|Decision|Scenario ID|Rule scenario|Rule readiness):[ \t]*(.*)$')
TASK_FIELD_PREFIX = re.compile(r'^ {0,3}(?:[-+*][ \t]+)?Rule[ \t]+(?:scenario|readiness)[ \t]*:', re.I | re.ASCII)
HEADING = re.compile(r'^ {0,3}(#{1,6})(?:[ \t]+(.*)|$)')


def plan_marker(data):
    markers, fields = [], False
    for _, line in content_lines(decode_artifact(data, errors='replace'), contract=True):
        if MARKER_PREFIX.match(line):
            markers.append(line)
        fields |= bool(TASK_FIELD_PREFIX.match(line))
    if markers and markers != [MARKER]:
        raise ContractError(f'plan.md: expected one exact {MARKER} marker')
    if fields and not markers:
        raise ContractError(f'plan.md: Rule scenario/readiness requires {MARKER}')
    return bool(markers)


def spec_lines(lines, path):
    # Delta templates use standalone multiline HTML comments. Preserve line numbers
    # and let the shared strict parser police the remaining visible Markdown.
    lines = lines.copy()
    fence, comment = None, False
    for i, line in enumerate(lines):
        if comment:
            _, end, tail = line.partition('-->')
            if end and tail.strip():
                raise ContractError(f'{path}:{i+1}: close block comments on a separate line')
            comment = not end
            lines[i] = ''
            continue
        marker = FENCE.match(line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
        elif valid_fence_opener(marker):
            fence = marker[1]
        elif re.match(r'^ {0,3}<!--', line) and '-->' not in line:
            comment = True
            lines[i] = ''
    if comment:
        raise ContractError(f'{path}: unclosed block comment')
    return contract_lines('\n'.join(lines), path)


@dataclass
class Scenario:
    where: str
    title: str
    id: str = ''

    def location(self):
        return f'{self.where}: scenario {self.title[:160]!r}'


@dataclass
class Requirement:
    where: str
    anchor: str | None
    heading: str | None
    modified: bool
    decisions: list = field(default_factory=list)
    scenario_headings: list = field(default_factory=list)
    rule: str = ''
    decision: str = ''
    reference: tuple | None = None
    scenarios: set = field(default_factory=set)


def section_lines(lines):
    """Preserve the same Setext section boundaries as the marked task parser."""
    prev, paragraph = 0, False
    for n, line in lines:
        underline = SETEXT_UNDERLINE.fullmatch(line)
        yield n, line, bool(underline and paragraph and prev + 1 == n)
        prev = n
        paragraph = (bool(line.strip()) and not underline and not line.startswith(('    ', '\t'))
                     and not NON_PARAGRAPH.match(line))


HISTORICAL_TITLE = r'(?:REMOVED|RENAMED)[ \t]+Requirements'


def requirements(data, path, *, delta):
    result = []
    req = None
    scenario = None
    depth = 0
    active, modified = not delta, False
    raw_lines = decode_artifact(data).split('\n')
    previous_line = ''
    for n, line, setext in section_lines(spec_lines(raw_lines, path)):
        if setext:
            # A '-' underline is an H2; its title was the preceding visible line.
            historical = line.lstrip().startswith('-') and re.fullmatch(HISTORICAL_TITLE, previous_line.strip())
            active = not delta and not historical
            req = None
            scenario = None
            continue
        previous_line = line
        where = f'{path}:{n}'
        heading = HEADING.match(line)
        if heading:
            depth = len(heading[1])
            title = (heading[2] or '').strip()
            if depth <= 2:
                if delta:
                    modified = depth == 2 and title == 'MODIFIED Requirements'
                    active = modified or (depth == 2 and title == 'ADDED Requirements')
                else:
                    # Canonical sources need no delta heading. Exclude only an
                    # explicit historical H2 and its children from the rule index.
                    active = depth != 2 or not re.fullmatch(HISTORICAL_TITLE + r'(?:[ \t]+#+)?', title)
            if depth <= 3:
                req = None
                if active and depth == 3 and re.fullmatch(r'Requirement:[ \t]+\S.*', title):
                    anchor = re.search(rf' \{{#({ANCHOR})\}}$', title)
                    # Compare the source heading, with the explicit anchor intact;
                    # display normalization must not make different archive keys equal.
                    raw = raw_lines[n - 1]
                    key = raw[len('### Requirement:'):].strip() if raw.startswith('### Requirement:') else None
                    req = Requirement(where, anchor[1] if anchor else None, key, modified)
                    result.append(req)
            if depth <= 4:
                scenario = None
                if req and depth == 4 and title.startswith('Scenario:'):
                    scenario = Scenario(where, title[len('Scenario:'):].strip() or '<unnamed>')
                    req.scenario_headings.append(scenario)
            continue
        if not active:
            continue
        match = FIELD.fullmatch(line.rstrip(' \t'))
        if not match:
            continue
        key, value = match.groups()
        if req is None or key in ('Rule scenario', 'Rule readiness'):
            raise ContractError(f'{where}: {key} requires the appropriate Requirement or task section')
        if key == 'Scenario ID':
            if depth != 4 or scenario is None:
                raise ContractError(f'{where}: Scenario ID requires a #### Scenario: heading')
            if scenario.id or not re.fullmatch(AC, value) or value in req.scenarios:
                raise ContractError(f'{scenario.location()}: expected exactly one unique Scenario ID (AC-...)')
            scenario.id = value
            req.scenarios.add(value)
        elif key == 'Decision':
            # Interpret Decision in context after the entire requirement is read.
            req.decisions.append((where, depth, value))
        elif depth != 3:
            raise ContractError(f'{where}: declare {key} directly under ### Requirement:')
        elif key == 'Rule' and not req.rule and re.fullmatch(BR, value):
            req.rule = value
        elif key == 'Rule reference' and not req.rule and (ref := REFERENCE.fullmatch(value)):
            req.rule = ref[1]
            req.reference = ref[2], ref[3]
        else:
            raise ContractError(f'{where}: malformed or duplicate {key} declaration')
    for req in result:
        if not req.rule and not req.scenarios:
            for where, _, value in req.decisions:
                if value in DECISIONS:
                    raise ContractError(f'{where}: Decision: {value} requires a Rule declaration')
            continue
        if not req.rule:
            raise ContractError(f'{req.where}: Scenario ID requires Rule or Rule reference')
        for where, depth, value in req.decisions:
            if depth != 3:
                raise ContractError(f'{where}: declare Decision directly under ### Requirement:')
            if req.decision or value not in DECISIONS:
                raise ContractError(f'{where}: expected one Decision: approved|proposed|blocked')
            req.decision = value
        if bool(req.decision) == bool(req.reference):
            raise ContractError(f'{req.where}: use Rule and Decision together, or Rule reference alone')
        for scenario in req.scenario_headings:
            if not scenario.id:
                raise ContractError(f'{scenario.location()}: expected exactly one Scenario ID (AC-...)')
    return result


@dataclass
class Policy:
    links: dict = field(default_factory=dict)
    blocked: list = field(default_factory=list)

    def result(self):
        return {'rule_blocked_tasks': sorted(self.blocked, key=id_key)}

    def evidence(self, record):
        task = record.get('id')
        pairs = self.links.get(task)
        if not pairs:
            return set()
        proofs = record.get('rule_scenarios')
        if isinstance(proofs, list) and len(proofs) == len(pairs):
            actual = set()
            for item in proofs:
                if (not isinstance(item, dict) or set(item) != {'rule', 'scenario', 'proof'}
                        or item['proof'] != 'policy_test' or not isinstance(item['rule'], str)
                        or not isinstance(item['scenario'], str)):
                    break
                actual.add((item['rule'], item['scenario']))
            else:
                if actual == pairs:
                    return {'rule_scenarios'}
        raise ContractError(f'evidence.json: task {task}: rule_scenarios needs one policy_test per declared pair')


def task_fields(plan):
    task = None
    for n, line, setext in section_lines(contract_lines(plan)):
        if match := PLAN_TASK.fullmatch(line):
            task = match[1]
        elif SECTION.match(line) or setext:
            task = None
        match = FIELD.fullmatch(line.rstrip(' \t'))
        if not match and TASK_FIELD_PREFIX.match(line):
            raise ContractError(f'plan.md:{n}: task {task or "outside section"}: use an unindented Rule scenario or Rule readiness line')
        if match:
            if not task or match[1] not in ('Rule scenario', 'Rule readiness'):
                raise ContractError(f'plan.md:{n}: {match[1]} requires the appropriate task or Requirement section')
            yield task, n, match[1], match[2]


def validate(plan, boxes, specs, load, *, spec_prefix, baseline_prefix):
    definitions, ownership, required_pairs = {}, {}, set()
    anchors, sources, replacements = {}, {}, {}
    used_rules, targets = set(), set()
    references = []

    def register(req, local):
        if not req.reference:
            if req.rule in definitions:
                raise ContractError(f'{req.where}: duplicate Rule {req.rule}')
            definitions[req.rule] = req.decision
        for ac in req.scenarios:
            if ac in ownership:
                raise ContractError(f'{req.where}: duplicate Scenario ID {ac}')
            ownership[ac] = req.rule
            if local:
                required_pairs.add((req.rule, ac))

    # Index local declarations first, so a consumer cannot change the effective
    # rule depending on the order in which spec files are read.
    for path, data in sorted(specs.items()):
        for req in requirements(data, path, delta=True):
            if not req.rule:
                continue
            used_rules.add(req.rule)
            register(req, True)
            if req.reference:
                references.append(req)
            elif req.modified and req.heading and baseline_prefix is not None:
                parts = path.removeprefix(spec_prefix).split('/')
                if len(parts) == 3 and parts[0] == 'specs' and parts[-1] == 'spec.md':
                    replacements[req.rule] = (baseline_prefix + '/'.join(parts), req.heading)

    for req in references:
        source, anchor = req.reference
        if (not exact_path(source) or not source.endswith('.md')
                or any(p.startswith('.') for p in source.split('/'))):
            raise ContractError(f'{req.where}: Rule reference requires an exact repository-relative Markdown path')
        if source not in sources:
            sources[source] = requirements(load(source), source, delta=False)
            index = anchors[source] = {}
            for entry in sources[source]:
                if entry.anchor:
                    if entry.anchor in index:
                        raise ContractError(f'{source}: ambiguous Rule reference anchor')
                    index[entry.anchor] = entry
        target = anchors[source].get(anchor)
        if not target or target.reference or target.rule != req.rule:
            raise ContractError(f'{req.where}: Rule reference must resolve to the definition of {req.rule}')
        targets.add((source, anchor))

    for source, entries in sources.items():
        for entry in entries:
            if not entry.rule or entry.reference:
                continue
            # The canonical file was still read and bound. Only its replaced
            # obligation (decision/scenario IDs) is omitted from the active index.
            if ((source, entry.anchor) in targets
                    and replacements.get(entry.rule) == (source, entry.heading)):
                continue
            register(entry, False)

    policy, readiness, covered = Policy(), {}, set()
    for task, n, key, value in task_fields(plan):
        where = f'plan.md:{n}: task {task}'
        if key == 'Rule scenario':
            pair = PAIR.fullmatch(value)
            if not pair:
                raise ContractError(f'{where}: expected Rule scenario: BR-id => AC-id')
            br, ac = pair.groups()
            if br not in used_rules or br not in definitions or ownership.get(ac) != br:
                raise ContractError(f'{where}: Scenario {ac} is not defined for Rule {br}')
            pairs = policy.links.setdefault(task, set())
            if (br, ac) in pairs:
                raise ContractError(f'{where}: duplicate Rule scenario')
            pairs.add((br, ac))
            covered.add((br, ac))
        else:
            if task in readiness or value not in ('ready', 'blocked'):
                raise ContractError(f'{where}: expected one Rule readiness: ready|blocked')
            readiness[task] = value
    if not definitions:
        raise ContractError('specs: rule contract requires at least one material Rule or Rule reference')
    if missing := sorted(required_pairs - covered):
        raise ContractError(f'plan.md: missing Rule scenario: {missing[0][0]} => {missing[0][1]}')
    if missing := sorted(used_rules - {br for br, _ in covered}):
        raise ContractError(f'plan.md: no Rule scenario covers {missing[0]}')
    for task in sorted(policy.links.keys() | readiness.keys(), key=id_key):
        if task not in policy.links or task not in readiness:
            raise ContractError(f'plan.md: task {task}: declare both Rule scenario and Rule readiness')
        if readiness[task] == 'blocked':
            policy.blocked.append(task)
            if boxes[task][0] == 'x':
                raise ContractError(f'tasks.md: task {task}: rule-blocked task cannot be checked')
        elif any(definitions[br] != 'approved' for br, _ in policy.links[task]):
            raise ContractError(f'plan.md: task {task}: proposed or blocked rule requires Rule readiness: blocked')
    return policy
