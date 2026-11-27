import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_task_dag import MARKER, microcontract

GUARD = Path(__file__).resolve().parents[1] / 'superpowers-bridge/scripts/bridge_guard.py'


class BridgeGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'repo ; dollar$'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'custom-base')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '--allow-empty', '-qm', 'base')
        self.change = self.repo / 'openspec/changes/example ; $name'
        self.change.mkdir(parents=True)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def run_guard(self, command='preflight', base='custom-base', change=None, script=GUARD):
        proc = subprocess.run(['/usr/bin/python3', str(script), command, '--repo', str(self.repo),
                               '--base', base, '--change', str(change or self.change)],
                              capture_output=True, text=True)
        self.assertTrue(proc.stdout, proc.stderr)
        return proc.returncode, json.loads(proc.stdout)

    def artifacts(self):
        for name in ('brainstorm.md', 'proposal.md', 'design.md', 'plan.md'):
            (self.change / name).write_text('content\n')
        (self.change / 'tasks.md').write_text('- [X] 1.1 First\n')
        spec = self.change / 'specs/example/spec.md'
        spec.parent.mkdir(parents=True)
        spec.write_text('spec\n')
        (self.repo / 'implementation.py').write_text('implementation\n')
        (self.change / 'candidate-manifest.json').write_text(json.dumps({'paths': [{'path': 'implementation.py', 'state': 'present'}]}))
        (self.change / 'plan.md').write_text('## Task 1.1\nPlan implementation\n')

    def verdict(self, digest, decision='- [x] PASS', checks='- [x] structural\n- [x] tests\n- [x] review'):
        (self.change / 'verify.md').write_text(
            f'## Candidate\n{digest}\n\n## Mandatory checks\n{checks}\n\n## Overall Decision\n{decision}\n')
        evidence = {'candidate': digest, 'tasks': [{'id': '1.1', 'plan': '1.1',
                    'red': {'command': 'test red', 'outcome': 'expected_failure', 'details': 'expected assertion'},
                    'green': {'command': 'test green', 'outcome': 'passed', 'details': 'all checks passed'}}],
                    'structural': {'command': 'validate', 'result': 'pass'},
                    'review': {'reviewer': 'independent reviewer', 'status': 'pass', 'candidate': digest},
                    'unresolved': []}
        (self.change / 'evidence.json').write_text(json.dumps(evidence))

    def test_missing_planning_artifacts_stop_preflight(self):
        self.assertTrue(GUARD.is_file(), 'read-only bridge guard is missing')
        self.assertNotEqual(self.run_guard()[0], 0)

    def test_preflight_custom_base_without_remote_and_bad_base(self):
        self.artifacts()
        self.assertEqual(self.run_guard()[0], 0)
        self.assertNotEqual(self.run_guard(base='missing')[0], 0)
        self.git('checkout', '--orphan', 'other')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '--allow-empty', '-qm', 'unrelated')
        self.assertNotEqual(self.run_guard()[0], 0)

    def test_reject_outside_and_symlink_escape(self):
        self.artifacts()
        outside = Path(self.tmp.name) / 'outside'
        outside.mkdir()
        (outside / 'secret').write_text('dummy')
        link = self.repo / 'escape'
        link.symlink_to(outside, target_is_directory=True)
        self.assertNotEqual(self.run_guard(change=outside)[0], 0)
        self.assertNotEqual(self.run_guard(change=link)[0], 0)
        (self.change / 'design.md').unlink()
        (self.change / 'design.md').symlink_to(outside / 'secret')
        self.assertNotEqual(self.run_guard()[0], 0)

    def test_verdict_requires_positive_unambiguous_and_fresh_candidate(self):
        self.artifacts()
        digest = self.run_guard()[1]['candidate']
        for decision in ('', '- [ ] PASS', '- [x] PASS\n- [X] FAIL', '```\n- [x] PASS\n```'):
            self.verdict(digest, decision)
            self.assertNotEqual(self.run_guard('verify')[0], 0, decision)
        self.verdict(digest)
        self.assertEqual(self.run_guard('verify')[0], 0)
        (self.change / 'design.md').write_text('changed\n')
        self.assertNotEqual(self.run_guard('verify')[0], 0)

    def test_unfinished_tasks_and_mandatory_checks_stop(self):
        self.artifacts()
        digest = self.run_guard()[1]['candidate']
        self.verdict(digest, checks='- [x] structural\n- [ ] tests\n- [x] review')
        self.assertNotEqual(self.run_guard('verify')[0], 0)

    def test_ignored_planning_artifact_is_bound(self):
        self.artifacts()
        (self.repo / '.gitignore').write_text('openspec/\n')
        digest = self.run_guard()[1]['candidate']
        self.verdict(digest)
        (self.change / 'design.md').write_text('changed ignored artifact\n')
        self.assertNotEqual(self.run_guard('verify')[0], 0)
        (self.change / 'tasks.md').write_text('- [ ] 1.1 First\n')
        digest = self.run_guard()[1]['candidate']
        self.verdict(digest)
        self.assertNotEqual(self.run_guard('verify')[0], 0)

    def test_source_contract_has_no_unsafe_shortcuts(self):
        schema = (GUARD.parents[1] / 'schema.yaml').read_text()
        self.assertIn('bridge_guard.py', schema)
        self.assertNotIn('origin/main', schema)
        self.assertNotIn("! grep -q", schema)
        self.assertNotIn('openspec archive -y', schema)
        self.assertIn('version: 2', schema)

    def test_missing_typed_evidence_cannot_pass(self):
        self.artifacts()
        digest = self.run_guard()[1]['candidate']
        self.verdict(digest)
        (self.change / 'evidence.json').unlink()
        self.assertNotEqual(self.run_guard('verify')[0], 0)

    def test_indented_fence_cannot_hide_unfinished_task(self):
        self.artifacts()
        (self.change / 'tasks.md').write_text('- [X] 1.1 First\n    ```\n- [ ] 1.2 Hidden\n    ```\n')
        self.assertNotEqual(self.run_guard()[0], 0)

    def test_nested_spec_is_supported(self):
        self.artifacts()
        spec = self.change / 'specs/example/spec.md'
        nested = self.change / 'specs/example/nested/spec.md'
        nested.parent.mkdir()
        spec.rename(nested)
        self.assertEqual(self.run_guard()[0], 0)

    def test_missing_manifest_stops_preflight(self):
        self.artifacts()
        (self.change / 'candidate-manifest.json').unlink()
        self.assertNotEqual(self.run_guard()[0], 0)

    def test_manifest_freshness_and_reports(self):
        self.artifacts()
        (self.repo / '.gitignore').write_text('implementation.py\n')
        digest = self.run_guard()[1]['candidate']
        self.verdict(digest)
        self.assertEqual(self.run_guard('verify')[0], 0)
        (self.change / 'retrospective.md').write_text('report\n')
        self.assertEqual(self.run_guard('verify')[0], 0)
        (self.repo / 'implementation.py').write_text('changed\n')
        self.assertNotEqual(self.run_guard('verify')[0], 0)

    def test_manifest_deletion_and_mutation_fail(self):
        self.artifacts()
        digest = self.run_guard()[1]['candidate']
        self.verdict(digest)
        (self.repo / 'implementation.py').unlink()
        self.assertNotEqual(self.run_guard('verify')[0], 0)
        (self.repo / 'implementation.py').write_text('implementation\n')
        (self.repo / 'added.py').write_text('added\n')
        (self.change / 'candidate-manifest.json').write_text(json.dumps({'paths': [{'path': 'implementation.py', 'state': 'present'}, {'path': 'added.py', 'state': 'present'}]}))
        self.assertNotEqual(self.run_guard('verify')[0], 0)

    def test_fences_and_inrepo_symlinks(self):
        self.artifacts()
        (self.change / 'tasks.md').write_text('- [X] 1.1 First\n```text\n- [ ] 2.1 example\n```\n')
        self.assertEqual(self.run_guard()[0], 0)
        (self.change / 'tasks.md').write_text('- [X] 1.1 First\n```\n- [ ] 2.1 example\n~~~\n')
        self.assertNotEqual(self.run_guard()[0], 0)
        (self.change / 'tasks.md').write_text('- [X] 1.1 First\n')
        (self.change / 'design.md').unlink()
        (self.change / 'design.md').symlink_to(self.repo / 'implementation.py')
        self.assertNotEqual(self.run_guard()[0], 0)

    def test_missing_plan_mapping_and_contradiction_fail(self):
        self.artifacts()
        (self.change / 'plan.md').write_text('content\n')
        digest = self.run_guard()[1]['candidate']
        self.verdict(digest)
        self.assertNotEqual(self.run_guard('verify')[0], 0)
        (self.change / 'plan.md').write_text('## Task 1.1\n')
        digest = self.run_guard()[1]['candidate']
        self.verdict(digest)
        with (self.change / 'verify.md').open('a') as stream:
            stream.write('\n## Evidence\nMandatory integration test NOT VERIFIED; review FAIL.\n')
        self.assertNotEqual(self.run_guard('verify')[0], 0)

    def test_workflow_uses_explicit_source_metadata(self):
        workflow = (GUARD.parents[2] / '.github/workflows/version-check.yml').read_text()
        self.assertIn('source-versions.json', workflow)
        self.assertNotIn("grep -E '^\\| v1", workflow)

    def test_ci_runs_offline_checks_before_pinned_schema(self):
        workflow = (GUARD.parents[2] / '.github/workflows/validate-schemas.yml').read_text()
        self.assertIn('unittest discover', workflow)
        self.assertIn('source-versions.json', workflow)
        self.assertIn('jq -er', workflow)
        self.assertLess(workflow.index('unittest discover'), workflow.index('Install OpenSpec CLI'))
        self.assertNotIn('npm install -g @fission-ai/openspec\n', workflow)

    def test_actual_weekly_jq_filters(self):
        metadata = GUARD.parents[1] / 'source-versions.json'
        workflow = (GUARD.parents[2] / '.github/workflows/version-check.yml').read_text()
        filters = [line.split("jq -er '", 1)[1].split("' ", 1)[0]
                   for line in workflow.splitlines() if "=$(jq -er '" in line]
        self.assertEqual(len(filters), 2)
        for expr in filters:
            self.assertEqual(subprocess.run(['/usr/bin/jq', '-er', expr, str(metadata)], capture_output=True).returncode, 0)
            for invalid in ('{}', '{"openspec":"1.2.3;echo bad","superpowers":"v1.2.3;bad"}'):
                self.assertNotEqual(subprocess.run(['/usr/bin/jq', '-er', expr], input=invalid, text=True, capture_output=True).returncode, 0)

    def test_red_green_outcomes_are_typed(self):
        self.artifacts()
        digest = self.run_guard()[1]['candidate']
        self.verdict(digest)
        path = self.change / 'evidence.json'
        evidence = json.loads(path.read_text())
        for red, green in [('pass', 'pass'), ('expected failure', 'error: tests skipped'),
                           ('expected failure', 'expected failure observed')]:
            evidence['tasks'][0]['red']['outcome'] = red
            evidence['tasks'][0]['green']['outcome'] = green
            path.write_text(json.dumps(evidence))
            self.assertNotEqual(self.run_guard('verify')[0], 0)

    def test_shipped_plan_template_heading(self):
        self.artifacts()
        template = (GUARD.parents[1] / 'templates/plan.md').read_text()
        plan = self.change / 'plan.md'
        plan.write_text(template.replace('<!-- stable tasks.md ID -->', 'Implement feature'))
        self.assertNotEqual(self.run_guard('candidate')[0], 0, 'incomplete new template passed')
        plan.write_text(MARKER + microcontract('1.1', writes='implementation.py'))
        digest = self.run_guard()[1]['candidate']
        self.verdict(digest)
        self.assertEqual(self.run_guard('verify')[0], 0)

    def test_planning_needs_only_plan_and_tasks_and_does_not_write(self):
        change = Path(self.tmp.name) / 'planning only'
        change.mkdir()
        (change / 'plan.md').write_text(MARKER + microcontract('1.1'))
        (change / 'tasks.md').write_text('- [ ] 1.1 First\n')
        before = {p.name: p.read_bytes() for p in change.iterdir()}
        proc = subprocess.run(['/usr/bin/python3', str(GUARD), 'planning', '--change', str(change)],
                              capture_output=True, text=True, timeout=5)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['status'], 'ok')
        self.assertEqual(before, {p.name: p.read_bytes() for p in change.iterdir()})
        (change / 'plan.md').write_text(microcontract('1.1'))
        proc = subprocess.run(proc.args, capture_output=True, text=True, timeout=5)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn('contract marker', json.loads(proc.stdout)['message'])

    def test_all_guard_phases_reject_incomplete_marked_contract(self):
        self.artifacts()
        plan = self.change / 'plan.md'
        plan.write_text(MARKER + microcontract('1.1').replace('- Owner/resolver: Alice\n', ''))
        self.verdict('obsolete')
        for command in ('planning', 'preflight', 'candidate', 'verify'):
            with self.subTest(command=command):
                result, report = self.run_guard(command)
                self.assertEqual(result, 1)
                self.assertIn('task 1.1', report['message'])
                self.assertIn('Owner/resolver', report['message'])

    def test_all_guard_phases_reject_microcontract_field_inside_raw_html(self):
        self.artifacts()
        plan = microcontract('1.1').replace('- Owner/resolver: Alice\n',
                                          '<pre>\n- Owner/resolver: Alice\n</pre>\n')
        (self.change / 'plan.md').write_text(MARKER + plan)
        _, report = self.run_guard('candidate')
        self.verdict(report.get('candidate', 'no candidate'))
        for command in ('planning', 'preflight', 'candidate', 'verify'):
            with self.subTest(command=command):
                result, report = self.run_guard(command)
                self.assertEqual(result, 1)
                self.assertIn('plan.md:', report['message'])
                self.assertIn('raw HTML', report['message'])

    def test_verify_rejects_unfinished_checkbox_with_noncanonical_bullet(self):
        self.artifacts()
        (self.change / 'plan.md').write_text(MARKER + microcontract('1.1'))
        (self.change / 'tasks.md').write_text('- [x] 1.1 First\n* [ ] 1.2 Unfinished\n')
        _, report = self.run_guard('candidate')
        self.verdict(report.get('candidate', 'no candidate'))
        result, report = self.run_guard('verify')
        self.assertEqual(result, 1)
        self.assertIn('tasks.md:2: expected a top-level checkbox', report['message'])

    def test_marked_verify_requires_report_sections_in_visible_markdown(self):
        self.artifacts()
        (self.change / 'plan.md').write_text(MARKER + microcontract('1.1'))
        digest = self.run_guard('candidate')[1]['candidate']
        self.verdict(digest)
        path = self.change / 'verify.md'
        report = path.read_text()
        for hidden in ('<pre>\n' + report + '## Footer\n</pre>\n',
                       '<!--\n' + report + '## Footer\n-->\n',
                       report.replace('\n' + digest + '\n', '\n    ' + digest + '\n')):
            with self.subTest(start=hidden.splitlines()[0]):
                path.write_text(hidden)
                self.assertEqual(self.run_guard('verify')[0], 1)
        path.write_text(report + '\n## Examples\n<!-- ## Candidate - [ ] FAIL -->\n'
                        '```html\n<pre>\n## Overall Decision\n- [ ] FAIL\n</pre>\n```\n')
        self.assertEqual(self.run_guard('verify')[0], 0)

    def test_marked_verify_checks_pending_plan_steps_in_visible_markdown(self):
        self.artifacts()
        path = self.change / 'plan.md'
        plan = MARKER + microcontract('1.1')
        for pending in ('* [ ]', '+ [~]', '1. [ ]', '  > 1) + [ ]'):
            with self.subTest(pending=pending):
                path.write_text(plan + pending + ' Run mandatory acceptance fixture\n')
                self.verdict(self.run_guard('candidate')[1]['candidate'])
                self.assertEqual(self.run_guard('verify')[0], 1)
        path.write_text(plan + '* [x] Ran fixture\n> 1. [X] Checked output\n'
                        '+ [Fixture info](docs.md)\n<!-- 1. [ ] Example -->\n'
                        '```md\n* [ ] Example\n```\n')
        self.verdict(self.run_guard('candidate')[1]['candidate'])
        self.assertEqual(self.run_guard('verify')[0], 0)

    def test_marked_planning_rejects_duplicate_resource_field_with_extra_spacing(self):
        self.artifacts()
        (self.change / 'plan.md').write_text(MARKER + microcontract('1.1')
                                            + '-  Shared resources: db:fixture\n')
        result, report = self.run_guard('planning')
        self.assertEqual(result, 1)
        self.assertIn('Shared resources', report['message'])

    def test_marked_verify_does_not_hide_pending_step_after_quoted_comment_opener(self):
        self.artifacts()
        (self.change / 'plan.md').write_text(MARKER + microcontract('1.1')
                                            + 'The opener is `<!--`.\n'
                                            + '- [ ] Run mandatory acceptance fixture\n'
                                            + 'The closer is `-->`.\n')
        _, report = self.run_guard('candidate')
        self.verdict(report.get('candidate', 'no candidate'))
        result, report = self.run_guard('verify')
        self.assertEqual(result, 1)
        self.assertIn('comment delimiter', report['message'])

    def test_legacy_candidate_does_not_activate_contract_from_ordinary_prose(self):
        self.artifacts()
        plan = self.change / 'plan.md'
        with plan.open('a') as stream:
            stream.write('Bridge task contract details are tracked by the owner.\n')
        result, report = self.run_guard('candidate')
        self.assertEqual(result, 0, report)
        self.verdict(report['candidate'])
        self.assertEqual(self.run_guard('verify')[0], 0)

    def test_candidate_marker_discovery_ignores_legacy_inline_comment_example(self):
        self.artifacts()
        path = self.change / 'plan.md'
        example = 'Example: <!--\nBridge task contract: 1\n-->\n'
        path.write_text(example + path.read_text())
        result, report = self.run_guard('candidate')
        self.assertEqual(result, 0, report)
        path.write_text(example + MARKER + microcontract('1.1'))
        result, report = self.run_guard('candidate')
        self.assertEqual(result, 1)
        self.assertIn('comment must close on the same line', report['message'])
        path.write_text(MARKER + microcontract('1.1') + MARKER)
        result, report = self.run_guard('candidate')
        self.assertEqual(result, 1)
        self.assertIn('duplicate bridge task contract marker', report['message'])

    def test_marked_planning_accepts_indented_single_line_code_span(self):
        self.artifacts()
        (self.change / 'plan.md').write_text(MARKER + microcontract('1.1') + '  ```literal```\n')
        result, report = self.run_guard('planning')
        self.assertEqual(result, 0, report)

    def test_marked_planning_rejects_escaped_comment_delimiter_before_extra_task(self):
        self.artifacts()
        (self.change / 'plan.md').write_text(MARKER + microcontract('1.1'))
        (self.change / 'tasks.md').write_text('- [ ] 1.1 Existing task\n\nLiteral \\<!-- in prose.\n\n'
                                              '- [ ] 1.2 Real extra task\n\nLiteral --> in prose.\n')
        result, report = self.run_guard('planning')
        self.assertEqual(result, 1)
        self.assertIn('tasks.md:3: escaped comment delimiter', report['message'])

    def test_marked_planning_rejects_ambiguous_comment_openers_before_extra_task(self):
        self.artifacts()
        (self.change / 'plan.md').write_text(MARKER + microcontract('1.1'))
        for opener in ('Literal \\` then `<!--` in prose.', '    <!-- code example'):
            with self.subTest(opener=opener):
                (self.change / 'tasks.md').write_text('- [ ] 1.1 Existing task\n\n' + opener
                                                      + '\n\n- [ ] 1.2 Visible\n\nLiteral --> in prose.\n')
                result, report = self.run_guard('planning')
                self.assertEqual(result, 1)
                self.assertIn('tasks.md:3:', report['message'])

    def test_marked_planning_rejects_multiline_inline_syntax_and_indented_fences(self):
        self.artifacts()
        (self.change / 'plan.md').write_text(MARKER + microcontract('1.1'))
        for tail, diagnostic in (
            ('  <!-- comment inside first item\n- [ ] 1.2 Extra top-level item\n\n-->\n',
             'comment must close on the same line'),
            ('The example starts `on this line\n<!-- literal -->\nand ends here`.\n',
             'inline code must close on the same line'),
            ('  ```\n- [ ] 1.2 Extra\n\n```\n', 'indented fence'),
        ):
            with self.subTest(diagnostic=diagnostic):
                (self.change / 'tasks.md').write_text('- [ ] 1.1 Existing\n' + tail)
                result, report = self.run_guard('planning')
                self.assertEqual(result, 1)
                self.assertIn('tasks.md:2:', report['message'])
                self.assertIn(diagnostic, report['message'])

    def test_legacy_guard_does_not_load_the_helper_for_ordinary_bridge_prose(self):
        self.artifacts()
        plan = self.change / 'plan.md'
        plan.write_text('## Task 1.1\nImplement the bridge from the old route.\n')
        script = Path(self.tmp.name) / GUARD.name
        script.write_bytes(GUARD.read_bytes())
        result, report = self.run_guard('candidate', script=script)
        self.assertEqual(result, 0, report)
        self.verdict(report['candidate'])
        self.assertEqual(self.run_guard('verify', script=script)[0], 0)

    def test_add_modify_delete_lifecycle(self):
        self.artifacts()
        (self.repo / 'old.py').write_text('old')
        manifest = {'paths': [{'path': 'implementation.py', 'state': 'present'},
                              {'path': 'new.py', 'state': 'present'},
                              {'path': 'old.py', 'state': 'absent'}]}
        (self.change / 'candidate-manifest.json').write_text(json.dumps(manifest))
        self.assertEqual(self.run_guard('preflight')[0], 0)
        (self.repo / 'implementation.py').write_text('modified')
        (self.repo / 'new.py').write_text('added')
        (self.repo / 'old.py').unlink()
        digest = self.run_guard('candidate')[1]['candidate']
        self.verdict(digest)
        self.assertEqual(self.run_guard('verify')[0], 0)
        (self.change / 'retrospective.md').write_text('report')
        self.assertEqual(self.run_guard('verify')[0], 0)
        (self.repo / 'old.py').write_text('reappeared')
        self.assertNotEqual(self.run_guard('verify')[0], 0)

    def test_green_details_must_not_contradict_outcome(self):
        self.artifacts()
        digest = self.run_guard()[1]['candidate']
        self.verdict(digest)
        path = self.change / 'evidence.json'
        record = json.loads(path.read_text())
        for detail in ('error: tests skipped', 'expected failure observed'):
            record['tasks'][0]['green']['details'] = detail
            path.write_text(json.dumps(record))
            self.assertNotEqual(self.run_guard('verify')[0], 0)

    def test_absent_path_with_symlink_parent_rejected(self):
        self.artifacts()
        (self.repo / 'link').symlink_to(self.repo / 'missing', target_is_directory=True)
        (self.change / 'candidate-manifest.json').write_text(json.dumps({'paths': [{'path': 'link/new.py', 'state': 'absent'}]}))
        self.assertNotEqual(self.run_guard('preflight')[0], 0)


if __name__ == '__main__':
    unittest.main()
