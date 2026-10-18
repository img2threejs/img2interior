#!/usr/bin/env python3
"""Create a labeled reference/render contact sheet for actual visual review, never a realism score."""
import argparse
import json
import math
from pathlib import Path
import re
import sys

from project_support import ARTIFACTS, confined, digest, project, workspace_path, write_json


def compare(workspace, renders, run_id, name, roi=None, width=640):
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', run_id):
        raise ValueError('run-id must be a plain slug, at most 64 characters')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', name):
        raise ValueError('name must be a plain slug, at most 64 characters')
    if not 128 <= width <= 1600 or not 1 <= len(renders) <= 7:
        raise ValueError('Use width 128..1600 and one to seven actual rendered images')
    if roi and not (all(math.isfinite(value) for value in roi) and 0 <= roi[0] < roi[2] <= 1 and 0 <= roi[1] < roi[3] <= 1):
        raise ValueError('ROI must be normalized left,top,right,bottom within 0..1')
    record = project(workspace)
    paths = [confined(workspace, record['source']['path'])] + [confined(workspace, value) for value in renders]
    output = confined(workspace, ARTIFACTS / 'production' / run_id / (name + '.png'))
    receipt = output.with_suffix('.json')
    if output.exists() or receipt.exists():
        raise ValueError('Comparison evidence already exists; choose a new run-id or name, never replace accepted captures')
    images, inputs = [], []
    for path in paths:
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            original_size = list(image.size)
            if roi:
                bounds = (math.floor(roi[0] * image.width), math.floor(roi[1] * image.height),
                          math.ceil(roi[2] * image.width), math.ceil(roi[3] * image.height))
                image = image.crop(bounds)
            rgba = image.convert('RGBA')
            canvas = Image.new('RGBA', rgba.size, '#f4f0e7')
            canvas.alpha_composite(rgba)
            preview = canvas.convert('RGB')
            preview.thumbnail((width, width), Image.Resampling.LANCZOS)
            images.append(preview)
            inputs.append({'path': path.relative_to(workspace).as_posix(), 'sha256': digest(path),
                           'decodedSize': original_size, 'normalizedROI': roi})
    cell_height = max(image.height for image in images) + 48
    columns = 2
    sheet = Image.new('RGB', (width * columns, cell_height * ((len(images) + columns - 1) // columns)), '#f4f0e7')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=16)
    for index, (image, path) in enumerate(zip(images, paths)):
        x, y = (index % columns) * width, (index // columns) * cell_height
        label = 'REFERENCE (' + record['source']['sourceKind'] + ')' if index == 0 else 'RENDER: ' + path.name
        draw.text((x + 12, y + 12), label, fill='#242321', font=font)
        sheet.paste(image, (x + (width - image.width) // 2, y + 44))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        sheet.save(stream, format='PNG')
    result = {'schemaVersion': 1, 'inputs': inputs, 'sheet': output.relative_to(workspace).as_posix(),
              'sha256': digest(output), 'purpose': 'Human/agent visual comparison; preserve each complete view without an automatic likeness grade',
              'visualAcceptanceEvaluated': False, 'pixelAlignmentAssumed': False}
    write_json(receipt, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--render', action='append', required=True, help='Workspace-relative actual render; repeat for multiple views')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--name', default='comparison')
    parser.add_argument('--roi', nargs=4, type=float, metavar=('LEFT', 'TOP', 'RIGHT', 'BOTTOM'))
    parser.add_argument('--width', type=int, default=640)
    args = parser.parse_args()
    try:
        result = compare(workspace_path(args.workspace), args.render, args.run_id, args.name, args.roi, args.width)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except ImportError as error:
        print('Install requirements-surfaces.txt in an isolated image-tools environment: ' + str(error), file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'status': 'error', 'error': str(error)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
