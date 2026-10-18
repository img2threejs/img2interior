"""Explicit image recipes, not an image-to-material inference engine.

Schema 1: operations have id, op and output (workspace-relative PNG). Input is
{texture, channel}, {model, include}, {path}, or {reference: true}. A dye operation
has dye:{space:srgb255|linear,value:[r,g,b]}, bounds and optional strength,
exponent, normalizeMean, blur, crop. Roughness uses offset, scale, center
(zero|median), bounds. Crop uses crop:[left,top,right,bottom]. Woven uses outputs
{basecolor,normal,roughness}, resolution, yarns, tileMetres, seed and dye; optional
warpHeight, crossHeight, rippleHeight, yarnWidth, dyeBounds, noise, roughness,
roughnessScale all use physical/linear units as named. Inputs are never modified.
"""
import math
import os
from pathlib import Path
import tempfile

from .storage import confined, hashes, read_json, write_json

MAX_PIXELS = 16 * 1024 * 1024


def dependencies():
    try:
        import numpy as np
        from PIL import Image, ImageFilter
    except ImportError as exc:
        raise RuntimeError('Surface preparation needs optional requirements-surfaces.txt (NumPy and Pillow)') from exc
    return np, Image, ImageFilter


def number(value, name, lower=None, upper=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    if (lower is not None and value < lower) or (upper is not None and value > upper):
        raise ValueError(f'{name} is outside its allowed range')
    return value


def bounds(value, name):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f'{name} requires [minimum, maximum]')
    lo, hi = [number(v, name) for v in value]
    if lo > hi:
        raise ValueError(f'{name} minimum exceeds maximum')
    return lo, hi


def linear(rgb, np):
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def srgb(rgb, np):
    return np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.maximum(rgb, 0) ** (1 / 2.4) - 0.055)


def dye_value(dye, np):
    if not isinstance(dye, dict) or dye.get('space') not in ('srgb255', 'linear'):
        raise ValueError('dye requires space srgb255 or linear')
    values = dye.get('value')
    if not isinstance(values, list) or len(values) != 3:
        raise ValueError('dye.value requires three color components')
    maximum = 255 if dye['space'] == 'srgb255' else 1
    color = np.asarray([number(v, 'dye', 0, maximum) for v in values], dtype=np.float32)
    return linear(color / 255, np) if maximum == 255 else color


def pixels(path, mode, Image):
    from PIL import ImageOps
    with Image.open(path) as image:
        if image.width * image.height > MAX_PIXELS:
            raise ValueError(f'Image exceeds {MAX_PIXELS} decoded pixels: {path}')
        return ImageOps.exif_transpose(image).convert(mode)


def statistics(image, np):
    array = np.asarray(image, dtype=np.float32) / 255
    if array.ndim == 2:
        array = array[..., None]
    return {'size': list(image.size), 'mode': image.mode, 'encoding': 'decoded uint8 / 255',
            'min': array.min(axis=(0, 1)).tolist(), 'max': array.max(axis=(0, 1)).tolist(),
            'mean': array.mean(axis=(0, 1)).tolist(), 'std': array.std(axis=(0, 1)).tolist()}


def crop_image(image, rectangle):
    if (not isinstance(rectangle, list) or len(rectangle) != 4 or
            any(type(v) is not int for v in rectangle)):
        raise ValueError('crop requires four integer pixel coordinates')
    left, top, right, bottom = rectangle
    if not 0 <= left < right <= image.width or not 0 <= top < bottom <= image.height:
        raise ValueError(f'Crop {rectangle} exceeds input image {image.size}; observe the actual image first')
    return image.crop(rectangle)


def transform(image, operation, np, ImageFilter):
    op = operation['op']
    if 'crop' in operation:
        image = crop_image(image, operation['crop'])
    if op == 'crop':
        if 'crop' not in operation:
            raise ValueError('crop operation requires an explicit crop rectangle')
        return np.asarray(image, dtype=np.float32) / 255
    if op == 'dye':
        blur = number(operation.get('blur', 0), 'blur', 0, 128)
        if blur:
            image = image.filter(ImageFilter.GaussianBlur(blur))
        scan = linear(np.asarray(image, dtype=np.float32) / 255, np)
        luminance = scan @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        median = float(np.median(luminance))
        if median <= 0:
            raise ValueError('Cannot normalize a scan with zero median luminance')
        lo, hi = bounds(operation['bounds'], 'dye bounds')
        if lo < 0:
            raise ValueError('Dye modulation cannot be negative')
        ratio = np.clip(luminance / median, lo, hi)
        ratio = ratio ** number(operation.get('exponent', 1), 'exponent', 0.01, 10)
        ratio = 1 + number(operation.get('strength', 1), 'strength', 0, 1) * (ratio - 1)
        normalize = operation.get('normalizeMean', False)
        if type(normalize) is not bool:
            raise ValueError('normalizeMean must be boolean')
        if normalize:
            if float(ratio.mean()) <= 0:
                raise ValueError('Cannot normalize zero modulation')
            ratio /= ratio.mean()
        return np.clip(srgb(ratio[..., None] * dye_value(operation['dye'], np), np), 0, 1)
    if op == 'roughness':
        scan = np.asarray(image, dtype=np.float32) / 255
        center = operation.get('center', 'zero')
        if center not in ('zero', 'median'):
            raise ValueError('roughness center must be zero or median')
        lo, hi = bounds(operation.get('bounds', [0, 1]), 'roughness bounds')
        if lo < 0 or hi > 1:
            raise ValueError('Roughness bounds must lie within [0,1]')
        return np.clip(number(operation['offset'], 'offset') + number(operation['scale'], 'scale') *
                       (scan - (np.median(scan) if center == 'median' else 0)), lo, hi)
    raise ValueError(f'Unknown surface operation: {op}')


def woven(operation, np):
    resolution, yarns = operation['resolution'], operation['yarns']
    if type(resolution) is not int or not 4 <= resolution <= 4096:
        raise ValueError('Woven resolution must be an integer in [4,4096]')
    if type(yarns) is not int or not 2 <= yarns <= resolution or yarns % 2:
        raise ValueError('Woven yarns must be an even integer in [2,resolution] for periodic crossing parity')
    tile = number(operation['tileMetres'], 'tileMetres', 0.0001, 100)
    seed = operation['seed']
    if type(seed) is not int or seed < 0:
        raise ValueError('Woven seed must be a nonnegative integer')
    coordinate = (np.arange(resolution, dtype=np.float32) + 0.5) * yarns / resolution
    x, y = coordinate[None, :], coordinate[:, None]
    ix, iy = np.floor(x).astype(np.int32), np.floor(y).astype(np.int32)
    fx, fy = x % 1 - 0.5, y % 1 - 0.5
    width = number(operation.get('yarnWidth', 0.49), 'yarnWidth', 0.01, 0.5)
    warp = np.sqrt(np.maximum(1 - (fx / width) ** 2, 0))
    weft = np.sqrt(np.maximum(1 - (fy / width) ** 2, 0))
    over = ((ix + iy) % 2) == 0
    high = number(operation.get('warpHeight', 0.00055), 'warpHeight', 0, 1)
    low = number(operation.get('crossHeight', 0.00009), 'crossHeight', 0, 1)
    ripple = number(operation.get('rippleHeight', 0.000012), 'rippleHeight', 0, 1)
    height = np.where(over, high * warp + low * weft, high * weft + low * warp)
    height += ripple * np.sin(x * np.pi * 8) * np.sin(y * np.pi * 6)
    du = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * resolution / (2 * tile)
    dv = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * resolution / (2 * tile)
    # PNG rows point down; OpenGL tangent-space +V points up.
    normal = np.stack((-du, dv, np.ones_like(height)), axis=-1)
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
    rng = np.random.default_rng(seed)
    lo, hi = bounds(operation.get('dyeBounds', [0.92, 1.08]), 'dyeBounds')
    if lo < 0:
        raise ValueError('Yarn dye modulation cannot be negative')
    yarn_dye = rng.uniform(lo, hi, (yarns, 2)).astype(np.float32)
    modulation = np.where(over, yarn_dye[ix, 0], yarn_dye[iy, 1])
    modulation += rng.normal(0, number(operation.get('noise', 0.007), 'noise', 0, 1),
                             (resolution, resolution)).astype(np.float32)
    color = np.clip(srgb(modulation[..., None] * dye_value(operation['dye'], np), np), 0, 1)
    roughness = np.clip(number(operation.get('roughness', 0.86), 'roughness', 0, 1) +
                        number(operation.get('roughnessScale', 0.05), 'roughnessScale') * (modulation - 1), 0, 1)
    return {'basecolor': color, 'normal': normal * 0.5 + 0.5, 'roughness': roughness}, {
        'tileMetres': tile, 'yarnPitchMetres': tile / yarns,
        'normalConvention': 'OpenGL tangent +Y; periodic central derivatives of physical height',
        'maximumNormalLengthError': float(np.max(np.abs(np.linalg.norm(normal, axis=-1) - 1)))}


def reference_path(workspace, recipe):
    spec = confined(workspace, recipe.get('spec', 'scene-spec.json'))
    return read_json(spec)['source'] if spec.exists() else 'public/assets/reference.png'


def resolve_input(workspace, reference, manifest, value):
    if not isinstance(value, dict):
        raise ValueError('input must be a path, reference, texture/channel or model/include object')
    if set(value) == {'path'}:
        relative = value['path']
    elif value == {'reference': True}:
        relative = reference
    elif set(value) == {'texture', 'channel'}:
        if value['channel'] not in ('color', 'normal', 'roughness'):
            raise ValueError('Texture channel must be color, normal or roughness')
        relative = manifest['textures'][value['texture']][value['channel']]
    elif set(value) == {'model', 'include'}:
        relative = manifest['modelIncludes'][value['model']][value['include']]
    else:
        raise ValueError(f'Ambiguous or unsupported surface input: {value}')
    path = confined(workspace, relative)
    if not path.is_file():
        raise ValueError(f'Missing surface input: {relative}')
    if 'texture' in value or 'model' in value:
        receipt = next((entry for entry in manifest['downloads'] if entry['path'] == relative), None)
        if receipt is None or hashes(path)[2] != receipt['sha256']:
            raise ValueError(f'Resource integrity mismatch: {relative}; fetch resources again')
    return relative, path


def save_image(workspace, relative, array, np, Image):
    if not np.isfinite(array).all():
        raise ValueError('Non-finite generated pixels')
    path = confined(workspace, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.fromarray(np.rint(np.clip(array, 0, 1) * 255).astype(np.uint8))
    fd, temporary = tempfile.mkstemp(prefix='.surface-', suffix='.png', dir=path.parent)
    os.close(fd)
    try:
        image.save(temporary, format='PNG', optimize=True)
        os.replace(temporary, confined(workspace, relative))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    decoded = pixels(path, image.mode, Image)
    return {'path': relative, 'sha256': hashes(path)[2], 'pixels': statistics(decoded, np)}


def prepare(workspace, recipe_path):
    np, Image, ImageFilter = dependencies()
    workspace = Path(workspace).resolve()
    recipe_file = confined(workspace, recipe_path)
    recipe = read_json(recipe_file)
    if not isinstance(recipe, dict) or type(recipe.get('schemaVersion')) is not int or recipe['schemaVersion'] != 1:
        raise ValueError('Surface recipe must have schemaVersion 1')
    operations = recipe.get('operations')
    if not isinstance(operations, list) or not operations or len(operations) > 100:
        raise ValueError('Surface recipe needs 1–100 operations')
    reference = reference_path(workspace, recipe)
    if 'referenceSha256' in recipe:
        if hashes(confined(workspace, reference))[2] != recipe['referenceSha256']:
            raise ValueError('This recipe is bound to a different reference image; author a new recipe instead of reusing its crops')
    manifest_relative = recipe.get('resourceManifest', '.img2/artifacts/interior/resources.json')
    manifest_file = confined(workspace, manifest_relative)
    needs_resources = any(isinstance(op, dict) and isinstance(op.get('input'), dict) and
                          ('texture' in op['input'] or 'model' in op['input']) for op in operations)
    manifest = read_json(manifest_file) if needs_resources else {}
    protected = {recipe_file, manifest_file, confined(workspace, reference),
                 confined(workspace, recipe.get('spec', 'scene-spec.json'))}
    planned, output_paths, ids = [], set(), set()
    for operation in operations:
        if not isinstance(operation, dict) or operation.get('op') not in ('dye', 'roughness', 'crop', 'woven'):
            raise ValueError('Each operation must be dye, roughness, crop or woven')
        identifier = operation.get('id')
        if not isinstance(identifier, str) or not identifier.strip() or identifier in ids:
            raise ValueError('Operations need unique nonempty ids')
        ids.add(identifier)
        source = None
        if operation['op'] == 'woven':
            outputs = operation.get('outputs')
            if not isinstance(outputs, dict) or set(outputs) != {'basecolor', 'normal', 'roughness'}:
                raise ValueError('Woven outputs must name basecolor, normal and roughness')
        else:
            source = resolve_input(workspace, reference, manifest, operation.get('input'))
            protected.add(source[1])
            outputs = {'image': operation.get('output')}
        for relative in outputs.values():
            path = confined(workspace, relative)
            if path.suffix.lower() != '.png' or not relative.startswith('public/assets/interior/'):
                raise ValueError('Surface outputs must be PNGs under public/assets/interior/')
            if path in output_paths:
                raise ValueError(f'Duplicate surface output: {relative}')
            output_paths.add(path)
        planned.append((operation, source, outputs))
    if output_paths & protected:
        raise ValueError('Surface outputs must not overwrite any recipe, source or resource input')
    records = []
    for operation, source, outputs in planned:
        record = {'id': operation['id'], 'operation': operation, 'inputs': [], 'outputs': {}}
        if operation['op'] == 'woven':
            arrays, metric = woven(operation, np)
            record.update(metric)
        else:
            relative, path = source
            image = pixels(path, 'L' if operation['op'] == 'roughness' else 'RGB', Image)
            record['inputs'].append({'path': relative, 'sha256': hashes(path)[2], 'pixels': statistics(image, np)})
            arrays = {'image': transform(image, operation, np, ImageFilter)}
        for channel, array in arrays.items():
            record['outputs'][channel] = save_image(workspace, outputs[channel], array, np, Image)
        records.append(record)
    receipt = {'schemaVersion': 1, 'recipe': recipe_path, 'recipeSha256': hashes(recipe_file)[2],
               'operations': records, 'limits': recipe.get('limits', []),
               'tools': {'numpy': np.__version__, 'Pillow': Image.__version__},
               'interpretation': 'Explicit authored transformations, not recovered physical reflectance or visual acceptance'}
    if needs_resources:
        receipt['resourceManifest'] = manifest_relative
        receipt['resourceManifestSha256'] = hashes(manifest_file)[2]
    write_json(workspace, '.img2/artifacts/interior/surfaces.json', receipt)
    return receipt
