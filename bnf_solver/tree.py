"""Parse trees and their renderings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, List, Sequence, Tuple

from .grammar import NonTerminal, Symbol, Terminal

__all__ = ["ParseTree"]

_UNICODE_GLYPHS = ("├── ", "└── ", "│   ", "    ")
_ASCII_GLYPHS = ("|-- ", "`-- ", "|   ", "    ")


@dataclass(frozen=True)
class ParseTree:
    """A node in a derivation.

    Terminal nodes are always leaves. A non-terminal leaf means the symbol
    derived the empty string (via an epsilon production).
    """

    symbol: Symbol
    children: Tuple["ParseTree", ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.children, tuple):
            object.__setattr__(self, "children", tuple(self.children))
        if isinstance(self.symbol, Terminal) and self.children:
            raise ValueError("terminal nodes cannot have children")

    # ------------------------------------------------------------- properties

    @property
    def is_leaf(self) -> bool:
        return not self.children

    @property
    def is_terminal(self) -> bool:
        return isinstance(self.symbol, Terminal)

    @property
    def label(self) -> str:
        """How this node is shown in a rendering."""
        if isinstance(self.symbol, Terminal):
            return str(self.symbol)
        if not self.children:
            return "{} (empty)".format(self.symbol)
        return str(self.symbol)

    @property
    def text(self) -> str:
        """The input substring this subtree derives."""
        if isinstance(self.symbol, Terminal):
            return self.symbol.text
        return "".join(child.text for child in self.children)

    @property
    def height(self) -> int:
        """1 for a leaf, otherwise 1 + the tallest child."""
        if not self.children:
            return 1
        return 1 + max(child.height for child in self.children)

    # ------------------------------------------------------------- traversal

    def walk(self) -> Iterator["ParseTree"]:
        """Pre-order traversal of every node, starting with ``self``."""
        yield self
        for child in self.children:
            for node in child.walk():
                yield node

    def leaves(self) -> Iterator["ParseTree"]:
        for node in self.walk():
            if node.is_leaf:
                yield node

    def terminals(self) -> Iterator[Terminal]:
        for node in self.walk():
            if isinstance(node.symbol, Terminal):
                yield node.symbol

    def __len__(self) -> int:
        return sum(1 for _ in self.walk())

    # ------------------------------------------------------------- rendering

    def pretty(self, ascii_only: bool = False) -> str:
        """Render as a box-drawing tree (the CLI default)."""
        glyphs = _ASCII_GLYPHS if ascii_only else _UNICODE_GLYPHS
        lines: List[str] = []
        self._render(lines, "", True, True, glyphs)
        return "\n".join(lines)

    def _render(
        self,
        lines: List[str],
        prefix: str,
        is_last: bool,
        is_root: bool,
        glyphs: Sequence[str],
    ) -> None:
        tee, last, bar, space = glyphs
        if is_root:
            lines.append(self.label)
            child_prefix = ""
        else:
            lines.append(prefix + (last if is_last else tee) + self.label)
            child_prefix = prefix + (space if is_last else bar)
        for index, child in enumerate(self.children):
            child._render(
                lines, child_prefix, index == len(self.children) - 1, False, glyphs
            )

    def to_indented(self, indent: str = "  ") -> str:
        """Render one node per line, nesting shown by plain indentation."""
        lines: List[str] = []

        def visit(node: "ParseTree", depth: int) -> None:
            lines.append(indent * depth + node.label)
            for child in node.children:
                visit(child, depth + 1)

        visit(self, 0)
        return "\n".join(lines)

    def to_bracketed(self) -> str:
        """Render in Lisp-ish bracketed notation, e.g. ``(expr (term "1"))``."""
        if isinstance(self.symbol, Terminal):
            return str(self.symbol)
        if not self.children:
            return "({})".format(self.symbol.name)
        inner = " ".join(child.to_bracketed() for child in self.children)
        return "({} {})".format(self.symbol.name, inner)

    def __str__(self) -> str:
        return self.pretty()
