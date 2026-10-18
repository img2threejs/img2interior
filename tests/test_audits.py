"""Black-box CLI regressions; uses the real img2 core and gate runner, never mock verdicts.

Set IMG2_HARNESS_SOURCE to a local harness checkout, or install ~/.img2/harness.
The harness is linked into a temporary IMG2_HOME; no host registration is changed.
"""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shlex
import struct
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parent.parent / "tools"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZ1sAAAAASUVORK5CYII=")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_file(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def mesh_fixture():
    positions = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    uvs = struct.pack("<6f", 0, 0, 1, 0, 0, 1)
    binary = positions + uvs + PNG
    document = {
        "asset": {"version": "2.0", "generator": "interior audit regression fixture"},
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(positions)},
                        {"buffer": 0, "byteOffset": len(positions), "byteLength": len(uvs)},
                        {"buffer": 0, "byteOffset": len(positions) + len(uvs), "byteLength": len(PNG)}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3",
                       "min": [0, 0, 0], "max": [1, 1, 0]},
                      {"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC2"}],
        "images": [{"bufferView": 2, "mimeType": "image/png"}],
        "textures": [{"source": 0}],
        "materials": [{"name": "Linen", "pbrMetallicRoughness": {
            "baseColorTexture": {"index": 0}, "metallicRoughnessTexture": {"index": 0},
            "roughnessFactor": 0.9, "metallicFactor": 0}, "normalTexture": {"index": 0, "scale": 0.7},
            "extensions": {"KHR_materials_sheen": {"sheenColorFactor": [0.12, 0.12, 0.12]}}}],
        "extensionsUsed": ["KHR_materials_sheen"],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "TEXCOORD_0": 1}, "material": 0}]}],
        "nodes": [{"mesh": 0}], "scenes": [{"nodes": [0]}], "scene": 0,
    }
    return document, binary


def write_glb(path, document, binary):
    payload = json.dumps(document, separators=(",", ":")).encode()
    payload += b" " * (-len(payload) % 4)
    chunks = struct.pack("<II", len(payload), 0x4E4F534A) + payload
    if binary is not None:
        binary += b"\x00" * (-len(binary) % 4)
        chunks += struct.pack("<II", len(binary), 0x004E4942) + binary
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, len(chunks) + 12) + chunks)


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = Path(os.environ.get("IMG2_HARNESS_SOURCE", str(Path.home() / ".img2/harness"))).expanduser().resolve()
        if not (cls.harness / "img2_core/gate_runner.py").is_file():
            raise unittest.SkipTest("real img2 harness required: set IMG2_HARNESS_SOURCE or install ~/.img2/harness")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="interior-audits-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "workspace with spaces"
        self.workspace.mkdir()
        self.home = self.root / "home"
        self.home.mkdir()
        (self.home / "harness").symlink_to(self.harness, target_is_directory=True)
        self.env = dict(os.environ, IMG2_HOME=str(self.home), PYTHONDONTWRITEBYTECODE="1",
                        PYTHONPATH=str(self.home / "harness"))
        self.assets = self.root / "external assets"
        self.assets.mkdir()
        self.glb = self.assets / "runtime.glb"
        self.document, self.binary = mesh_fixture()
        self.write_model()
        self.policy = self.root / "policy.json"
        self.policy_data = {"schemaVersion": 1, "materials": [{"name": "Linen",
            "requireBaseColorTexture": True, "requireNormalTexture": True,
            "requireRoughnessTexture": True, "minRoughnessFactor": 0.8,
            "maxMetallicFactor": 0, "maxSheenColorFactor": 0.2, "texCoord": 0}]}
        json_file(self.policy, self.policy_data)
        source = self.assets / "source.png"
        source.write_bytes(PNG)
        portable = self.assets / "portable.glb"
        portable_doc = copy.deepcopy(self.document)
        portable_doc["asset"]["generator"] = "distinct static portable fixture"
        write_glb(portable, portable_doc, self.binary)
        # Hash-only native/sidecar fixtures: no claim that these reopen in Blender or an EXR consumer.
        (self.assets / "master.blend").write_bytes(b"BLENDER-v300 native fixture bytes; consumer reopening is explicitly not audited")
        (self.assets / "ambient.exr").write_bytes(b"declared sidecar fixture bytes")
        self.contract = self.root / "delivery.json"
        self.contract_data = {"schemaVersion": 1, "root": str(self.assets), "assets": [],
            "runtime": {"asset": "runtime", "sidecars": ["ambient"]},
            "portable": {"asset": "portable", "limitations": ["Static lighting; no interactive cloth."]},
            "native": {"asset": "master"}, "limitations": ["Authored scale, not a measured survey."]}
        for identifier, role, name in [("source", "source", "source.png"), ("runtime", "runtime", "runtime.glb"),
                                       ("portable", "portable", "portable.glb"), ("master", "native", "master.blend"),
                                       ("ambient", "sidecar", "ambient.exr")]:
            self.contract_data["assets"].append({"id": identifier, "role": role, "path": name,
                                                 "sha256": digest(self.assets / name)})
        json_file(self.contract, self.contract_data)

    def write_model(self):
        write_glb(self.glb, self.document, self.binary)

    def command(self, tool, *arguments, expected=0):
        process = subprocess.run([sys.executable, str(TOOLS / tool), "--workspace", str(self.workspace), *map(str, arguments)],
                                 cwd=self.workspace, env=self.env, capture_output=True, text=True)
        self.assertEqual(process.returncode, expected, process.stdout + process.stderr)
        self.assertFalse(process.stderr, process.stderr)
        result = json.loads(process.stdout)  # Rejects additional stdout and pseudo-envelopes.
        if "--gate" in arguments:
            self.assertEqual(set(result), {"kind", "version", "gate", "plugin", "status", "reasons", "evidence"})
            self.assertEqual(result["kind"], "img2.gate-verdict")
            self.assertEqual(result["version"], 1)
            self.assertEqual(result["plugin"], "interior")
            self.assertEqual(result["status"], {0: "pass", 1: "fail", 2: "error"}[expected])
            if expected:
                self.assertTrue(result["reasons"])
        return result

    def materials(self, expected=0):
        return self.command("audit_materials.py", "--glb", self.glb, "--policy", self.policy, expected=expected)

    def delivery(self, expected=0):
        return self.command("audit_delivery.py", "--contract", self.contract, expected=expected)

    def snapshot(self):
        return {str(path.relative_to(self.workspace)): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in self.workspace.rglob("*") if path.is_file()}

    def test_happy_path_real_bindings_receipts_and_read_only_gates(self):
        state_dir = self.workspace / ".img2"
        state_dir.mkdir()
        json_file(state_dir / "state.json", {"version": 1, "workspace": str(self.workspace),
            "plugins": {"interior": {"stages": {"intake": "sentinel"}}, "other": {"keep": True}}})
        self.materials()
        self.delivery()
        before = self.snapshot()
        self.command("audit_materials.py", "--gate")
        self.command("audit_delivery.py", "--gate")
        self.assertEqual(before, self.snapshot())
        state = json.loads((state_dir / "state.json").read_text())
        self.assertEqual(state["plugins"]["interior"]["stages"], {"intake": "sentinel"})
        self.assertEqual(state["plugins"]["other"], {"keep": True})
        self.assertIn("materialAudit", state["plugins"]["interior"])
        self.assertIn("deliveryAudit", state["plugins"]["interior"])

    def test_missing_receipts_fail_without_writing(self):
        self.command("audit_materials.py", "--gate", expected=1)
        self.command("audit_delivery.py", "--gate", expected=1)
        self.assertEqual(self.snapshot(), {})

    def test_absent_maps_fail_even_with_image_inventory(self):
        del self.document["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"]
        self.write_model()
        self.materials(expected=1)
        self.command("audit_materials.py", "--gate", expected=1)

    def test_missing_duplicate_and_unbound_targets_fail(self):
        pristine = copy.deepcopy(self.document)
        mutations = (lambda doc: doc["materials"][0].update(name="Other"),
                     lambda doc: doc["materials"].append(copy.deepcopy(doc["materials"][0])),
                     lambda doc: doc["meshes"][0]["primitives"][0].pop("material"))
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                self.document = copy.deepcopy(pristine)
                mutate(self.document)
                self.write_model()
                self.materials(expected=1)

    def test_precise_gltf_defaults_do_not_invent_policy_expectations(self):
        self.document["materials"][0] = {"name": "Linen"}
        self.policy_data["materials"] = [{"name": "Linen"}]
        json_file(self.policy, self.policy_data)
        self.write_model()
        result = self.materials()
        factors = result["materials"][0]["factors"]
        self.assertEqual(factors["roughnessFactor"], 1)
        self.assertEqual(factors["metallicFactor"], 1)
        self.assertEqual(factors["sheenColorFactor"], [0, 0, 0])
        self.policy_data["materials"][0]["maxMetallicFactor"] = 0
        json_file(self.policy, self.policy_data)
        self.materials(expected=1)

    def test_transform_texcoord_override_is_effective_binding(self):
        texture = self.document["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"]
        texture["extensions"] = {"KHR_texture_transform": {"texCoord": 1}}
        self.document["extensionsUsed"].append("KHR_texture_transform")
        del self.policy_data["materials"][0]["texCoord"]
        json_file(self.policy, self.policy_data)
        self.write_model()
        self.materials(expected=1)
        self.document["meshes"][0]["primitives"][0]["attributes"]["TEXCOORD_1"] = 1
        self.write_model()
        result = self.materials()
        self.assertEqual(result["materials"][0]["textures"]["baseColorTexture"]["texCoord"], 1)
        self.policy_data["materials"][0]["texCoord"] = 0
        json_file(self.policy, self.policy_data)
        self.materials(expected=1)

    def test_broken_indices_storage_and_uv_counts_are_errors(self):
        pristine = copy.deepcopy(self.document)
        mutations = [lambda doc: doc["textures"][0].update(source=99),
                     lambda doc: doc["textures"][0].update(source=True),
                     lambda doc: doc["materials"][0]["normalTexture"].update(index=8),
                     lambda doc: doc["bufferViews"][2].update(byteLength=999999),
                     lambda doc: doc["accessors"][1].update(count=4),
                     lambda doc: doc["accessors"][1].update(count=2),
                     lambda doc: doc["accessors"][1].update(type="SCALAR"),
                     lambda doc: doc["images"][0].update(uri="also.png")]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                self.document = copy.deepcopy(pristine)
                mutate(self.document)
                self.write_model()
                self.materials(expected=2)

    def test_truncated_invalid_and_duplicate_chunks_never_pass(self):
        valid = self.glb.read_bytes()
        bad_cases = [valid[:8], valid[:-4], valid + b"junk", b"nope" + valid[4:]]
        wrong_version = bytearray(valid)
        struct.pack_into("<I", wrong_version, 4, 1)
        bad_cases.append(wrong_version)
        overflow_chunk = bytearray(valid)
        struct.pack_into("<I", overflow_chunk, 12, 0xFFFFFFFC)
        bad_cases.append(overflow_chunk)
        duplicate = bytearray(valid + struct.pack("<II", 4, 0x4E4F534A) + b"{}  ")
        struct.pack_into("<I", duplicate, 8, len(duplicate))
        bad_cases.append(duplicate)
        for index, raw in enumerate(bad_cases):
            with self.subTest(case=index):
                self.glb.write_bytes(raw)
                self.materials(expected=2)

    def test_policy_rejects_nonfinite_booleans_duplicates_and_typos(self):
        pristine = copy.deepcopy(self.policy_data)
        mutations = [lambda doc: doc["materials"][0].update(minRoughnessFactor=float("nan")),
                     lambda doc: doc["materials"][0].update(maxMetallicFactor=True),
                     lambda doc: doc["materials"][0].update(requireNormalTexture="true"),
                     lambda doc: doc["materials"][0].update(texCoord=-1),
                     lambda doc: doc["materials"][0].update(texCoord=True),
                     lambda doc: doc["materials"][0].update(requireRoughnessTexure=True),
                     lambda doc: doc["materials"].append(copy.deepcopy(doc["materials"][0])),
                     lambda doc: doc.update(schemaVersion=True)]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                policy = copy.deepcopy(pristine)
                mutate(policy)
                json_file(self.policy, policy)
                self.materials(expected=2)
        self.policy.write_text('{"schemaVersion":1,"schemaVersion":1,"materials":[]}', encoding="utf-8")
        self.materials(expected=2)

    def test_external_image_and_buffer_resources_are_pinned(self):
        (self.assets / "fabric.png").write_bytes(PNG)
        self.document["images"] = [{"uri": "fabric.png"}]
        self.write_model()
        result = self.materials()
        self.assertEqual(result["resources"][0]["sha256"], digest(self.assets / "fabric.png"))
        (self.assets / "fabric.png").write_bytes(PNG + b"changed")
        self.command("audit_materials.py", "--gate", expected=1)
        (self.assets / "fabric.png").write_bytes(PNG)
        self.command("audit_materials.py", "--gate")
        (self.assets / "fabric.png").unlink()
        self.command("audit_materials.py", "--gate", expected=1)

    def test_external_buffer_bytes_and_bounds_are_rechecked(self):
        buffer = self.assets / "mesh.bin"
        buffer.write_bytes(self.binary)
        self.document["buffers"][0]["uri"] = "mesh.bin"
        write_glb(self.glb, self.document, None)
        result = self.materials()
        self.assertEqual(result["resources"][0]["sha256"], digest(buffer))
        buffer.write_bytes(self.binary[:-4])
        self.command("audit_materials.py", "--gate", expected=1)
        self.materials(expected=2)

    def test_metadata_bound_is_enforced_before_reading_payload(self):
        length = 16 * 1024 * 1024 + 4
        total = 12 + 8 + length
        with self.glb.open("wb") as handle:
            handle.write(struct.pack("<4sII", b"glTF", 2, total))
            handle.write(struct.pack("<II", length, 0x4E4F534A))
            handle.seek(total - 1)
            handle.write(b" ")
        self.materials(expected=2)

    def test_embedded_data_uri_and_missing_external_image(self):
        self.document["images"] = [{"uri": "data:image/png;base64," + base64.b64encode(PNG).decode()}]
        self.write_model()
        self.materials()
        self.document["images"] = [{"uri": "absent.png"}]
        self.write_model()
        self.materials(expected=1)
        self.document["images"] = [{"uri": "data:image/png;base64,not-base64!"}]
        self.write_model()
        self.materials(expected=2)

    def test_resource_escapes_and_unselected_escapes_are_refused(self):
        outside = self.root / "outside.png"
        outside.write_bytes(PNG)
        (self.assets / "escape.png").symlink_to(outside)
        for uri in ("../outside.png", "%2e%2e/outside.png", "escape.png", str(outside),
                    "https://example.test/image.png", "file:///tmp/image.png", "..\\outside.png"):
            with self.subTest(uri=uri):
                self.document["images"] = [{"bufferView": 2, "mimeType": "image/png"}, {"uri": uri}]
                self.write_model()
                self.materials(expected=2)

    def test_changed_policy_glb_and_receipt_cannot_reuse_pass(self):
        self.materials()
        original_policy = self.policy.read_bytes()
        self.policy.write_bytes(original_policy + b"\n")
        self.command("audit_materials.py", "--gate", expected=1)
        self.policy.write_bytes(original_policy)
        original_glb = self.glb.read_bytes()
        changed = bytearray(original_glb)
        changed[-4] ^= 1
        self.glb.write_bytes(changed)
        self.command("audit_materials.py", "--gate", expected=1)
        self.glb.write_bytes(original_glb)
        receipt = self.workspace / ".img2/artifacts/interior/material-audit.json"
        data = json.loads(receipt.read_text())
        data["materials"] = []
        json_file(receipt, data)
        self.command("audit_materials.py", "--gate", expected=1)

    def test_relative_delivery_root_and_all_assets_rehashed(self):
        self.contract_data["root"] = self.assets.name
        json_file(self.contract, self.contract_data)
        self.delivery()
        for row in self.contract_data["assets"]:
            with self.subTest(role=row["role"]):
                path = self.assets / row["path"]
                previous = path.read_bytes()
                path.write_bytes(previous + b"changed")
                result = self.command("audit_delivery.py", "--gate", expected=1)
                self.assertTrue(any(row["id"] in reason for reason in result["reasons"]))
                path.write_bytes(previous)
        self.command("audit_delivery.py", "--gate")

    def test_contract_change_does_not_silently_reauthorize_assets(self):
        self.delivery()
        (self.assets / "ambient.exr").write_bytes(b"changed and repinned by a different contract")
        self.contract_data["assets"][-1]["sha256"] = digest(self.assets / "ambient.exr")
        json_file(self.contract, self.contract_data)
        self.command("audit_delivery.py", "--gate", expected=1)

    def test_duplicate_paths_ids_roles_dependencies_and_missing_limits(self):
        pristine = copy.deepcopy(self.contract_data)
        mutations = [lambda doc: doc["assets"][1].update(id="source"),
                     lambda doc: doc["assets"][1].update(path="source.png"),
                     lambda doc: doc["assets"][1].update(role="source"),
                     lambda doc: doc["runtime"].update(asset="portable"),
                     lambda doc: doc["runtime"].update(sidecars=[]),
                     lambda doc: doc["runtime"].update(sidecars=["ambient", "ambient"]),
                     lambda doc: doc["runtime"].update(sidecars=["source"]),
                     lambda doc: doc["portable"].update(limitations=[]),
                     lambda doc: doc.update(limitations=[""]),
                     lambda doc: doc["assets"][0].update(sha256="0"),
                     lambda doc: doc.update(schemaVersion=True)]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                value = copy.deepcopy(pristine)
                mutate(value)
                json_file(self.contract, value)
                self.delivery(expected=2)

    def test_identical_portable_and_wrong_hash_are_negative_audits(self):
        (self.assets / "portable.glb").write_bytes(self.glb.read_bytes())
        self.contract_data["assets"][2]["sha256"] = digest(self.glb)
        json_file(self.contract, self.contract_data)
        self.delivery(expected=1)
        self.command("audit_delivery.py", "--gate", expected=1)
        self.contract_data["assets"][0]["sha256"] = "0" * 64
        json_file(self.contract, self.contract_data)
        self.delivery(expected=1)

    def test_delivery_escapes_symlinks_aliases_and_missing_assets(self):
        outside = self.root / "outside.png"
        outside.write_bytes(PNG)
        (self.assets / "escape.png").symlink_to(outside)
        original = self.contract_data["assets"][0]["path"]
        for path in ("../outside.png", str(outside), "escape.png", "https://example.test/file", "a/../source.png"):
            with self.subTest(path=path):
                self.contract_data["assets"][0]["path"] = path
                json_file(self.contract, self.contract_data)
                self.delivery(expected=2)
        self.contract_data["assets"][0]["path"] = original
        (self.assets / "alias.glb").symlink_to(self.glb)
        self.contract_data["assets"][2]["path"] = "alias.glb"
        json_file(self.contract, self.contract_data)
        self.delivery(expected=2)
        self.contract_data["assets"][2]["path"] = "missing.glb"
        json_file(self.contract, self.contract_data)
        self.delivery(expected=1)

    def test_input_collision_cannot_overwrite_original_policy(self):
        self.policy = self.workspace / ".img2/artifacts/interior/material-audit.json"
        self.policy.parent.mkdir(parents=True)
        json_file(self.policy, self.policy_data)
        original = self.policy.read_bytes()
        self.materials(expected=2)
        self.assertEqual(self.policy.read_bytes(), original)
        self.assertFalse((self.workspace / ".img2/state.json").exists())

    def test_no_output_or_state_symlink_escape(self):
        outside = self.root / "outside-output"
        outside.mkdir()
        (self.workspace / ".img2").symlink_to(outside, target_is_directory=True)
        self.materials(expected=2)
        self.delivery(expected=2)
        self.command("audit_materials.py", "--gate", expected=2)
        self.assertEqual(list(outside.iterdir()), [])

    def test_malformed_gate_arguments_keep_exact_error_envelope(self):
        self.command("audit_materials.py", "--gate", "--policy", self.policy, expected=2)
        self.command("audit_delivery.py", "--gate", "--unknown", expected=2)

    def test_real_gate_runner_pass_fail_and_error_semantics(self):
        self.materials()
        self.delivery()
        plugin = self.root / "runner plugin"
        plugin.mkdir()
        gates = []
        for identifier, tool in (("interior-materials", "audit_materials.py"), ("interior-delivery", "audit_delivery.py")):
            command = " ".join([shlex.quote(sys.executable), shlex.quote(str(TOOLS / tool)),
                                '--workspace "{workspace}" --gate'])
            gates.append({"id": identifier, "command": command, "blocking": True,
                          "after": [] if not gates else ["interior-materials"]})
        json_file(plugin / "gates.json", gates)
        def run(expected):
            process = subprocess.run([sys.executable, "-m", "img2_core.gate_runner", "--plugin-dir", str(plugin),
                                      "--workspace", str(self.workspace)], env=self.env, cwd=self.workspace,
                                     capture_output=True, text=True)
            self.assertEqual(process.returncode, expected, process.stdout + process.stderr)
            self.assertFalse(process.stderr)
            result = json.loads(process.stdout)
            self.assertEqual(result["kind"], "img2.gate-run")
            return result
        result = run(0)
        self.assertEqual([row["status"] for row in result["results"]], ["pass", "pass"])
        self.assertFalse(result["stopped"])
        self.policy.write_bytes(self.policy.read_bytes() + b"\n")
        result = run(1)
        self.assertEqual([row["status"] for row in result["results"]], ["fail", "skipped"])
        self.assertEqual(result["results"][0]["envelope"]["gate"], "interior-materials")
        self.materials()
        # Malformed persisted state exercises the real tool's error, not an echo command.
        (self.workspace / ".img2/state.json").write_text('{"version":1,"plugins":null}', encoding="utf-8")
        result = run(1)
        self.assertEqual([row["status"] for row in result["results"]], ["error", "skipped"])
        self.assertEqual(result["results"][0]["exitCode"], 2)


if __name__ == "__main__":
    unittest.main()
