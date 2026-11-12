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
python3 '<bundle>/scripts/bridge_guard.py' preflight --repo '<repo>' --base '<base>' --change '<change>'
python3 '<bundle>/scripts/bridge_guard.py' candidate --repo '<repo>' --base '<base>' --change '<change>'
python3 '<bundle>/scripts/bridge_guard.py' verify --repo '<repo>' --base '<base>' --change '<change>'
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
are bounded to 4 MiB. The supported Markdown fence syntax allows 0–3 leading
spaces; ambiguous indented fences are rejected.

Map skills to observed native names, e.g. `brainstorming` or
`superpowers:brainstorming`, and record actual invocation. Supported subagent
mode requires authorization; inline mode still needs TDD and review. Discovery
alone is not proof of loading or behavior. Commits, new workspaces, installs,
archive, release, PR, push and merge require separate authorization. Archive is
not human acceptance or release. Optional checks cannot replace mandatory checks
without owner approval.

## Migration from v1

Version 2 changes the verification format and adds the guard. Preserve existing
consumer artifacts and history; do not overwrite or delete them automatically.
With owner authorization, update the bundle and migrate active change task IDs,
plan evidence and verification into the v2 format, then run preflight afresh.
Do not reinterpret old empty or absent FAIL checkboxes as PASS. Installation and
upgrade actions are outside this guidance and require their own authorization.
Earlier v2 string-only manifests and result-only test records must migrate to
the explicit final-state entries and outcome fields above.
