"""An Earley parser for arbitrary context-free (BNF) grammars.

Earley's algorithm is used because BNF grammars are context free but are not
necessarily LL(1) or even unambiguous: they may be left recursive, right
recursive, ambiguous, and contain epsilon productions. Earley handles all of
those without any grammar transformation.

The parser is *scannerless*: there is no separate tokenizer, so a terminal
matches a literal substring of the input at the current position. Positions are
therefore character offsets, and ``n`` below is ``len(text)``.

Complexity: O(n^3) worst case for ambiguous grammars, O(n^2) for unambiguous
ones, and linear for most practical grammars.

Nullable non-terminals get the Aycock & Horspool treatment: when the predictor
sees a nullable symbol it immediately also advances the item over it, which is
the standard fix for Earley's well-known epsilon bug.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple, Union

from .errors import GrammarError, SolverError
from .grammar import Grammar, NonTerminal, Production, Symbol, Terminal
from .tree import ParseTree

__all__ = ["EarleyParser", "ParseResult", "parse", "recognize", "parse_tree"]


class _Item:
    """An Earley item: ``production``, dot position, and origin chart index.

    ``back`` / ``child`` record *one* way the item was reached, which is all we
    need to rebuild a single parse tree. They are written once, at creation
    time, and always point at items created earlier — so following them can
    never loop, even for infinitely ambiguous grammars.
    """

    __slots__ = ("production", "dot", "origin", "back", "child")

    def __init__(
        self,
        production: Production,
        dot: int,
        origin: int,
        back: Optional["_Item"] = None,
        child: Optional[Union["_Item", ParseTree]] = None,
    ) -> None:
        self.production = production
        self.dot = dot
        self.origin = origin
        self.back = back
        self.child = child

    @property
    def next_symbol(self) -> Optional[Symbol]:
        symbols = self.production.symbols
        return symbols[self.dot] if self.dot < len(symbols) else None

    @property
    def is_complete(self) -> bool:
        return self.dot >= len(self.production.symbols)

    @property
    def key(self) -> Tuple[Production, int, int]:
        return (self.production, self.dot, self.origin)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        symbols = [str(sym) for sym in self.production.symbols]
        symbols.insert(self.dot, "*")
        return "{} ::= {} ({})".format(self.production.head, " ".join(symbols), self.origin)


class _Chart:
    """The item set for one input position, with a dedup index."""

    __slots__ = ("items", "_seen", "_expecting")

    def __init__(self) -> None:
        self.items: List[_Item] = []
        self._seen: Dict[Tuple[Production, int, int], _Item] = {}
        self._expecting: Dict[NonTerminal, List[_Item]] = {}

    def add(self, item: _Item) -> bool:
        """Add ``item`` unless an equivalent one is present. True if added."""
        key = item.key
        if key in self._seen:
            return False
        self._seen[key] = item
        self.items.append(item)
        nxt = item.next_symbol
        if isinstance(nxt, NonTerminal):
            self._expecting.setdefault(nxt, []).append(item)
        return True

    def expecting(self, nonterminal: NonTerminal) -> List[_Item]:
        """Items whose dot sits before ``nonterminal`` (live list, may grow)."""
        return self._expecting.setdefault(nonterminal, [])

    def __len__(self) -> int:
        return len(self.items)


@dataclass(frozen=True)
class ParseResult:
    """The outcome of one parse attempt."""

    recognized: bool
    start: NonTerminal
    text: str
    tree: Optional[ParseTree] = None
    furthest_position: int = 0

    def __bool__(self) -> bool:
        return self.recognized

    def __str__(self) -> str:  # pragma: no cover - convenience
        state = "derivable" if self.recognized else "not derivable"
        return "{!r} is {} from {}".format(self.text, state, self.start)


class EarleyParser:
    """Parses input strings against a :class:`Grammar`.

    Instances cache grammar-derived tables, so reuse one parser when checking
    many strings against the same grammar.
    """

    def __init__(self, grammar: Grammar):
        self.grammar = grammar
        self._productions: Dict[NonTerminal, Tuple[Production, ...]] = {
            nt: grammar.productions_for(nt) for nt in grammar.nonterminals
        }
        self._null_trees: Dict[NonTerminal, ParseTree] = _compute_nullable(grammar)

    @property
    def nullable(self) -> Tuple[NonTerminal, ...]:
        """Non-terminals that can derive the empty string."""
        return tuple(self._null_trees)

    # ------------------------------------------------------------------ API

    def parse(
        self, text: str, start: Optional[Union[str, NonTerminal]] = None
    ) -> ParseResult:
        """Parse ``text``; the result carries a parse tree when it succeeds."""
        start_symbol = self._resolve_start(start)
        charts = self._build_charts(text, start_symbol)
        furthest = max(i for i, chart in enumerate(charts) if chart.items) if charts else 0

        final = None
        for item in charts[len(text)].items:
            if (
                item.origin == 0
                and item.is_complete
                and item.production.head == start_symbol
            ):
                final = item
                break
        if final is None:
            return ParseResult(False, start_symbol, text, None, furthest)
        return ParseResult(True, start_symbol, text, _tree_from_item(final), furthest)

    def recognize(
        self, text: str, start: Optional[Union[str, NonTerminal]] = None
    ) -> bool:
        """True when ``text`` is derivable from ``start``."""
        return self.parse(text, start).recognized

    def parse_tree(
        self, text: str, start: Optional[Union[str, NonTerminal]] = None
    ) -> Optional[ParseTree]:
        """A parse tree for ``text``, or ``None`` when it is not derivable."""
        return self.parse(text, start).tree

    # -------------------------------------------------------------- internals

    def _resolve_start(self, start: Optional[Union[str, NonTerminal]]) -> NonTerminal:
        try:
            if start is None:
                return self.grammar.start
            return self.grammar.resolve(start)
        except GrammarError as exc:
            raise SolverError(str(exc))

    def _build_charts(self, text: str, start_symbol: NonTerminal) -> List[_Chart]:
        n = len(text)
        charts = [_Chart() for _ in range(n + 1)]
        for production in self._productions.get(start_symbol, ()):
            charts[0].add(_Item(production, 0, 0))

        for i, chart in enumerate(charts):
            index = 0
            while index < len(chart.items):
                item = chart.items[index]
                index += 1
                symbol = item.next_symbol

                if symbol is None:
                    # COMPLETER: advance every item waiting on this head.
                    waiting = charts[item.origin].expecting(item.production.head)
                    j = 0
                    while j < len(waiting):
                        parent = waiting[j]
                        j += 1
                        chart.add(
                            _Item(
                                parent.production,
                                parent.dot + 1,
                                parent.origin,
                                parent,
                                item,
                            )
                        )
                elif isinstance(symbol, NonTerminal):
                    # PREDICTOR: open every alternative of the expected symbol.
                    for production in self._productions.get(symbol, ()):
                        chart.add(_Item(production, 0, i))
                    null_tree = self._null_trees.get(symbol)
                    if null_tree is not None:
                        # Aycock & Horspool: also step over a nullable symbol.
                        chart.add(
                            _Item(
                                item.production,
                                item.dot + 1,
                                item.origin,
                                item,
                                null_tree,
                            )
                        )
                else:
                    # SCANNER: match a literal substring of the input.
                    literal = symbol.text
                    if not literal:
                        chart.add(
                            _Item(
                                item.production,
                                item.dot + 1,
                                item.origin,
                                item,
                                ParseTree(symbol),
                            )
                        )
                    elif text.startswith(literal, i):
                        charts[i + len(literal)].add(
                            _Item(
                                item.production,
                                item.dot + 1,
                                item.origin,
                                item,
                                ParseTree(symbol),
                            )
                        )
        return charts


def _compute_nullable(grammar: Grammar) -> Dict[NonTerminal, ParseTree]:
    """Map each nullable non-terminal to one empty derivation of it."""
    null_trees: Dict[NonTerminal, ParseTree] = {}
    productions = list(grammar.productions())
    changed = True
    while changed:
        changed = False
        for production in productions:
            if production.head in null_trees:
                continue
            children: List[ParseTree] = []
            derives_empty = True
            for symbol in production.symbols:
                if isinstance(symbol, Terminal):
                    if symbol.text:
                        derives_empty = False
                        break
                    children.append(ParseTree(symbol))
                else:
                    subtree = null_trees.get(symbol)
                    if subtree is None:
                        derives_empty = False
                        break
                    children.append(subtree)
            if derives_empty:
                null_trees[production.head] = ParseTree(production.head, tuple(children))
                changed = True
    return null_trees


def _tree_from_item(item: _Item) -> ParseTree:
    """Rebuild a parse tree by walking an item's recorded derivation."""
    children: List[ParseTree] = []
    cursor: Optional[_Item] = item
    while cursor is not None and cursor.dot > 0:
        child = cursor.child
        if isinstance(child, ParseTree):
            children.append(child)
        elif isinstance(child, _Item):
            children.append(_tree_from_item(child))
        cursor = cursor.back
    children.reverse()
    return ParseTree(item.production.head, tuple(children))


# ------------------------------------------------------------- module helpers


def parse(
    grammar: Grammar, text: str, start: Optional[Union[str, NonTerminal]] = None
) -> ParseResult:
    """Convenience wrapper: parse ``text`` against ``grammar``."""
    return EarleyParser(grammar).parse(text, start)


def recognize(
    grammar: Grammar, text: str, start: Optional[Union[str, NonTerminal]] = None
) -> bool:
    """Convenience wrapper: is ``text`` derivable from ``grammar``?"""
    return EarleyParser(grammar).recognize(text, start)


def parse_tree(
    grammar: Grammar, text: str, start: Optional[Union[str, NonTerminal]] = None
) -> Optional[ParseTree]:
    """Convenience wrapper: a parse tree for ``text``, or ``None``."""
    return EarleyParser(grammar).parse_tree(text, start)
