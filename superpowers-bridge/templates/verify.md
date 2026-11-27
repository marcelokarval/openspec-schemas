# Verification report

The machine-readable sections are self-reported; guard success does not prove
tests ran, review independence, or human acceptance. Paste the final candidate digest.

## Candidate

<final candidate SHA-256>

## Mandatory checks

- [ ] structural
- [ ] tests
- [ ] review

## Overall Decision

- [ ] PASS

## Evidence and outstanding gaps

<!-- For each linked pair, cite the policy test and observed RED/GREEN on this candidate. Distinguish historical characterization or a decision source from proof of the approved result. In that task's evidence.json record, include one entry per pair, for example: -->
<!-- "rule_scenarios":[{"rule":"BR-LIMIT","scenario":"AC-OVER","proof":"policy_test"}] -->

Record commands, results, review identity and candidate, spec/design coherence,
and deferred work. Unverified mandatory checks block PASS. Optional checks do
not replace mandatory acceptance without owner approval. Put typed task, test,
structural and reviewer records in evidence.json as described in the README;
run guard verify. The manifest must cover the actual implementation scope.
