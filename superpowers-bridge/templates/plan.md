# Implementation plan

Bridge task contract: 1
<!-- Only for material rules: add the following marker as a plain line alongside the task marker. Omit it and all rule fields otherwise. -->
<!-- Bridge rule contract: 1 -->

**Goal:** <!-- goal -->
**Architecture:** <!-- decisions -->
**Skill mapping and observed invocation:** <!-- evidence -->

## Task 1.1: <!-- stable tasks.md ID -->

- Depends on: none
- Needs: none

<!-- Only inside a materially linked task: write one bare line per distinct rule/scenario pair and exactly one readiness line for the task. Cover every local rule scenario. -->
<!-- Rule scenario: BR-LIMIT => AC-OVER -->
<!-- Rule readiness: ready -->
<!-- Choose blocked if any linked decision is proposed or blocked, or a material input is missing. Name the resolver and resume condition below. Ready does not authorize execution. -->

<!-- Use exactly one top-level dependency line per task: `- Depends on: none` or `- Depends on: 1.1, 1.2`. IDs must refer to tasks; absence in a legacy plan is unknown, not none. Dependencies alone do not establish safe parallelism. -->
<!-- Planning: keep the marker and fill one microcontract per executable tasks.md ID. For non-root tasks, replace Needs: none with one Needs: ID => output-id line per dependency; copy that task's exact Produces identifier. -->
- Outcome: <!-- What can a reviewer accept independently? -->
- Owner/resolver: <!-- Who owns this outcome or resolves a material open decision? -->
- Inputs: <!-- Required inputs other than Needs, or none -->
- Produces: <!-- One exact output identifier; Outcome describes what it delivers -->
- Write paths: <!-- Exact repo-relative paths separated by commas, or none -->
- Exclusions: <!-- Exact repo-relative paths this task must not write, or none -->
- Shared resources: <!-- Identifiers separated by commas (e.g. db:test or port:8080), or none -->
- Acceptance: <!-- What check on the same candidate proves the outcome? -->
- Stop: <!-- What condition blocks this task? -->
- Resume: <!-- What prerequisite or evidence permits resuming this task? -->

<!-- Execution: record actual outcomes only after observing them. -->
- RED command and observed failure: <!-- evidence -->
- GREEN command and observed result: <!-- evidence -->
- Typed evidence outcomes: RED expected_failure; GREEN passed.
- Review candidate identity and reviewer: <!-- evidence -->
- Remaining gaps: <!-- none or blockers -->
