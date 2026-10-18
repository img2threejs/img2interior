#!/usr/bin/env python3
"""Run the installed harness gate runner with an explicit plugin directory."""
import os, sys
root = os.environ.get("IMG2_HOME")
if root: sys.path.insert(0, os.path.join(root, "harness"))
else:
    try: import _img2_local; sys.path.insert(0, _img2_local.CORE)
    except ImportError: sys.exit("img2: core not linked - run `img2 sync`")
from img2_core import require_core_api
require_core_api(1)
from img2_core.gate_runner import main

if __name__ == "__main__":
    sys.exit(main())
