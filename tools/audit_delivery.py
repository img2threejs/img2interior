#!/usr/bin/env python3
"""Rehash declared source/runtime/portable/native assets and runtime dependencies."""
import os, sys
sys.dont_write_bytecode = True
root = os.environ.get("IMG2_HOME")
if root: sys.path.insert(0, os.path.join(root, "harness"))
else:
    try: import _img2_local; sys.path.insert(0, _img2_local.CORE)
    except ImportError: sys.exit("img2: core not linked - run `img2 sync`")
from img2_core import require_core_api
require_core_api(1)

from pathlib import Path
from urllib.parse import urlsplit

from audit_support import (AuditFailure, Parser, check_pin, confined_file, emit, fields,
                           file_hash, input_path, load_receipt, persist, pin, read_json,
                           sha_value, string_list, text, workspace_path)

GATE = "interior-delivery"
RECEIPT = "delivery-audit.json"
STATE_KEY = "deliveryAudit"
LIMITATIONS = [
    "Hashes prove current byte identity against this declared contract, not provenance or visual fidelity.",
    "Runtime sidecars are the declared dependency set; this audit does not execute a viewer or discover undeclared network/runtime dependencies.",
    "Portable and native consumer reopening, Khronos glTF validity, packed native resources, interaction behavior, and matched visual comparisons require separate human/agent evidence.",
    "A distinct portable file is not proof that runtime interaction, lighting, or PBR behavior survives export; the portable limitations remain part of delivery.",
]


def validate_contract(contract, contract_path):
    fields(contract, ["schemaVersion", "root", "assets", "runtime", "portable", "native", "limitations"], [], "delivery contract")
    if type(contract["schemaVersion"]) is not int or contract["schemaVersion"] != 1:
        raise ValueError("contract schemaVersion must be 1")
    root_text = text(contract["root"], "contract.root")
    if "\\" in root_text or urlsplit(root_text).scheme or urlsplit(root_text).netloc or "\x00" in root_text or "?" in root_text or "#" in root_text:
        raise ValueError("contract.root must be a local filesystem directory, not a URL")
    root = Path(root_text)
    if not root.is_absolute():
        root = contract_path.parent / root
    root = root.resolve()
    if not root.is_dir():
        raise AuditFailure(f"asset root is not an existing directory: {root}")
    string_list(contract["limitations"], "contract.limitations", nonempty=True)
    rows = contract["assets"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("contract.assets must be a nonempty array")
    assets, paths, files = {}, set(), set()
    roles = {role: [] for role in ("source", "runtime", "portable", "native", "sidecar")}
    for row in rows:
        fields(row, ["id", "role", "path", "sha256"], [], "asset")
        identifier = text(row["id"], "asset.id")
        if identifier in assets:
            raise ValueError(f"duplicate asset id: {identifier}")
        role = text(row["role"], "asset.role")
        if role not in roles:
            raise ValueError(f"unsupported asset role: {role}")
        expected = sha_value(row["sha256"], f"{identifier}.sha256")
        path = confined_file(root, row["path"])
        # Resolve symlinks and filesystem identity too: aliases are not separate deliveries.
        stat = path.stat()
        identity = (stat.st_dev, stat.st_ino)
        if path in paths or identity in files:
            raise ValueError(f"duplicate asset path or file alias: {row['path']}")
        paths.add(path)
        files.add(identity)
        roles[role].append(identifier)
        assets[identifier] = {"id": identifier, "role": role, "path": row["path"],
                              "resolvedPath": str(path), "expectedSha256": expected}
    for role in ("source", "runtime", "portable", "native"):
        if len(roles[role]) != 1:
            raise ValueError(f"contract needs exactly one {role} asset")
    for role in ("runtime", "portable", "native"):
        required = ["asset"] + ({"runtime": ["sidecars"], "portable": ["limitations"], "native": []}[role])
        section = fields(contract[role], required, [], role)
        identifier = text(section["asset"], f"{role}.asset")
        if identifier != roles[role][0]:
            raise ValueError(f"{role}.asset must reference the declared {role} role")
    sidecars = string_list(contract["runtime"]["sidecars"], "runtime.sidecars")
    if len(set(sidecars)) != len(sidecars) or set(sidecars) != set(roles["sidecar"]):
        raise ValueError("runtime.sidecars must reference each sidecar exactly once and no other asset")
    string_list(contract["portable"]["limitations"], "portable.limitations", nonempty=True)
    return root, assets


def evaluate(contract_path):
    contract_pin = pin(contract_path)
    contract = read_json(contract_path)
    root, assets = validate_contract(contract, contract_path)
    reasons = []
    for asset in assets.values():
        asset["sha256"] = file_hash(asset["resolvedPath"])
        asset["byteLength"] = Path(asset["resolvedPath"]).stat().st_size
        if asset["sha256"] != asset["expectedSha256"]:
            reasons.append(f"{asset['id']}: current SHA256 differs from contract")
    runtime = assets[contract["runtime"]["asset"]]
    portable = assets[contract["portable"]["asset"]]
    if runtime["sha256"] == portable["sha256"]:
        reasons.append("runtime and portable are byte-identical; cannot masquerade as separate representations")
    # Re-resolve names after hashing to catch symlink replacement or root changes.
    for asset in assets.values():
        current = confined_file(root, asset["path"])
        if str(current) != asset["resolvedPath"]:
            raise AuditFailure(f"asset path changed during audit: {asset['id']}")
    check_pin(contract_pin, "contract")
    return {"schemaVersion": 1, "audit": GATE, "passed": not reasons, "reasons": reasons,
            "inputs": {"contract": contract_pin}, "root": str(root), "assets": list(assets.values()),
            "runtime": contract["runtime"], "portable": contract["portable"], "native": contract["native"],
            "declaredLimitations": contract["limitations"], "limitations": LIMITATIONS,
            "consumerReopeningEvaluated": False, "visualComparisonEvaluated": False,
            "khronosValidityEvaluated": False}


def gate(workspace):
    receipt = load_receipt(workspace, RECEIPT, STATE_KEY)
    if receipt.get("audit") != GATE:
        raise ValueError("wrong audit receipt kind")
    inputs = fields(receipt.get("inputs"), ["contract"], [], "receipt.inputs")
    contract = check_pin(inputs["contract"], "contract")
    current = evaluate(contract)
    if current["root"] != receipt.get("root") or current["assets"] != receipt.get("assets"):
        current["passed"] = False
        current["reasons"].append("delivery assets or resolved paths changed since audit")
    if not receipt["passed"]:
        current["passed"] = False
        current["reasons"].append("stored delivery audit was negative; run the normal audit after repair")
    return current


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    gate_mode = "--gate" in argv
    try:
        parser = Parser(description=__doc__)
        parser.add_argument("--workspace", required=True)
        parser.add_argument("--contract")
        parser.add_argument("--gate", action="store_true")
        args = parser.parse_args(argv)
        workspace = workspace_path(args.workspace)
        if args.gate:
            if args.contract:
                raise ValueError("--gate reads the pinned contract; do not supply --contract")
            report = gate(workspace)
        else:
            if not args.contract:
                raise ValueError("normal audit requires --contract")
            report = evaluate(input_path(args.contract))
            persist(workspace, RECEIPT, STATE_KEY, report)
        return emit(GATE, "pass" if report["passed"] else "fail", report["reasons"], report, gate_mode=gate_mode)
    except AuditFailure as exc:
        return emit(GATE, "fail", [str(exc)], {}, gate_mode=gate_mode)
    except (ValueError, OSError, RuntimeError, RecursionError) as exc:
        return emit(GATE, "error", [str(exc)], {}, gate_mode=gate_mode)


if __name__ == "__main__":
    sys.exit(main())
