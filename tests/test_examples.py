"""Every example grammar must parse, validate and behave as documented."""

import pytest

from bnf_solver import EarleyParser, parse_grammar_file

CASES = {
    "arithmetic.bnf": ("expr", ["1+2*3", "(10-2)/4", "7"], ["1+", "()", "1 + 2"]),
    "balanced.bnf": ("brackets", ["", "()", "([]())", "[][]"], ["(", "([)]", "]"]),
    "sentence.bnf": (
        "sentence",
        ["the cat sees a dog", "a lazy dog sleeps"],
        ["the cat", "dog sleeps"],
    ),
    "json-value.bnf": (
        "value",
        ['{"a":1}', "[]", "true", '[{"x":null},2]'],
        ["{", '{"a"}', "[,]"],
    ),
}


def test_every_example_is_covered(examples_dir):
    on_disk = sorted(path.name for path in examples_dir.glob("*.bnf"))
    assert on_disk == sorted(CASES)


@pytest.mark.parametrize("filename", sorted(CASES))
def test_example_grammar(examples_dir, filename):
    start, accepted, rejected = CASES[filename]
    grammar = parse_grammar_file(examples_dir / filename)
    grammar.validate()
    parser = EarleyParser(grammar)
    for text in accepted:
        assert parser.recognize(text, start), "expected {!r} to parse".format(text)
        assert parser.parse_tree(text, start).text == text
    for text in rejected:
        assert not parser.recognize(text, start), "expected {!r} to fail".format(text)
