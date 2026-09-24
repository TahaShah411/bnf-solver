"""Tests for parse tree structure and rendering."""

import pytest

from bnf_solver import NonTerminal, ParseTree, Terminal, parse_grammar, parse_tree

# <expr> -> <term> "+" <term>, with each <term> a single digit.
LEAF_1 = ParseTree(Terminal("1"))
LEAF_2 = ParseTree(Terminal("2"))
TERM_1 = ParseTree(NonTerminal("term"), (LEAF_1,))
TERM_2 = ParseTree(NonTerminal("term"), (LEAF_2,))
EXPR = ParseTree(NonTerminal("expr"), (TERM_1, ParseTree(Terminal("+")), TERM_2))


def test_leaf_and_terminal_flags():
    assert LEAF_1.is_leaf and LEAF_1.is_terminal
    assert not EXPR.is_leaf and not EXPR.is_terminal


def test_text_concatenates_terminals():
    assert EXPR.text == "1+2"
    assert TERM_1.text == "1"


def test_height_and_size():
    assert LEAF_1.height == 1
    assert EXPR.height == 3
    assert len(EXPR) == 6
    assert len(list(EXPR.leaves())) == 3
    assert [t.text for t in EXPR.terminals()] == ["1", "+", "2"]


def test_walk_is_preorder():
    labels = [node.label for node in EXPR.walk()]
    assert labels == ['<expr>', '<term>', '"1"', '"+"', '<term>', '"2"']


def test_terminal_nodes_cannot_have_children():
    with pytest.raises(ValueError, match="terminal nodes cannot have children"):
        ParseTree(Terminal("x"), (LEAF_1,))


def test_pretty_uses_box_drawing():
    assert EXPR.pretty() == "\n".join(
        [
            "<expr>",
            "├── <term>",
            "│   └── \"1\"",
            "├── \"+\"",
            "└── <term>",
            "    └── \"2\"",
        ]
    )


def test_pretty_ascii_mode():
    assert EXPR.pretty(ascii_only=True) == "\n".join(
        [
            "<expr>",
            "|-- <term>",
            "|   `-- \"1\"",
            "|-- \"+\"",
            "`-- <term>",
            "    `-- \"2\"",
        ]
    )


def test_str_is_the_pretty_rendering():
    assert str(EXPR) == EXPR.pretty()


def test_to_indented():
    assert EXPR.to_indented(indent="..") == "\n".join(
        [
            "<expr>",
            "..<term>",
            '....\"1\"',
            '..\"+\"',
            "..<term>",
            '....\"2\"',
        ]
    )


def test_to_bracketed():
    assert EXPR.to_bracketed() == '(expr (term "1") "+" (term "2"))'


def test_empty_nonterminal_is_labelled_and_rendered():
    empty = ParseTree(NonTerminal("opt"))
    assert empty.label == "<opt> (empty)"
    assert empty.text == ""
    assert empty.to_bracketed() == "(opt)"
    assert empty.pretty() == "<opt> (empty)"


def test_rendering_a_real_parse(arithmetic):
    tree = parse_tree(arithmetic, "(1)", "expr")
    rendered = tree.pretty()
    assert rendered.splitlines()[0] == "<expr>"
    assert '"("' in rendered and '")"' in rendered
    assert tree.text == "(1)"


def test_escaped_terminals_render_quoted():
    grammar = parse_grammar('<s> ::= "\\n" | "q\\"q"')
    assert parse_tree(grammar, "\n", "s").to_bracketed() == '(s "\\n")'
    assert parse_tree(grammar, 'q"q', "s").to_bracketed() == '(s "q\\"q")'
