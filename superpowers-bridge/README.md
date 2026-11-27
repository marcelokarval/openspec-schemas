# superpowers-bridge v2

[English](README.md) · [繁體中文](README.zh-TW.md)

This bundle connects [OpenSpec](https://github.com/Fission-AI/OpenSpec)
artifacts with [Superpowers](https://github.com/obra/superpowers) planning and
execution discipline. The schema remains prompt guidance, not runtime enforcement.
OpenSpec 2.0.0 and Superpowers 7.0.2 are source-review targets only: no
end-to-end compatibility, agent execution, or CLI validation is claimed.

## Preflight and verification

From an authorized workspace, select an explicit Git repository root, ancestor
base, and existing change directory. No remote is required. Paths are arguments,
not shell fragments; quote them. Replace `<bundle>` with this bundle's path:

```sh
python3 -B '<bundle>/scripts/bridge_guard.py' preflight --repo '<repo>' --base '<base>' --change '<change>'
python3 -B '<bundle>/scripts/bridge_guard.py' candidate --repo '<repo>' --base '<base>' --change '<change>'
python3 -B '<bundle>/scripts/bridge_guard.py' verify --repo '<repo>' --base '<base>' --change '<change>'
```

Preflight requires nonempty brainstorm, proposal, design, tasks, plan and at least
one nested `specs/**/spec.md`. Missing files STOP: do not reconstruct from conversation.
Creating or transferring a workspace requires separate authorization and another
preflight. Tasks use unique `- [ ] 1.1 description` IDs; plan steps reference
those IDs and record observed RED/GREEN and review candidate identity.

After implementation run candidate. Put its candidate digest alone in
`verify.md` under `## Candidate`. Under `## Mandatory checks` put exactly the
three lines `- [x] structural`, `- [x] tests`, `- [x] review` when each is
actually evidenced. Under `## Overall Decision`, use only `- [x] PASS` after
all mandatory work and gaps are resolved. Other states are not PASS. Then run
verify. Before preflight create `candidate-manifest.json` in the change, for
example `{"paths":[{"path":"src/new.py","state":"present"},{"path":"src/old.py","state":"absent"}]}`.
Paths are explicit repository-relative files, including relevant ignored files.
Preflight permits planned additions to be absent and planned deletions to exist;
candidate and verify require present files to exist and absent paths not to exist.
Existing parent components cannot be symlinks. The preflight digest is provisional.
Do not list reports or files within the change. The owner and reviewer must
check manifest completeness: omitted files and future additions are not detected.
Base, HEAD, manifest, named files and required planning/specs are bound. Symlink
components and unsupported file types are rejected. Post-verification reports
are excluded, so writing a retrospective does not invalidate the candidate.
Changes to covered bytes invalidate the digest. The guard checks formats and freshness, not whether tests ran, whether
review was independent, semantic completeness, or human acceptance.

`evidence.json` is a separate self-report, excluded from the digest to avoid a
cycle. Required shape (replace example values, and create one task record per
task ID):

```json
{"candidate":"<digest>","tasks":[{"id":"1.1","plan":"1.1","red":{"command":"test command","outcome":"expected_failure","details":"expected assertion"},"green":{"command":"test command","outcome":"passed","details":"all checks passed"}}],"structural":{"command":"validation command","result":"pass"},"review":{"reviewer":"independent reviewer identity","status":"pass","candidate":"<digest>"},"unresolved":[]}
```

RED and GREEN outcomes require these exact enums; details must not contradict
GREEN. Plan headings may be `## Task 1.1` or `## Task 1.1: Title`, with no uncompleted plan
checkboxes. The guard rejects conflict markers such as FAIL and NOT VERIFIED in
the verification report; use separate records for prior failed attempts. JSON
records remain assertions requiring independent examination. Individual files
are bounded to 4 MiB. The legacy guard fence syntax allows 0–3 leading spaces.
Marked artifacts require fence openers in column 0.

Map skills to observed native names, e.g. `brainstorming` or
`superpowers:brainstorming`, and record actual invocation. Supported subagent
mode requires authorization; inline mode still needs TDD and review. Discovery
alone is not proof of loading or behavior. Commits, new workspaces, installs,
archive, release, PR, push and merge require separate authorization. Archive is
not human acceptance or release. Optional checks cannot replace mandatory checks
without owner approval.

## Planning with task microcontracts

Decompose, review, and refine the plan before execution. Give each task one
outcome a reviewer can verify independently, and keep its supporting steps with
it. `tasks.md` stays the canonical checklist. Keep its stable IDs and proven
progress; give newly split work new IDs, update affected references in both
artifacts, and revalidate. No per-task files or separate tracker are needed.

New plans must keep one literal `Bridge task contract: 1` line. Under each
`## Task X.Y` or `## Task X.Y: Title`, fill these top-level fields as in the
template:

- `Outcome`, `Owner/resolver`, `Acceptance`, `Stop` and `Resume` require concrete
  text. Name who owns the outcome or resolves open decisions, the check that
  proves the complete outcome, when to stop, and what allows resumption.
- `Inputs` records required inputs outside the task graph, or `none`.
- `Depends on` lists prerequisite IDs, or `none`. Use one `Needs: ID => output-id`
  per prerequisite and match its `Produces` identifier exactly. A root instead
  has one `Needs: none`. `Produces` is one identifier for the delivered output;
  describe the output in `Outcome`.
- `Write paths`, `Exclusions`, and `Shared resources` are comma-separated lists,
  or `none` when empty. Paths are exact repository-relative names, with letters,
  digits, `.`, `_`, `@`, `+`, or `-` in slash-separated segments; no absolute
  paths, traversal, or globs. `Exclusions` limits this task's writes. Resource and
  output IDs start with an ASCII letter or digit and may also contain `_ . : -`.
  Each path or identifier is limited to 1,024 characters.

Fenced examples and HTML comments do not count. In marked artifacts, HTML
comments and inline code must open and close on the same line, and raw HTML
blocks are rejected. Use a fence for multiline examples or literal HTML
comment delimiters. Open each example fence in column 0, without indentation.
Outside comments and fences, marked artifacts reject backslash-escaped comment
delimiters and comment delimiters in inline code or after an unmatched backtick
run on the same line. In a marked plan, use an unindented `-` for each task microcontract field;
spaces or tabs around field names do not change which field is declared.
In `tasks.md`, use only top-level `- [ ] X.Y Description` entries
with the supported checkbox states; alternate list markers and nested task
checkboxes are rejected. The checker also rejects blank prompts, placeholders
such as `TBD`, and conflicting declarations.
Before handing off a new plan and after refining it, run:

```sh
python3 -B '<bundle>/scripts/bridge_guard.py' planning --change '<change-dir>'
```

Without rule opt-in, `planning` reads the task contract in `plan.md` and
`tasks.md`. Rule planning also reads the delta specs. No candidate manifest is
needed. For a canonical rule outside the change, use the containing Git root:

```sh
python3 -B '<bundle>/scripts/bridge_guard.py' planning --repo '<repo>' --change '<change-dir>'
```

The resolved bundle's `scripts/bridge_guard.py --help` defines the CLI.
`planning` requires `Bridge task contract: 1` in every plan it validates.
Add `Bridge rule contract: 1` only when the change involves material rules.
Unknown or duplicate
markers fail wherever the contract is read. `preflight`, `candidate`, and
`verify` also validate marked plans against `tasks.md`; candidate identity still
binds the original bytes. For marked plans, `verify` requires visible report
sections and rejects unfinished plan checkboxes on ordinary Markdown list items,
including nested items. Existing unmarked plans retain their legacy guard and
projection behavior. There is no automatic migration. A structural pass does
not prove the inputs exist, that claims are complete, or that a plan is approved.

The agent selects the rule contract when two interpretations would change an
outcome, permission or acceptance criterion. A wording change with no such effect
needs no declaration. Use the existing requirement: distinguish what a source
shows from who decided what should happen. New behavior need not have a baseline.
Give the expected outcome and a nearby case requiring a different answer.
Keep REMOVED Reason/Migration and RENAMED FROM/TO intact. A pure rename
adds no rule. For a removal or cross-cutting change, specify any changed outcome
in the affected surviving capability and reference the shared decision.

- Under `### Requirement:` write bare lines `Rule: BR-LIMIT` and `Decision: approved`
  (or `proposed` / `blocked`). Give each material `#### Scenario:` its own bare
  `Scenario ID: AC-OVER` line, using unique IDs. For a shared definition use
  `Rule reference: BR-LIMIT => policies/limits.md#limit` instead of redefining it.
  The target must be a regular Markdown file outside the change in the same repo;
  its `### Requirement: Limit {#limit}` must define that rule and decision directly.
  The guard binds the referenced file's bytes. An ordinary citation or URL may
  explain provenance but is neither resolved by this wire nor proof of behavior.
- In `plan.md` add `Bridge rule contract: 1` alongside the task marker. Under each
  materially linked task use one bare `Rule scenario: BR-LIMIT => AC-OVER` per pair
  and one `Rule readiness: ready` or `Rule readiness: blocked`. Cover every local
  declared scenario. Record a shared gap once: resolver, affected IDs and what
  permits resumption. A proposed or blocked decision blocks its tasks; no status
  grants execution. Leave blocked tasks unchecked.
- Ask: could incompatible implementations both pass these scenarios? Would the
  implementer have to invent policy? If either answer is yes, refine the affected
  decision or scenario. For each pair, test the approved outcome with TDD and link
  observed RED/GREEN to this candidate. In the task’s `evidence.json` record add
  `"rule_scenarios":[{"rule":"BR-LIMIT","scenario":"AC-OVER","proof":"policy_test"}]`,
  one entry per pair. Characterization alone cannot prove intended policy.

Before dispatch, remove `rule_blocked_tasks` from the DAG's dependency-ready
IDs and exclude all their transitive consumers. Recompute the independent batch
from remaining ready IDs, respecting reservations, actual inputs, resource and
write conflicts, and grants. Leave the DAG unchanged; `Next front` alone is
insufficient. A localized block can pass planning but prevents final verification.

Execution consumes and rechecks the approved plan. If a material input, decision,
or scope is missing, return the affected front to planning for refinement. Keep
unaffected work eligible when independently ready, free of conflicts, and
authorized; do not bypass a failed guard. Neither checker replaces Superpowers
or native orchestration.

## Task dependency projection

For each task section headed `## Task 1.2` or `## Task 1.2: Title` in
`plan.md`, write exactly one top-level line in one of these forms:

```md
- Depends on: none
- Depends on: 1.1, 1.2
```

The second form lists existing stable task IDs separated by comma and space;
use it instead of `none`, not alongside it. For example, this excerpt shows
just the dependency lines in two task sections:

```md
## Task 1.1: Prepare input
- Depends on: none

## Task 1.2: Consume input
- Depends on: 1.1
```

The DAG is derived from the plan and task checkboxes, not a new source of
authority. For multitask work, present the ASCII DAG, a task table, and the next
front by default. Generate the ASCII projection (the default) or optionally
Mermaid from the same generator:

```sh
python3 -B "<bundle>/scripts/task_dag.py" --change "<change-dir>"
python3 -B "<bundle>/scripts/task_dag.py" --change "<change-dir>" --format mermaid
```

The generator writes to stdout only by default; it does not update the plan,
checkboxes, or other files. On resumption, recompute from the current sources;
show the view again only if dependencies, checkbox state, or the next front
changed. A missing dependency line in a
legacy plan means unknown, not `none`; do not migrate or assume independence.
A checked `[x]` records task state, not acceptance, authorization, or proof of
safe parallelism. Even independent graph nodes can conflict over files or other
resources: check those conflicts and grants separately before dispatch. In the
ASCII table, `checked` means marked with consistent declared predecessors;
`ready` means an open checkbox with all declared ancestors consistently marked;
`blocked` means a predecessor is unsatisfied; `unknown` means no declaration;
`inconsistent` means marked despite an unsatisfied predecessor. In the legacy
view, `Next front` lists all `ready` IDs and makes no resource claim. `[~]`
neither proves execution nor releases a successor.

For marked plans, `Dependency ready` shows all ready IDs. `Declared conflicts`
reports shared write paths (including a declared path and its descendants) and
shared resource IDs across tasks, separately from DAG edges. `Next front` is a
deterministic batch: reserve all `[~]` claims, then consider ready IDs in numeric
order and skip any that collide with a reservation or a selected ID. Mermaid
reports the same batch and collisions as comments, never as edges. The batch
covers declared conflicts only. Read the plan and check actual inputs, claims,
and grants before dispatch. Both tools use regular UTF-8 artifacts of at most
4 MiB each and refuse symlinked artifacts and special files.

## Migration from v1

Version 2 changes the verification format and adds the guard. Preserve existing
consumer artifacts and history; do not overwrite or delete them automatically.
With owner authorization, update the bundle and migrate active change task IDs,
plan evidence and verification into the v2 format, then run preflight afresh.
Do not reinterpret old empty or absent FAIL checkboxes as PASS. Installation and
upgrade actions are outside this guidance and require their own authorization.
Earlier v2 string-only manifests and result-only test records must migrate to
the explicit final-state entries and outcome fields above.
