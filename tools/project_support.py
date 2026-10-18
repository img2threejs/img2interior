"""Local project operations; no scene generation or writes at import time."""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit

PLUGIN = Path(__file__).resolve().parent.parent
ARTIFACTS = Path('.img2/artifacts/interior')
OAK_SOURCE = '95eb31d840165964deac849813dc77ad18bad71f1df90770bff1f7b4a5fb666b'
SOURCE_KINDS = ('photo', 'render', 'synthetic-design-reference', 'floorplan')


def workspace_path(value):
    workspace = Path(value).expanduser().resolve()
    if workspace == PLUGIN or workspace.is_relative_to(PLUGIN):
        raise ValueError('The installed plugin cannot be the authored workspace')
    return workspace


def confined(workspace, relative):
    workspace = workspace_path(workspace)
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Expected a workspace-relative path: ' + str(relative))
    lexical = workspace / relative
    resolved = lexical.resolve()
    if not resolved.is_relative_to(workspace) or lexical.is_symlink():
        raise ValueError('Workspace path escapes or aliases an output: ' + str(relative))
    return resolved


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('Non-finite JSON number: ' + value)
    return number


def read_json(path):
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Project JSON exceeds 4 MiB: ' + str(path))
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_pairs,
                      parse_float=_finite_float,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite JSON: ' + value)))


def write_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name + '.', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_json(path, value):
    write_bytes(path, (json.dumps(value, indent=2, allow_nan=False) + '\n').encode('utf-8'))


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def _exif_orientation(payload):
    if not payload.startswith(b'Exif\0\0'):
        return 1
    tiff = payload[6:]
    if len(tiff) < 8 or tiff[:2] not in (b'II', b'MM'):
        return 1
    order = 'little' if tiff[:2] == b'II' else 'big'
    offset = int.from_bytes(tiff[4:8], order)
    if offset + 2 > len(tiff):
        return 1
    count = int.from_bytes(tiff[offset:offset + 2], order)
    if count > 4096 or offset + 2 + count * 12 > len(tiff):
        return 1
    for index in range(count):
        entry = offset + 2 + index * 12
        if int.from_bytes(tiff[entry:entry + 2], order) == 274:
            if (int.from_bytes(tiff[entry + 2:entry + 4], order) == 3
                    and int.from_bytes(tiff[entry + 4:entry + 8], order) == 1):
                value = int.from_bytes(tiff[entry + 8:entry + 10], order)
                return value if 1 <= value <= 8 else 1
    return 1


def image_geometry(data):
    """Read header geometry, not a pixel decode or image-content classification."""
    orientation = 1
    if len(data) >= 33 and data[:8] == b'\x89PNG\r\n\x1a\n' and data[12:16] == b'IHDR':
        width, height = struct.unpack('>II', data[16:24])
        extension = '.png'
    elif data.startswith(b'\xff\xd8'):
        offset, width, height = 2, None, None
        sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
        while offset < len(data):
            if data[offset] != 0xFF:
                raise ValueError('Malformed JPEG marker sequence')
            while offset < len(data) and data[offset] == 0xFF:
                offset += 1
            if offset >= len(data):
                break
            marker = data[offset]
            offset += 1
            if marker in (0xDA, 0xD9):
                break
            if marker == 0x01 or 0xD0 <= marker <= 0xD8:
                continue
            if offset + 2 > len(data):
                raise ValueError('Truncated JPEG segment')
            length = int.from_bytes(data[offset:offset + 2], 'big')
            if length < 2 or offset + length > len(data):
                raise ValueError('Truncated JPEG segment')
            if marker == 0xE1:
                orientation = _exif_orientation(data[offset + 2:offset + length])
            if marker in sof:
                if length < 8:
                    raise ValueError('Invalid JPEG frame')
                height, width = struct.unpack('>HH', data[offset + 3:offset + 7])
            offset += length
        if width is None or height is None:
            raise ValueError('JPEG has no supported frame header')
        extension = '.jpg'
    elif len(data) >= 25 and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        chunk = data[12:16]
        if chunk == b'VP8X' and len(data) >= 30:
            width = 1 + int.from_bytes(data[24:27], 'little')
            height = 1 + int.from_bytes(data[27:30], 'little')
        elif chunk == b'VP8L' and data[20] == 0x2F:
            bits = int.from_bytes(data[21:25], 'little')
            width, height = (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        elif chunk == b'VP8 ' and len(data) >= 30 and data[23:26] == b'\x9d\x01\x2a':
            width, height = struct.unpack('<HH', data[26:30])
            width, height = width & 0x3FFF, height & 0x3FFF
        else:
            raise ValueError('Unsupported WebP frame header; convert a copy to PNG for analysis')
        extension = '.webp'
    else:
        raise ValueError('Reference must be PNG, JPEG or WebP; convert unsupported formats without replacing source truth')
    if not 0 < width <= 32768 or not 0 < height <= 32768 or width * height > 160_000_000:
        raise ValueError('Reference dimensions exceed the supported analysis bound')
    size = [height, width] if orientation in (5, 6, 7, 8) else [width, height]
    return {'extension': extension, 'sourceImageSize': size, 'encodedSize': [width, height],
            'exifOrientation': orientation, 'pixelDecodingEvaluated': False}


def project(workspace):
    record = read_json(confined(workspace, ARTIFACTS / 'project.json'))
    source = confined(workspace, record['source']['path'])
    if digest(source) != record['source']['sha256']:
        raise ValueError('Pinned project reference changed; use a new project/run rather than silently repinning')
    return record


def start(workspace, image, source_kind, authorization, references):
    record_path = confined(workspace, ARTIFACTS / 'project.json')
    if record_path.exists():
        raise ValueError('Project already initialized; resume its existing analysis instead of resetting it')
    source = Path(image).expanduser().resolve(strict=True)
    if source.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('Reference exceeds 64 MiB')
    data = source.read_bytes()
    if len(data) > 64 * 1024 * 1024:
        raise ValueError('Reference exceeds 64 MiB')
    geometry = image_geometry(data)
    relative = Path('public/assets/reference' + geometry['extension'])
    destination = confined(workspace, relative)
    if destination.exists() and digest(destination) != hashlib.sha256(data).hexdigest():
        raise ValueError('Refusing to replace a different existing project reference: ' + str(relative))
    if not authorization.strip():
        raise ValueError('Reference processing authorization must not be empty')
    if source_kind not in SOURCE_KINDS:
        raise ValueError('Unsupported sourceKind')
    for url in references:
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise ValueError('Reference URLs must be explicit HTTP(S) URLs')
    record = {'schemaVersion': 1, 'createdAt': datetime.now(timezone.utc).isoformat(),
              'source': {'path': relative.as_posix(), 'originalPath': str(source),
                         'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
                         'sourceKind': source_kind, 'authorization': authorization, **geometry},
              'references': references,
              'analysisRequired': ['Observe source pixels and references with image/browser tools',
                                   'Author intake, normalized visible anchors and uncertainty',
                                   'Author scene-spec.json and image-specific build_scene(context)',
                                   'Select suitable licensed resources; do not default to Oak/Linen'],
              'visualAcceptanceEvaluated': False}
    if not destination.exists():
        write_bytes(destination, data)
    write_json(record_path, record)
    return {'status': 'ready-for-analysis', 'project': record, 'receipt': str(record_path),
            'next': 'Read the image; author intake/spec/builder before initializing workflow attestations'}


def _template_files(template):
    files = []
    excluded = {'.git', 'node_modules', 'dist', '__pycache__', '.DS_Store'}
    for path in template.rglob('*'):
        relative = path.relative_to(template)
        if any(part in excluded for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError('Template contains a symlink: ' + str(relative))
        if path.is_file():
            files.append((relative, path))
    if not files:
        raise ValueError('Installed plugin has no usable template: ' + str(template))
    return files


def install_template(workspace, template, receipt_name):
    receipt_path = confined(workspace, ARTIFACTS / receipt_name)
    previous = read_json(receipt_path).get('files', {}) if receipt_path.exists() else {}
    files = _template_files(template)
    planned = []
    for relative, source in files:
        destination = confined(workspace, relative)
        wanted = digest(source)
        if destination.exists():
            actual = digest(destination)
            if actual != wanted and actual != previous.get(relative.as_posix()):
                raise ValueError('Refusing to overwrite an unowned/edited project file: ' + str(relative))
        planned.append((relative, source, destination, wanted))
    owned = {}
    for relative, source, destination, wanted in planned:
        if not destination.exists() or digest(destination) != wanted:
            write_bytes(destination, source.read_bytes())
        owned[relative.as_posix()] = wanted
    write_json(receipt_path, {'schemaVersion': 1, 'template': template.relative_to(PLUGIN).as_posix(), 'files': owned})
    return {'status': 'installed', 'files': sorted(owned), 'receipt': str(receipt_path)}


def use_recipe(workspace, name):
    record = project(workspace)
    if name != 'oak-linen':
        raise ValueError('Only the explicitly guarded oak-linen reproduction recipe is shipped; author new scenes from their own image')
    if record['source']['sha256'] != OAK_SOURCE:
        raise ValueError('Oak/Linen recipe requires its exact authorized source; it is never a fallback for another image')
    result = install_template(workspace, PLUGIN / 'recipes/oak-linen', 'recipe-install.json')
    spec_path = confined(workspace, 'scene-spec.json')
    spec = read_json(spec_path)
    spec['source'] = record['source']['path']
    spec['sourceKind'] = record['source']['sourceKind']
    spec['authoring']['sourceImageSize'] = record['source']['sourceImageSize']
    write_json(spec_path, spec)
    ownership = read_json(confined(workspace, ARTIFACTS / 'recipe-install.json'))
    ownership['files']['scene-spec.json'] = digest(spec_path)
    write_json(confined(workspace, ARTIFACTS / 'recipe-install.json'), ownership)
    return {**result, 'recipe': name, 'visualAcceptanceEvaluated': False}


def _public_asset(workspace, value):
    if not isinstance(value, str):
        raise ValueError('Manifest dependency URL must be a string')
    parsed = urlsplit(value)
    decoded = unquote(parsed.path)
    if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment
            or not decoded.startswith('/assets/') or '..' in PurePosixPath(decoded).parts):
        raise ValueError('Delivery requires local /assets/ URLs: ' + value)
    return confined(workspace, Path('public') / decoded.lstrip('/'))


def delivery_contract(workspace, spec_file):
    workspace = workspace_path(workspace)
    record = project(workspace)
    spec = read_json(confined(workspace, spec_file))
    manifest_path = confined(workspace, 'public/assets/interior/manifest.json')
    manifest = read_json(manifest_path)
    assets, paths, ids = [], {}, set()
    def add(identity, role, path):
        relative = path.relative_to(workspace).as_posix()
        resolved = path.resolve()
        if resolved in paths:
            previous_id, previous_role = paths[resolved]
            if previous_role == role == 'sidecar':
                return previous_id
            raise ValueError('Distinct delivery roles alias one file: ' + relative)
        if identity in ids or not path.is_file():
            raise ValueError('Duplicate identity or missing delivery file: ' + relative)
        ids.add(identity); paths[resolved] = (identity, role)
        assets.append({'id': identity, 'role': role, 'path': relative, 'sha256': digest(path)})
        return identity
    source = _public_asset(workspace, manifest['sourceImage'])
    if source != confined(workspace, record['source']['path']):
        raise ValueError('Exported sourceImage does not match the pinned project reference')
    add('source', 'source', source)
    for key, identity, role in [('model', 'runtime', 'runtime'), ('portableModel', 'portable', 'portable'), ('blender', 'native', 'native')]:
        add(identity, role, _public_asset(workspace, manifest[key]))
    add('manifest', 'sidecar', manifest_path)
    sidecars = ['manifest']
    for key in ('environment', 'background'):
        if manifest.get(key):
            identity = add(key, 'sidecar', _public_asset(workspace, manifest[key]))
            if identity not in sidecars:
                sidecars.append(identity)
    for atlas in manifest.get('lightmaps', []):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', str(atlas.get('id', ''))):
            raise ValueError('Invalid atlas identity')
        identity = 'lightmap-' + atlas['id']
        identity = add(identity, 'sidecar', _public_asset(workspace, atlas['url']))
        if identity not in sidecars:
            sidecars.append(identity)
    limitations = [spec.get('sourceViewLimit', ''), spec.get('portability', '')]
    limitations = [value for value in limitations if isinstance(value, str) and value.strip()]
    if len(limitations) != 2:
        raise ValueError('Declare sourceViewLimit and portability before producing a delivery contract')
    doc = {'schemaVersion': 1, 'root': str(workspace), 'assets': assets,
           'runtime': {'asset': 'runtime', 'sidecars': sidecars},
           'portable': {'asset': 'portable', 'limitations': [spec['portability']]},
           'native': {'asset': 'native'}, 'limitations': limitations}
    output = confined(workspace, ARTIFACTS / 'delivery-contract.json')
    write_json(output, doc)
    return {'status': 'recorded', 'contract': str(output), 'assets': len(assets),
            'consumerReopeningEvaluated': False, 'visualAcceptanceEvaluated': False}


def snapshot(workspace, input_file, run_id, name):
    """Freeze an observed report/capture, without accepting its claims."""
    workspace = workspace_path(workspace)
    for value in (run_id, name):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', value):
            raise ValueError('Snapshot run-id and name must be plain slugs, at most 64 characters')
    source = confined(workspace, input_file)
    if not source.is_file() or not source.stat().st_size:
        raise ValueError('Snapshot requires a nonempty workspace file')
    sha256 = digest(source)
    output = confined(workspace, ARTIFACTS / 'production' / run_id / 'evidence' / (name + '-' + sha256[:16] + source.suffix))
    if output.exists():
        if digest(output) != sha256:
            raise ValueError('Existing snapshot content does not match its identity')
    else:
        write_bytes(output, source.read_bytes())
        if digest(output) != sha256:
            output.unlink()
            raise ValueError('Input changed while freezing evidence; capture again after the writer finishes')
    return {'status': 'recorded', 'path': output.relative_to(workspace).as_posix(),
            'sha256': sha256, 'bytes': output.stat().st_size, 'visualAcceptanceEvaluated': False}


def preflight(workspace, interpreter=None):
    checks = {}
    for binary in ('node', 'npm'):
        executable = shutil.which(binary)
        if not executable:
            checks[binary] = {'status': 'missing'}
            continue
        result = subprocess.run([executable, '--version'], capture_output=True, text=True, timeout=30)
        checks[binary] = {'status': 'available' if result.returncode == 0 else 'error',
                          'version': result.stdout.strip(), 'path': executable}
        if binary == 'node' and result.returncode == 0:
            major = int(result.stdout.strip().removeprefix('v').split('.')[0])
            if major not in (18, 20) and major < 22:
                checks[binary]['status'] = 'unsupported-version'
    python = interpreter or os.environ.get('IMG2_BLENDER_PYTHON')
    if not python:
        candidates = [workspace / '.venv-blender/bin/python', workspace / '.venv-blender/Scripts/python.exe']
        python = next((str(path) for path in candidates if path.is_file()), None)
    if python:
        code = ('import sys,json,bpy,numpy; print(json.dumps({"python":list(sys.version_info[:3]),'
                '"bpy":list(bpy.app.version),"numpy":numpy.__version__}))')
        try:
            process = subprocess.run([str(python), '-c', code], capture_output=True, text=True, timeout=120)
            if process.returncode:
                checks['authoring'] = {'status': 'missing-dependency', 'reason': process.stderr.strip()[-2000:]}
            else:
                versions = json.loads(process.stdout.strip().splitlines()[-1])
                compatible = versions['python'][:2] == [3, 11] and versions['bpy'][:2] == [4, 3] and versions['numpy'] == '1.26.4'
                checks['authoring'] = {'status': 'compatible' if compatible else 'unsupported-version',
                                       'versions': versions, 'interpreter': str(python)}
        except (OSError, subprocess.TimeoutExpired, ValueError, IndexError) as error:
            checks['authoring'] = {'status': 'error', 'reason': str(error)}
    else:
        checks['authoring'] = {'status': 'missing', 'required': 'Isolated Python 3.11, bpy 4.3.0, NumPy 1.26.4; requirements-authoring.txt'}
    ready = all(value['status'] in ('available', 'compatible') for value in checks.values())
    return {'status': 'ready' if ready else 'blocked', 'checks': checks,
            'browserRequired': 'Use the agent host browser for actual image/scene/interaction review; no screenshot truth is inferred',
            'installsPerformed': False}
