"""Make the project root importable so ``import bnf_solver`` works uninstalled."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
