import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "superpowers-bridge/scripts/task_dag.py"
MARKER = "Bridge task contract: 1\n"


def microcontract(task, *, parents="none", needs="none", writes="none", resources="none"):
    needs = "".join(f"- Needs: {value}\n" for value in needs.split("\n"))
    return (f"## Task {task}: Deliver a slice\n"
            f"- Depends on: {parents}\n{needs}"
            "- Outcome: CLI reports the expected counter\n"
            "- Owner/resolver: Alice\n- Inputs: none\n"
            f"- Produces: output-{task}\n- Write paths: {writes}\n"
            f"- Exclusions: none\n- Shared resources: {resources}\n"
            "- Acceptance: The fixture returns count 3\n"
            "- Stop: The fixture contract changes\n"
            "- Resume: Recheck the approved fixture contract\n")


class TaskDagTest(unittest.TestCase):
    def test_marked_projection_separates_dependencies_from_declared_collisions(self):
        plan = (MARKER + microcontract("1.1", writes="src/a.py", resources="db:test")
                + microcontract("1.2", writes="src/a.py")
                + microcontract("1.3", resources="db:test")
                + microcontract("1.4", writes="src/b.py")
                + microcontract("1.5", parents="1.1", needs="1.1 => output-1.1")
                + microcontract("1.6", writes="src/b.py"))
        tasks = "".join(f"- [{mark}] 1.{i} Task {i}\n"
                        for i, mark in enumerate("~     ", 1))
        for args in ((), ("--format", "mermaid")):
            with self.subTest(args=args):
                output = self.output(plan, tasks, *args)
                self.assertIn("Dependency ready: 1.2, 1.3, 1.4, 1.6", output)
                self.assertIn("Next front: 1.4", output)
                self.assertIn("declared conflicts only", output)
                self.assertIn("path src/a.py: 1.1, 1.2", output)
                self.assertIn("resource db:test: 1.1, 1.3", output)
                self.assertIn("path src/b.py: 1.4, 1.6", output)
                edges = [line.strip() for line in output.splitlines() if " --> " in line]
                self.assertEqual(edges[-1:], ["task_1_1 --> task_1_5" if args else "1.1 --> 1.5"])
                self.assertFalse(any("1_2 -->" in line or "1.2 -->" in line for line in edges))

    def test_marked_contract_requires_one_matching_output_per_dependency(self):
        parents = microcontract("1.1") + microcontract("1.2")
        tasks = "- [x] 1.1 First\n- [x] 1.2 Second\n- [ ] 1.3 Consumer\n"
        valid = "1.1 => output-1.1\n1.2 => output-1.2"
        self.assertIn("Next front: 1.3", self.output(
            MARKER + parents + microcontract("1.3", parents="1.1, 1.2", needs=valid), tasks))
        for needs in ("none", "1.1 => output-1.1", valid + "\n1.1 => output-1.1",
                      valid.replace("output-1.2", "wrong-output"), valid + "\n1.9 => output-1.9"):
            with self.subTest(needs=needs):
                self.invalid(MARKER + parents + microcontract("1.3", parents="1.1, 1.2", needs=needs),
                             tasks, "task 1.3")

    def test_marked_contract_ignores_examples_and_rejects_placeholders(self):
        valid = microcontract("1.1")
        tasks = "- [ ] 1.1 Actual\n"
        examples = "```md\nBridge task contract: 99\n- Owner/resolver: Example\n```\n"
        self.assertIn("Next front: 1.1", self.output(MARKER + valid + examples, tasks))
        for placeholder in ("<!-- owner -->", "TBD", "<owner>", "none"):
            with self.subTest(placeholder=placeholder):
                self.invalid(MARKER + valid.replace("Alice", placeholder) + examples,
                             tasks, "Owner/resolver")

    def test_marked_contract_rejects_bad_claims(self):
        valid = microcontract("1.1", writes="src/a.py", resources="db:fixture")
        for old, new in (("src/a.py", "../a.py"), ("src/a.py", "src/*.py"),
                         ("src/a.py", "/src/a.py"), ("src/a.py", "src//a.py"),
                         ("db:fixture", "a shared thing"), ("db:fixture", "none, db:a"),
                         ("Exclusions: none", "Exclusions: src/a.py")):
            with self.subTest(new=new):
                self.invalid(MARKER + valid.replace(old, new), "- [ ] 1.1 Real\n", "task 1.1")

    def test_marked_dag_does_not_release_successors_from_raw_html_checkboxes(self):
        plan = (MARKER + microcontract("1.1")
                + microcontract("1.2", parents="1.1", needs="1.1 => output-1.1"))
        tasks = "<pre>\n- [x] 1.1 Producer\n</pre>\n- [ ] 1.2 Consumer\n"
        self.invalid(plan, tasks, "tasks.md:1: raw HTML")

    def test_marked_dag_rejects_noncanonical_checkboxes(self):
        for bullet in ("*", "+", "1.", "1)", "  -", "  *", "- -", "> -"):
            with self.subTest(bullet=bullet):
                self.invalid(MARKER + microcontract("1.1"),
                             f"- [x] 1.1 Actual\n{bullet} [ ] 1.2 Unfinished\n",
                             "tasks.md:2: expected a top-level checkbox")

    def test_marked_dag_ignores_html_and_checkboxes_inside_comments_and_fences(self):
        plan = MARKER + microcontract("1.1")
        tasks = ("<!-- <div> * [x] 1.2 Example </div> -->\n"
                 "```html\n<pre>\n1. [x] 1.2 Example\n</pre>\n```\n"
                 "- [ ] 1.1 Actual <!-- note -->\n")
        self.assertIn("Next front: 1.1", self.output(plan, tasks))

    def test_marked_dag_rejects_duplicate_claims_and_edges_even_with_extra_spacing(self):
        plan = MARKER + microcontract("1.1") + microcontract("1.2", resources="db:fixture")
        tasks = "- [ ] 1.1 First\n- [ ] 1.2 Second\n"
        for duplicate, message in (("-  Shared resources: db:fixture\n", "Shared resources"),
                                   ("-\tDepends on: 1.1\n", "duplicate Depends on"),
                                   ("  - Shared resources: db:fixture\n", "Shared resources")):
            with self.subTest(duplicate=duplicate):
                self.invalid(plan + duplicate, tasks, message)

    def test_marked_dag_reads_top_level_claims_and_edges_with_extra_spacing(self):
        plan = (MARKER + microcontract("1.1", resources="db:fixture")
                + microcontract("1.2", resources="db:fixture")
                + microcontract("1.3", parents="1.1", needs="1.1 => output-1.1"))
        plan = plan.replace("- Shared resources:", "-  Shared\tresources :")
        plan = plan.replace("- Depends on:", "-\tDepends  on :")
        output = self.output(plan, "- [ ] 1.1 First\n- [ ] 1.2 Second\n- [ ] 1.3 Third\n")
        self.assertIn("1.1 --> 1.3", output)
        self.assertIn("resource db:fixture: 1.1, 1.2", output)
        self.assertIn("Next front: 1.1\n", output)

    def test_unknown_or_duplicate_marker_does_not_use_legacy_projection(self):
        for prefix in (MARKER + MARKER, "Bridge task contract: 2\n", "Bridge task contract:\n",
                       "Bridge task contract : 1\n"):
            with self.subTest(prefix=prefix):
                self.invalid(prefix + self.plan(("1.1", "none")), self.tasks(" "), "contract marker")

    def test_ordinary_legacy_prose_is_not_a_contract_declaration(self):
        plan = "Bridge task contract details are tracked by the owner.\n" + self.plan(("1.1", "none"))
        self.assertIn("Next front: 1.1", self.output(plan, self.tasks(" ")))

    def test_legacy_comment_and_indented_fence_examples_do_not_activate_contract(self):
        plan = ("<!-- Legacy example\nBridge task contract: 9\n-->\n"
                "  ```md\nBridge task contract: 8\n  ```\n" + self.plan(("1.1", "none")))
        self.assertIn("Next front: 1.1", self.output(plan, self.tasks(" ")))

    def test_dag_marker_discovery_ignores_legacy_inline_comment_example(self):
        example = "Example: <!--\nBridge task contract: 1\n-->\n"
        self.assertIn("Next front: 1.1", self.output(example + self.plan(("1.1", "none")), self.tasks(" ")))
        self.invalid(example + MARKER + microcontract("1.1"), "- [ ] 1.1 Visible\n",
                     "plan.md:1: comment must close on the same line")

    def test_marked_dag_accepts_indented_single_line_code_span(self):
        self.assertIn("Next front: 1.1", self.output(MARKER + microcontract("1.1"),
                                                     "- [ ] 1.1 Visible\n  ```literal```\n"))

    def test_marked_dag_does_not_hide_a_checkbox_after_a_quoted_comment_opener(self):
        plan = MARKER + microcontract("1.1")
        tasks = ("- [ ] 1.1 Visible\nThe opener is ``see `<!--` here``.\n"
                 "- [ ] 1.2 Missing in plan\nThe closer is `-->`.\n")
        self.invalid(plan, tasks, "tasks.md:2: comment delimiter")

    def test_quoted_comment_opener_cannot_hide_contract_marker(self):
        plan = "The opener is `<!--`.\n" + MARKER + "The closer is `-->`.\n" + microcontract("1.1")
        self.invalid(plan, "- [ ] 1.1 Visible\n", "plan.md:1: comment delimiter")

    def test_real_comments_can_follow_inline_code_in_marked_artifacts(self):
        plan = MARKER + microcontract("1.1")
        tasks = ("See `notes.md`. <!-- Real inline comment with `backticks`. -->\n"
                 "````md\n<!-- Sample comment\n  ```\nThe opener is `<!--.\n"
                 "- [ ] 1.2 Example\n-->\n````\n- [ ] 1.1 Visible\n")
        self.assertIn("Next front: 1.1", self.output(plan, tasks))

    def test_marked_dag_rejects_escaped_comment_delimiter_before_extra_task(self):
        tasks = ('- [ ] 1.1 Existing task\n\nLiteral \\<!-- in prose.\n\n'
                 '- [ ] 1.2 Real extra task\n\nLiteral --> in prose.\n')
        self.invalid(MARKER + microcontract('1.1'), tasks, 'tasks.md:3: escaped comment delimiter')
        self.assertIn('Next front: 1.1, 1.2\n',
                      self.output(self.plan(('1.1', 'none'), ('1.2', 'none')), tasks))

    def test_even_backslashes_do_not_escape_a_real_comment(self):
        tasks = ('Prose \\\\<!-- real comment -->\n'
                 '- [ ] 1.1 Existing task\n')
        self.assertIn('Next front: 1.1', self.output(MARKER + microcontract('1.1'), tasks))

    def test_marked_dag_rejects_ambiguous_comment_openers_before_extra_task(self):
        for opener, message in (('Literal \\` then `<!--` in prose.', 'comment delimiter in inline code'),
                                ('    <!-- code example', 'comment must close on the same line'),
                                ('\t<!-- code example', 'comment must close on the same line'),
                                ('Prose <!-- unfinished inline', 'comment must close on the same line'),
                                ('<!-- first --> <!-- second', 'comment must close on the same line'),
                                ('<!-- first\n--> <!-- second', 'comment must close on the same line')):
            with self.subTest(opener=opener):
                tasks = '- [ ] 1.1 Existing task\n\n' + opener + '\n\n- [ ] 1.2 Visible\n\nLiteral --> in prose.\n'
                self.invalid(MARKER + microcontract('1.1'), tasks, message)

    def test_marked_dag_rejects_multiline_inline_syntax_and_indented_fences(self):
        for tail, message in (
            ('  <!-- comment inside first item\n- [ ] 1.2 Extra top-level item\n\n-->\n',
             'comment must close on the same line'),
            ('The example starts `on this line\n<!-- literal -->\nand ends here`.\n',
             'inline code must close on the same line'),
            ('  ```\n- [ ] 1.2 Extra\n\n```\n', 'indented fence'),
        ):
            with self.subTest(message=message):
                self.invalid(MARKER + microcontract('1.1'), '- [ ] 1.1 Existing\n' + tail,
                             'tasks.md:2: ' + message)

    def run_dag(self, plan, tasks, *args, seed="0"):
        with tempfile.TemporaryDirectory() as directory:
            change = Path(directory)
            if plan is not None:
                (change / "plan.md").write_text(plan, encoding="utf-8")
            (change / "tasks.md").write_text(tasks, encoding="utf-8")
            before = {path.name: path.read_bytes() for path in change.iterdir()}
            result = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "--change", directory, *args],
                capture_output=True, text=True, encoding="utf-8", timeout=5,
                env={**os.environ, "PYTHONHASHSEED": seed},
            )
            self.assertEqual(before, {path.name: path.read_bytes() for path in change.iterdir()})
            return result

    def output(self, plan, tasks, *args, seed="0"):
        result = self.run_dag(plan, tasks, *args, seed=seed)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return result.stdout

    def invalid(self, plan, tasks, message):
        result = self.run_dag(plan, tasks)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn(message, result.stderr)

    def test_ascii_shows_branch_join_states_and_next_front(self):
        plan = self.plan(("1.4: Integrate", "1.3, 1.2"), ("1.3", "1.1"),
                         ("1.2: Build CLI", "1.1"), ("1.1: Prepare interface", "none"))
        tasks = "- [ ] 1.4 Merge\n- [ ] 1.3 Write docs\n- [ ] 1.2 CLI\n- [x] 1.1 Setup\n"
        output = self.output(plan, tasks)
        self.assertEqual(output, self.output(plan, tasks, "--format", "ascii", seed="23"))
        self.assertIn("1.1 --> {1.2, 1.3}", output)
        self.assertIn("{1.2, 1.3} --> 1.4", output)
        self.assertIn("1.1 [x] checked none Prepare interface", self.compact(output))
        self.assertIn("1.3 [ ] ready 1.1 Write docs", self.compact(output))
        self.assertIn("1.4 [ ] blocked 1.2, 1.3 Integrate", self.compact(output))
        self.assertIn("Next front: 1.2, 1.3\n", output)
        self.assertIn("not acceptance", output)
        self.assertIn("safe parallelism", output)

    def test_ascii_table_keeps_long_ids_without_padding_other_rows_to_their_width(self):
        long_id = "1.1234567890123456789012345678901234567890"
        plan = self.plan(("1.1", "none"), (long_id, "none"), ("1.2", long_id))
        output = self.output(plan, f"- [ ] 1.1\n- [x] {long_id}\n- [ ] 1.2\n")
        short_row = next(line for line in output.splitlines() if line.startswith("1.1 "))
        self.assertLessEqual(short_row.index("[ ]") - len("1.1"), 23)
        self.assertIn(f"{long_id} [x] checked none", self.compact(output))
        self.assertIn(f"1.2 [ ] ready {long_id} Task", self.compact(output))

    def test_mermaid_shows_same_nodes_and_direct_edges(self):
        plan = self.plan(("1.1: Interface", "none"), ("1.2: CLI", "1.1"),
                         ("1.3: Guide", "1.1"), ("1.4: Integrate", "1.2, 1.3"))
        output = self.output(plan, self.tasks("x", " ", " ", " "), "--format", "mermaid")
        self.assertTrue(output.startswith("flowchart LR\n"))
        self.assertEqual([line.strip() for line in output.splitlines() if " --> " in line],
                         ["task_1_1 --> task_1_2", "task_1_1 --> task_1_3",
                          "task_1_2 --> task_1_4", "task_1_3 --> task_1_4"])
        self.assertIn('task_1_1["1.1 Interface (checked)"]', output)
        self.assertIn('task_1_4["1.4 Integrate (blocked)"]', output)

    def test_missing_metadata_never_satisfies_a_checked_dependency(self):
        plan = self.plan(("1.1: Legacy", None), ("1.2: Descendant", "1.1"),
                         ("1.3: Explicit root", "none"))
        output = self.output(plan, self.tasks("x", " ", " "))
        self.assertIn("1.1 [x] unknown unknown Legacy", self.compact(output))
        self.assertIn("1.2 [ ] blocked 1.1 Descendant", self.compact(output))
        self.assertIn("Next front: 1.3\n", output)

    def test_legacy_plan_does_not_guess_dependencies_from_prose(self):
        plan = "## Task 1.1\n- Inputs and dependencies: none\n## Task 1.2\n"
        output = self.output(plan, "- [x] 1.1 A\n- [ ] 1.2 B\n")
        self.assertIn("1.2 [ ] unknown unknown B", self.compact(output))
        self.assertIn("Next front: none\n", output)

    def test_transitively_inconsistent_checkbox_never_releases_successor(self):
        plan = self.plan(("1.1", "none"), ("1.2", "1.1"), ("1.3", "1.2"), ("1.4", "1.3"))
        output = self.compact(self.output(plan, self.tasks(" ", "X", "x", " ")))
        self.assertIn("1.2 [x] inconsistent", output)
        self.assertIn("1.3 [x] inconsistent", output)
        self.assertIn("1.4 [ ] blocked", output)
        self.assertIn("Next front: 1.1\n", output)

    def test_examples_in_fences_comments_and_nested_bullets_are_not_metadata(self):
        plan = ("## Task 1.1\n   ~~~~markdown\n## Task 9.9\n~~~\n- Depends on: none\n   ~~~~\n"
                "`````\n- Depends on: none\n## Task 9.8\n`````\n"
                "<!-- example\n- Depends on: none\n## Task 9.7\n-->\n"
                "- Example:\n  - Depends on: none\n")
        tasks = "- [ ] 1.1 Actual\n  - [x] 9.4\n```md\n- [x] 9.5\n```\n<!--\n- [x] 9.6\n-->\n"
        output = self.output(plan, tasks)
        self.assertIn("1.1 [ ] unknown", self.compact(output))
        self.assertIn("Next front: none\n", output)

    def test_dependency_outside_task_section_is_not_used(self):
        output = self.output("## Task 1.1\n## Notes\n- Depends on: none\n", self.tasks(" "))
        self.assertIn("Next front: none\n", output)

    def test_setext_section_boundary_is_equivalent_to_atx(self):
        plan = "## Task 1.1\n\n{heading}\n- Depends on: none\n"
        tasks = self.tasks(" ")
        for atx, setext in (("## Notes", "Notes\n-----"), ("# Notes", "Notes\n=====")):
            with self.subTest(heading=atx):
                expected = self.output(plan.format(heading=atx), tasks)
                self.assertIn("Next front: none\n", expected)
                self.assertEqual(self.output(plan.format(heading=setext), tasks), expected)

    def test_tilde_checkbox_is_retained_and_never_releases_successors(self):
        plan = self.plan(("1.1", "none"), ("1.2", "1.1"), ("1.3", "1.2"), ("1.4", None))
        tasks = self.tasks("~", "x", " ", "~")
        output = self.compact(self.output(plan, tasks))
        self.assertIn("1.1 [~] marked none Task", output)
        self.assertIn("1.2 [x] inconsistent 1.1", output)
        self.assertIn("1.3 [ ] blocked 1.2", output)
        self.assertIn("1.4 [~] unknown unknown", output)
        self.assertIn("Next front: none\n", output)
        self.assertIn("does not prove execution", output)
        mermaid = self.output(plan, tasks, "--format", "mermaid")
        self.assertIn('task_1_1["1.1 Task [~] (marked)"]', mermaid)
        self.assertIn('task_1_4["1.4 Task [~] (unknown)"]', mermaid)

    def test_tilde_checkbox_cannot_hide_a_duplicate_id(self):
        plan = self.plan(("1.1", "none"), ("1.2", "1.1"))
        for first, second in (("x", "~"), ("~", "x")):
            with self.subTest(first=first):
                self.invalid(plan, f"- [{first}] 1.1 A\n- [{second}] 1.1 B\n- [ ] 1.2 C\n",
                             "duplicate task ID 1.1")

    def test_titles_cannot_add_markup_mermaid_statements_or_terminal_controls(self):
        controls = "\x1b\u202e\u2028"
        title = 'Useful title " ]; <b>bold</b> %%{directive}%% `command` | &lt;tag&gt; '
        plan = self.plan(("1.1: " + title + controls + " tail", "none"))
        for args in ((), ("--format", "mermaid")):
            output = self.output(plan, self.tasks(" "), *args)
            self.assertIn("Useful title", output)
            self.assertIn("tail", output)
            for token in (*controls, "<b>", "%%{", "&lt;", "`command`"):
                self.assertNotIn(token, output)
            if args:
                lines = [line for line in output.splitlines() if not line.strip().startswith("%%")]
                self.assertEqual(len(lines), 2)
                self.assertEqual(lines[1].count('"'), 2)

    def test_id_divergence_rejected_both_ways(self):
        self.invalid("## Task 1.1\n", "- [ ] 1.2\n", "ID mismatch")
        self.invalid("## Task 1.1\n## Task 1.2\n", self.tasks(" "), "ID mismatch")
        self.invalid("# Plan\n", self.tasks(" "), "ID mismatch")

    def test_duplicate_ids_and_dependency_declarations_rejected(self):
        self.invalid("## Task 1.1\n## Task 1.1\n", self.tasks(" "), "duplicate task ID 1.1")
        self.invalid("## Task 1.1\n", "- [ ] 1.1\n- [x] 1.1\n", "duplicate task ID 1.1")
        self.invalid("## Task 1.1\n- Depends on: none\n- Depends on: none\n",
                     self.tasks(" "), "duplicate Depends on")

    def test_invalid_dependencies_rejected(self):
        for value, message in (("1.9", "unknown dependency 1.9"),
                               ("1.2", "self-dependency"),
                               ("", "invalid Depends on"),
                               ("none, 1.1", "invalid Depends on"),
                               ("1.1,", "invalid Depends on"),
                               ("1.1, 1.1", "duplicate dependency")):
            with self.subTest(value=value):
                self.invalid(self.plan(("1.1", "none"), ("1.2", value)),
                             self.tasks(" ", " "), message)

    def test_cycle_rejected_even_when_checkboxes_are_checked(self):
        self.invalid(self.plan(("1.1", "1.2"), ("1.2", "1.1")),
                     self.tasks("x", "x"), "dependency cycle")

    def test_missing_artifact_reports_error_without_rendering(self):
        self.invalid(None, self.tasks(" "), "plan.md")

    def test_symlink_artifacts_are_rejected(self):
        self.check_artifact_type(lambda path, target: path.symlink_to(target), "symbolic link")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFOs")
    def test_fifo_artifacts_are_rejected_without_waiting_for_a_writer(self):
        self.check_artifact_type(lambda path, _: os.mkfifo(path), "regular file")

    def test_directory_artifacts_are_rejected(self):
        self.check_artifact_type(lambda path, _: path.mkdir(), "regular file")

    def check_artifact_type(self, create_entry, reason):
        inputs = {"plan.md": self.plan(("1.1", "none")), "tasks.md": self.tasks(" ")}
        for name, text in inputs.items():
            with self.subTest(artifact=name), tempfile.TemporaryDirectory() as directory:
                change = Path(directory)
                for other, contents in inputs.items():
                    if other != name:
                        (change / other).write_text(contents, encoding="utf-8")
                target = change / "local-fixture.md"
                target.write_text(text, encoding="utf-8")
                create_entry(change / name, target)
                try:
                    result = subprocess.run(
                        [sys.executable, "-B", str(SCRIPT), "--change", directory],
                        capture_output=True, text=True, encoding="utf-8", timeout=2,
                    )
                except subprocess.TimeoutExpired:
                    self.fail(f"CLI blocked on local fixture {name}")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertIn(name, result.stderr)
                self.assertIn(reason, result.stderr)

    def test_artifact_size_limit_is_four_mib_per_file(self):
        limit = 4 * 1024 * 1024
        plan, tasks = self.plan(("1.1", "none")), self.tasks(" ")
        self.output(plan + "#" * (limit - len(plan)), tasks + "#" * (limit - len(tasks)))
        for name, contents in (("plan.md", plan), ("tasks.md", tasks)):
            with self.subTest(artifact=name):
                oversized = contents + "#" * (limit + 1 - len(contents))
                self.invalid(oversized if name == "plan.md" else plan,
                             oversized if name == "tasks.md" else tasks,
                             f"{name}: exceeds 4 MiB")

    def test_no_task_ids_fails_closed_in_both_formats(self):
        for args in ((), ("--format", "mermaid")):
            with self.subTest(args=args):
                result = self.run_dag("# Plan\n", "# Tasks\n", *args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertIn("no task IDs", result.stderr)

    @staticmethod
    def plan(*entries):
        return "".join(f"## Task {heading}\n" +
                       (f"- Depends on: {parents}\n" if parents is not None else "")
                       for heading, parents in entries)

    @staticmethod
    def tasks(*marks):
        return "".join(f"- [{mark}] 1.{i}\n" for i, mark in enumerate(marks, 1))

    @staticmethod
    def compact(output):
        return "\n".join(" ".join(line.split()) for line in output.splitlines()) + "\n"

    def test_review_a2_inline_multiline_comment_hides_legacy_dependency(self):
        hidden = '## Task 1.1\nNotes: <!--\n- Depends on: none\n-->\n'
        output = self.output(hidden, '- [ ] 1.1 Actual\n')
        self.assertIn('1.1 [ ] unknown', self.compact(output))
        self.assertIn('Next front: none\n', output)
        self.assertIn('Next front: 1.1\n', self.output(hidden + '- Depends on: none\n', '- [ ] 1.1 Actual\n'))
        quoted = '## Task 1.1\nExample `<!--` in prose.\n- Depends on: none\n'
        self.assertIn('Next front: 1.1\n', self.output(quoted, '- [ ] 1.1 Actual\n'))

    def test_review_a5_legacy_reads_two_space_checkbox_indentation(self):
        tasks = '  - [ ] 1.1 Actual\n'
        self.assertIn('Next front: 1.1\n', self.output(self.plan(('1.1', 'none')), tasks))
        self.invalid(MARKER + microcontract('1.1'), tasks, 'top-level checkbox')

    def test_review_a6_inline_links_are_not_malformed_tasks(self):
        plan = MARKER + microcontract('1.1')
        tasks = '- [Design](design.md)\n- [ ] 1.1 Actual\n'
        self.assertIn('Next front: 1.1\n', self.output(plan, tasks))
        for bad in ('- [?] 1.1 Invalid', '- [x] 1.1 Duplicate', '- [x](design.md)'):
            self.invalid(plan, tasks + bad + '\n', 'tasks.md:3:')

    def test_adjust_a2_chained_multiline_comments_stay_hidden(self):
        tasks = '- [ ] 1.1 Actual\n'
        for opening in ('Notes: <!-- First\n--> <!-- Second', '<!-- First --> <!-- Second'):
            with self.subTest(opening=opening):
                comment = opening + '\n- Depends on: none\n-->\n'
                hidden = '## Task 1.1\n' + comment
                output = self.output(hidden, tasks)
                self.assertIn('1.1 [ ] unknown', self.compact(output))
                self.assertIn('Next front: none\n', output)
                self.assertIn('Next front: 1.1\n', self.output(hidden + '- Depends on: none\n', tasks))
                self.invalid(MARKER + microcontract('1.1') + comment, tasks, 'comment must close on the same line')

    def test_adjust_a6_titled_and_reference_links_are_documentation(self):
        plan = MARKER + microcontract('1.1')
        links = ('- [Design](design.md "Design notes")\n'
                 '- [Design][notes]\n\n[notes]: design.md\n')
        tasks = '- [Design](design.md)\n- [ ] 1.1 Actual\n\n[notes]: design.md\n'
        for link in links.splitlines()[:2]:
            with self.subTest(link=link):
                self.assertIn('Next front: 1.1\n', self.output(plan, link + '\n[notes]: design.md\n- [ ] 1.1 Actual\n'))
        for bad in ('- [?] 1.1 [Design][notes]', '- [x] 1.1 Duplicate',
                    '- [x][notes]', '- [Design](design.md "unfinished)', '- [Design][notes'):
            with self.subTest(bad=bad):
                self.invalid(plan, tasks + bad + '\n', 'tasks.md:5:')

    def test_adjust_a6_complete_links_allow_attached_prose(self):
        plan = MARKER + microcontract('1.1')
        for link in ('[Design](design.md)', '[Design](design.md "Design notes")', '[Design][notes]'):
            for suffix in ('.', ', for context', ' and see the notes'):
                with self.subTest(link=link, suffix=suffix):
                    tasks = f'- {link}{suffix}\n- [ ] 1.1 Actual\n\n[notes]: design.md\n'
                    self.assertIn('Next front: 1.1\n', self.output(plan, tasks))
