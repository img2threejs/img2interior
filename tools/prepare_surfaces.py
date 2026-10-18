"""Execute an authored surface recipe without changing its source images."""
import argparse
import json
from pathlib import Path
import sys

# Installed library search path only; derivatives are confined to --workspace.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from resources_lib.surfaces import prepare


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--workspace', required=True)
    cli.add_argument('--recipe', required=True, help='Workspace-relative schemaVersion 1 recipe JSON')
    args = cli.parse_args(argv)
    try:
        workspace = Path(args.workspace).expanduser().resolve()
        if not workspace.is_dir():
            raise ValueError('Workspace must be an existing authored directory')
        result, code = prepare(workspace, args.recipe), 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        result, code = {'status': 'error', 'reason': str(exc)}, 2
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return code


if __name__ == '__main__':
    sys.exit(main())
