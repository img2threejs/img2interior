import os, sys
root = os.environ.get("IMG2_HOME")
if root: sys.path.insert(0, os.path.join(root, "harness"))
else:
    try: import _img2_local; sys.path.insert(0, _img2_local.CORE)
    except ImportError: sys.exit("img2: core not linked - run `img2 sync`")
from img2_core import require_core_api
require_core_api(1)

import argparse
import json

from workflow_support import (DECISIONS, STAGES, Incomplete, Refusal, describe,
                              initialize, read_run, record, revise, workspace_path)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Refusal(message)


def parser():
    cli = Parser(description="Record explicit interior reviewer attestations, not automatic visual certification.")
    commands = cli.add_subparsers(dest="command", required=True)
    for name in ("init", "next", "record", "revise", "report"):
        command = commands.add_parser(name)
        command.add_argument("--workspace", required=True)
        if name == "init":
            command.add_argument("--image", required=True)
            command.add_argument("--intake", required=True)
        elif name == "record":
            command.add_argument("--stage", choices=STAGES, required=True)
            command.add_argument("--decision", choices=DECISIONS, required=True)
            command.add_argument("--reviewer", required=True)
            command.add_argument("--note", required=True)
            command.add_argument("--evidence", action="append", default=[], help="Repeat for each workspace evidence file; required for acceptance.")
        elif name == "revise":
            command.add_argument("--from", dest="from_stage", choices=STAGES, required=True)
            command.add_argument("--reason", required=True)
    return cli


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        workspace = workspace_path(args.workspace)
        if args.command == "init":
            run = initialize(workspace, args.image, args.intake)
        elif args.command == "record":
            run = record(workspace, args.stage, args.decision, args.reviewer, args.note, args.evidence)
        elif args.command == "revise":
            run = revise(workspace, args.from_stage, args.reason)
        else:
            run = read_run(workspace)
        result = describe(run, workspace)
        if args.command == "report":
            result["workflow"] = run
        code = 3 if args.command in ("next", "record") and result.get("explicitBlock") else 0
        if args.command == "record" and args.decision == "reject":
            code = 1
    except Incomplete as exc:
        result, code = {"status": "fail", "reasons": [str(exc)]}, 1
    except (OSError, ValueError, RuntimeError) as exc:
        result, code = {"status": "error", "reasons": [str(exc)]}, 2
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
