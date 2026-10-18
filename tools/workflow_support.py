"""Interior attestations: ordered, content-pinned, append-only decision history.

This checks provenance and workflow consistency, never visual quality. All mutation
runs inside img2_core's plugin-subtree transaction; readers never acquire a lock.
"""

import copy
import hashlib
import json
import math
import os
from pathlib import Path

from img2_core.paths import resolve_workspace
from img2_core.state import update_plugin_state

STAGES = ("intake", "camera", "geometry", "materials", "lighting", "interaction", "delivery", "review")
DECISIONS = ("accept", "reject", "request-input", "stop")
WORKFLOW_KEYS = ("schemaVersion", "source", "intake", "stages", "history")
ATTESTATION = "Reviewer attestation only; existence, order and freshness are checked, not visual quality."


class Refusal(ValueError):
    """Malformed input or an operation that would destroy provenance."""


class Incomplete(ValueError):
    """Well-formed run that is incomplete or no longer fresh."""


def nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise Refusal(f"{label} must be nonempty text")
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Refusal(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value):
    raise Refusal(f"nonfinite JSON constant: {value}")


def _float(value):
    number = float(value)
    if not math.isfinite(number):
        raise Refusal(f"nonfinite JSON number: {value}")
    return number


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_float=_float)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Refusal(f"malformed JSON in {path}: {exc}") from exc


def validate_intake(doc):
    if not isinstance(doc, dict) or type(doc.get("schemaVersion")) is not int or doc["schemaVersion"] != 1:
        raise Refusal("intake schemaVersion must be integer 1")
    if doc.get("sourceKind") not in ("synthetic-design-reference", "photo", "render", "floorplan"):
        raise Refusal("intake sourceKind is invalid")
    nonempty(doc.get("authorization"), "intake authorization")
    scale = doc.get("scale")
    if not isinstance(scale, dict) or scale.get("unit") != "m" or scale.get("basis") not in ("authored-estimate", "measured"):
        raise Refusal("intake scale requires unit m and basis authored-estimate or measured")
    nonempty(scale.get("note"), "intake scale note")
    components = doc.get("components")
    if not isinstance(components, list) or not components:
        raise Refusal("intake components must be a nonempty array")
    for component in components:
        nonempty(component, "intake component")
    if len({item.strip() for item in components}) != len(components):
        raise Refusal("intake components must be unique")
    if not isinstance(doc.get("unknowns"), list) or any(not isinstance(item, str) for item in doc["unknowns"]):
        raise Refusal("intake unknowns must be an array of strings")
    if type(doc.get("interactionRequired")) is not bool:
        raise Refusal("intake interactionRequired must be boolean")
    return doc


def workspace_path(raw):
    if not Path(raw).expanduser().is_absolute():
        raise Refusal("--workspace must be absolute")
    workspace = resolve_workspace(raw)
    if not workspace.is_dir():
        raise Refusal("workspace must be an existing directory")
    # Core's state writer follows parent directories. Reject redirected control
    # paths before handing it a workspace, including its temporary file and lock.
    for relative in (".img2", ".img2/artifacts", ".img2/artifacts/interior",
                     ".img2/state.json", ".img2/state.json.tmp", ".img2/.lock"):
        path = workspace / relative
        if path.is_symlink():
            raise Refusal(f"workspace control path must not be a symlink: {path}")
    return workspace


def input_path(workspace, raw):
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = workspace / path
    return Path(os.path.abspath(path))


def snapshot_path(workspace):
    return workspace / ".img2/artifacts/interior/intake.json"


def pin_file(path, workspace=None):
    path = Path(path)
    resolved = path.resolve(strict=True)
    if workspace is not None and not resolved.is_relative_to(workspace):
        raise Refusal(f"evidence must resolve inside workspace: {path}")
    if not resolved.is_file():
        raise Refusal(f"not a regular file: {path}")
    digest = hashlib.sha256()
    size = 0
    with resolved.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    if not size:
        raise Refusal(f"empty file is not evidence: {path}")
    return {"path": str(path), "resolvedPath": str(resolved), "sha256": digest.hexdigest(), "size": size}


def validate_pin(pin):
    if not isinstance(pin, dict) or set(pin) != {"path", "resolvedPath", "sha256", "size"}:
        raise Refusal("malformed file pin")
    for key in ("path", "resolvedPath"):
        nonempty(pin[key], f"pin {key}")
        if not Path(pin[key]).is_absolute():
            raise Refusal(f"pin {key} must be absolute")
    digest = pin["sha256"]
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise Refusal("pin sha256 must be 64 lowercase hex characters")
    if type(pin["size"]) is not int or pin["size"] <= 0:
        raise Refusal("pin size must be a positive integer")


def includes_snapshot(evidence, snapshot):
    # A workspace alias can spell the same file differently; retain its lexical
    # pin for later retarget detection, but compare resolved identity and bytes.
    return any(all(pin[key] == snapshot[key] for key in ("resolvedPath", "sha256", "size"))
               for pin in evidence)


def pending_stages():
    return {name: {"status": "pending"} for name in STAGES}


def invalidate(stages, stage):
    for name in STAGES[STAGES.index(stage):]:
        stages[name] = {"status": "pending"}


def cursor(stages):
    return next((name for name in STAGES if stages[name]["status"] != "accepted"), None)


def validate_run(run, workspace):
    if not isinstance(run, dict):
        raise Refusal("plugins.interior must be an object")
    if not any(key in run for key in WORKFLOW_KEYS):
        return None
    if type(run.get("schemaVersion")) is not int or run["schemaVersion"] != 1:
        raise Refusal("interior schemaVersion must be integer 1")
    validate_pin(run.get("source"))
    intake = run.get("intake")
    if not isinstance(intake, dict) or set(intake) != {"input", "snapshot"}:
        raise Refusal("malformed intake metadata")
    validate_pin(intake["input"])
    validate_pin(intake["snapshot"])
    if intake["snapshot"]["path"] != str(snapshot_path(workspace)) or intake["snapshot"]["resolvedPath"] != str(snapshot_path(workspace)):
        raise Refusal("intake snapshot is not at the required workspace path")
    history = run.get("history")
    if not isinstance(history, list) or not history:
        raise Refusal("interior history must contain initialization")
    expected_init = {"sequence": 1, "action": "init", "source": run["source"], "intake": intake}
    if history[0] != expected_init:
        raise Refusal("initialization history disagrees with immutable input pins")
    stages = pending_stages()
    for sequence, event in enumerate(history[1:], 2):
        if not isinstance(event, dict) or type(event.get("sequence")) is not int or event["sequence"] != sequence:
            raise Refusal("history sequence is malformed")
        stage = event.get("stage")
        if stage not in STAGES:
            raise Refusal("history contains an unknown stage")
        if event.get("action") == "revise":
            if set(event) != {"sequence", "action", "stage", "reason"}:
                raise Refusal("malformed revision history")
            nonempty(event["reason"], "revision reason")
            invalidate(stages, stage)
        elif event.get("action") == "record":
            if set(event) != {"sequence", "action", "stage", "decision", "reviewer", "note", "evidence", "attestation"}:
                raise Refusal("malformed decision history")
            decision = event["decision"]
            if decision not in DECISIONS or event["attestation"] != ATTESTATION:
                raise Refusal("malformed decision or attestation")
            nonempty(event["reviewer"], "reviewer")
            nonempty(event["note"], "note")
            evidence = event["evidence"]
            if not isinstance(evidence, list) or (decision == "accept" and not evidence):
                raise Refusal("acceptance requires evidence")
            for pin in evidence:
                validate_pin(pin)
                if not Path(pin["resolvedPath"]).is_relative_to(workspace):
                    raise Refusal("stored evidence escapes workspace")
            if len({pin["resolvedPath"] for pin in evidence}) != len(evidence):
                raise Refusal("duplicate evidence files")
            if decision == "accept":
                if stage != cursor(stages) or stages[stage]["status"] != "pending":
                    raise Refusal("history contains out-of-order or duplicate stage acceptance")
                if stage == "intake" and not includes_snapshot(evidence, intake["snapshot"]):
                    raise Refusal("intake acceptance must include its validated snapshot")
            elif any(stages[name]["status"] != "accepted" for name in STAGES[:STAGES.index(stage)]):
                raise Refusal("history contains out-of-order decision")
            invalidate(stages, stage)
            stages[stage] = {"status": {"accept": "accepted", "reject": "rejected", "request-input": "blocked", "stop": "stopped"}[decision], "record": sequence}
        else:
            raise Refusal("unknown history action")
    if run.get("stages") != stages:
        raise Refusal("stage state disagrees with decision history")
    return run


def read_run(workspace):
    path = workspace / ".img2/state.json"
    if not path.exists():
        return None
    envelope = read_json(path)
    if not isinstance(envelope, dict) or type(envelope.get("version")) is not int or envelope["version"] != 1 or not isinstance(envelope.get("plugins"), dict):
        raise Refusal("malformed img2 state envelope")
    return validate_run(envelope["plugins"].get("interior", {}), workspace)


def freshness(run, workspace):
    reasons = []
    pins = [("source", run["source"], None), ("intake input", run["intake"]["input"], None),
            ("intake snapshot", run["intake"]["snapshot"], workspace)]
    for stage in STAGES:
        item = run["stages"][stage]
        if item["status"] == "accepted":
            event = run["history"][item["record"] - 1]
            pins.extend((f"{stage} evidence", pin, workspace) for pin in event["evidence"])
    checked = {}
    for label, pin, boundary in pins:
        key = (pin["path"], boundary)
        if key not in checked:
            try:
                checked[key] = pin_file(pin["path"], boundary)
            except (OSError, ValueError, RuntimeError) as exc:
                checked[key] = str(exc)
        current = checked[key]
        if current != pin:
            reasons.append(f"{label} is stale or unavailable: {pin['path']}" + (f" ({current})" if isinstance(current, str) else ""))
    # Parsing only fresh bytes distinguishes stale content from a malformed run.
    if not any(label.startswith("intake") for label in reasons):
        validate_intake(read_json(run["intake"]["snapshot"]["path"]))
    return reasons


def describe(run, workspace):
    if run is None:
        return {"status": "pending", "nextStage": None, "action": "init", "reasons": ["workflow is not initialized"], "attestation": ATTESTATION}
    stage = cursor(run["stages"])
    reasons = freshness(run, workspace)
    status = run["stages"][stage]["status"] if stage else "completed"
    explicit_block = status in ("blocked", "stopped")
    if reasons and not explicit_block:
        status = "blocked"
    if stage and run["stages"][stage]["status"] != "pending":
        record = run["history"][run["stages"][stage]["record"] - 1]
        reasons.append(record["note"])
    return {"status": status, "nextStage": stage, "action": "revise" if status in ("rejected", "stopped", "blocked") else ("record" if stage else "complete"),
            "reasons": reasons, "explicitBlock": explicit_block, "attestation": ATTESTATION}


def initialize(workspace, image, intake_file):
    read_run(workspace)  # Strict parsing before core's permissive JSON loader.
    image = input_path(workspace, image)
    intake_file = input_path(workspace, intake_file)
    source = pin_file(image)
    intake_input = pin_file(intake_file)
    intake_doc = validate_intake(read_json(intake_file))
    if pin_file(intake_file) != intake_input:
        raise Refusal("intake changed while initializing")
    snapshot = snapshot_path(workspace)
    payload = (json.dumps(intake_doc, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")

    def change(subtree):
        if validate_run(subtree, workspace) is not None:
            raise Refusal("workflow already initialized; use revise, never reset history")
        if snapshot.exists() or snapshot.is_symlink():
            raise Refusal("intake snapshot already exists; refusing to overwrite provenance")
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        with snapshot.open("xb") as stream:
            stream.write(payload)
        intake = {"input": intake_input, "snapshot": pin_file(snapshot, workspace)}
        subtree.update(schemaVersion=1, source=source, intake=intake, stages=pending_stages(),
                       history=[{"sequence": 1, "action": "init", "source": copy.deepcopy(source), "intake": copy.deepcopy(intake)}])

    state = update_plugin_state(workspace, "interior", change)
    return state["plugins"]["interior"]


def record(workspace, stage, decision, reviewer, note, evidence):
    nonempty(reviewer, "reviewer")
    nonempty(note, "note")
    if decision == "accept" and not evidence:
        raise Refusal("acceptance requires at least one evidence file")
    pins = [pin_file(input_path(workspace, path), workspace) for path in evidence]
    if len({pin["resolvedPath"] for pin in pins}) != len(pins):
        raise Refusal("duplicate evidence files")
    read_run(workspace)

    def change(subtree):
        run = validate_run(subtree, workspace)
        if run is None:
            raise Incomplete("workflow is not initialized")
        if any(run["stages"][name]["status"] != "accepted" for name in STAGES[:STAGES.index(stage)]):
            raise Incomplete("preceding stages must be accepted in order")
        if decision == "accept":
            if run["stages"][stage]["status"] != "pending":
                raise Refusal("stage already decided; revise before accepting again")
            reasons = freshness(run, workspace)
            if reasons:
                raise Incomplete("; ".join(reasons))
            if stage == "intake" and not includes_snapshot(pins, run["intake"]["snapshot"]):
                raise Refusal("intake acceptance must include the validated intake snapshot")
        event = {"sequence": len(run["history"]) + 1, "action": "record", "stage": stage,
                 "decision": decision, "reviewer": reviewer, "note": note, "evidence": pins, "attestation": ATTESTATION}
        invalidate(run["stages"], stage)
        run["stages"][stage] = {"status": {"accept": "accepted", "reject": "rejected", "request-input": "blocked", "stop": "stopped"}[decision], "record": event["sequence"]}
        run["history"].append(event)

    state = update_plugin_state(workspace, "interior", change)
    return state["plugins"]["interior"]


def revise(workspace, stage, reason):
    nonempty(reason, "revision reason")
    read_run(workspace)

    def change(subtree):
        run = validate_run(subtree, workspace)
        if run is None:
            raise Incomplete("workflow is not initialized")
        invalidate(run["stages"], stage)
        run["history"].append({"sequence": len(run["history"]) + 1, "action": "revise", "stage": stage, "reason": reason})

    state = update_plugin_state(workspace, "interior", change)
    return state["plugins"]["interior"]


def evaluate_gate(workspace):
    run = read_run(workspace)
    if run is None:
        return ["workflow is not initialized"], {"attestation": ATTESTATION}
    reasons = freshness(run, workspace)
    reasons.extend(f"{stage} is {run['stages'][stage]['status']}, not accepted" for stage in STAGES if run["stages"][stage]["status"] != "accepted")
    return reasons, {"attestation": ATTESTATION, "source": run["source"], "intake": run["intake"],
                     "stages": run["stages"], "historyLength": len(run["history"])}
