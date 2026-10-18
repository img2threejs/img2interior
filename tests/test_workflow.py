"""Consumer-facing workflow regressions, using the real installed core and CLIs.

Set IMG2_HARNESS_SOURCE to a local img2 checkout, or install ~/.img2/harness.
No third-party libraries, network access, or generated visual certifications.
"""

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


PLUGIN = Path(__file__).resolve().parent.parent
STAGES = ("intake", "camera", "geometry", "materials", "lighting", "interaction", "delivery", "review")
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=")


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = Path(os.environ.get("IMG2_HARNESS_SOURCE", str(Path.home() / ".img2/harness"))).expanduser().resolve()
        if not (cls.harness / "img2_core/gate_runner.py").is_file():
            raise RuntimeError("Install img2 or set IMG2_HARNESS_SOURCE to its checkout before running workflow tests")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="interior workflow ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "user project"
        self.workspace.mkdir()
        home = self.root / "img2 home"
        home.mkdir()
        (home / "harness").symlink_to(self.harness, target_is_directory=True)
        self.env = {**os.environ, "IMG2_HOME": str(home), "PYTHONPATH": str(self.harness), "PYTHONDONTWRITEBYTECODE": "1"}
        self.image = self.root / "reference.png"
        self.image.write_bytes(PNG)
        self.intake = self.workspace / "author-intake.json"
        self.intake_data = {"schemaVersion": 1, "sourceKind": "synthetic-design-reference",
                            "authorization": "Authored reference, approved for this project.",
                            "scale": {"unit": "m", "basis": "authored-estimate", "note": "Sofa scale is an authored estimate, not measured."},
                            "components": ["sofa", "linen curtains"], "unknowns": ["Unseen wall depth"],
                            "interactionRequired": True}
        self.intake.write_text(json.dumps(self.intake_data), encoding="utf-8")
        self.snapshot = self.workspace / ".img2/artifacts/interior/intake.json"
        self.state_path = self.workspace / ".img2/state.json"

    def execute(self, argv, expected=0):
        proc = subprocess.run(argv, cwd=self.workspace, env=self.env, text=True, capture_output=True, timeout=30)
        self.assertEqual(proc.returncode, expected, f"{argv}\nstdout: {proc.stdout}\nstderr: {proc.stderr}")
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.fail(f"Expected exactly one JSON document, got {proc.stdout!r}; stderr={proc.stderr!r}")
        self.assertIsInstance(result, dict)
        return result

    def cli(self, command, *args, expected=0):
        return self.execute([sys.executable, str(PLUGIN / "tools/interior_workflow.py"), command,
                             "--workspace", str(self.workspace), *map(str, args)], expected)

    def gate(self, expected=0):
        result = self.execute([sys.executable, str(PLUGIN / "tools/gate_workflow.py"),
                               "--workspace", str(self.workspace)], expected)
        self.assertEqual(set(result), {"kind", "version", "gate", "plugin", "status", "reasons", "evidence"})
        self.assertEqual(result["kind"], "img2.gate-verdict")
        self.assertEqual(result["version"], 1)
        self.assertEqual(result["gate"], "interior-workflow")
        self.assertEqual(result["plugin"], "interior")
        self.assertEqual(result["status"], {0: "pass", 1: "fail", 2: "error"}[expected])
        self.assertEqual(bool(result["reasons"]), expected != 0)
        return result

    def init(self, expected=0):
        return self.cli("init", "--image", self.image, "--intake", self.intake, expected=expected)

    def evidence(self, stage):
        if stage == "intake":
            return self.snapshot
        path = self.workspace / f"{stage}-review.txt"
        if not path.exists():
            path.write_text(f"Explicit {stage} review fixture; not a visual quality certificate.\n", encoding="utf-8")
        return path

    def record(self, stage, decision="accept", expected=0, evidence=None):
        paths = [self.evidence(stage)] if evidence is None else evidence
        args = ["--stage", stage, "--decision", decision, "--reviewer", "Named reviewer", "--note", f"Reviewed {stage}: {decision}"]
        for path in paths:
            args.extend(["--evidence", str(path)])
        return self.cli("record", *args, expected=expected)

    def complete(self):
        self.init()
        for stage in STAGES:
            self.record(stage)

    def state(self):
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def run_state(self):
        return self.state()["plugins"]["interior"]

    def fingerprint(self):
        return {str(path.relative_to(self.workspace)): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in self.workspace.rglob("*") if path.is_file()}

    def test_init_snapshots_source_and_intake_without_acceptance(self):
        result = self.init()
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["nextStage"], "intake")
        run = self.run_state()
        self.assertEqual(run["source"]["sha256"], hashlib.sha256(PNG).hexdigest())
        self.assertEqual(json.loads(self.snapshot.read_text()), self.intake_data)
        self.assertEqual(run["intake"]["snapshot"]["sha256"], hashlib.sha256(self.snapshot.read_bytes()).hexdigest())
        self.assertTrue(all(item["status"] == "pending" for item in run["stages"].values()))
        self.assertEqual(len(run["history"]), 1)
        self.gate(expected=1)
        self.assertEqual(self.image.read_bytes(), PNG)

    def test_complete_run_and_read_only_consumers(self):
        self.complete()
        before = self.fingerprint()
        self.assertEqual(self.cli("next")["status"], "completed")
        self.assertEqual(self.cli("report")["workflow"], self.run_state())
        self.gate()
        self.assertEqual(self.fingerprint(), before)

    def test_missing_run_reads_do_not_create_state(self):
        before = self.fingerprint()
        self.assertEqual(self.cli("next")["action"], "init")
        self.assertIsNone(self.cli("report")["workflow"])
        self.gate(expected=1)
        self.assertEqual(self.fingerprint(), before)
        self.assertFalse((self.workspace / ".img2").exists())

    def test_wrong_order_and_duplicate_acceptance_do_not_change_history(self):
        self.init()
        before = self.run_state()
        self.record("camera", expected=1)
        self.assertEqual(self.run_state(), before)
        self.record("intake")
        before = self.run_state()
        self.record("intake", expected=2)
        self.assertEqual(self.run_state(), before)
        self.record("geometry", "reject", expected=1)
        self.assertEqual(self.run_state(), before)

    def test_reinitialize_refuses_without_resetting_any_history(self):
        self.complete()
        before = self.fingerprint()
        self.init(expected=2)
        self.assertEqual(self.fingerprint(), before)

    def test_intake_acceptance_requires_snapshot_and_nonempty_evidence(self):
        self.init()
        self.record("intake", evidence=[], expected=2)
        self.record("intake", evidence=[self.intake], expected=2)
        empty = self.workspace / "empty.txt"
        empty.touch()
        self.record("intake", evidence=[self.snapshot, empty], expected=2)
        self.record("intake", evidence=[self.snapshot, self.snapshot], expected=2)
        self.assertEqual(len(self.run_state()["history"]), 1)

    def test_reviewer_and_note_are_explicit_nonempty_attestations(self):
        self.init()
        for reviewer, note in ((" ", "reviewed"), ("reviewer", " ")):
            with self.subTest(reviewer=reviewer, note=note):
                self.cli("record", "--stage", "intake", "--decision", "accept", "--reviewer", reviewer,
                         "--note", note, "--evidence", self.snapshot, expected=2)
        self.cli("record", "--stage", "intake", "--decision", "accept", "--note", "reviewed",
                 "--evidence", self.snapshot, expected=2)
        self.assertEqual(len(self.run_state()["history"]), 1)

    def test_source_change_blocks_acceptance_and_gate_without_repinning(self):
        self.init()
        self.record("intake")
        before = self.run_state()
        self.image.write_bytes(PNG + b"changed")
        self.record("camera", expected=1)
        self.assertEqual(self.run_state(), before)
        self.assertEqual(self.cli("next")["status"], "blocked")
        self.gate(expected=1)
        self.cli("revise", "--from", "intake", "--reason", "Reconsider source")
        self.record("intake", expected=1)
        self.assertEqual(self.run_state()["source"], before["source"])

    def test_earlier_changed_or_missing_evidence_blocks_later_acceptance(self):
        self.init()
        self.record("intake")
        self.record("camera")
        camera = self.evidence("camera")
        original = camera.read_bytes()
        camera.write_bytes(original + b"changed")
        self.record("geometry", expected=1)
        self.gate(expected=1)
        camera.unlink()
        self.record("geometry", expected=1)
        camera.write_bytes(original)
        self.record("geometry")

    def test_final_gate_checks_source_intake_and_every_stage_evidence(self):
        self.complete()
        for path in [self.image, self.intake, self.snapshot, *(self.evidence(stage) for stage in STAGES[1:])]:
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(original + b"\nchanged")
                self.gate(expected=1)
                path.write_bytes(original)
        self.gate()

    def test_rejection_invalidates_downstream_and_preserves_prior_history(self):
        self.complete()
        old = copy.deepcopy(self.run_state()["history"])
        result = self.record("geometry", "reject", expected=1)
        self.assertEqual((result["status"], result["nextStage"]), ("rejected", "geometry"))
        run = self.run_state()
        self.assertEqual(run["history"][:len(old)], old)
        self.assertEqual(run["stages"]["camera"]["status"], "accepted")
        self.assertEqual(run["stages"]["geometry"]["status"], "rejected")
        self.assertTrue(all(run["stages"][name]["status"] == "pending" for name in STAGES[3:]))
        self.gate(expected=1)
        self.record("geometry", expected=2)
        self.cli("revise", "--from", "geometry", "--reason", "Corrected form after review")
        for stage in STAGES[2:]:
            self.record(stage)
        self.gate()
        self.assertEqual(self.run_state()["history"][:len(old)], old)

    def test_revision_allows_new_evidence_without_mutating_old_receipts(self):
        self.complete()
        old = copy.deepcopy(self.run_state()["history"])
        self.evidence("camera").write_text("Revised matching-camera review\n")
        self.gate(expected=1)
        self.cli("revise", "--from", "camera", "--reason", "Re-author camera alignment")
        self.assertEqual(self.cli("next")["status"], "pending")
        for stage in STAGES[1:]:
            self.record(stage)
        self.gate()
        self.assertEqual(self.run_state()["history"][:len(old)], old)

    def test_request_input_and_stop_require_explicit_revision(self):
        self.init()
        self.record("intake")
        for decision, status in (("request-input", "blocked"), ("stop", "stopped")):
            with self.subTest(decision=decision):
                self.record("camera", decision, evidence=[], expected=3)
                before = self.fingerprint()
                self.assertEqual(self.cli("next", expected=3)["status"], status)
                self.cli("report")
                self.gate(expected=1)
                self.assertEqual(self.fingerprint(), before)
                self.record("camera", expected=2)
                self.cli("revise", "--from", "camera", "--reason", "Reviewer supplied missing information")
                self.assertEqual(self.cli("next")["status"], "pending")
        self.record("camera")

    def test_external_and_symlink_escaping_evidence_is_refused(self):
        self.init()
        external = self.root / "outside-review.txt"
        external.write_text("Outside workspace")
        link = self.workspace / "review-link.txt"
        link.symlink_to(external)
        for path in (external, link, self.workspace / "../outside-review.txt"):
            with self.subTest(path=str(path)):
                self.record("intake", evidence=[self.snapshot, path], expected=2)
        self.assertEqual(len(self.run_state()["history"]), 1)

    def test_intake_snapshot_accepts_workspace_path_alias(self):
        self.init()
        alias = self.root / "project-alias"
        alias.symlink_to(self.workspace, target_is_directory=True)
        self.record("intake", evidence=[alias / ".img2/artifacts/interior/intake.json"])
        for stage in STAGES[1:]:
            self.record(stage)
        self.gate()

    def test_retargeted_evidence_symlink_is_stale_even_if_bytes_match(self):
        self.init()
        self.record("intake")
        first = self.workspace / "first.txt"
        second = self.workspace / "second.txt"
        first.write_text("Same reviewer evidence")
        second.write_bytes(first.read_bytes())
        link = self.workspace / "camera-link.txt"
        link.symlink_to(first)
        self.record("camera", evidence=[link])
        link.unlink()
        link.symlink_to(second)
        self.record("geometry", expected=1)
        self.gate(expected=1)

    def test_other_plugin_and_audit_subtrees_survive_all_mutations(self):
        self.state_path.parent.mkdir()
        audits = {"materialAudit": {"receipt": "material", "passed": False}, "deliveryAudit": {"receipt": "delivery"}}
        other = {"schemaVersion": 17, "private": ["untouched", {"run": 42}]}
        self.state_path.write_text(json.dumps({"version": 1, "workspace": str(self.workspace),
                                               "plugins": {"other-plugin": other, "interior": audits}, "userField": "retain"}))
        self.init()
        self.record("intake")
        self.record("camera", "reject", expected=1)
        self.cli("revise", "--from", "camera", "--reason", "Reconsider camera")
        self.record("camera")
        state = self.state()
        self.assertEqual(state["plugins"]["other-plugin"], other)
        self.assertEqual(state["userField"], "retain")
        for key, value in audits.items():
            self.assertEqual(state["plugins"]["interior"][key], value)

    def test_malformed_intake_refused_without_snapshot_or_state(self):
        variants = ["", "{", '{"schemaVersion":1,"schemaVersion":1}', '{"schemaVersion":1e999}',
                    json.dumps({**self.intake_data, "components": ["sofa", "sofa"]}),
                    json.dumps({**self.intake_data, "schemaVersion": True}),
                    json.dumps({**self.intake_data, "interactionRequired": "yes"}),
                    json.dumps({**self.intake_data, "authorization": " "}),
                    json.dumps({**self.intake_data, "scale": {"unit": "m", "basis": "guessed", "note": "estimate"}}),
                    json.dumps({**self.intake_data, "untrustedNumber": float("nan")})]
        for data in variants:
            with self.subTest(data=data):
                self.intake.write_text(data)
                self.init(expected=2)
                self.assertFalse(self.snapshot.exists())
                self.assertFalse(self.state_path.exists())

    def test_empty_image_refused(self):
        self.image.write_bytes(b"")
        self.init(expected=2)
        self.assertFalse(self.snapshot.exists())

    def test_malformed_or_duplicate_state_never_passes_gate(self):
        self.complete()
        good = self.state_path.read_text()
        duplicate_stage = good.replace('"camera": {', '"camera": {"status":"accepted"}, "camera": {', 1)
        for bad in ("{", "[]", duplicate_stage, good.replace('"schemaVersion": 1', '"schemaVersion": NaN', 1)):
            with self.subTest(data=bad[:60]):
                self.state_path.write_text(bad)
                self.gate(expected=2)
                self.cli("report", expected=2)
        self.state_path.write_text(good)
        state = self.state()
        state["plugins"]["interior"]["history"] = []
        self.state_path.write_text(json.dumps(state))
        self.gate(expected=2)

    def test_forged_stage_summary_cannot_skip_missing_history(self):
        self.init()
        state = self.state()
        for stage in STAGES:
            state["plugins"]["interior"]["stages"][stage] = {"status": "accepted", "record": 1}
        self.state_path.write_text(json.dumps(state))
        self.gate(expected=2)

    def test_symlinked_control_directory_cannot_redirect_writes(self):
        outside = self.root / "outside-state"
        outside.mkdir()
        (self.workspace / ".img2").symlink_to(outside, target_is_directory=True)
        self.init(expected=2)
        self.assertEqual(list(outside.iterdir()), [])

    def test_real_gate_runner_pass_fail_and_error(self):
        # A one-gate manifest isolates this slice while invoking the real harness
        # runner and the actual shipped gate, not a substitute verdict script.
        registration = self.root / "runner plugin"
        registration.mkdir()
        command = f"{shlex.quote(sys.executable)} {shlex.quote(str(PLUGIN / 'tools/gate_workflow.py'))} --workspace \"{{workspace}}\""
        (registration / "gates.json").write_text(json.dumps([
            {"id": "interior-workflow", "command": command, "blocking": True, "after": []}]))
        argv = [sys.executable, "-m", "img2_core.gate_runner", "--plugin-dir", str(registration), "--workspace", str(self.workspace)]
        incomplete = self.execute(argv, expected=1)
        self.assertEqual(incomplete["kind"], "img2.gate-run")
        self.assertTrue(incomplete["stopped"])
        self.assertEqual([item["status"] for item in incomplete["results"]], ["fail"])
        self.complete()
        passed = self.execute(argv)
        self.assertFalse(passed["stopped"])
        self.assertEqual([item["status"] for item in passed["results"]], ["pass"])
        self.evidence("lighting").write_text("Changed after final review")
        failed = self.execute(argv, expected=1)
        self.assertEqual([item["status"] for item in failed["results"]], ["fail"])
        self.state_path.write_text("{not JSON}")
        errored = self.execute(argv, expected=1)
        self.assertEqual([item["status"] for item in errored["results"]], ["error"])
        self.assertEqual(errored["results"][0]["exitCode"], 2)



if __name__ == "__main__":
    unittest.main()
