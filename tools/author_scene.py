#!/usr/bin/env python3
"""Run explicit native production stages with a compatible bpy Python interpreter."""
from argparse import ArgumentParser
from pathlib import Path
import sys
import uuid

# Installed library search path only; authoring/output roots come from --workspace.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from authoring import context_from_args, bound_module


def parser():
    p = ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=['draft', 'bake', 'probe', 'export', 'render', 'refresh-material', 'calibrate', 'material-regression'])
    p.add_argument('--workspace', required=True)
    p.add_argument('--spec', default='scene-spec.json')
    p.add_argument('--run-id', default=uuid.uuid4().hex)
    p.add_argument('--width', type=int, default=1280)
    p.add_argument('--samples', type=int, default=64)
    p.add_argument('--resolution', type=int, default=2048)
    p.add_argument('--atlas')
    p.add_argument('--view', default='source')
    p.add_argument('--image', action='append', default=[], help='W-relative image to refresh in packed master; repeatable')
    return p


def main():
    args = parser().parse_args()
    if min(args.width, args.samples, args.resolution) < 1:
        raise ValueError('width, samples and resolution must be positive')
    context = context_from_args(args)
    if args.view != 'source' and args.view not in context.spec['authoring']['inspectionViews']:
        raise ValueError('Unknown inspection view')
    marker = context.evidence / (args.stage + '-' + (args.atlas or args.view) + '.started')
    with marker.open('x') as stream:
        stream.write('This stage owns its evidence paths; use a new run-id for revisions.\n')
    if args.stage in ('calibrate', 'material-regression'):
        from authoring.regression import calibrate, material_regression
        result = (calibrate if args.stage == 'calibrate' else material_regression)(context, args)
        import json
        print(json.dumps(result), flush=True)
    else:
        module = bound_module('pipeline', context)
        getattr(module, 'stage_' + args.stage.replace('-', '_'))(args)


if __name__ == '__main__':
    main()
