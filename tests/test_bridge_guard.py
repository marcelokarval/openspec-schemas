import json
from pathlib import Path
import subprocess
import tempfile
import unittest

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

    def run_guard(self, command='preflight', base='custom-base', change=None):
        proc = subprocess.run(['/usr/bin/python3', str(GUARD), command, '--repo', str(self.repo),
                               '--base', base, '--change', str(change or self.change)],
                              capture_output=True, text=True)
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
        (self.change / 'plan.md').write_text(template.replace('<!-- stable tasks.md ID -->', 'Implement feature'))
        digest = self.run_guard()[1]['candidate']
        self.verdict(digest)
        self.assertEqual(self.run_guard('verify')[0], 0)

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
