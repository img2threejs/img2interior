#!/usr/bin/env python3
"""Create an image-led workspace and install real production templates, without accepting its quality."""
import argparse
import json
import sys

from project_support import (PLUGIN, SOURCE_KINDS, delivery_contract, install_template,
                             preflight, project, snapshot, start, use_recipe, workspace_path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('start', help='Pin and copy one supplied image; analysis remains agent work')
    create.add_argument('--workspace', required=True)
    create.add_argument('--image', required=True)
    create.add_argument('--source-kind', choices=SOURCE_KINDS, default='photo')
    create.add_argument('--authorization', default='User supplied reference for local reconstruction; publication rights are not established')
    create.add_argument('--reference-url', action='append', default=[])
    check = commands.add_parser('preflight', help='Probe actual executables without installing anything')
    check.add_argument('--workspace', required=True)
    check.add_argument('--blender-python')
    viewer = commands.add_parser('install-viewer', help='Install the production viewer without overwriting user edits')
    viewer.add_argument('--workspace', required=True)
    recipe = commands.add_parser('use-recipe', help='Explicitly reproduce a source-pinned case, not an arbitrary image')
    recipe.add_argument('--workspace', required=True)
    recipe.add_argument('--recipe', choices=('oak-linen',), required=True)
    delivery = commands.add_parser('delivery-contract', help='Hash actual manifest dependencies; does not certify consumer rendering')
    delivery.add_argument('--workspace', required=True)
    delivery.add_argument('--spec', default='scene-spec.json')
    capture = commands.add_parser('snapshot', help='Freeze a current workspace report/capture without overwriting accepted evidence')
    capture.add_argument('--workspace', required=True)
    capture.add_argument('--input', required=True)
    capture.add_argument('--run-id', required=True)
    capture.add_argument('--name', required=True)
    args = parser.parse_args(argv)
    try:
        workspace = workspace_path(args.workspace)
        if args.command == 'start':
            result = start(workspace, args.image, args.source_kind, args.authorization, args.reference_url)
        elif args.command == 'preflight':
            result = preflight(workspace, args.blender_python)
        elif args.command == 'install-viewer':
            project(workspace)
            result = install_template(workspace, PLUGIN / 'runtime/viewer', 'viewer-install.json')
            result['next'] = 'Run npm ci, npm run build and a loopback dev/preview server; inspect the actual browser'
        elif args.command == 'use-recipe':
            result = use_recipe(workspace, args.recipe)
        elif args.command == 'snapshot':
            result = snapshot(workspace, args.input, args.run_id, args.name)
        else:
            result = delivery_contract(workspace, args.spec)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 1 if result.get('status') == 'blocked' else 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'status': 'error', 'error': str(error)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
