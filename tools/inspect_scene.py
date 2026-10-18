#!/usr/bin/env python3
"""Independently reopen and render a packed master or portable GLB."""
from argparse import ArgumentParser
from pathlib import Path
import sys
import uuid
# Installed library search path only; consumer/output roots come from --workspace.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from authoring import context_from_args, bound_module


def main():
    p = ArgumentParser(description=__doc__)
    p.add_argument('asset', choices=['master', 'portable'])
    p.add_argument('--workspace', required=True)
    p.add_argument('--spec', default='scene-spec.json')
    p.add_argument('--run-id', default=uuid.uuid4().hex)
    p.add_argument('--width', type=int, default=1280)
    p.add_argument('--samples', type=int, default=64)
    p.add_argument('--view', default='source')
    args = p.parse_args()
    if min(args.width, args.samples) <= 0:
        raise ValueError('width and samples must be positive')
    context = context_from_args(args)
    if args.view != 'source' and args.view not in context.spec['authoring']['inspectionViews']:
        raise ValueError('Unknown inspection view')
    with (context.evidence / f'inspect-{args.asset}-{args.view}.started').open('x') as stream:
        stream.write('Independent native consumer invocation\n')
    bound_module('inspection', context).run(args)


if __name__ == '__main__':
    main()
