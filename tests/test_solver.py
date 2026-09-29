"""Tests for the Earley solver: acceptance, rejection and parse trees."""

import pytest

from bnf_solver import (
    EarleyParser,
    NonTerminal,
    SolverError,
    parse,
    parse_grammar,
    parse_grammar_file,
    parse_tree,
    recognize,
)

ACCEPTED_ARITHMETIC = ["1", "1+2", "1+2*3", "(1+2)*3", "((7))", "1*2*3+4", "(1)"]
REJECTED_ARITHMETIC = ["", "1+", "+1", "1++2", "(1", "1)", "1 + 2", "a", "()"]


@pytest.mark.parametrize("text", ACCEPTED_ARITHMETIC)
def test_arithmetic_accepts(arithmetic, text):
    assert recognize(arithmetic, text, "expr")


@pytest.mark.parametrize("text", REJECTED_ARITHMETIC)
def test_arithmetic_rejects(arithmetic, text):
    assert not recognize(arithmetic, text, "expr")


@pytest.mark.parametrize("text", ACCEPTED_ARITHMETIC)
def test_tree_spells_the_input_back(arithmetic, text):
    tree = parse_tree(arithmetic, text, "expr")
    assert tree is not None
    assert tree.text == text
    assert tree.symbol == NonTerminal("expr")


def test_precedence_is_reflected_in_the_tree(arithmetic):
    tree = parse_tree(arithmetic, "1+2*3", "expr")
    # The unambiguous grammar must group as 1 + (2 * 3).
    assert tree.to_bracketed() == (
        '(expr (expr (term (factor (number "1")))) "+" '
        '(term (term (factor (number "2"))) "*" (factor (number "3"))))'
    )


def test_left_recursion_is_left_associative(arithmetic):
    tree = parse_tree(arithmetic, "1+2+3", "expr")
    assert tree.children[0].text == "1+2"
    assert tree.children[2].text == "3"


BALANCED_ACCEPTED = ["", "()", "(())", "()()", "((()))", "()(())()"]
BALANCED_REJECTED = ["(", ")", "(()", "())", ")(", "(()))("]


@pytest.mark.parametrize("text", BALANCED_ACCEPTED)
def test_balanced_accepts(balanced, text):
    assert recognize(balanced, text, "s")


@pytest.mark.parametrize("text", BALANCED_REJECTED)
def test_balanced_rejects(balanced, text):
    assert not recognize(balanced, text, "s")


def test_nullable_start_symbol_yields_an_empty_tree(balanced):
    result = parse(balanced, "", "s")
    assert result.recognized
    assert result.tree.text == ""
    assert result.tree.symbol == NonTerminal("s")


def test_ambiguous_and_nullable_grammar_still_terminates(examples_dir):
    grammar = parse_grammar_file(examples_dir / "balanced.bnf")
    parser = EarleyParser(grammar)
    assert parser.recognize("", "brackets")
    assert parser.recognize("([]())[]", "brackets")
    assert not parser.recognize("([)]", "brackets")
    tree = parser.parse_tree("([]())[]", "brackets")
    assert tree.text == "([]())[]"


def test_nullable_set_is_computed(examples_dir):
    grammar = parse_grammar_file(examples_dir / "balanced.bnf")
    assert EarleyParser(grammar).nullable == (NonTerminal("brackets"),)


SENTENCES = [
    ("the cat sees a dog", True),
    ("a small dog chases the grey cat", True),
    ("the cat sleeps", True),
    ("the cat sees a lazy dog", True),
    ("cat sees dog", False),
    ("the cat sees", True),  # a bare verb is a complete verb-phrase
    ("the cat sees ", False),
    ("the cat cat", False),
    ("the  cat sleeps", False),
    ("", False),
]


@pytest.mark.parametrize("text, expected", SENTENCES)
def test_toy_sentence_grammar(sentence, text, expected):
    assert recognize(sentence, text, "sentence") is expected


def test_sentence_tree_structure(sentence):
    tree = parse_tree(sentence, "the cat sleeps", "sentence")
    assert tree.to_bracketed() == (
        '(sentence (noun-phrase (article "the") " " (noun "cat")) " " '
        '(verb-phrase (verb "sleeps")))'
    )


def test_scannerless_matching_backtracks_over_terminal_prefixes():
    # A greedy tokenizer would commit to "ab" and fail; Earley tries both.
    grammar = parse_grammar('<s> ::= <x> "b"\n<x> ::= "a" | "ab"')
    assert recognize(grammar, "ab", "s")
    assert recognize(grammar, "abb", "s")
    assert not recognize(grammar, "a", "s")


def test_shared_prefix_words_are_handled(sentence):
    # "the" is a prefix of nothing here, but "a" is a prefix of "a dog"; the
    # article/noun split must still be found.
    assert recognize(sentence, "a telescope sleeps", "sentence")


def test_right_recursion():
    grammar = parse_grammar('<list> ::= <item> | <item> "," <list>\n<item> ::= "x"')
    assert recognize(grammar, "x,x,x,x", "list")
    assert not recognize(grammar, "x,", "list")


def test_deeply_nullable_chain():
    grammar = parse_grammar(
        """
        <s> ::= <a> <b> <c> "end"
        <a> ::= "a" | ""
        <b> ::= <a> | ""
        <c> ::= <b> | ""
        """
    )
    assert recognize(grammar, "end", "s")
    assert recognize(grammar, "aaaend", "s")
    tree = parse_tree(grammar, "end", "s")
    assert tree.text == "end"


def test_cyclic_grammar_does_not_hang():
    grammar = parse_grammar('<a> ::= <b> | "x"\n<b> ::= <a>')
    assert recognize(grammar, "x", "a")
    assert not recognize(grammar, "y", "a")


def test_start_symbol_defaults_to_the_first_rule(arithmetic):
    assert parse(arithmetic, "1+2").start == NonTerminal("expr")


def test_start_symbol_may_be_given_in_brackets(arithmetic):
    assert recognize(arithmetic, "1*2", "<term>")


def test_unknown_start_symbol_raises(arithmetic):
    with pytest.raises(SolverError, match="no rule defines <nope>"):
        parse(arithmetic, "1", "nope")


def test_parse_result_reports_how_far_it_got(arithmetic):
    result = parse(arithmetic, "1+2*)", "expr")
    assert not result.recognized
    assert result.tree is None
    assert result.furthest_position == 4
    assert bool(result) is False


def test_parse_result_is_truthy_on_success(arithmetic):
    assert bool(parse(arithmetic, "1", "expr")) is True


def test_parser_instance_can_be_reused(arithmetic):
    parser = EarleyParser(arithmetic)
    assert parser.recognize("1+1", "expr")
    assert not parser.recognize("1+", "expr")
    assert parser.recognize("(1+1)*2", "expr")


def test_multi_digit_numbers_via_example_grammar(examples_dir):
    grammar = parse_grammar_file(examples_dir / "arithmetic.bnf")
    parser = EarleyParser(grammar)
    assert parser.recognize("120*3-45", "expr")
    assert parser.parse_tree("120", "expr").text == "120"


def test_json_example_grammar(examples_dir):
    grammar = parse_grammar_file(examples_dir / "json-value.bnf")
    parser = EarleyParser(grammar)
    assert parser.recognize('{"a":[1,true,null]}', "value")
    assert parser.recognize("{}", "value")
    assert parser.recognize("[]", "value")
    assert not parser.recognize('{"a":}', "value")
    assert not parser.recognize("[1,]", "value")
