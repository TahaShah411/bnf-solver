"""Tests for the command line interface."""

import subprocess
import sys
from pathlib import Path

import pytest

from bnf_solver.cli import EXIT_ERROR, EXIT_NOT_DERIVABLE, EXIT_OK, main

ROOT = Path(__file__).resolve().parents[1]
ARITHMETIC = str(ROOT / "examples" / "arithmetic.bnf")


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_derivable_prints_a_tree(capsys):
    code, out, _ = run(capsys, "-g", ARITHMETIC, "-s", "expr", "-i", "1+2*3")
    assert code == EXIT_OK
    assert out.startswith("DERIVABLE")
    assert "<expr>" in out
    assert "└──" in out


def test_not_derivable_explains_where_it_stopped(capsys):
    code, out, _ = run(capsys, "-g", ARITHMETIC, "-s", "expr", "-i", "1+*2")
    assert code == EXIT_NOT_DERIVABLE
    assert out.startswith("NOT DERIVABLE")
    assert "position 2 of 4" in out
    assert "^" in out


@pytest.mark.parametrize(
    "style, needle",
    [
        ("bracket", '(expr (term (factor (number (digit "1")))))'),
        ("ascii", "`-- "),
        ("indent", "  <term>"),
    ],
)
def test_output_formats(capsys, style, needle):
    code, out, _ = run(capsys, "-g", ARITHMETIC, "-s", "expr", "-i", "1", "--format", style)
    assert code == EXIT_OK
    assert needle in out


def test_format_none_suppresses_the_tree(capsys):
    code, out, _ = run(capsys, "-g", ARITHMETIC, "-s", "expr", "-i", "1", "--format", "none")
    assert code == EXIT_OK
    assert "<term>" not in out
    assert out.splitlines() == ["DERIVABLE", "'1' can be derived from <expr>"]


def test_quiet_prints_nothing(capsys):
    code, out, err = run(capsys, "-g", ARITHMETIC, "-s", "expr", "-i", "1", "-q")
    assert (code, out, err) == (EXIT_OK, "", "")
    code, out, err = run(capsys, "-g", ARITHMETIC, "-s", "expr", "-i", "x", "-q")
    assert (code, out, err) == (EXIT_NOT_DERIVABLE, "", "")


def test_inline_grammar_and_default_start(capsys):
    code, out, _ = run(capsys, "-G", '<s> ::= "a" <s> | "a"', "-i", "aaa")
    assert code == EXIT_OK
    assert "<s>" in out


def test_show_grammar(capsys):
    code, out, _ = run(capsys, "-G", '<s> ::= "a"', "-i", "a", "--show-grammar")
    assert code == EXIT_OK
    assert '<s> ::= "a"' in out


def test_start_symbol_may_include_brackets(capsys):
    code, _, _ = run(capsys, "-g", ARITHMETIC, "-s", "<term>", "-i", "2*3")
    assert code == EXIT_OK


def test_input_from_file_is_stripped(capsys, tmp_path):
    path = tmp_path / "input.txt"
    path.write_text("  1+2\n")
    code, out, _ = run(capsys, "-g", ARITHMETIC, "-s", "expr", "-f", str(path))
    assert code == EXIT_OK
    assert "DERIVABLE" in out


def test_no_strip_keeps_whitespace(capsys, tmp_path):
    path = tmp_path / "input.txt"
    path.write_text("1+2\n")
    code, _, _ = run(capsys, "-g", ARITHMETIC, "-s", "expr", "-f", str(path), "--no-strip")
    assert code == EXIT_NOT_DERIVABLE


def test_strip_can_be_forced_for_a_string(capsys):
    code, _, _ = run(capsys, "-g", ARITHMETIC, "-s", "expr", "-i", " 1+2 ", "--strip")
    assert code == EXIT_OK


def test_missing_grammar_file_is_an_error(capsys, tmp_path):
    code, _, err = run(capsys, "-g", str(tmp_path / "nope.bnf"), "-i", "1")
    assert code == EXIT_ERROR
    assert "cannot read grammar" in err


def test_malformed_grammar_is_an_error(capsys):
    code, _, err = run(capsys, "-G", '<s> ::= ', "-i", "a")
    assert code == EXIT_ERROR
    assert "error:" in err


def test_unknown_start_symbol_is_an_error(capsys):
    code, _, err = run(capsys, "-g", ARITHMETIC, "-s", "nope", "-i", "1")
    assert code == EXIT_ERROR
    assert "no rule defines <nope>" in err


def test_grammar_source_is_required(capsys):
    with pytest.raises(SystemExit) as info:
        main(["-i", "1"])
    assert info.value.code == 2


def test_module_entry_point_end_to_end():
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "bnf_solver",
            "--grammar",
            ARITHMETIC,
            "--start",
            "expr",
            "--string",
            "1+2*3",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert process.returncode == EXIT_OK
    assert "DERIVABLE" in process.stdout
    assert "<factor>" in process.stdout


def test_module_entry_point_reads_stdin():
    process = subprocess.run(
        [sys.executable, "-m", "bnf_solver", "-g", ARITHMETIC, "-s", "expr", "-q"],
        cwd=str(ROOT),
        input="(1+2)*3\n",
        capture_output=True,
        text=True,
    )
    assert process.returncode == EXIT_OK
