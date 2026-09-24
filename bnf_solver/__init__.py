"""bnf_solver - parse BNF grammars and decide whether strings are derivable.

Typical use::

    from bnf_solver import parse_grammar, parse

    grammar = parse_grammar('<s> ::= "a" <s> | "a"')
    result = parse(grammar, "aaa", start="s")
    print(result.recognized)
    print(result.tree.pretty())
"""

from .errors import BNFError, BNFSyntaxError, GrammarError, SolverError
from .grammar import (
    Grammar,
    NonTerminal,
    Production,
    Rule,
    Symbol,
    Terminal,
    quote_terminal,
)
from .parser import Token, parse_grammar, parse_grammar_file, tokenize
from .solver import EarleyParser, ParseResult, parse, parse_tree, recognize
from .tree import ParseTree
from .version import __version__

__all__ = [
    # grammar model
    "Grammar",
    "Rule",
    "Production",
    "Symbol",
    "Terminal",
    "NonTerminal",
    "quote_terminal",
    # grammar text -> model
    "parse_grammar",
    "parse_grammar_file",
    "tokenize",
    "Token",
    # solving
    "EarleyParser",
    "ParseResult",
    "parse",
    "parse_tree",
    "recognize",
    "ParseTree",
    # errors
    "BNFError",
    "BNFSyntaxError",
    "GrammarError",
    "SolverError",
    "__version__",
]
