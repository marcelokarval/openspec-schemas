# Local bridge acceptance candidate — 2026-11-12

Status: **bounded local inline acceptance completed**. Source/CI and the first
fixture were accepted by independent reviewer `ses_e2e1e6da4ffeWS3fv5af6p2mE3`.
The ordered live inline cycle was independently accepted by
`ses_e2e17a2f1ffeeQlQRQ6kQhXI3R`. Both fixtures passed final guard verification
after their retrospectives. Hosted CI and global adoption remain separate.

## OpenSpec CLI observation

The installed standalone OpenSpec 2.0.0 executable was mounted read-only in an
isolated bubblewrap sandbox with `--unshare-all`, no network, cleared environment,
`OPENSPEC_TELEMETRY=0`, `DO_NOT_TRACK=1`, scratch-local HOME/XDG/TMP, 128 MiB
tmpfs, 1 GiB address space, 64 process, 10 MiB file, 40 CPU-second and 60-second
wall limits. Source and toolchain were read-only. A disposable copy of the bundle
was placed in scratch at `openspec/schemas/superpowers-bridge`.

The exact host executable is `/home/marcelo-karval/.local/bin/openspec` (not a
filename containing the version). Reproducible sandbox mount fragment:
`--dir /tools --ro-bind /home/marcelo-karval/.local/bin/openspec /tools/openspec`.
Use this with the full recipe below, not as a host execution instruction:

```sh
/usr/bin/timeout 60 /usr/bin/bwrap --unshare-all --die-with-parent --new-session \
  --ro-bind /usr /usr --ro-bind /bin /bin --ro-bind /lib /lib --ro-bind /lib64 /lib64 \
  --dir /tools --ro-bind /home/marcelo-karval/.local/bin/openspec /tools/openspec \
  --ro-bind "$PWD" /src --proc /proc --dev /dev --size 134217728 --tmpfs /scratch \
  --chdir /scratch --clearenv --setenv HOME /scratch --setenv TMPDIR /scratch \
  --setenv XDG_CACHE_HOME /scratch --setenv XDG_CONFIG_HOME /scratch \
  --setenv PATH /tools:/usr/bin:/bin --setenv OPENSPEC_TELEMETRY 0 --setenv DO_NOT_TRACK 1 \
  /usr/bin/python3 -c 'import os,resource,shutil; resource.setrlimit(resource.RLIMIT_CPU,(40,40)); resource.setrlimit(resource.RLIMIT_AS,(1073741824,1073741824)); resource.setrlimit(resource.RLIMIT_NPROC,(64,64)); resource.setrlimit(resource.RLIMIT_FSIZE,(10485760,10485760)); os.makedirs("/scratch/openspec/schemas"); shutil.copytree("/src/superpowers-bridge","/scratch/openspec/schemas/superpowers-bridge"); os.execv("/tools/openspec",["openspec","schema","validate","superpowers-bridge","--json"])'
```

- `openspec schema validate superpowers-bridge --json`: exit 0, `valid: true`,
  `issues: []`.
- `openspec schemas --json`: exit 0, bridge listed with `source: project`.
- `openspec new change normalize-label --schema superpowers-bridge`: exit 0;
  created the change in scratch. The CLI noted that no OpenSpec root had been
  found and created one; no global initialization was performed.
- `openspec status --change normalize-label --json`: exit 0, schema name
  `superpowers-bridge`, brainstorm ready, remaining planning artifacts blocked.
- `openspec instructions brainstorm --change normalize-label --json`: exit 0,
  returned the bridge instruction, template and resolved change path.
- `openspec instructions apply --change normalize-label --json`: exit 0,
  `state: blocked`, missing plan and prerequisites, as expected before planning.

These are bounded CLI observations, not full OpenSpec integration or a claim
about Superpowers 7.0.2. Native skills loaded in this session from
`~/.agents/skills/test-driven-development/SKILL.md`, `writing-plans/SKILL.md`,
`executing-plans/SKILL.md`, and `openspec-apply-change/SKILL.md`; installed
skill versions are not established as upstream 7.0.2. Human-predefined fixture
requirements replaced an additional brainstorming interview. No separate agent
was dispatched by this implementation owner.

## Fixture and manual rerun contract

Fixture used: `/tmp/opencode/bridge-acceptance-20261112-terra`. This disposable
directory contained only dummy code and a local empty Git base, and is removed
after final verification rather than retained as a production package. Function
contract: strings only; split/join Unicode whitespace; casefold; blank raises
ValueError and non-string raises TypeError.

In the documented OS sandbox, mount the fixture read-only at `/fixture`, run
`python3 -m unittest test_normalize_label -v` with working directory `/fixture`.
Observed RED on the initial identity stub: 3 failures (blank, non-string and
Unicode/casefold). Observed GREEN after implementation: 3 tests passed. The
fixture artifacts were authored as compact examples informed by templates, not
generated via a live agent invoking each artifact instruction; this remains a
coverage limitation. Independent review checked them and ran additional tests.

The guard `candidate` invocation using base `fixture-base` returned base and
HEAD `b1d6614e83b1f5733c354ec2e0d7e384ea03603d`, candidate
`cafb1b81a58c8185bba9ed5a4f48cd7e18412456ff568db927ff2cd14fb5991f`.
After independent review the coordinator must create truthful evidence and
verification records, rerun guard verify, write the retrospective, rerun verify,
and decide cleanup. Independent Sol review accepted that exact candidate with
three fixture tests and thirteen additional checks. Subsequently, strict
`openspec validate normalize-label --strict --json` returned exit 0, one valid
change, zero issues. Truthful `verify.md` and `evidence.json` were written and
the guard verify returned status ok for the unchanged candidate. The coordinator
wrote the retrospective and independently ran the final guard in the 64 MiB
network-isolated sandbox: exit 0, unchanged candidate, status ok.

## Ordered live-cycle fixture

`/tmp/opencode/bridge-live-acceptance-20261112-terra` was the second disposable
fixture. In separate sandbox invocations with the current fixture mounted
read-only and copied into scratch, OpenSpec 2.0.0 returned `instructions` JSON
in this exact order: brainstorm, proposal, design, specs, tasks, plan; each exit
0. The agent read each returned template/instruction and wrote its artifact via
native patch before requesting the next. The initial change was created with
`openspec new change normalize-label --schema superpowers-bridge` in a scratch
project with an explicit OpenSpec root and copied schema; its metadata was
reproduced in the persistent fixture. Artifact paths followed CLI output under
`openspec/changes/normalize-label/`.

Native brainstorming, writing-plans, test-driven-development and executing-plans
were loaded via the skill tool from their corresponding `~/.agents/skills/*/SKILL.md`
paths. User-approved predetermined design replaced another interview; no claim
is made that the installed skills are upstream Superpowers 7.0.2. Apply
instructions returned `ready`, 0/1 tasks, and guard preflight passed before
implementation files existed. Identity-stub RED produced three assertion failures;
GREEN produced three passing tests. After marking the task done, apply reported
`all_done`, 1/1. Schema validation and strict change validation each returned
exit 0, valid true, zero issues. Guard candidate status was ok with base/HEAD
`9a6739b867331d9a099be16f53e3b066752f3fda` and candidate
`74b69b8b6e3f4c90bc459dc82dcfab8e189f48f08e0237bbec321813cd2d1df6`.
Fresh independent reviewer `ses_e2e17a2f1ffeeQlQRQ6kQhXI3R` reproduced the official
CLI schema/strict-change validation, instruction endpoints, ready/all_done states,
planned-absent preflight, candidate identity, three tests and identity-stub
RED/GREEN reconstruction, seventeen additional cases and seven idempotence checks.
The reviewer accepted the bounded inline cycle. Original authoring chronology is
author-reported; later reproduction is not retrospective observation of that
timeline. Installed native skill identity is not upstream Superpowers 7.0.2 proof.

The coordinator then wrote truthful evidence.json and verify.md using that actual
review identity, ran guard verify successfully, wrote retrospective.md, and ran
verify again successfully without changing candidate inputs. The final two-fixture
check used the full 64 MiB sandbox recipe with read-only fixture mounts and returned
status ok for both original candidate digests.

### Retained identity

- Official executable SHA-256: `99332e5ad3ddc1f2f77411d0e844a1bd97f7c249fb70d0977a068bb512e36384`.
- Bridge schema SHA-256: `ad677a5ac387553879770b6f97574ae0ff4f4f6312643f3732e1d80974377d10`.
- Live implementation SHA-256: `0ccad26c988a3023d3d2a6cd8b1e351e3715225b3208f5e921e39d54a11c665c`.
- Live test SHA-256: `4b36665af1837fc6989c2a58746734f087d43186901782e5f5b4e47bfafb4a01`.

### Cleanup and scope

Both named dummy fixtures were removed after checking their dummy source/tests,
absence of remotes and visible process/file-descriptor/mount consumers. No global
skills were overwritten or activated. The official
CLI remains at its approved standard location; PATH and shell startup files were
not modified. CLI source version is pinned for reproducible checks, not a permanent
ban on upgrading; latest-release drift checks remain separate.

This is not full subagent-mode workflow proof, automatic evidence truth,
deployment, global adoption, or upstream Superpowers 7.0.2 runtime certification.

## Repository regressions

The full offline Python suite passed 23 tests in the 64 MiB bwrap sandbox. It
executes the weekly workflow's exact jq expressions against real metadata and
invalid missing/injection fixtures. The pull-request workflow now runs these
offline checks before pinned OpenSpec structural validation. The actual hosted
CI run remains pending. The weekly workflow was not dispatched.
