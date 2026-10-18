"""Search, inspect and acquire CC0 assets into an explicit authoring workspace."""
import argparse
import json
from pathlib import Path
import sys

# Installed library search path only; acquisitions are confined to --workspace.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from resources_lib.polyhaven import CREDIT, Client, describe, fetch, save_query, search


def main(argv=None):
    cli = argparse.ArgumentParser(description='Powered by Poly Haven — CC0 assets; live API terms apply separately.')
    commands = cli.add_subparsers(dest='command', required=True)
    for name in ('search', 'info', 'files', 'fetch'):
        command = commands.add_parser(name)
        command.add_argument('--workspace', required=True)
        if name == 'search':
            command.add_argument('--type', choices=('textures', 'models', 'hdris'), required=True)
            command.add_argument('--query', required=True)
            command.add_argument('--limit', type=int, default=10)
        elif name == 'fetch':
            command.add_argument('--selection', required=True, help='Workspace-relative selection JSON')
        else:
            command.add_argument('--id', required=True)
    args = cli.parse_args(argv)
    print(CREDIT, file=sys.stderr)
    try:
        workspace = Path(args.workspace).expanduser().resolve()
        if not workspace.is_dir():
            raise ValueError('Workspace must be an existing authored directory')
        client = Client()
        if args.command == 'fetch':
            result = fetch(workspace, args.selection, client)
        elif args.command == 'search':
            result = save_query(workspace, 'search', {'type': args.type, 'query': args.query, 'limit': args.limit},
                                search(client, args.type, args.query, args.limit))
        else:
            result = save_query(workspace, args.command, {'id': args.id}, describe(client, args.command, args.id))
        code = 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        result, code = {'status': 'error', 'reason': str(exc), 'credit': CREDIT}, 2
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return code


if __name__ == '__main__':
    sys.exit(main())
