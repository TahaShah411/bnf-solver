"""Tests for turning BNF text into grammar objects, including error cases."""

import pytest

from bnf_solver import (
    BNFError,
    BNFSyntaxError,
    GrammarError,
    NonTerminal,
    Terminal,
    parse_grammar,
    parse_grammar_file,
    tokenize,
)
from bnf_solver.parser import DEFINE, EOF_TOKEN, NONTERMINAL, PIPE, TERMINAL


def test_tokenize_kinds():
    kinds = [token.kind for token in tokenize('<a> ::= "x" | <b>')]
    assert kinds == [NONTERMINAL, DEFINE, TERMINAL, PIPE, NONTERMINAL, EOF_TOKEN]


def test_tokenize_tracks_positions():
    tokens = tokenize('<a> ::= "x"\n<b> ::= "y"')
    assert (tokens[0].line, tokens[0].column) == (1, 1)
    assert (tokens[3].line, tokens[3].column) == (2, 1)
    assert (tokens[4].line, tokens[4].column) == (2, 5)


def test_parses_the_readme_grammar(arithmetic):
    assert [nt.name for nt in arithmetic.nonterminals] == [
        "expr",
        "term",
        "factor",
        "number",
    ]
    expr = arithmetic.productions_for("expr")
    assert expr[0].symbols == (NonTerminal("expr"), Terminal("+"), NonTerminal("term"))
    assert expr[1].symbols == (NonTerminal("term"),)
    factor = arithmetic.productions_for("factor")
    assert factor[0].symbols == (
        Terminal("("),
        NonTerminal("expr"),
        Terminal(")"),
    )


def test_single_quoted_terminals_and_escapes():
    grammar = parse_grammar("""<a> ::= 'it''s' | "q\\"q" | "tab\\there" | "back\\\\slash" """)
    texts = [t.text for t in grammar.terminals]
    assert "q\"q" in texts
    assert "tab\there" in texts
    assert "back\\slash" in texts


def test_comments_and_blank_lines_are_ignored():
    grammar = parse_grammar(
        """
        # a leading comment
        <a> ::= "x"   # trailing comment

        <b> ::= "y"
        """
    )
    assert len(grammar) == 2


def test_rule_may_span_multiple_lines():
    grammar = parse_grammar(
        """
        <a> ::= "x"
              | "y"
              | <a> "z"
        <b> ::= "b"
        """
    )
    assert len(grammar.productions_for("a")) == 3
    assert len(grammar) == 2


def test_hyphens_and_spaces_in_nonterminal_names():
    grammar = parse_grammar('<noun phrase> ::= <the-article>\n<the-article> ::= "the"')
    assert NonTerminal("noun phrase") in grammar


def test_empty_terminal_means_epsilon():
    grammar = parse_grammar('<a> ::= "" | "x" <a>')
    productions = grammar.productions_for("a")
    assert productions[0].is_epsilon
    assert productions[0].symbols == ()


def test_empty_terminal_is_dropped_from_a_longer_sequence():
    grammar = parse_grammar('<a> ::= "x" "" "y"')
    assert grammar.productions_for("a")[0].symbols == (Terminal("x"), Terminal("y"))


def test_parse_grammar_file(examples_dir):
    grammar = parse_grammar_file(examples_dir / "arithmetic.bnf")
    assert NonTerminal("digit") in grammar
    assert len(grammar.productions_for("digit")) == 10


def test_parse_grammar_file_reports_the_path(tmp_path):
    path = tmp_path / "broken.bnf"
    path.write_text('<a> ::= "unterminated\n')
    with pytest.raises(BNFSyntaxError, match="broken.bnf"):
        parse_grammar_file(path)


# --------------------------------------------------------------- error cases


@pytest.mark.parametrize(
    "text, message",
    [
        ('<a> ::= "x" <b>', "undefined non-terminal"),
        ("", "no rules"),
        ("   # just a comment\n", "no rules"),
    ],
)
def test_semantic_errors(text, message):
    with pytest.raises(GrammarError, match=message):
        parse_grammar(text)


@pytest.mark.parametrize(
    "text, message",
    [
        ('<a> "x"', r"expected '::='"),
        ('"a" ::= "x"', "expected a non-terminal"),
        ('<a> ::= "unterminated', "unterminated terminal string"),
        ("<a ::= 'x'", "unterminated non-terminal"),
        ('<> ::= "x"', "empty non-terminal name"),
        ('<a> ::= | "x"', "empty alternative"),
        ('<a> ::= "x" |', "empty alternative"),
        ('<a> ::= "x" ; "y"', "unexpected character"),
        ('<a> ::= "x"\n<b> ::=', "empty alternative"),
        ('<a> ::= "x\\', "dangling escape"),
    ],
)
def test_syntax_errors(text, message):
    with pytest.raises(BNFSyntaxError, match=message):
        parse_grammar(text)


def test_syntax_error_carries_a_position():
    with pytest.raises(BNFSyntaxError) as info:
        parse_grammar('<a> ::= "x"\n<b> ::= @')
    error = info.value
    assert error.line == 2
    assert error.column == 9
    assert "line 2, column 9" in str(error)


def test_all_errors_share_a_base_class():
    for text in ('<a> ::= @', '<a> ::= <missing>'):
        with pytest.raises(BNFError):
            parse_grammar(text)


def test_validation_can_be_switched_off():
    grammar = parse_grammar('<a> ::= <b>', validate=False)
    assert len(grammar) == 1
