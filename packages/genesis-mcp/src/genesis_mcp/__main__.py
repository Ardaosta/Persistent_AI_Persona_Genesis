"""Entry point so a client can launch this with `python -m genesis_mcp`.

Invoking by module rather than by console script is deliberate: it works from a
bare Python install with the packages on PYTHONPATH, with no pip install and no
entry-point shim, which is the difference between "a companion installs this itself in
five minutes" and "someone has to fix a PATH on its person's laptop first."
"""

import sys

from genesis_mcp.server import main

if __name__ == "__main__":
    sys.exit(main())
