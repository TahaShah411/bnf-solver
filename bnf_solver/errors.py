"""Exception hierarchy for :mod:`bnf_solver`.

Every error raised by this package derives from :class:`BNFError`, so callers
that do not care about the distinction can catch a single type.
"""

from __future__ import annotations

from typing import Optional

__all__ = ["BNFError", "BNFSyntaxError", "GrammarError", "SolverError"]


class BNFError(Exception):
    """Base class for all errors raised by :mod:`bnf_solver`."""


class BNFSyntaxError(BNFError):
    """Raised when a BNF grammar definition cannot be tokenised or parsed.

    Carries the position of the offending token so that the message can point
    at the problem the way a compiler would.
    """

    def __init__(self, message: str, line: Optional[int] = None, column: Optional[int] = None):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(str(self))

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        if self.line is None:
            return self.message
        return "line {}, column {}: {}".format(self.line, self.column, self.message)


class GrammarError(BNFError):
    """Raised when a grammar is syntactically fine but semantically broken.

    For example: a rule references a non-terminal that nothing defines, or a
    start symbol is requested that the grammar does not declare.
    """


class SolverError(BNFError):
    """Raised when a parse request itself is invalid (bad start symbol, ...)."""
