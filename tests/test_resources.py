"""Resource integrity/path/manifest and real decoded-material behavior.

No network is required: only the HTTP transport is substituted, while planning,
streaming, hashes, on-disk glTF references and all image operations are real.
Image cases explicitly skip without the optional surface dependencies.
"""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.request

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN))
from resources_lib import polyhaven as ph
from resources_lib import surfaces
from resources_lib.storage import MAX_JSON, confined, hashes, read_json, write_json

try:
    import numpy as np
    from PIL import Image
except ImportError:
    np = Image = None


def file_descriptor(name, payload):
    return {'url': 'https://dl.polyhaven.org/file/ph-assets/' + name,
            'size': len(payload), 'md5': hashlib.md5(payload, usedforsecurity=False).hexdigest()}


class Transport:
    def __init__(self):
        self.json = {}
        self.payloads = {}
        self.requests = []
        self.transfers = []

    def get(self, endpoint):
        self.requests.append(endpoint)
        return copy.deepcopy(self.json[endpoint])

    def open(self, url):
        self.transfers.append(url)
        return io.BytesIO(self.payloads[url])

    def add(self, name, payload):
        item = file_descriptor(name, payload)
        self.payloads[item['url']] = payload
        return item


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='interior resources ')
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name)
        self.client = Transport()

    def save(self, relative, data):
        write_json(self.workspace, relative, data)

    def texture_selection(self):
        files = {key: {'2k': {'jpg': self.client.add(f'linen_{key}_2k.jpg', key.encode())}}
                 for key in ('Diffuse', 'nor_gl', 'Rough')}
        self.client.json.update({'/info/linen': {'name': 'Linen', 'type': 1}, '/files/linen': files})
        return {'schemaVersion': 1, 'reason': 'Observed textile', 'textures': [
            {'id': 'linen', 'resolution': '2k', 'format': 'jpg', 'purpose': 'Seat upholstery'}]}

    def model_selection(self, uri='textures/color.jpg'):
        document = {'asset': {'version': '2.0'}, 'buffers': [{'uri': 'mesh.bin', 'byteLength': 4}],
                    'images': [{'uri': uri}]}
        item = self.client.add('chair_original_2k.gltf', json.dumps(document).encode())
        item['include'] = {'mesh.bin': self.client.add('mesh.bin', b'mesh'),
                           'textures/color.jpg': self.client.add('color.jpg', b'color')}
        self.client.json.update({'/info/chair': {'type': 2}, '/files/chair': {'gltf': {'2k': {'gltf': item}}}})
        return {'schemaVersion': 1, 'reason': 'Selected editable chair', 'models': [
            {'id': 'chair', 'resolution': '2k', 'format': 'gltf', 'purpose': 'Chair'}]}


class ResourceTests(WorkspaceTests):


    def test_gltf_relative_dependencies_resolve_after_acquisition(self):
        self.save('selection.json', self.model_selection())
        result = ph.fetch(self.workspace, 'selection.json', self.client)
        root = self.workspace / result['models']['chair']
        for entry in read_json(root)['buffers'] + read_json(root)['images']:
            self.assertTrue((root.parent / entry['uri']).is_file())

    def test_missing_gltf_dependency_cannot_publish_receipt(self):
        self.save('selection.json', self.model_selection('textures/not-in-descriptor.jpg'))
        with self.assertRaisesRegex(ValueError, 'include map'):
            ph.fetch(self.workspace, 'selection.json', self.client)
        self.assertFalse((self.workspace / '.img2/artifacts/interior/resources.json').exists())

    def test_cache_checks_bytes_not_only_size(self):
        item = self.client.add('scan.jpg', b'correct')
        relative = 'resources/polyhaven/scan/scan.jpg'
        first = ph.acquire(self.client, self.workspace, 'scan', relative, item)
        self.assertEqual(ph.acquire(self.client, self.workspace, 'scan', relative, item), first)
        self.assertEqual(len(self.client.transfers), 1)
        (self.workspace / relative).write_bytes(b'corrupt')
        self.assertEqual(ph.acquire(self.client, self.workspace, 'scan', relative, item), first)
        self.assertEqual(len(self.client.transfers), 2)
        self.assertEqual((self.workspace / relative).read_bytes(), b'correct')

    def test_bad_download_is_not_published_and_preserves_old_file(self):
        item = self.client.add('scan.jpg', b'correct')
        relative = 'resources/polyhaven/scan/scan.jpg'
        path = confined(self.workspace, relative)
        path.parent.mkdir(parents=True)
        path.write_bytes(b'old')
        for bad in (b'short', b'wrong!!', b'too-many-bytes'):
            self.client.payloads[item['url']] = bad
            with self.assertRaisesRegex(ValueError, 'byte length|MD5'):
                ph.acquire(self.client, self.workspace, 'scan', relative, item)
            self.assertEqual(path.read_bytes(), b'old')
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_missing_map_and_wrong_asset_type_fail_before_download(self):
        selection = self.texture_selection()
        del self.client.json['/files/linen']['nor_gl']
        with self.assertRaisesRegex(ValueError, 'nor_gl'):
            ph.plan_selection(self.client, self.workspace, selection)
        self.client.json['/info/linen']['type'] = 2
        with self.assertRaisesRegex(ValueError, 'type'):
            ph.plan_selection(self.client, self.workspace, selection)
        self.assertEqual(self.client.transfers, [])

    def test_descriptor_limits_and_confined_include_paths(self):
        selection = self.model_selection()
        item = self.client.json['/files/chair']['gltf']['2k']['gltf']
        dependency = next(iter(item['include'].values()))
        for bad in ('../escape', '/absolute', 'textures/../../escape', 'C:/drive',
                    'textures\\escape', 'textures/%2e%2e/escape'):
            item['include'] = {bad: dependency}
            with self.subTest(path=bad), self.assertRaises(ValueError):
                ph.plan_selection(self.client, self.workspace, selection)
        oversized = {**dependency, 'size': ph.MAX_FILE + 1}
        with self.assertRaisesRegex(ValueError, 'size'):
            ph.descriptor(oversized)
        with self.assertRaisesRegex(ValueError, 'MD5'):
            ph.descriptor({**dependency, 'md5': 'not-a-hash'})
        self.assertEqual(self.client.transfers, [])

    def test_symlink_paths_are_refused_even_inside_workspace(self):
        target = self.workspace / 'original'
        target.mkdir()
        (self.workspace / 'resources').symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            confined(self.workspace, 'resources/scan.jpg')
        self.assertEqual(list(target.iterdir()), [])

    def test_urls_and_redirects_never_leave_observed_provider_hosts(self):
        for url in ('http://dl.polyhaven.org/file', 'https://dl.polyhaven.org.evil.test/file',
                    'https://user@api.polyhaven.com/file', 'file:///tmp/file',
                    'https://localhost/file', 'https://cdn.polyhaven.com:8443/file'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                ph.safe_url(url)
        for host in ph.HOSTS:
            self.assertEqual(ph.safe_url(f'https://{host}/file'), f'https://{host}/file')
        with self.assertRaises(ValueError):
            ph.SafeRedirect().redirect_request(urllib.request.Request('https://api.polyhaven.com/files/a'),
                                                None, 302, 'Found', {}, 'https://evil.test/payload')

    def test_oversized_json_fails_before_parsing(self):
        path = self.workspace / 'large.json'
        with path.open('wb') as stream:
            stream.truncate(MAX_JSON + 1)
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            read_json(path)



@unittest.skipUnless(np is not None and Image is not None,
                     'optional image behavior tests need requirements-surfaces.txt (NumPy and Pillow)')
class SurfaceTests(WorkspaceTests):
    def image(self, relative, array):
        path = confined(self.workspace, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.asarray(array, dtype=np.uint8)).save(path)
        return path

    def recipe(self, operations, **extra):
        self.save('surfaces.json', {'schemaVersion': 1, 'operations': operations, **extra})
        return surfaces.prepare(self.workspace, 'surfaces.json')

    def output(self, name):
        with Image.open(self.workspace / ('public/assets/interior/' + name)) as image:
            return np.asarray(image).copy()

    def test_dye_removes_scan_hue_but_preserves_luminance_variation(self):
        source = self.image('input.png', [[[20, 40, 120], [50, 100, 200], [90, 150, 240]]])
        original = source.read_bytes()
        receipt = self.recipe([{'id': 'cloth', 'op': 'dye', 'input': {'path': 'input.png'},
                                'dye': {'space': 'linear', 'value': [0.25, 0.125, 0.0625]},
                                'bounds': [0.1, 2], 'output': 'public/assets/interior/cloth.png'}])
        encoded = self.output('cloth.png').astype(float) / 255
        decoded = np.where(encoded <= 0.04045, encoded / 12.92, ((encoded + 0.055) / 1.055) ** 2.4)
        self.assertTrue(np.all(np.diff(decoded[0, :, 0]) > 0))
        np.testing.assert_allclose(decoded[0, 1], [0.25, 0.125, 0.0625], atol=0.003)
        np.testing.assert_allclose(decoded[..., 0], decoded[..., 1] * 2, atol=0.006)
        self.assertEqual(source.read_bytes(), original)
        output = receipt['operations'][0]['outputs']['image']
        self.assertEqual(output['sha256'], hashes(self.workspace / output['path'])[2])
        self.assertEqual(output['pixels']['size'], [3, 1])
        self.assertGreater(output['pixels']['std'][0], 0)

    def test_mean_normalized_dye_and_centered_roughness(self):
        self.image('color.png', [[[50, 50, 50], [100, 100, 100], [150, 150, 150]]])
        self.image('rough.png', [[0, 128, 255]])
        self.recipe([
            {'id': 'dye', 'op': 'dye', 'input': {'path': 'color.png'}, 'bounds': [0.7, 1.15],
             'normalizeMean': True, 'dye': {'space': 'linear', 'value': [0.3, 0.3, 0.3]},
             'output': 'public/assets/interior/color.png'},
            {'id': 'rough', 'op': 'roughness', 'input': {'path': 'rough.png'}, 'center': 'median',
             'offset': 0.42, 'scale': 0.30, 'bounds': [0.30, 0.58],
             'output': 'public/assets/interior/rough.png'}])
        encoded = self.output('color.png').astype(float) / 255
        decoded = np.where(encoded <= 0.04045, encoded / 12.92, ((encoded + 0.055) / 1.055) ** 2.4)
        np.testing.assert_allclose(decoded.mean(axis=(0, 1)), [0.3, 0.3, 0.3], atol=0.004)
        np.testing.assert_array_equal(self.output('rough.png'), [[76, 107, 145]])

    def test_reference_extension_and_crop_require_explicit_observed_rectangle(self):
        source = self.image('public/assets/reference.tiff', np.arange(36, dtype=np.uint8).reshape(3, 4, 3))
        self.save('scene-spec.json', {'source': 'public/assets/reference.tiff'})
        receipt = self.recipe([{'id': 'art', 'op': 'crop', 'input': {'reference': True},
                                'crop': [1, 0, 3, 2], 'output': 'public/assets/interior/art.png'}],
                              referenceSha256=hashes(source)[2])
        np.testing.assert_array_equal(self.output('art.png'), np.arange(36, dtype=np.uint8).reshape(3, 4, 3)[:2, 1:3])
        self.assertEqual(receipt['operations'][0]['inputs'][0]['path'], 'public/assets/reference.tiff')
        with self.assertRaisesRegex(ValueError, 'different reference'):
            self.recipe([{'id': 'art', 'op': 'crop', 'input': {'reference': True},
                          'crop': [1, 0, 3, 2], 'output': 'public/assets/interior/wrong.png'}], referenceSha256='0' * 64)
        self.assertFalse((self.workspace / 'public/assets/interior/wrong.png').exists())
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            self.recipe([{'id': 'art', 'op': 'crop', 'input': {'reference': True},
                          'crop': [0, 0, 5, 5], 'output': 'public/assets/interior/padded.png'}])

    def test_resource_channel_integrity_and_no_source_overwrite(self):
        path = self.image('resources/polyhaven/cloth/source.png', [[[100, 100, 100]]])
        self.save('.img2/artifacts/interior/resources.json', {
            'textures': {'cloth': {'color': 'resources/polyhaven/cloth/source.png'}},
            'downloads': [{'path': 'resources/polyhaven/cloth/source.png', 'sha256': hashes(path)[2]}]})
        operation = {'id': 'cloth', 'op': 'dye', 'input': {'texture': 'cloth', 'channel': 'color'},
                     'bounds': [0.5, 1.5], 'dye': {'space': 'srgb255', 'value': [120, 130, 140]},
                     'output': 'public/assets/interior/cloth.png'}
        self.recipe([operation])
        np.testing.assert_array_equal(self.output('cloth.png'), [[[120, 130, 140]]])
        path.write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            self.recipe([operation])
        source = self.image('public/assets/interior/original.png', [[[42, 42, 42]]])
        original = source.read_bytes()
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            self.recipe([{**operation, 'input': {'path': 'public/assets/interior/original.png'},
                          'output': 'public/assets/interior/original.png'}])
        self.assertEqual(source.read_bytes(), original)

    def test_woven_is_deterministic_metric_and_unit_normal(self):
        operation = {'id': 'rug', 'op': 'woven', 'resolution': 64, 'yarns': 8,
                     'tileMetres': 0.36, 'seed': 42, 'dye': {'space': 'srgb255', 'value': [195, 188, 167]},
                     'outputs': {key: f'public/assets/interior/rug-{key}.png'
                                 for key in ('basecolor', 'normal', 'roughness')}}
        first = self.recipe([operation])
        arrays, metrics = surfaces.woven(operation, np)
        normal = arrays['normal'] * 2 - 1
        np.testing.assert_allclose(np.linalg.norm(normal, axis=-1), 1, atol=1e-6)
        self.assertLess(metrics['maximumNormalLengthError'], 1e-6)
        self.assertGreater(float(normal[..., 0].std()), 0)
        self.assertTrue(np.all(normal[..., 2] > 0))
        second = self.recipe([operation])
        self.assertEqual(first['operations'][0]['outputs'], second['operations'][0]['outputs'])
        larger, _ = surfaces.woven({**operation, 'tileMetres': 0.72}, np)
        larger_normal = larger['normal'] * 2 - 1
        np.testing.assert_allclose(larger_normal[..., :2] / larger_normal[..., 2:],
                                   normal[..., :2] / normal[..., 2:] / 2, atol=1e-6)
        different, _ = surfaces.woven({**operation, 'seed': 43}, np)
        self.assertFalse(np.array_equal(arrays['basecolor'], different['basecolor']))
        np.testing.assert_array_equal(arrays['normal'], different['normal'])
        smooth, _ = surfaces.woven({**operation, 'rippleHeight': 0}, np)
        smooth_normal = smooth['normal'] * 2 - 1
        # At the rising left/top flank of the first crossing, +U slopes up and
        # downward image rows slope up: OpenGL requires negative X, positive Y.
        self.assertLess(smooth_normal[2, 2, 0], 0)
        self.assertGreater(smooth_normal[2, 2, 1], 0)

    def test_blur_strength_and_exponent_control_real_scan_variation(self):
        checker = np.indices((16, 16)).sum(axis=0) % 2
        self.image('scan.png', np.repeat((checker * 100 + 100)[..., None], 3, axis=2))
        base = {'id': 'original', 'op': 'dye', 'input': {'path': 'scan.png'},
                'dye': {'space': 'srgb255', 'value': [160, 140, 120]},
                'bounds': [0.1, 3], 'output': 'public/assets/interior/original.png'}
        self.recipe([base,
                     {**base, 'id': 'blur', 'blur': 2, 'output': 'public/assets/interior/blur.png'},
                     {**base, 'id': 'weak', 'strength': 0, 'output': 'public/assets/interior/weak.png'},
                     {**base, 'id': 'power', 'exponent': 0.6, 'output': 'public/assets/interior/power.png'}])
        self.assertLess(self.output('blur.png')[..., 0].std(), self.output('original.png')[..., 0].std())
        np.testing.assert_array_equal(self.output('weak.png')[0, 0], [160, 140, 120])
        self.assertEqual(float(self.output('weak.png')[..., 0].std()), 0)
        self.assertLess(self.output('power.png')[..., 0].std(), self.output('original.png')[..., 0].std())

    def test_zero_median_and_duplicate_outputs_fail_instead_of_nan_or_overwrite(self):
        self.image('black.png', [[[0, 0, 0]]])
        operation = {'id': 'black', 'op': 'dye', 'input': {'path': 'black.png'},
                     'bounds': [0.5, 1.5], 'dye': {'space': 'linear', 'value': [0.3, 0.3, 0.3]},
                     'output': 'public/assets/interior/black.png'}
        with self.assertRaisesRegex(ValueError, 'zero median'):
            self.recipe([operation])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.recipe([operation, {**operation, 'id': 'other'}])
        self.assertFalse((self.workspace / 'public/assets/interior/black.png').exists())


if __name__ == '__main__':
    unittest.main()
