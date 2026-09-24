"""Parse BNF grammar definitions (text) into :class:`~bnf_solver.grammar.Grammar`.

Supported syntax::

    # comments run to the end of the line
    <expr>   ::= <expr> "+" <term> | <term>
    <term>   ::= <term> "*" <factor> | <factor>
    <factor> ::= "(" <expr> ")" | <digit>
    <digit>  ::= "0" | "1"
    <maybe>  ::= ""            # the empty string (epsilon)

* Non-terminals are written ``<between-angle-brackets>``.
* Terminals are quoted with ``"`` or ``'`` and understand the escapes
  ``\\\\``, ``\\"``, ``\\'``, ``\\n``, ``\\t``, ``\\r``.
* ``::=`` separates head from body, ``|`` separates alternatives.
* A sequence is whitespace separated; a rule may span several lines because a
  new rule only begins at ``<head> ::=``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple, Union

from .errors import BNFSyntaxError, GrammarError
from .grammar import Grammar, NonTerminal, Production, Rule, Symbol, Terminal

__all__ = ["parse_grammar", "parse_grammar_file", "tokenize", "Token"]

NONTERMINAL = "NONTERMINAL"
TERMINAL = "TERMINAL"
DEFINE = "DEFINE"
PIPE = "PIPE"
EOF_TOKEN = "EOF"

_QUOTES = "\"'"
_COMMENT = "#"
_ESCAPE_MAP = {"\\": "\\", '"': '"', "'": "'", "n": "\n", "t": "\t", "r": "\r", "0": "\0"}


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        return "{}({!r}) at {}:{}".format(self.kind, self.value, self.line, self.column)


def _describe(token: Token) -> str:
    if token.kind == EOF_TOKEN:
        return "end of input"
    if token.kind == NONTERMINAL:
        return "<{}>".format(token.value)
    if token.kind == TERMINAL:
        return '"{}"'.format(token.value)
    return "'{}'".format(token.value)


def tokenize(text: str) -> List[Token]:
    """Split BNF source into tokens. Raises :class:`BNFSyntaxError`."""
    tokens: List[Token] = []
    line = 1
    column = 1
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\n":
            line += 1
            column = 1
            i += 1
            continue
        if ch in " \t\r\f\v":
            i += 1
            column += 1
            continue
        if ch == _COMMENT:
            while i < n and text[i] != "\n":
                i += 1
            continue
        start_line, start_col = line, column
        if ch == "<":
            end = text.find(">", i + 1)
            newline = text.find("\n", i + 1)
            if end == -1 or (newline != -1 and newline < end):
                raise BNFSyntaxError("unterminated non-terminal (missing '>')", start_line, start_col)
            name = text[i + 1 : end].strip()
            if not name:
                raise BNFSyntaxError("empty non-terminal name '<>'", start_line, start_col)
            if "<" in name:
                raise BNFSyntaxError(
                    "'<' is not allowed inside a non-terminal name", start_line, start_col
                )
            tokens.append(Token(NONTERMINAL, name, start_line, start_col))
            column += (end + 1) - i
            i = end + 1
            continue
        if ch in _QUOTES:
            quote = ch
            i += 1
            column += 1
            chars: List[str] = []
            while True:
                if i >= n or text[i] == "\n":
                    raise BNFSyntaxError(
                        "unterminated terminal string (missing closing {})".format(quote),
                        start_line,
                        start_col,
                    )
                cur = text[i]
                if cur == "\\":
                    if i + 1 >= n or text[i + 1] == "\n":
                        raise BNFSyntaxError(
                            "dangling escape at end of terminal string", line, column
                        )
                    nxt = text[i + 1]
                    chars.append(_ESCAPE_MAP.get(nxt, nxt))
                    i += 2
                    column += 2
                    continue
                if cur == quote:
                    i += 1
                    column += 1
                    break
                chars.append(cur)
                i += 1
                column += 1
            tokens.append(Token(TERMINAL, "".join(chars), start_line, start_col))
            continue
        if text.startswith("::=", i):
            tokens.append(Token(DEFINE, "::=", start_line, start_col))
            i += 3
            column += 3
            continue
        if ch == "|":
            tokens.append(Token(PIPE, "|", start_line, start_col))
            i += 1
            column += 1
            continue
        raise BNFSyntaxError("unexpected character {!r}".format(ch), start_line, start_col)
    tokens.append(Token(EOF_TOKEN, "", line, column))
    return tokens


class _RuleParser:
    """Recursive-descent parser over the token stream produced by :func:`tokenize`."""

    def __init__(self, tokens: Sequence[Token]):
        self._tokens = tokens
        self._pos = 0

    @property
    def current(self) -> Token:
        return self._tokens[self._pos]

    def peek(self, offset: int = 1) -> Token:
        index = min(self._pos + offset, len(self._tokens) - 1)
        return self._tokens[index]

    def advance(self) -> Token:
        token = self._tokens[self._pos]
        if token.kind != EOF_TOKEN:
            self._pos += 1
        return token

    def at_rule_start(self) -> bool:
        return self.current.kind == NONTERMINAL and self.peek().kind == DEFINE

    def parse_rules(self) -> List[Rule]:
        rules: List[Rule] = []
        while self.current.kind != EOF_TOKEN:
            rules.append(self.parse_rule())
        return rules

    def parse_rule(self) -> Rule:
        head_token = self.current
        if head_token.kind != NONTERMINAL:
            raise BNFSyntaxError(
                "expected a non-terminal at the start of a rule, found {}".format(
                    _describe(head_token)
                ),
                head_token.line,
                head_token.column,
            )
        self.advance()
        define = self.current
        if define.kind != DEFINE:
            raise BNFSyntaxError(
                "expected '::=' after <{}>, found {}".format(head_token.value, _describe(define)),
                define.line,
                define.column,
            )
        self.advance()

        head = NonTerminal(head_token.value)
        alternatives: List[Tuple[Symbol, ...]] = []
        while True:
            alternatives.append(self.parse_alternative(head_token))
            if self.current.kind == PIPE:
                self.advance()
                continue
            break
        return Rule(head, tuple(alternatives))

    def parse_alternative(self, head_token: Token) -> Tuple[Symbol, ...]:
        start = self.current
        symbols: List[Symbol] = []
        count = 0
        while True:
            token = self.current
            if token.kind in (EOF_TOKEN, PIPE) or self.at_rule_start():
                break
            if token.kind == NONTERMINAL:
                symbols.append(NonTerminal(token.value))
            elif token.kind == TERMINAL:
                # An explicit "" is how the grammar spells epsilon; it adds
                # nothing to a sequence, so drop it here.
                if token.value != "":
                    symbols.append(Terminal(token.value))
            else:
                raise BNFSyntaxError(
                    "unexpected {} in the body of <{}>".format(
                        _describe(token), head_token.value
                    ),
                    token.line,
                    token.column,
                )
            count += 1
            self.advance()
        if count == 0:
            raise BNFSyntaxError(
                "empty alternative in <{}> (write \"\" for the empty string)".format(
                    head_token.value
                ),
                start.line,
                start.column,
            )
        return tuple(symbols)


def parse_grammar(
    text: str,
    start: Optional[Union[str, NonTerminal]] = None,
    validate: bool = True,
) -> Grammar:
    """Parse BNF source into a :class:`Grammar`.

    Args:
        text: the grammar definition.
        start: optional start symbol; defaults to the head of the first rule.
        validate: when true (default), reject grammars that reference
            non-terminals no rule defines.

    Raises:
        BNFSyntaxError: on malformed syntax.
        GrammarError: on an empty grammar, an unknown ``start``, or (when
            ``validate``) undefined non-terminals.
    """
    tokens = tokenize(text)
    rules = _RuleParser(tokens).parse_rules()
    if not rules:
        raise GrammarError("grammar contains no rules")
    grammar = Grammar(rules, start=start)
    if validate:
        grammar.validate()
    return grammar


def parse_grammar_file(
    path: Union[str, "os.PathLike[str]"],
    start: Optional[Union[str, NonTerminal]] = None,
    validate: bool = True,
    encoding: str = "utf-8",
) -> Grammar:
    """Read a ``.bnf`` file and parse it with :func:`parse_grammar`."""
    with open(path, "r", encoding=encoding) as handle:
        text = handle.read()
    try:
        return parse_grammar(text, start=start, validate=validate)
    except BNFSyntaxError as exc:
        raise BNFSyntaxError("{}: {}".format(os.fspath(path), exc.message), exc.line, exc.column)
