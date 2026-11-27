"""Black-box tests for the additive material-rule wire."""
import json
import os
import subprocess
import unittest

import test_bridge_guard as base
from test_task_dag import MARKER, microcontract

RULE_MARKER = 'Bridge rule contract: 1\n'
SPEC = ('## ADDED Requirements\n### Requirement: Limit\nRule: BR-LIMIT\nDecision: approved\n'
        '#### Scenario: Reject over limit\nScenario ID: AC-OVER\n')
LINK = 'Rule scenario: BR-LIMIT => AC-OVER\nRule readiness: ready\n'
PLAN = MARKER + RULE_MARKER + microcontract('1.1') + LINK
REF = ('## ADDED Requirements\n### Requirement: Consumer\nRule reference: BR-LIMIT => policies/limits.md#limit\n'
       '#### Scenario: Local case\nScenario ID: AC-LOCAL\n')
EXTERNAL = SPEC.split('\n', 1)[1].replace('Requirement: Limit', 'Requirement: Limit {#limit}')
PROOF = {'rule': 'BR-LIMIT', 'scenario': 'AC-OVER', 'proof': 'policy_test'}


class RuleTest(unittest.TestCase):
    git = base.BridgeGuardTest.git
    run_guard = base.BridgeGuardTest.run_guard
    verdict = base.BridgeGuardTest.verdict

    def setUp(self):
        base.BridgeGuardTest.setUp(self)
        base.BridgeGuardTest.artifacts(self)
        self.spec = self.change / 'specs/example/spec.md'
        self.plan = self.change / 'plan.md'
        self.tasks = self.change / 'tasks.md'
        self.source = self.repo / 'policies/limits.md'
        self.source.parent.mkdir()
        self.spec.write_text(SPEC)
        self.plan.write_text(PLAN)

    def reject(self, phase, diagnostic):
        code, report = self.run_guard(phase)
        self.assertEqual(code, 1, report)
        self.assertIn(diagnostic, report['message'])

    def planning(self):
        p = subprocess.run(['/usr/bin/python3', str(base.GUARD), 'planning', '--change', str(self.change)],
                           capture_output=True, text=True, timeout=5)
        return p.returncode, json.loads(p.stdout)

    def test_wrong_owner_all_phases(self):
        self.spec.write_text(SPEC + SPEC.replace('LIMIT', 'OTHER').replace('OVER', 'OTHER'))
        self.plan.write_text(PLAN.replace('=> AC-OVER', '=> AC-OTHER'))
        for phase in ('planning', 'preflight', 'candidate', 'verify'):
            with self.subTest(phase=phase):
                self.reject(phase, 'AC-OTHER')

    def test_definitions_coverage_and_scope(self):
        for spec, plan, diag in (
            (SPEC + SPEC, PLAN, 'BR-LIMIT'),
            (SPEC + SPEC.replace('LIMIT', 'OTHER'), PLAN, 'AC-OVER'),
            (SPEC.replace('#### Scenario:', '### Other:'), PLAN, 'Scenario ID'),
            (SPEC.replace('Decision: approved', 'Decision: proposed\nDecision: approved'), PLAN, 'Decision'),
            (SPEC + '#### Scenario: Another\nScenario ID: AC-EXTRA\n', PLAN, 'AC-EXTRA'),
            (SPEC, PLAN.replace(RULE_MARKER, ''), 'Bridge rule contract'),
            (SPEC, PLAN.replace(MARKER, ''), 'task contract'),
            (SPEC, PLAN.replace(LINK, '## Other\n' + LINK), 'Rule scenario'),
            (SPEC, PLAN.replace('Rule readiness: ready\n', ''), 'readiness'),
            (SPEC, PLAN + LINK, 'duplicate'),
            (SPEC.replace('Rule: BR-LIMIT', '```\nRule: BR-LIMIT\n```'), PLAN, 'Rule'),
            (SPEC.replace('Scenario ID: AC-OVER', '<!-- Scenario ID: AC-OVER -->'), PLAN, 'Scenario'),
        ):
            with self.subTest(diag=diag):
                self.spec.write_text(spec)
                self.plan.write_text(plan)
                self.reject('planning', diag)

    def test_blocked_is_local_and_never_checked(self):
        self.tasks.write_text('- [ ] 1.1 A\n- [x] 1.2 B\n')
        for decision in ('proposed', 'blocked'):
            self.spec.write_text(SPEC.replace('approved', decision))
            self.plan.write_text(PLAN + microcontract('1.2'))
            self.reject('planning', '1.1')
            self.plan.write_text(PLAN.replace('readiness: ready', 'readiness: blocked') + microcontract('1.2'))
            for phase in ('planning', 'preflight', 'candidate'):
                code, report = self.run_guard(phase)
                self.assertEqual(code, 0, report)
                self.assertEqual(report['rule_blocked_tasks'], ['1.1'])
            self.reject('verify', '1.1')
            self.tasks.write_text('- [x] 1.1 A\n- [x] 1.2 B\n')
            self.reject('candidate', '1.1')
            self.tasks.write_text('- [ ] 1.1 A\n- [x] 1.2 B\n')

    def test_external_source_and_local_scenario_bound(self):
        self.assertEqual(self.planning()[0], 0)
        self.spec.write_text(REF)
        self.plan.write_text(PLAN + 'Rule scenario: BR-LIMIT => AC-LOCAL\n')
        self.source.write_text(EXTERNAL)
        code, report = self.planning()
        self.assertEqual(code, 1, report)
        self.assertIn('--repo', report['message'])
        digest = self.run_guard('candidate')[1]['candidate']
        self.source.write_text(EXTERNAL + '\nEditorial update.\n')
        self.assertNotEqual(self.run_guard('candidate')[1]['candidate'], digest)
        self.source.write_text(EXTERNAL.replace('BR-LIMIT', 'BR-OTHER'))
        self.reject('preflight', 'BR-LIMIT')

    def test_reference_never_guesses_or_follows_special_paths(self):
        self.source.write_text(EXTERNAL)
        for target in ('policies/limits.md#absent', '../limits.md#limit', '/limits.md#limit',
                       'https://host/limits.md#limit', '.git/limits.md#limit', 'missing.md#limit'):
            with self.subTest(target=target):
                self.spec.write_text(REF.split('####')[0].replace('policies/limits.md#limit', target))
                self.reject('planning', 'reference')
        self.spec.write_text(REF.split('####')[0])
        self.source.unlink()
        self.source.symlink_to(self.spec)
        self.reject('planning', 'reference')
        self.source.unlink()
        os.mkfifo(self.source)
        self.reject('planning', 'reference')

    def test_verify_requires_exact_policy_proof_for_each_pair(self):
        digest = self.run_guard('candidate')[1]['candidate']
        self.verdict(digest)
        path = self.change / 'evidence.json'
        evidence = json.loads(path.read_text())
        self.reject('verify', 'rule_scenarios')
        for proofs in ([], [PROOF, PROOF], [dict(PROOF, proof='characterization')],
                       [dict(PROOF, scenario='AC-OTHER')], [dict(PROOF, rule='BR-OTHER')]):
            evidence['tasks'][0]['rule_scenarios'] = proofs
            path.write_text(json.dumps(evidence))
            self.reject('verify', 'rule_scenarios')
        evidence['tasks'][0]['rule_scenarios'] = [PROOF]
        path.write_text(json.dumps(evidence))
        self.assertEqual(self.run_guard('verify')[0], 0)
        self.spec.write_text(SPEC + '\nClarification.\n')
        self.assertEqual(self.run_guard('verify')[0], 1)

    def test_plain_planning_does_not_open_specs(self):
        self.plan.write_text(MARKER + microcontract('1.1'))
        self.spec.unlink()
        self.spec.symlink_to(self.tmp.name)
        self.assertEqual(self.planning()[0], 0)

    def test_standalone_legacy_guard_accepts_ordinary_rule_prose(self):
        self.plan.write_text('## Task 1.1\nDocument the business rule.\n')
        self.spec.write_text('The BR-LIMIT label is documentation only.\n')
        script = self.repo / 'guard.py'
        script.write_bytes(base.GUARD.read_bytes())
        self.assertEqual(self.run_guard('candidate', script=script)[0], 0)

    def test_metadata_stays_in_its_own_markdown_section(self):
        for injection in ('Other section\n=============', '#### Other section', '##### Notes'):
            with self.subTest(heading=injection):
                self.spec.write_text(SPEC.replace('Rule: BR-LIMIT', injection + '\nRule: BR-LIMIT'))
                self.reject('planning', 'Rule')
        self.spec.write_text(SPEC.replace('Scenario ID:', '##### Details\nScenario ID:'))
        self.reject('planning', 'Scenario ID')

    def test_external_id_must_be_unique_across_loaded_sources(self):
        self.spec.write_text(REF + REF.replace('BR-LIMIT', 'BR-OTHER').replace('limits.md#limit', 'other.md#other').replace('AC-LOCAL', 'AC-OTHERLOCAL'))
        self.plan.write_text(PLAN + 'Rule scenario: BR-LIMIT => AC-LOCAL\n'
                            'Rule scenario: BR-OTHER => AC-OTHER\nRule scenario: BR-OTHER => AC-OTHERLOCAL\n')
        self.source.write_text(EXTERNAL)
        other = EXTERNAL.replace('{#limit}', '{#other}').replace('BR-LIMIT', 'BR-OTHER').replace('AC-OVER', 'AC-OTHER')
        (self.source.parent / 'other.md').write_text(other + EXTERNAL)
        self.reject('planning', 'BR-LIMIT')

    def test_referenced_definition_can_supply_decision_without_scenarios(self):
        self.source.write_text(EXTERNAL.split('#### Scenario:')[0])
        self.spec.write_text(REF)
        self.plan.write_text(PLAN.replace('AC-OVER', 'AC-LOCAL'))
        code, report = self.run_guard('candidate')
        self.assertEqual(code, 0, report)
        self.verdict(report['candidate'])
        path = self.change / 'evidence.json'
        evidence = json.loads(path.read_text())
        evidence['tasks'][0]['rule_scenarios'] = [dict(PROOF, scenario='AC-LOCAL')]
        path.write_text(json.dumps(evidence))
        self.assertEqual(self.run_guard('verify')[0], 0)
        self.source.write_text(self.source.read_text() + 'Changed.\n')
        self.assertEqual(self.run_guard('verify')[0], 1)

    def test_multiline_spec_comments_and_fences_are_examples(self):
        fake = '### Requirement: Other\nRule: BR-LIMIT\nDecision: blocked\n'
        self.spec.write_text('<!--\n' + fake + '-->\n~~~md\n' + fake + '~~~\n' + SPEC)
        self.assertEqual(self.planning()[0], 0)

    def test_legacy_spec_rule_is_not_a_material_declaration(self):
        self.spec.write_text('### Requirement: Existing\nRule: BR-LEAD-001\n#### Scenario: Existing\n')
        for plan in (MARKER + microcontract('1.1'), '## Task 1.1\nOld prose plan.\n'):
            self.plan.write_text(plan)
            for phase in ('preflight', 'candidate'):
                code, report = self.run_guard(phase)
                self.assertEqual(code, 0, report)
                self.assertEqual(set(report), {'status', 'notice', 'base', 'head', 'candidate'})
            self.verdict(report['candidate'])
            self.assertEqual(self.run_guard('verify')[0], 0)
        self.plan.write_text(MARKER + microcontract('1.1'))
        code, report = self.planning()
        self.assertEqual((code, set(report)), (0, {'status', 'notice'}))
        for field in ('Rule scenario: BR-LEAD-001 => AC-EXAMPLE', 'Rule readiness: blocked'):
            self.plan.write_text(MARKER + microcontract('1.1') + field + '\n')
            for phase in ('planning', 'preflight', 'candidate', 'verify'):
                self.reject(phase, 'Bridge rule contract')

    def test_noncanonical_task_declarations_do_not_silently_exempt_a_task(self):
        self.tasks.write_text('- [x] 1.1 A\n- [x] 1.2 B\n')
        for malformed in ('- Rule readiness: blocked', ' Rule scenario: BR-LIMIT => AC-OVER',
                          'Rule readiness : blocked'):
            with self.subTest(malformed=malformed):
                self.plan.write_text(PLAN + microcontract('1.2') + malformed + '\n')
                self.reject('candidate', '1.2')

    def test_material_record_shape_is_local_and_multi_scenario_proofs_are_exact(self):
        self.tasks.write_text('- [x] 1.1 A\n- [x] 1.2 B\n')
        self.spec.write_text(SPEC + '#### Scenario: At limit\nScenario ID: AC-AT\n')
        self.plan.write_text(PLAN + 'Rule scenario: BR-LIMIT => AC-AT\n' + microcontract('1.2'))
        self.verdict(self.run_guard('candidate')[1]['candidate'])
        path = self.change / 'evidence.json'
        evidence = json.loads(path.read_text())
        material = evidence['tasks'][0]
        evidence['tasks'].append(dict(material, id='1.2', plan='1.2'))
        material['rule_scenarios'] = [PROOF]
        path.write_text(json.dumps(evidence))
        self.reject('verify', 'rule_scenarios')
        material['rule_scenarios'].append(dict(PROOF, scenario='AC-AT'))
        path.write_text(json.dumps(evidence))
        self.assertEqual(self.run_guard('verify')[0], 0)

    def test_duplicate_and_unknown_markers_and_hidden_examples(self):
        for value in ('Bridge rule contract: 2\n', RULE_MARKER + RULE_MARKER):
            self.plan.write_text(PLAN.replace(RULE_MARKER, value))
            self.reject('planning', 'Bridge rule contract')
        self.plan.write_text(MARKER + microcontract('1.1') + '\n```md\n' + RULE_MARKER + LINK + '```\n'
                            '<!-- Rule readiness: blocked -->\n')
        self.assertEqual(set(self.run_guard('candidate')[1]), {'status', 'notice', 'base', 'head', 'candidate'})

    def test_review_removed_pair_cannot_support_any_phase(self):
        removed = SPEC.replace('ADDED', 'REMOVED').replace('Rule: BR-LIMIT',
            '**Reason**: Retired limit.\n**Migration**: Use the new policy.\nRule: BR-LIMIT')
        self.spec.write_text(removed)
        # Give the old guard a fresh, otherwise sufficient report, so an unrelated
        # stale/missing report cannot mask verify accepting the historical pair.
        _, candidate = self.run_guard('candidate')
        self.verdict(candidate.get('candidate', 'unavailable'))
        path = self.change / 'evidence.json'
        evidence = json.loads(path.read_text())
        evidence['tasks'][0]['rule_scenarios'] = [PROOF]
        path.write_text(json.dumps(evidence))
        for phase in ('planning', 'preflight', 'candidate', 'verify'):
            with self.subTest(phase=phase):
                self.reject(phase, 'BR-LIMIT')
        # Historical IDs neither duplicate nor override a current MODIFIED rule.
        self.spec.write_text(SPEC.replace('ADDED', 'MODIFIED') + removed.replace('approved', 'blocked'))
        self.assertEqual(self.planning()[0], 0)
        for heading in ('', '## RENAMED Requirements\n'):
            with self.subTest(heading=heading):
                self.spec.write_text(heading + SPEC.split('\n', 1)[1])
                self.reject('planning', 'BR-LIMIT')

    def test_review_standalone_prose_is_not_a_loader_trigger(self):
        script = self.repo / 'guard.py'
        script.write_bytes(base.GUARD.read_bytes())
        for prose in ('Document the rule for this scenario.',
                      'Bridge task contract details: document the rule for this scenario.'):
            with self.subTest(prose=prose):
                self.plan.write_text('## Task 1.1\n' + prose + '\n')
                code, report = self.run_guard('candidate', script=script)
                self.assertEqual(code, 0, report)
                self.verdict(report['candidate'])
                self.assertEqual(self.run_guard('verify', script=script)[0], 0)
        for field in ('Rule<!-- gap -->scenario: BR-LIMIT => AC-OVER', 'Rule\treadiness : blocked'):
            self.plan.write_text('## Task 1.1\n' + field + '\n')
            self.reject('candidate', 'Bridge rule contract')

    def test_review_legacy_auxiliary_link_is_not_a_candidate_input(self):
        self.plan.write_text('## Task 1.1\nLegacy plan.\n')
        digest = self.run_guard('candidate')[1]['candidate']
        image = self.repo / 'original.svg'
        image.write_bytes(b'original')
        alias = self.spec.with_name('diagram.svg')
        alias.symlink_to(os.path.relpath(image, alias.parent))
        for phase in ('preflight', 'candidate'):
            with self.subTest(phase=phase):
                code, report = self.run_guard(phase)
                self.assertEqual(code, 0, report)
                self.assertEqual(report['candidate'], digest)
        alias.unlink()
        alias.symlink_to(image.parent, target_is_directory=True)
        self.assertEqual(self.run_guard('preflight')[0], 1)
        alias.unlink()
        self.spec.unlink()
        self.spec.symlink_to(image)
        self.assertEqual(self.run_guard('candidate')[0], 1)

    def test_external_history_cannot_support_any_phase(self):
        self.spec.write_text(REF.split('#### Scenario:')[0])
        for section in ('REMOVED', 'RENAMED'):
            self.source.write_text(f'## {section} Requirements\n' + EXTERNAL)
            # If candidate succeeds, verify gets fresh, complete evidence for
            # those very bytes; a missing report must not explain the rejection.
            _, candidate = self.run_guard('candidate')
            self.verdict(candidate.get('candidate', 'unavailable'))
            path = self.change / 'evidence.json'
            evidence = json.loads(path.read_text())
            evidence['tasks'][0]['rule_scenarios'] = [PROOF]
            path.write_text(json.dumps(evidence))
            for phase in ('planning', 'preflight', 'candidate', 'verify'):
                with self.subTest(section=section, phase=phase):
                    self.reject(phase, 'Rule reference')

    def test_external_history_does_not_shadow_or_supply_current_scenarios(self):
        self.spec.write_text(REF.split('#### Scenario:')[0])
        for heading, subsequent in (('## REMOVED Requirements', '## Current policy'),
                                    ('## RENAMED Requirements ##', '# Current policy'),
                                    ('REMOVED Requirements\n--------------------', 'Current policy\n--------------')):
            with self.subTest(heading=heading):
                history = heading + '\n' + EXTERNAL.replace('approved', 'blocked')
                for source in (history + subsequent + '\n' + EXTERNAL, EXTERNAL + history):
                    self.source.write_text(source)
                    code, report = self.run_guard('planning')
                    self.assertEqual((code, report.get('rule_blocked_tasks')), (0, []), report)
                # The same BR and anchor may be current, but the old AC is not.
                self.source.write_text(history + subsequent + '\n' + EXTERNAL.replace('AC-OVER', 'AC-NOW'))
                self.plan.write_text(PLAN + 'Rule scenario: BR-LIMIT => AC-NOW\n')
                self.reject('planning', 'AC-OVER')
                self.plan.write_text(PLAN)
