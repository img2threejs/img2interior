"""Project safety and consumer-facing provenance boundaries; no network or Blender."""
import base64
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent.parent / 'tools'
sys.path.insert(0, str(TOOLS))
import project_support as production

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=')


class ProjectBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='interior project boundaries ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / 'project with spaces'
        self.workspace.mkdir()
        self.image = self.root / 'supplied.png'
        self.image.write_bytes(PNG)

    def start(self):
        return production.start(self.workspace, self.image, 'photo', 'User supplied for local study', [])

    def test_initialized_project_cannot_be_reset_with_a_new_reference(self):
        self.start()
        receipt = self.workspace / production.ARTIFACTS / 'project.json'
        before = production.digest(receipt)
        self.image.write_bytes(PNG + b'a different supplied file')
        with self.assertRaisesRegex(ValueError, 'already initialized'):
            self.start()
        self.assertEqual(production.digest(receipt), before)

    def test_changed_pinned_reference_is_not_silently_repinned(self):
        self.start()
        (self.workspace / 'public/assets/reference.png').write_bytes(PNG + b'tampered')
        with self.assertRaisesRegex(ValueError, 'reference changed'):
            production.project(self.workspace)

    def test_other_image_never_uses_the_oak_room_as_a_fallback(self):
        self.start()
        with self.assertRaisesRegex(ValueError, 'exact authorized source'):
            production.use_recipe(self.workspace, 'oak-linen')
        self.assertFalse((self.workspace / 'scene-spec.json').exists())

    def test_symlinked_public_directory_cannot_redirect_reference_write(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.workspace / 'public').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'escapes'):
            self.start()
        self.assertEqual(list(outside.iterdir()), [])

    def test_installed_plugin_is_never_an_authoring_workspace(self):
        with self.assertRaisesRegex(ValueError, 'installed plugin'):
            production.workspace_path(production.PLUGIN / 'nested workspace')

    def test_frozen_evidence_tampering_is_detected_without_replacing_it(self):
        original = self.workspace / 'observed.json'
        original.write_text('{"measurement": 7.636}', encoding='utf-8')
        frozen = production.snapshot(self.workspace, 'observed.json', 'round-01', 'contact')
        path = self.workspace / frozen['path']
        path.write_text('{"measurement": 0}', encoding='utf-8')
        changed = production.digest(path)
        with self.assertRaisesRegex(ValueError, 'does not match'):
            production.snapshot(self.workspace, 'observed.json', 'round-01', 'contact')
        self.assertEqual(production.digest(path), changed)

    def test_snapshot_cannot_read_external_files_or_escape_its_run(self):
        self.image.write_bytes(PNG)
        for path, run in [('../supplied.png', 'round'), ('supplied.png', '../outside')]:
            with self.subTest(path=path, run=run), self.assertRaises(ValueError):
                production.snapshot(self.workspace, path, run, 'image')

    def test_template_upgrade_preserves_user_edits_without_partial_updates(self):
        package = self.root / 'package'
        template = package / 'runtime/viewer'
        (template / 'src').mkdir(parents=True)
        (template / 'package.json').write_text('{"private":true}', encoding='utf-8')
        (template / 'src/app.js').write_text('export const version = 1;', encoding='utf-8')
        with patch.object(production, 'PLUGIN', package):
            production.install_template(self.workspace, template, 'viewer-install.json')
            (self.workspace / 'package.json').write_text('{"private":true,"user":"edited"}', encoding='utf-8')
            (template / 'src/app.js').write_text('export const version = 2;', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'unowned/edited'):
                production.install_template(self.workspace, template, 'viewer-install.json')
            self.assertEqual((self.workspace / 'src/app.js').read_text(), 'export const version = 1;')
            self.assertIn('edited', (self.workspace / 'package.json').read_text())

    def test_unambiguous_finite_project_json_is_required(self):
        path = self.workspace / 'scene-spec.json'
        for value in ['{"lens":50,"lens":10}', '{"lens":NaN}', '{"lens":1e999}']:
            with self.subTest(value=value):
                path.write_text(value, encoding='utf-8')
                with self.assertRaises(ValueError):
                    production.read_json(path)

    def delivery_inputs(self):
        self.start()
        directory = self.workspace / 'public/assets/interior'
        directory.mkdir()
        # This tool inventories bytes, not consumer validity; reopening is a separate gate.
        for name in ('runtime.glb', 'portable.glb', 'master.blend', 'shared.exr'):
            (directory / name).write_bytes(('inventory fixture: ' + name).encode())
        spec = {'sourceViewLimit': 'Unseen depth is authored, not measured.',
                'portability': 'Static color only; no runtime interaction.'}
        (self.workspace / 'scene-spec.json').write_text(json.dumps(spec), encoding='utf-8')
        manifest = {'sourceImage': '/assets/reference.png', 'model': '/assets/interior/runtime.glb',
                    'portableModel': '/assets/interior/portable.glb', 'blender': '/assets/interior/master.blend',
                    'environment': '/assets/interior/shared.exr', 'background': '/assets/interior/shared.exr'}
        return directory, manifest

    def test_shared_environment_dependency_has_one_contract_identity(self):
        directory, manifest = self.delivery_inputs()
        (directory / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        production.delivery_contract(self.workspace, 'scene-spec.json')
        contract = production.read_json(self.workspace / production.ARTIFACTS / 'delivery-contract.json')
        dependencies = contract['runtime']['sidecars']
        self.assertEqual(dependencies, ['manifest', 'environment'])
        paths = [asset['path'] for asset in contract['assets']]
        self.assertEqual(len(paths), len(set(paths)))

    def test_delivery_rejects_external_or_traversing_manifest_dependencies(self):
        directory, manifest = self.delivery_inputs()
        for url in ['https://example.com/private.exr', '/assets/%2e%2e/private.exr', '/assets/interior/shared.exr?hidden=1']:
            with self.subTest(url=url):
                manifest['environment'] = url
                (directory / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'local /assets/'):
                    production.delivery_contract(self.workspace, 'scene-spec.json')
        self.assertFalse((self.workspace / production.ARTIFACTS / 'delivery-contract.json').exists())

    @unittest.skipUnless(importlib.util.find_spec('PIL'), 'Pillow is an optional production image dependency')
    def test_oriented_jpeg_reports_display_aspect_for_camera_planning(self):
        from PIL import Image
        image = Image.new('RGB', (16, 9), '#d2ceca')
        exif = image.getexif()
        exif[274] = 6
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', exif=exif)
        geometry = production.image_geometry(buffer.getvalue())
        self.assertEqual(geometry['sourceImageSize'], [9, 16])
        self.assertEqual(geometry['encodedSize'], [16, 9])


if __name__ == '__main__':
    unittest.main()
