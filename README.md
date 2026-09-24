# bnf-solver

A small, dependency-free Python library and CLI that reads a **BNF grammar**,
then decides whether a given string is **derivable** from it — and if it is,
shows you a **parse tree**.

It uses an [Earley parser](https://en.wikipedia.org/wiki/Earley_parser), so it
works on *any* context-free grammar: left recursive, right recursive, ambiguous,
or full of empty productions. No grammar rewriting, no LL(1) restriction, no
separate tokenizer.

```console
$ python -m bnf_solver --grammar examples/arithmetic.bnf --start expr --string "1+2*3"
DERIVABLE
'1+2*3' can be derived from <expr>

<expr>
├── <expr>
│   └── <term>
│       └── <factor>
│           └── <number>
│               └── <digit>
│                   └── "1"
├── "+"
└── <term>
    ├── <term>
    │   └── <factor>
    │       └── <number>
    │           └── <digit>
    │               └── "2"
    ├── "*"
    └── <factor>
        └── <number>
            └── <digit>
                └── "3"
```

## Supported BNF syntax

```bnf
# comments run to the end of the line
<expr>   ::= <expr> "+" <term> | <term>
<term>   ::= <term> "*" <factor> | <factor>
<factor> ::= "(" <expr> ")" | <number>
<number> ::= "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9"
```

| Element | Syntax | Notes |
| --- | --- | --- |
| Non-terminal | `<name>` | Any characters except `<`, `>` and newlines: `<noun-phrase>`, `<unsigned int>` |
| Terminal | `"text"` or `'text'` | Escapes: `\\`, `\"`, `\'`, `\n`, `\t`, `\r`, `\0` |
| Definition | `::=` | |
| Alternatives | `\|` | |
| Sequence | whitespace separated | `<a> "," <b>` |
| Empty string | `""` | `<opt> ::= "x" \| ""` makes `<opt>` nullable |
| Comment | `# ...` | To end of line |

Other details:

* A rule may span **several lines** — a new rule only begins at `<head> ::=`,
  so continuation lines starting with `|` work naturally.
* Declaring the same head twice **merges** its alternatives.
* The **start symbol** defaults to the head of the first rule; override it with
  `--start` (brackets optional: `expr` and `<expr>` both work).
* Grammars are **validated** on load: referencing a non-terminal that no rule
  defines is an error.
* Matching is **scannerless**: a terminal matches a literal substring of the
  input, so whitespace in the input is only allowed where the grammar says so.
  That is why `examples/sentence.bnf` spells out the spaces between words.

## Install

Zero runtime dependencies; Python 3.8+.

```bash
# run straight from a checkout
python -m bnf_solver --help

# or install it
pip install .            # adds the `bnf-solver` command
pip install -e ".[dev]"  # editable, plus pytest
```

## CLI usage

```bash
python -m bnf_solver --grammar FILE [--start SYMBOL] [--string TEXT] [options]
bnf-solver --grammar FILE ...        # after `pip install .`
```

| Option | Meaning |
| --- | --- |
| `-g, --grammar FILE` | Grammar file (`.bnf`) |
| `-G, --grammar-text BNF` | Grammar given inline |
| `-s, --start SYMBOL` | Start symbol (default: first rule) |
| `-i, --string TEXT` | Input string to test |
| `-f, --input-file FILE` | Read the input from a file (default: stdin) |
| `--format {tree,ascii,indent,bracket,none}` | Parse tree rendering (default `tree`) |
| `--strip` / `--no-strip` | Trim surrounding whitespace (on by default for file/stdin input) |
| `--show-grammar` | Print the normalised grammar first |
| `-q, --quiet` | Print nothing; just set the exit code |

Exit codes: **0** derivable, **1** not derivable, **2** error (bad grammar,
unknown start symbol, unreadable file).

### Examples

Arithmetic, bracketed output:

```console
$ python -m bnf_solver -g examples/arithmetic.bnf -s expr -i "(1+2)*3" --format bracket
DERIVABLE
'(1+2)*3' can be derived from <expr>

(expr (term (term (factor "(" (expr (expr (term (factor (number (digit "1"))))) "+" (term (factor (number (digit "2"))))) ")")) "*" (factor (number (digit "3")))))
```

A rejected string tells you how far the parser got:

```console
$ python -m bnf_solver -g examples/arithmetic.bnf -s expr -i "1+*2"
NOT DERIVABLE
'1+*2' cannot be derived from <expr>
the parser got as far as position 2 of 4
  1+*2
    ^
```

An ambiguous, nullable grammar (`<brackets> ::= <brackets> <brackets> | "(" <brackets> ")" | "[" <brackets> "]" | ""`):

```console
$ python -m bnf_solver -g examples/balanced.bnf -s brackets -i "([]())" --format bracket
DERIVABLE
'([]())' can be derived from <brackets>

(brackets "(" (brackets (brackets "[" (brackets) "]") (brackets "(" (brackets) ")")) ")")
```

A toy natural-language grammar, ASCII tree:

```console
$ python -m bnf_solver -g examples/sentence.bnf -s sentence -i "the cat sleeps" --format ascii
DERIVABLE
'the cat sleeps' can be derived from <sentence>

<sentence>
|-- <noun-phrase>
|   |-- <article>
|   |   `-- "the"
|   |-- " "
|   `-- <noun>
|       `-- "cat"
|-- " "
`-- <verb-phrase>
    `-- <verb>
        `-- "sleeps"
```

Inline grammar, piped input, exit code only:

```console
$ echo "aaa" | python -m bnf_solver -G '<s> ::= "a" <s> | "a"' -q ; echo $?
0
```

### Example grammars

| File | Start symbol | What it shows |
| --- | --- | --- |
| `examples/arithmetic.bnf` | `expr` | Left recursion and operator precedence, multi-digit numbers |
| `examples/balanced.bnf` | `brackets` | An ambiguous **and** nullable grammar |
| `examples/sentence.bnf` | `sentence` | A toy English fragment with explicit spaces |
| `examples/json-value.bnf` | `value` | Nested, mutually recursive structures |

## Library usage

```python
from bnf_solver import parse_grammar, parse_grammar_file, EarleyParser, parse, recognize

grammar = parse_grammar('''
    <expr>  ::= <expr> "+" <digit> | <digit>
    <digit> ::= "0" | "1" | "2"
''')

recognize(grammar, "1+2", start="expr")      # -> True

result = parse(grammar, "1+2", start="expr") # -> ParseResult
result.recognized                            # True (ParseResult is also truthy)
result.tree.text                             # '1+2'
print(result.tree.pretty())                  # box-drawing tree
print(result.tree.to_bracketed())            # (expr (expr (digit "1")) "+" (digit "2"))
print(result.tree.to_indented())             # plain indentation

# Reuse one parser for many inputs against the same grammar:
parser = EarleyParser(parse_grammar_file("examples/arithmetic.bnf"))
parser.recognize("120*3", "expr")            # -> True
parser.parse_tree("1+", "expr")              # -> None
```

Public API: `parse_grammar`, `parse_grammar_file`, `tokenize`, `Grammar`,
`Rule`, `Production`, `Terminal`, `NonTerminal`, `EarleyParser`, `parse`,
`parse_tree`, `recognize`, `ParseResult`, `ParseTree`, and the errors
`BNFError`, `BNFSyntaxError`, `GrammarError`, `SolverError` (all deriving from
`BNFError`).

### Modules

| Module | Contents |
| --- | --- |
| `bnf_solver/grammar.py` | `Terminal`, `NonTerminal`, `Production`, `Rule`, `Grammar` |
| `bnf_solver/parser.py` | Tokenizer + recursive-descent reader for BNF text |
| `bnf_solver/solver.py` | The Earley parser and `ParseResult` |
| `bnf_solver/tree.py` | `ParseTree` and its three renderings |
| `bnf_solver/cli.py` | Argument parsing and output for the command line |
| `bnf_solver/errors.py` | Exception hierarchy |

## Running the tests

```bash
pip install -e ".[dev]"   # or: pip install -r requirements-dev.txt
pytest
```

The suite covers grammar data structures, BNF parsing (including a dozen
malformed-grammar error cases), solving and parse-tree construction for four
grammars, tree rendering, and the CLI end to end.

## Algorithm and complexity

The solver is a scannerless **Earley recogniser** with parse-tree
reconstruction.

For an input of `n` characters it builds `n + 1` *charts*. A chart entry (an
*item*) is a production with a dot marking how much of it has matched, plus the
input position where the match started. Each chart is processed once with three
operations:

* **Predict** — the dot sits before `<x>`: add every alternative of `<x>`,
  starting here.
* **Scan** — the dot sits before a terminal that matches the input at this
  position: copy the item, dot advanced, into the chart `len(terminal)` ahead.
* **Complete** — the dot is at the end: advance every item that was waiting on
  this non-terminal at the position where the item started.

The input is derivable iff the final chart holds a completed item for the start
symbol that began at position 0.

Two details worth calling out:

* **Nullable symbols.** Textbook Earley mishandles empty productions. This
  implementation uses the Aycock & Horspool fix: nullable non-terminals are
  computed up front, and the predictor immediately also advances the dot over
  any nullable symbol.
* **Parse trees.** Each item records the single predecessor item and child that
  first produced it. Because those pointers are written only at creation time
  and always refer to already-created items, following them is acyclic even for
  infinitely ambiguous grammars — so tree reconstruction terminates and returns
  one valid derivation. (For an ambiguous input this is *a* parse tree, not all
  of them.)

**Complexity.** Items are deduplicated per chart, so there are `O(|G| · n)`
items per chart and `O(|G| · n²)` overall. Completion is the expensive step:

| Grammar | Time | Space |
| --- | --- | --- |
| Ambiguous (worst case) | `O(|G|² · n³)` | `O(|G| · n²)` |
| Unambiguous | `O(|G|² · n²)` | `O(|G| · n²)` |
| LR(k)-ish, in practice | `O(n)` | `O(|G| · n²)` |

`n` is the number of **characters**, not tokens, because the parser is
scannerless — convenient for small grammars, but it means the cubic term bites
sooner than it would with a real tokenizer. Tree reconstruction is linear in the
size of the tree it returns, and is recursive, so pathologically deep
derivations can hit Python's recursion limit.

## License

MIT.
