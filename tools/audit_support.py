"""Shared, stdlib-only validation and receipt I/O for the two interior audits."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from urllib.parse import unquote, urlsplit

from img2_core.paths import resolve_workspace
from img2_core.state import update_plugin_state

JSON_LIMIT = 16 * 1024 * 1024
HASH_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z")


class AuditFailure(ValueError):
    """An evaluated, negative audit (as opposed to malformed input)."""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def object_value(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def fields(value, required, optional, label):
    object_value(value, label)
    missing = set(required) - value.keys()
    extra = value.keys() - set(required) - set(optional)
    if missing or extra:
        raise ValueError(f"{label}: missing fields {sorted(missing)}, unknown fields {sorted(extra)}")
    return value


def text(value, label):
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"{label} must be nonempty text without NUL")
    return value


def integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def factor(value, label):
    if type(value) not in (int, float) or not 0 <= value <= 1:
        raise ValueError(f"{label} must be a finite number in [0,1]")
    return value


def string_list(value, label, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{label} must be {'a nonempty' if nonempty else 'an'} array")
    return [text(item, label) for item in value]


def sha_value(value, label):
    if not isinstance(value, str) or not HASH_PATTERN.fullmatch(value):
        raise ValueError(f"{label} must be a 64-character SHA256 hex digest")
    return value.lower()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"nonfinite JSON number: {value}")


def decode_json(raw, label):
    try:
        result = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"{label}: invalid JSON: {exc}") from exc
    # JSON exponent overflow (1e999) does not use parse_constant.
    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{label}: nonfinite number")
        if isinstance(value, dict):
            for child in value.values():
                finite(child)
        elif isinstance(value, list):
            for child in value:
                finite(child)
    finite(result)
    return result


def read_json(path):
    with Path(path).open("rb") as handle:
        raw = handle.read(JSON_LIMIT + 1)
    if len(raw) > JSON_LIMIT:
        raise ValueError(f"JSON metadata exceeds {JSON_LIMIT} bytes: {path}")
    return decode_json(raw, str(path))


def file_hash(path):
    path = Path(path)
    if not path.is_file():
        raise AuditFailure(f"missing regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        before = os.fstat(handle.fileno())
        if before.st_size == 0:
            raise AuditFailure(f"empty file: {path}")
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
        after = os.fstat(handle.fileno())
    current = path.stat()
    stamp = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
    if stamp(before) != stamp(after) or stamp(after) != stamp(current):
        raise AuditFailure(f"file changed during hashing: {path}")
    return digest.hexdigest()


def input_path(value):
    return Path(text(value, "input path")).expanduser().absolute()


def confined_file(root, value, *, uri=False):
    """Only relative local files; URI decoding happens before containment checks."""
    text(value, "resource path")
    if uri:
        if re.search(r"%(?![0-9A-Fa-f]{2})", value):
            raise ValueError(f"invalid percent escape: {value}")
        value = unquote(value, errors="strict")
    parsed = urlsplit(value)
    parts = value.split("/")
    if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or
            ":" in value or "\\" in value or "\x00" in value or
            PurePosixPath(value).is_absolute() or any(part in ("", ".", "..") for part in parts)):
        raise ValueError(f"resource must be a confined relative POSIX path: {value}")
    root = Path(root).resolve(strict=True)
    candidate = root.joinpath(*parts)
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"resource escapes root: {value}")
    if not resolved.is_file():
        raise AuditFailure(f"missing resource: {candidate}")
    return resolved


def workspace_path(value):
    workspace = resolve_workspace(value)
    if not workspace.is_dir():
        raise ValueError(f"workspace must be an existing directory: {workspace}")
    return workspace


def owned_paths(workspace, filename):
    """Refuse redirection of artifact writes or core's state/lock/temp writes."""
    names = [".img2", ".img2/artifacts", ".img2/artifacts/interior",
             ".img2/state.json", ".img2/state.json.tmp", ".img2/.lock",
             f".img2/artifacts/interior/{filename}"]
    for name in names:
        candidate = workspace / name
        if candidate.is_symlink() or not candidate.resolve().is_relative_to(workspace):
            raise ValueError(f"refusing redirected workspace path: {candidate}")
    return workspace / ".img2/artifacts/interior" / filename


def persist(workspace, filename, state_key, report):
    path = owned_paths(workspace, filename)
    # Never overwrite a declared input through a collision with our output or core state.
    inputs = [Path(item["path"]).resolve() for item in report["inputs"].values()]
    inputs.extend(Path(item["path"]).resolve() for item in report.get("resources", []))
    inputs.extend(Path(item["resolvedPath"]) for item in report.get("assets", []))
    outputs = [path, workspace / ".img2/state.json", workspace / ".img2/state.json.tmp",
               workspace / ".img2/.lock"]
    for output in outputs:
        for source in inputs:
            if output.resolve() == source or (output.exists() and source.samefile(output)):
                raise ValueError(f"audit output collides with a read-only input: {source}")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=filename + ".", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    metadata = {"schemaVersion": 1, "receipt": str(path.relative_to(workspace)),
                "sha256": hashlib.sha256(encoded).hexdigest()}
    def update(subtree):
        object_value(subtree, "plugins.interior")
        subtree[state_key] = metadata
    update_plugin_state(workspace, "interior", update)


def load_receipt(workspace, filename, state_key):
    path = owned_paths(workspace, filename)
    state_path = workspace / ".img2/state.json"
    if not path.is_file() or not state_path.is_file():
        raise AuditFailure(f"no stored {state_key} receipt; run the normal audit first")
    state = object_value(read_json(state_path), "state")
    if type(state.get("version")) is not int or state["version"] != 1:
        raise ValueError("invalid state envelope version")
    plugins = object_value(state.get("plugins"), "state.plugins")
    subtree = object_value(plugins.get("interior", {}), "plugins.interior")
    if state_key not in subtree:
        raise AuditFailure(f"no stored {state_key} metadata")
    metadata = fields(subtree[state_key], ["schemaVersion", "receipt", "sha256"], [], state_key)
    if type(metadata["schemaVersion"]) is not int or metadata["schemaVersion"] != 1:
        raise ValueError("unsupported receipt metadata version")
    if metadata["receipt"] != str(path.relative_to(workspace)):
        raise ValueError("receipt metadata does not point to the owned receipt")
    if file_hash(path) != sha_value(metadata["sha256"], "receipt hash"):
        raise AuditFailure("stored receipt changed after audit")
    receipt = object_value(read_json(path), "receipt")
    if type(receipt.get("schemaVersion")) is not int or receipt["schemaVersion"] != 1:
        raise ValueError("unsupported audit receipt version")
    if type(receipt.get("passed")) is not bool:
        raise ValueError("receipt passed must be boolean")
    return receipt


def pin(path):
    return {"path": str(path), "sha256": file_hash(path)}


def check_pin(value, label):
    fields(value, ["path", "sha256"], [], label)
    path = input_path(value["path"])
    if not Path(value["path"]).is_absolute():
        raise ValueError(f"{label} receipt path must be absolute")
    if file_hash(path) != sha_value(value["sha256"], label):
        raise AuditFailure(f"{label} changed since audit")
    return path


def emit(gate, status, reasons, evidence, *, gate_mode):
    if gate_mode:
        result = {"kind": "img2.gate-verdict", "version": 1, "gate": gate,
                  "plugin": "interior", "status": status, "reasons": reasons, "evidence": evidence}
    else:
        result = evidence or {"schemaVersion": 1, "passed": False, "reasons": reasons}
        result = dict(result, status=status)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return {"pass": 0, "fail": 1, "error": 2}[status]
