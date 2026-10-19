# SPDX-License-Identifier: Apache-2.0
"""Stdlib context tests; opt-in real bpy regressions via IMG2_BLENDER_PYTHON."""
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from authoring import Context, context_from_args


def reference_png(path):
    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind+payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 4,3,8,2,0,0,0))
                     + chunk(b'IDAT', zlib.compress((b'\x00'+b'\x80\x90\xa0'*4)*3)) + chunk(b'IEND',b''))


class ContextTests(unittest.TestCase):
    def test_confines_absolute_traversal_and_symlink(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            workspace = Path(root).resolve()
            context = Context(workspace, {}, workspace/'assets', workspace/'evidence')
            self.assertEqual(context.resolve('input.png'), workspace/'input.png')
            for path in ('../escape', '/tmp/escape'):
                with self.assertRaises(ValueError):
                    context.resolve(path)
            (workspace/'link').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                context.resolve('link/escape')

    def test_rejects_installed_plugin_workspaces_and_symlinks(self):
        for workspace in (ROOT, ROOT / 'examples' / 'not-a-workspace'):
            with self.assertRaisesRegex(ValueError, 'outside the installed plugin'):
                Context(workspace, {}, workspace/'assets', workspace/'evidence')
        args = SimpleNamespace(workspace=str(ROOT), spec='scene-spec.json', run_id='forbidden')
        with self.assertRaisesRegex(ValueError, 'outside the installed plugin'):
            context_from_args(args)
        parent = ROOT.parent.resolve()
        context = Context(parent, {}, parent/'assets', parent/'evidence')
        with self.assertRaisesRegex(ValueError, 'installed plugin'):
            context.resolve(ROOT.name + '/reference')
        with tempfile.TemporaryDirectory() as directory:
            link = Path(directory)/'installed'
            link.symlink_to(ROOT, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'outside the installed plugin'):
                Context(link, {}, link/'assets', link/'evidence')

    def test_import_is_inert_without_bpy(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-c',
                'import authoring; from pathlib import Path; assert not list(Path.cwd().iterdir())'],
                cwd=directory, env={**os.environ, 'PYTHONPATH':str(ROOT)}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_source_size_and_run_slug(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference_png(root/'public/assets/reference.png')
            spec = {'source':'public/assets/reference.png', 'authoring':{'sourceImageSize':[4,3]}}
            (root/'scene-spec.json').write_text(json.dumps(spec))
            args = SimpleNamespace(workspace=str(root), spec='scene-spec.json', run_id='first')
            args.run_id = '../escape'
            with self.assertRaises(ValueError):
                context_from_args(args)
            args.run_id = 'second'
            spec['authoring']['sourceImageSize'] = [4,0]
            (root/'scene-spec.json').write_text(json.dumps(spec))
            with self.assertRaises(ValueError):
                context_from_args(args)


@unittest.skipUnless(os.environ.get('IMG2_BLENDER_PYTHON'), 'Set IMG2_BLENDER_PYTHON for real native regressions')
class NativeRegressions(unittest.TestCase):
    def test_packed_pixels_sheen_and_asymmetric_uv1_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference_png(root/'public/assets/reference.png')
            spec = json.loads((ROOT/'examples/studio/scene-spec.json').read_text())
            spec['authoring']['sourceImageSize'] = [4,3]
            (root/'scene-spec.json').write_text(json.dumps(spec))
            for stage in ('material-regression', 'calibrate'):
                command = [os.environ['IMG2_BLENDER_PYTHON'], str(ROOT/'tools/author_scene.py'), stage,
                           '--workspace', str(root), '--run-id', stage, '--width','128','--samples','4']
                result = subprocess.run(command, capture_output=True, text=True, timeout=600)
                self.assertEqual(result.returncode, 0, result.stdout+'\n'+result.stderr)
                filename = 'calibration.json' if stage == 'calibrate' else 'material-regression.json'
                receipt = json.loads((root/'.img2/artifacts/interior/production'/stage/filename).read_text())
                if stage == 'material-regression':
                    self.assertLessEqual(receipt['packedAlbedoPixelError'], 1e-6)
                    self.assertIs(receipt['externalMapRemovedBeforeReopen'], True)
                    self.assertIs(receipt['uv0Preserved'], True)
                    self.assertIs(receipt['nativeSheenRestoredAfterSuccessAndFailure'], True)
                    self.assertEqual(len(receipt['actualGltfSheen']), 3)
                    for actual, expected in zip(receipt['actualGltfSheen'], [.096, .060, .030]):
                        self.assertAlmostEqual(actual, expected, delta=1e-6)
                else:
                    self.assertEqual(receipt['texCoord'], 1)
                    self.assertLessEqual(receipt['coordinateRoundTripMaxError'], 1e-5)
                    self.assertLessEqual(receipt['decodedPixelMeanError'], .01)
                    self.assertEqual(set(receipt['probeAxes']), {'positiveX','negativeX','positiveZ','negativeZ'})
                    for reading in receipt['probeAxes'].values():
                        self.assertLessEqual(reading['maxError'], .001)
                    runtime = receipt['runtimeLightmap']
                    self.assertLessEqual(runtime['decodedExrMaxError'], 1e-6)


if __name__ == '__main__':
    unittest.main()
