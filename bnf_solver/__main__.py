"""Allow ``python -m bnf_solver``."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
