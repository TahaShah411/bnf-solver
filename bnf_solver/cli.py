"""Command line entry point: ``python -m bnf_solver`` / ``bnf-solver``."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional, Sequence

from .errors import BNFError
from .grammar import Grammar
from .parser import parse_grammar, parse_grammar_file
from .solver import EarleyParser, ParseResult
from .version import __version__

__all__ = ["main", "build_arg_parser"]

EXIT_OK = 0
EXIT_NOT_DERIVABLE = 1
EXIT_ERROR = 2

_FORMATS = ("tree", "ascii", "indent", "bracket", "none")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bnf-solver",
        description=(
            "Decide whether a string is derivable from a BNF grammar and, if it "
            "is, print a parse tree."
        ),
        epilog=(
            'example: python -m bnf_solver --grammar examples/arithmetic.bnf '
            '--start expr --string "1+2*3"'
        ),
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("-g", "--grammar", metavar="FILE", help="path to a .bnf grammar file")
    source.add_argument(
        "-G", "--grammar-text", metavar="BNF", help="grammar given inline as a string"
    )

    parser.add_argument(
        "-s",
        "--start",
        metavar="SYMBOL",
        help="start symbol, with or without angle brackets (default: first rule)",
    )
    parser.add_argument(
        "-i", "--string", metavar="TEXT", help="input string to test"
    )
    parser.add_argument(
        "-f",
        "--input-file",
        metavar="FILE",
        help="read the input string from a file (default: stdin)",
    )
    parser.add_argument(
        "--format",
        choices=_FORMATS,
        default="tree",
        help="parse tree rendering (default: tree)",
    )
    parser.add_argument(
        "--strip",
        dest="strip",
        action="store_true",
        default=None,
        help="strip surrounding whitespace from the input",
    )
    parser.add_argument(
        "--no-strip",
        dest="strip",
        action="store_false",
        help="keep surrounding whitespace (default for --string)",
    )
    parser.add_argument(
        "--show-grammar",
        action="store_true",
        help="print the normalised grammar before solving",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="print nothing; use the exit code"
    )
    parser.add_argument("--version", action="version", version="bnf-solver " + __version__)
    return parser


def _load_grammar(args: argparse.Namespace) -> Grammar:
    if args.grammar:
        return parse_grammar_file(args.grammar)
    return parse_grammar(args.grammar_text)


def _load_input(args: argparse.Namespace) -> str:
    if args.string is not None:
        text = args.string
        default_strip = False
    elif args.input_file:
        with open(args.input_file, "r", encoding="utf-8") as handle:
            text = handle.read()
        default_strip = True
    else:
        text = sys.stdin.read()
        default_strip = True
    strip = default_strip if args.strip is None else args.strip
    return text.strip() if strip else text


def _render_tree(result: ParseResult, style: str) -> str:
    tree = result.tree
    assert tree is not None  # only called for a successful parse
    if style == "tree":
        return tree.pretty()
    if style == "ascii":
        return tree.pretty(ascii_only=True)
    if style == "indent":
        return tree.to_indented()
    return tree.to_bracketed()


def _failure_hint(result: ParseResult) -> List[str]:
    text = result.text
    position = result.furthest_position
    lines = [
        "the parser got as far as position {} of {}".format(position, len(text))
    ]
    if text and "\n" not in text and len(text) <= 200:
        lines.append("  " + text)
        lines.append("  " + " " * position + "^")
    return lines


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the CLI. Returns 0 (derivable), 1 (not derivable) or 2 (error)."""
    args = build_arg_parser().parse_args(argv)
    out = sys.stdout

    try:
        grammar = _load_grammar(args)
    except BNFError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return EXIT_ERROR
    except OSError as exc:
        print("error: cannot read grammar: {}".format(exc), file=sys.stderr)
        return EXIT_ERROR

    if args.show_grammar and not args.quiet:
        print(grammar.to_bnf(), file=out)
        print(file=out)

    try:
        text = _load_input(args)
    except OSError as exc:
        print("error: cannot read input: {}".format(exc), file=sys.stderr)
        return EXIT_ERROR

    try:
        result = EarleyParser(grammar).parse(text, args.start)
    except BNFError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return EXIT_ERROR

    if args.quiet:
        return EXIT_OK if result.recognized else EXIT_NOT_DERIVABLE

    if not result.recognized:
        print("NOT DERIVABLE", file=out)
        print("{!r} cannot be derived from {}".format(text, result.start), file=out)
        for line in _failure_hint(result):
            print(line, file=out)
        return EXIT_NOT_DERIVABLE

    print("DERIVABLE", file=out)
    print("{!r} can be derived from {}".format(text, result.start), file=out)
    if args.format != "none":
        print(file=out)
        print(_render_tree(result, args.format), file=out)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
