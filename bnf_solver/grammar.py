"""Data structures for BNF grammars.

The model is deliberately small:

* :class:`Terminal` and :class:`NonTerminal` are the two kinds of *symbol*.
* A :class:`Production` is one right-hand side: ``<head> ::= sym sym sym``.
* A :class:`Rule` groups every alternative declared for one head.
* A :class:`Grammar` is an ordered collection of rules plus lookup helpers.

All of these are immutable (frozen dataclasses / read-only views), which makes
them hashable and safe to share between parsers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple, Union

from .errors import GrammarError

__all__ = [
    "Terminal",
    "NonTerminal",
    "Symbol",
    "Production",
    "Rule",
    "Grammar",
    "quote_terminal",
]

_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\n": "\\n",
    "\t": "\\t",
    "\r": "\\r",
}

EPSILON = "ε"  # the Greek letter used to render an empty right-hand side


def quote_terminal(text: str) -> str:
    """Render ``text`` the way the BNF parser would accept it back."""
    return '"' + "".join(_ESCAPES.get(ch, ch) for ch in text) + '"'


@dataclass(frozen=True)
class Terminal:
    """A literal piece of input text, written ``"like this"`` in BNF."""

    text: str

    @property
    def is_terminal(self) -> bool:
        return True

    def __len__(self) -> int:
        return len(self.text)

    def __str__(self) -> str:
        return quote_terminal(self.text)


@dataclass(frozen=True)
class NonTerminal:
    """A grammar variable, written ``<like-this>`` in BNF."""

    name: str

    @property
    def is_terminal(self) -> bool:
        return False

    def __str__(self) -> str:
        return "<{}>".format(self.name)


Symbol = Union[Terminal, NonTerminal]


def _render_symbols(symbols: Sequence[Symbol]) -> str:
    if not symbols:
        return EPSILON
    return " ".join(str(sym) for sym in symbols)


@dataclass(frozen=True)
class Production:
    """One alternative of one rule: a head plus an ordered symbol sequence."""

    head: NonTerminal
    symbols: Tuple[Symbol, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.head, NonTerminal):
            raise TypeError("production head must be a NonTerminal, got {!r}".format(self.head))
        if not isinstance(self.symbols, tuple):
            object.__setattr__(self, "symbols", tuple(self.symbols))

    @property
    def is_epsilon(self) -> bool:
        """True when this production derives the empty string directly."""
        return len(self.symbols) == 0

    def __len__(self) -> int:
        return len(self.symbols)

    def __iter__(self) -> Iterator[Symbol]:
        return iter(self.symbols)

    def __str__(self) -> str:
        return "{} ::= {}".format(self.head, _render_symbols(self.symbols))


@dataclass(frozen=True)
class Rule:
    """Every alternative declared for a single head, in source order."""

    head: NonTerminal
    alternatives: Tuple[Tuple[Symbol, ...], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.head, NonTerminal):
            raise TypeError("rule head must be a NonTerminal, got {!r}".format(self.head))
        object.__setattr__(
            self, "alternatives", tuple(tuple(alt) for alt in self.alternatives)
        )

    @property
    def productions(self) -> Tuple[Production, ...]:
        return tuple(Production(self.head, alt) for alt in self.alternatives)

    def __len__(self) -> int:
        return len(self.alternatives)

    def __iter__(self) -> Iterator[Tuple[Symbol, ...]]:
        return iter(self.alternatives)

    def __str__(self) -> str:
        rhs = " | ".join(_render_symbols(alt) for alt in self.alternatives)
        return "{} ::= {}".format(self.head, rhs)


class Grammar:
    """An ordered set of rules with convenient lookups.

    Rules are keyed by head name; declaring the same head twice merges the
    alternatives (in declaration order) instead of shadowing the first rule.
    """

    def __init__(
        self,
        rules: Iterable[Rule],
        start: Optional[Union[str, NonTerminal]] = None,
    ) -> None:
        self._rules: Dict[str, Rule] = {}
        for rule in rules:
            if not isinstance(rule, Rule):
                raise TypeError("expected Rule instances, got {!r}".format(rule))
            existing = self._rules.get(rule.head.name)
            if existing is None:
                self._rules[rule.head.name] = rule
            else:
                self._rules[rule.head.name] = Rule(
                    existing.head, existing.alternatives + rule.alternatives
                )
        self._start: Optional[NonTerminal] = self.resolve(start) if start is not None else None

    # ------------------------------------------------------------------ views

    @property
    def rules(self) -> Tuple[Rule, ...]:
        return tuple(self._rules.values())

    @property
    def nonterminals(self) -> Tuple[NonTerminal, ...]:
        """Defined non-terminals, in declaration order."""
        return tuple(rule.head for rule in self._rules.values())

    @property
    def terminals(self) -> Tuple[Terminal, ...]:
        """Every distinct terminal used anywhere, sorted by text."""
        seen = {
            sym
            for rule in self._rules.values()
            for alt in rule.alternatives
            for sym in alt
            if isinstance(sym, Terminal)
        }
        return tuple(sorted(seen, key=lambda t: t.text))

    @property
    def start(self) -> NonTerminal:
        """The explicit start symbol, or the head of the first rule."""
        if self._start is not None:
            return self._start
        if not self._rules:
            raise GrammarError("grammar contains no rules")
        return next(iter(self._rules.values())).head

    def productions(self) -> Iterator[Production]:
        for rule in self._rules.values():
            for production in rule.productions:
                yield production

    def rule_for(self, symbol: Union[str, NonTerminal]) -> Rule:
        return self._rules[self.resolve(symbol).name]

    def productions_for(self, symbol: Union[str, NonTerminal]) -> Tuple[Production, ...]:
        """Alternatives for ``symbol``; an empty tuple if it is not defined."""
        name = symbol.name if isinstance(symbol, NonTerminal) else str(symbol)
        rule = self._rules.get(name)
        return rule.productions if rule is not None else ()

    # ------------------------------------------------------------- validation

    def resolve(self, symbol: Union[str, NonTerminal]) -> NonTerminal:
        """Turn ``"expr"``, ``"<expr>"`` or ``NonTerminal("expr")`` into a symbol.

        Raises :class:`GrammarError` if no rule defines it.
        """
        if isinstance(symbol, NonTerminal):
            name = symbol.name
        elif isinstance(symbol, str):
            name = symbol.strip()
            if len(name) >= 2 and name.startswith("<") and name.endswith(">"):
                name = name[1:-1].strip()
        else:
            raise TypeError("expected a str or NonTerminal, got {!r}".format(symbol))
        if name not in self._rules:
            known = ", ".join(str(nt) for nt in self.nonterminals) or "(none)"
            raise GrammarError(
                "no rule defines <{}>; defined non-terminals: {}".format(name, known)
            )
        return self._rules[name].head

    def undefined_nonterminals(self) -> Tuple[NonTerminal, ...]:
        """Non-terminals that are referenced but never given a rule."""
        missing: List[NonTerminal] = []
        seen = set()
        for rule in self._rules.values():
            for alt in rule.alternatives:
                for sym in alt:
                    if isinstance(sym, NonTerminal) and sym.name not in self._rules:
                        if sym.name not in seen:
                            seen.add(sym.name)
                            missing.append(sym)
        return tuple(missing)

    def validate(self) -> "Grammar":
        """Check the grammar is self-contained; return ``self`` for chaining."""
        if not self._rules:
            raise GrammarError("grammar contains no rules")
        missing = self.undefined_nonterminals()
        if missing:
            raise GrammarError(
                "undefined non-terminal(s): {}".format(
                    ", ".join(str(nt) for nt in missing)
                )
            )
        return self

    # ------------------------------------------------------------- rendering

    def to_bnf(self) -> str:
        """Render the grammar back to BNF text (round-trips through the parser)."""
        if not self._rules:
            return ""
        width = max(len(str(rule.head)) for rule in self._rules.values())
        lines = []
        for rule in self._rules.values():
            head = str(rule.head).ljust(width)
            rhs = " | ".join(_render_symbols(alt) for alt in rule.alternatives)
            lines.append("{} ::= {}".format(head, rhs))
        return "\n".join(lines)

    # ------------------------------------------------------------- dunders

    def __len__(self) -> int:
        return len(self._rules)

    def __iter__(self) -> Iterator[Rule]:
        return iter(self._rules.values())

    def __contains__(self, symbol: object) -> bool:
        if isinstance(symbol, NonTerminal):
            return symbol.name in self._rules
        if isinstance(symbol, str):
            name = symbol.strip()
            if len(name) >= 2 and name.startswith("<") and name.endswith(">"):
                name = name[1:-1].strip()
            return name in self._rules
        return False

    def __str__(self) -> str:
        return self.to_bnf()

    def __repr__(self) -> str:
        return "Grammar({} rules, start={})".format(
            len(self._rules), self._start or "auto"
        )
