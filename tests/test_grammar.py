"""Tests for the grammar data structures themselves."""

import pytest

from bnf_solver import (
    Grammar,
    GrammarError,
    NonTerminal,
    Production,
    Rule,
    Terminal,
    parse_grammar,
    quote_terminal,
)


def test_symbol_rendering():
    assert str(NonTerminal("expr")) == "<expr>"
    assert str(Terminal("+")) == '"+"'
    assert str(Terminal('a"b')) == '"a\\"b"'
    assert str(Terminal("\n")) == '"\\n"'
    assert quote_terminal("\\") == '"\\\\"'


def test_symbol_equality_and_hashing():
    assert NonTerminal("a") == NonTerminal("a")
    assert NonTerminal("a") != Terminal("a")
    assert len({Terminal("x"), Terminal("x"), NonTerminal("x")}) == 2


def test_production_basics():
    production = Production(NonTerminal("e"), (NonTerminal("e"), Terminal("+")))
    assert len(production) == 2
    assert not production.is_epsilon
    assert str(production) == '<e> ::= <e> "+"'
    assert Production(NonTerminal("e")).is_epsilon
    assert str(Production(NonTerminal("e"))) == "<e> ::= ε"


def test_production_head_must_be_a_nonterminal():
    with pytest.raises(TypeError):
        Production(Terminal("x"), ())


def test_rule_expands_to_productions():
    head = NonTerminal("digit")
    rule = Rule(head, ((Terminal("0"),), (Terminal("1"),)))
    assert len(rule) == 2
    assert rule.productions == (
        Production(head, (Terminal("0"),)),
        Production(head, (Terminal("1"),)),
    )
    assert str(rule) == '<digit> ::= "0" | "1"'


def test_grammar_views(arithmetic):
    assert len(arithmetic) == 4
    assert [nt.name for nt in arithmetic.nonterminals] == [
        "expr",
        "term",
        "factor",
        "number",
    ]
    assert arithmetic.start == NonTerminal("expr")
    assert Terminal("*") in arithmetic.terminals
    assert NonTerminal("term") in arithmetic
    assert "<term>" in arithmetic
    assert "nope" not in arithmetic
    assert len(arithmetic.productions_for("expr")) == 2


def test_grammar_resolve_accepts_several_spellings(arithmetic):
    assert arithmetic.resolve("expr") == NonTerminal("expr")
    assert arithmetic.resolve("<expr>") == NonTerminal("expr")
    assert arithmetic.resolve(NonTerminal("expr")) == NonTerminal("expr")


def test_grammar_resolve_rejects_unknown_symbol(arithmetic):
    with pytest.raises(GrammarError, match="no rule defines <nope>"):
        arithmetic.resolve("nope")


def test_explicit_start_symbol():
    grammar = parse_grammar('<a> ::= "a"\n<b> ::= "b"', start="b")
    assert grammar.start == NonTerminal("b")


def test_unknown_explicit_start_symbol_is_rejected():
    with pytest.raises(GrammarError):
        parse_grammar('<a> ::= "a"', start="z")


def test_duplicate_heads_merge_alternatives():
    grammar = parse_grammar('<x> ::= "a"\n<x> ::= "b"')
    assert len(grammar) == 1
    assert len(grammar.productions_for("x")) == 2


def test_productions_for_unknown_symbol_is_empty(arithmetic):
    assert arithmetic.productions_for("missing") == ()


def test_undefined_nonterminals_are_reported():
    grammar = parse_grammar('<a> ::= <b>', validate=False)
    assert grammar.undefined_nonterminals() == (NonTerminal("b"),)
    with pytest.raises(GrammarError, match="undefined non-terminal"):
        grammar.validate()


def test_empty_grammar_has_no_start():
    grammar = Grammar([])
    with pytest.raises(GrammarError):
        _ = grammar.start
    with pytest.raises(GrammarError):
        grammar.validate()


def test_grammar_rejects_non_rules():
    with pytest.raises(TypeError):
        Grammar(["<x> ::= 'a'"])


def test_to_bnf_round_trips(arithmetic):
    text = arithmetic.to_bnf()
    assert '<expr>   ::= <expr> "+" <term> | <term>' in text
    reparsed = parse_grammar(text)
    assert reparsed.to_bnf() == text
