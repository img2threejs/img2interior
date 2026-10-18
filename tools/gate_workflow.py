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

from workflow_support import ATTESTATION, Refusal, evaluate_gate, workspace_path


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Refusal(message)


def main(argv=None):
    evidence = {"attestation": ATTESTATION}
    try:
        parser = Parser(description="Check ordered interior attestations and current file hashes; never grade visual quality.")
        parser.add_argument("--workspace", required=True)
        args = parser.parse_args(argv)
        reasons, evidence = evaluate_gate(workspace_path(args.workspace))
        status = "fail" if reasons else "pass"
    except (OSError, ValueError, RuntimeError) as exc:
        status, reasons = "error", [str(exc)]
    print(json.dumps({"kind": "img2.gate-verdict", "version": 1, "gate": "interior-workflow",
                      "plugin": "interior", "status": status, "reasons": reasons, "evidence": evidence},
                     indent=2, sort_keys=True, allow_nan=False))
    return {"pass": 0, "fail": 1, "error": 2}[status]


if __name__ == "__main__":
    sys.exit(main())
