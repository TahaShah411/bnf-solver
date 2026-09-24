"""Shared fixtures: the example grammars and a couple of inline ones."""

from pathlib import Path

import pytest

from bnf_solver import parse_grammar, parse_grammar_file

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"

ARITHMETIC_BNF = """
<expr>   ::= <expr> "+" <term> | <term>
<term>   ::= <term> "*" <factor> | <factor>
<factor> ::= "(" <expr> ")" | <number>
<number> ::= "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9"
"""

BALANCED_BNF = """
<s> ::= "(" <s> ")" <s> | ""
"""


@pytest.fixture(scope="session")
def examples_dir():
    return EXAMPLES_DIR


@pytest.fixture
def arithmetic():
    return parse_grammar(ARITHMETIC_BNF)


@pytest.fixture
def balanced():
    return parse_grammar(BALANCED_BNF)


@pytest.fixture
def sentence():
    return parse_grammar_file(EXAMPLES_DIR / "sentence.bnf")
