"""Live Poly Haven client, independent of the API server implementation.

Downloaded assets are CC0. Access to the live service has separate terms and
requires identifiable requests and visible credit; see API_TERMS.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.parse
import urllib.request
from uuid import uuid4

from .storage import MAX_JSON, confined, hashes, read_json, relative_path, write_json

API = 'https://api.polyhaven.com'
API_TERMS = 'https://github.com/Poly-Haven/Public-API/blob/master/ToS.md'
CREDIT = 'Powered by Poly Haven'
HEADERS = {'User-Agent': 'img2interior/0.2 PolyHavenResourceClient',
           'Referer': 'https://img2interior.local/authoring'}
HOSTS = frozenset(('api.polyhaven.com', 'dl.polyhaven.org', 'cdn.polyhaven.com'))
MAX_FILE = 512 * 1024 * 1024
MAX_TOTAL = 4 * 1024 * 1024 * 1024
TYPES = {'hdris': 0, 'textures': 1, 'models': 2}
PROVENANCE = {'provider': 'Poly Haven', 'license': 'CC0-1.0',
              'licenseUrl': 'https://polyhaven.com/license', 'apiTerms': API_TERMS,
              'credit': CREDIT}


def safe_url(url):
    if not isinstance(url, str) or any(ord(c) < 33 for c in url):
        raise ValueError('Invalid resource URL')
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in HOSTS or
            parsed.username is not None or parsed.password is not None or
            parsed.port not in (None, 443) or parsed.fragment):
        raise ValueError(f'Only Poly Haven HTTPS API/CDN URLs are permitted: {url}')
    return url


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        safe_url(newurl)
        return super().redirect_request(request, response, code, message, headers, newurl)


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(SafeRedirect())

    def open(self, url):
        return self.opener.open(urllib.request.Request(safe_url(url), headers=HEADERS), timeout=120)

    def get(self, endpoint):
        with self.open(API + endpoint) as response:
            payload = response.read(MAX_JSON + 1)
        if len(payload) > MAX_JSON:
            raise ValueError('Poly Haven JSON response exceeds the 16 MiB limit')
        result = json.loads(payload)
        if not isinstance(result, dict):
            raise ValueError('Expected an API JSON object')
        return result


def asset_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,159}', value):
        raise ValueError(f'Invalid Poly Haven asset id: {value!r}')
    return value


def describe(client, kind, identifier):
    if kind not in ('info', 'files'):
        raise ValueError('Expected info or files')
    return client.get(f'/{kind}/{asset_id(identifier)}')


def search(client, kind, query, limit=10):
    query = query.strip().lower()
    if kind not in TYPES or not 1 <= len(query) <= 100 or not 1 <= limit <= 100:
        raise ValueError('Search requires a supported type, 1–100 character query and limit 1–100')
    return client.get('/search?' + urllib.parse.urlencode({'q': query, 't': kind, 'limit': limit}))


def save_query(workspace, command, request, result):
    relative = f'.img2/artifacts/interior/polyhaven/{command}-{uuid4().hex}.json'
    receipt = {**PROVENANCE, 'request': request, 'result': result, 'receipt': relative}
    write_json(workspace, relative, receipt)
    return receipt


def descriptor(value):
    if not isinstance(value, dict):
        raise ValueError('Expected a file descriptor')
    size = value.get('size')
    if type(size) is not int or not 0 < size <= MAX_FILE:
        raise ValueError(f'File size must be between 1 and {MAX_FILE} bytes')
    if not isinstance(value.get('md5'), str) or not re.fullmatch('[0-9a-fA-F]{32}', value['md5']):
        raise ValueError('File descriptor is missing a publisher MD5 digest')
    safe_url(value.get('url'))
    return value


def choose(files, key, resolution, format_name, identifier):
    try:
        return descriptor(files[key][resolution][format_name])
    except KeyError as exc:
        raise ValueError(f'{identifier}: missing {key}/{resolution}/{format_name}; inspect files before selecting') from exc


def filename(item):
    name = urllib.parse.unquote(urllib.parse.urlsplit(item['url']).path.rsplit('/', 1)[-1])
    relative_path(name)
    if '/' in name:
        raise ValueError('Encoded path separator in publisher filename')
    return name


def plan_selection(client, workspace, selection):
    if not isinstance(selection, dict) or type(selection.get('schemaVersion')) is not int or selection['schemaVersion'] != 1:
        raise ValueError('Selection must have schemaVersion 1')
    if not isinstance(selection.get('reason'), str) or not selection['reason'].strip():
        raise ValueError('Selection must explain its reason')
    manifest = {**PROVENANCE, 'schemaVersion': 1, 'selection': selection,
                'models': {}, 'textures': {}, 'hdris': {}, 'modelIncludes': {}, 'assetInfo': {}}
    jobs = {}
    seen = set()

    def enqueue(identifier, relative, item):
        descriptor(item)
        path = f'resources/polyhaven/{identifier}/{relative}'
        confined(workspace, path)
        if path in jobs and jobs[path][1] != item:
            raise ValueError(f'Conflicting publisher files at {path}')
        jobs[path] = (identifier, item)
        return path

    for kind in TYPES:
        entries = selection.get(kind, [])
        if not isinstance(entries, list) or len(entries) > 100:
            raise ValueError(f'{kind} must be a list of at most 100 selections')
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError('Each selection must be an object')
            identifier = asset_id(entry.get('id'))
            if identifier in seen:
                raise ValueError(f'Duplicate selected asset: {identifier}')
            seen.add(identifier)
            if not isinstance(entry.get('purpose'), str) or not entry['purpose'].strip():
                raise ValueError(f'{identifier}: purpose is required')
            resolution, format_name = entry.get('resolution'), entry.get('format')
            if not isinstance(resolution, str) or not re.fullmatch(r'[1-9][0-9]?k', resolution):
                raise ValueError(f'{identifier}: expected an explicit resolution such as 2k')
            allowed = {'models': ('gltf',), 'textures': ('jpg', 'png', 'exr'), 'hdris': ('hdr', 'exr')}
            if format_name not in allowed[kind]:
                raise ValueError(f'{identifier}: unsupported {kind} format {format_name!r}')
            info = describe(client, 'info', identifier)
            if info.get('type') != TYPES[kind]:
                raise ValueError(f'{identifier}: API type does not match selected {kind}')
            manifest['assetInfo'][identifier] = info
            files = describe(client, 'files', identifier)
            if kind == 'textures':
                channels = {}
                for channel, key in (('color', 'Diffuse'), ('normal', 'nor_gl'), ('roughness', 'Rough')):
                    item = choose(files, key, resolution, format_name, identifier)
                    channels[channel] = enqueue(identifier, filename(item), item)
                manifest[kind][identifier] = channels
            else:
                key = 'gltf' if kind == 'models' else 'hdri'
                item = choose(files, key, resolution, format_name, identifier)
                manifest[kind][identifier] = enqueue(identifier, filename(item), item)
                if kind == 'models':
                    includes = item.get('include', {})
                    if not isinstance(includes, dict) or len(includes) > 1000:
                        raise ValueError(f'{identifier}: invalid glTF include map')
                    manifest['modelIncludes'][identifier] = {
                        relative: enqueue(identifier, relative, child) for relative, child in includes.items()}
    if sum(item['size'] for _, item in jobs.values()) > MAX_TOTAL:
        raise ValueError('Selection exceeds the 4 GiB total transfer limit; use smaller selections')
    return manifest, jobs


def acquire(client, workspace, identifier, relative, item):
    descriptor(item)
    path = confined(workspace, relative)
    expected = item['md5'].lower()
    if path.is_file() and path.stat().st_size == item['size']:
        count, md5, sha256 = hashes(path)
        if md5 == expected:
            return {'assetId': identifier, 'path': relative, 'url': item['url'],
                    'bytes': count, 'publisherMd5': item['md5'], 'sha256': sha256}
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.download-', dir=path.parent)
    count = 0
    md5, sha256 = hashlib.md5(usedforsecurity=False), hashlib.sha256()
    try:
        with os.fdopen(fd, 'wb') as output, client.open(item['url']) as response:
            while True:
                block = response.read(min(1024 * 1024, item['size'] - count + 1))
                if not block:
                    break
                count += len(block)
                if count > item['size']:
                    raise ValueError(f'{identifier}: publisher byte length exceeded for {relative}')
                md5.update(block)
                sha256.update(block)
                output.write(block)
        if count != item['size'] or md5.hexdigest() != expected:
            raise ValueError(f'{identifier}: publisher byte length or MD5 mismatch for {relative}')
        os.replace(temporary, confined(workspace, relative))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {'assetId': identifier, 'path': relative, 'url': item['url'], 'bytes': count,
            'publisherMd5': item['md5'], 'sha256': sha256.hexdigest()}


def verify_gltf(workspace, path, includes):
    document = read_json(confined(workspace, path))
    if document.get('asset', {}).get('version') != '2.0':
        raise ValueError(f'Expected glTF 2.0: {path}')
    for entry in document.get('buffers', []) + document.get('images', []):
        uri = entry.get('uri')
        if uri is None or uri.startswith('data:'):
            continue
        parsed = urllib.parse.urlsplit(uri)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError(f'Nonlocal glTF dependency: {uri}')
        relative = urllib.parse.unquote(uri)
        relative_path(relative)
        if relative not in includes or not confined(workspace, includes[relative]).is_file():
            raise ValueError(f'glTF dependency is missing from publisher include map: {uri}')


def fetch(workspace, selection_path, client=None):
    workspace = Path(workspace).resolve()
    selection_file = confined(workspace, selection_path)
    selection = read_json(selection_file)
    client = client or Client()
    manifest, jobs = plan_selection(client, workspace, selection)
    receipts = [acquire(client, workspace, identifier, relative, item)
                for relative, (identifier, item) in jobs.items()]
    for identifier, path in manifest['models'].items():
        verify_gltf(workspace, path, manifest['modelIncludes'][identifier])
    manifest.update({'downloads': receipts, 'totalBytes': sum(item['bytes'] for item in receipts),
                     'selectionPath': selection_path, 'selectionSha256': hashes(selection_file)[2]})
    write_json(workspace, '.img2/artifacts/interior/resources.json', manifest)
    return manifest
