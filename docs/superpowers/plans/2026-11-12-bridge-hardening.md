# Bridge hardening implementation plan

**Goal:** Preserve OpenSpec artifact ownership and Superpowers execution discipline while replacing the bridge's misleading readiness checks with reproducible, local validation.

**Approved scope:** Local source checkout only. No push, PR, merge, dependency installation, global activation, additional worktree, backup, network inference, or modification of upstream repositories. The owner approved this design and authorized a Terra medium implementation agent plus a fresh Sol medium read-only reviewer.

**Architecture:** Keep this a self-contained OpenSpec schema bundle. Add a small Python-standard-library read-only guard for objective checks, with explicitly supplied change directory and Git base. The guard is an invoked validator, not a runtime enforcement hook or a semantic proof. Schema instructions and templates must call it and state what remains human/agent judgment. Preserve upstream attribution and historical records.

**Technology:** Existing YAML and Markdown; Python 3 standard library and Git for offline regression. No dependency fetching. OpenSpec CLI validation and real-agent integration remain unverified unless an already available supported runtime can be used without installation or paid inference.

## Implementation boundary

One implementation owner: native general agent, requested `omniroute/cx/gpt-6.1-terra#medium`, Standard. One new independent reviewer after the candidate is frozen: native general agent, requested `omniroute/cx/gpt-6.1-sol#medium`, Standard. Requested bindings are not provider-observation evidence. No nested delegation.

### 1. Objective readiness checks — RED, then GREEN

- Add `tests/test_bridge_guard.py` before production code. Use `unittest`, real disposable Git repositories, dummy artifacts, and no remote services. Run focused tests and observe the expected failure before implementing.
- Add `superpowers-bridge/scripts/bridge_guard.py` as a read-only CLI. Keep subcommands small and documented. At minimum validate workspace/artifact readiness, explicit Git base/HEAD identity, task tracking, and a positive, unambiguous verification verdict. Use structured JSON output and nonzero exits for missing, malformed, stale or incomplete inputs. Do not print file contents, environment, Git errors or secrets.
- Require explicit repository/base selection; never assume origin/main, origin/master, a remote, or commits as a proxy for implementation. Reject unresolved refs and paths outside the selected repository, symlink escapes and missing required artifacts. Never copy, move, stage, commit or delete consumer files.
- Before apply, prove that the named change and all required planning artifacts are visible in the selected workspace. Reuse an authorized workspace; creating or transferring one requires a separate explicit action and a repeated preflight. Missing artifacts STOP rather than reconstruction from chat.
- Verification requires exactly one positive verdict in its designated section, explicit mandatory-check results, no unresolved mandatory task/deferred gap, and candidate binding. A missing FAIL is not PASS. A record self-reported by an agent is not independent proof of test execution or approval; the contract must say so.
- Cover uppercase/spacing checkbox variants, false positives in fenced examples, empty/unselected/multiple/contradictory verdicts, changed candidate/artifacts, absent remotes, custom base names, shell metacharacters in names and paths, missing files and symlink boundaries.

### 2. Integrate the source contract — regression first

- Add source-contract regression checks before editing the schema/templates. Validate that the unsafe negative grep gate, hardcoded remote base, silent fallback and automatic archive/PR instructions are removed and replaced with explicit guard calls and human gates.
- Update `superpowers-bridge/schema.yaml`, planning/task/verify/retrospective templates, and adopter fragments. Bind plan steps to stable coarse task IDs, require RED/GREEN command evidence and review candidate identity, distinguish not verified from PASS, and keep archive separate from release and human acceptance.
- Preserve the supported subagent mode without claiming current inline Superpowers lacks TDD/review. Accept observed native skill names through an explicit capability mapping rather than requiring a plugin namespace everywhere. Do not infer that skill discovery proves loading or behavior.
- Do not introduce automatic commits, worktree creation, pushes, installs, archive, PR or merge; describe separate authorization gates. Optional manual checks cannot replace mandatory acceptance without owner approval.

### 3. Documentation and local proof

- Update the English canonical README and Traditional Chinese translation (or clearly supersede outdated sections in both) with the changed contract, commands, migration requirements and compatibility limitations. Keep bundle self-contained. Do not rewrite historical design/retrospective files.
- Bump bundle/schema major when the contract or required artifacts change; document migration without deleting old consumer artifacts. State OpenSpec 2.0.0 and Superpowers 7.0.2 as source-review targets only, not end-to-end tested support.
- Run all regressions in an OS sandbox: network disabled, clean allowlisted environment, scratch HOME/tmp/cache, source and toolchain read-only, scratch-only writes, CPU/memory/process/file/wall limits. Start namespaces before applying process limits. Use existing bwrap/Python/Git only. Remove disposable scratch after successful proof. If sandbox cannot start, stop and report the exact limitation rather than running target code on the host.
- Final report: changed files, RED/GREEN evidence, full test results, remaining gaps and commands not run. No commit/push. Freeze candidate with file hashes for fresh read-only review.

## Acceptance

Objective regressions pass; malformed/missing/stale evidence fails closed; workspace absence and fresh repositories have deterministic outcomes; no host credentials/network exposed to tests; schema, templates and both README languages agree on authority and limits. Independent review is required before claiming this local slice accepted. Real-agent cycle, OpenSpec CLI validation, remote CI and adoption are separate pending gates, not implied by local tests.
