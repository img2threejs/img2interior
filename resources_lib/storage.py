"""Bounded JSON and workspace-only files shared by the resource commands."""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import tempfile

MAX_JSON = 16 * 1024 * 1024


def relative_path(value):
    if not isinstance(value, str) or not value or any(c in value for c in ('\\', ':', '%', '\x00')):
        raise ValueError(f'Expected a plain workspace-relative path: {value!r}')
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ('', '.', '..') for p in value.split('/')):
        raise ValueError(f'Unsafe relative path: {value!r}')
    return path


def confined(workspace, relative):
    root = Path(workspace).resolve()
    plugin = Path(__file__).resolve().parents[1]
    if root == plugin or root.is_relative_to(plugin):
        raise ValueError('The installed plugin cannot be the authored workspace')
    path = root
    for part in relative_path(relative).parts:
        path = path / part
        if path.is_symlink():
            raise ValueError(f'Symlink is not a resource path: {relative}')
    if not path.resolve().is_relative_to(root):
        raise ValueError(f'Path escapes workspace: {relative}')
    return path


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def _float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f'Non-finite JSON number: {value}')
    return number


def _constant(value):
    raise ValueError(f'Non-finite JSON value: {value}')


def read_json(path):
    with Path(path).open('rb') as stream:
        payload = stream.read(MAX_JSON + 1)
    if len(payload) > MAX_JSON:
        raise ValueError(f'JSON exceeds {MAX_JSON} bytes: {path}')
    return json.loads(payload, object_pairs_hook=_pairs, parse_float=_float, parse_constant=_constant)


def write_json(workspace, relative, data):
    payload = (json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    path = confined(workspace, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.img2-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
        os.replace(temporary, confined(workspace, relative))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def hashes(path):
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    count = 0
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            count += len(block)
            md5.update(block)
            sha256.update(block)
    return count, md5.hexdigest(), sha256.hexdigest()
