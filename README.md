<div align="center">

# contx

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![Tree-sitter](https://img.shields.io/badge/parser-Tree--sitter-3178C6?logo=visualstudiocode&logoColor=white)](#how-it-works)
[![License](https://img.shields.io/badge/license-MIT-8b5cf6)](#license)
[![CI](https://img.shields.io/badge/build-passing-8b5cf6)](#)

</div>

`contx` is a Tree-sitter-based code analyzer that turns a source tree into a
structured context file for LLM-assisted development. It walks a project,
parses every supported file into a syntax tree, and extracts symbols,
signatures, docstrings, call relationships, and complexity metrics — then
emits either a single Markdown brief or a queryable JSON index.

It is built for the terminal and meant to be piped into a model prompt or
queried offline, so you can give an assistant precise, scoped context instead
of pasting whole files.

## Why

Dumping an entire repository into a prompt wastes context and buries the
relevant definitions. `contx` instead produces a symbol-level map: what
functions/classes/types exist, where they live, what they call, and how
complex they are. The JSON index can be queried after the fact (`search`,
`fetch`, `callers`) without re-parsing.

## How it works

1. **Language detection** — `detect_languages_in_project` walks the tree and
   maps file extensions (and bare filenames like `Makefile`, `Dockerfile`) to
   languages, skipping `.git`, `node_modules`, `venv`, `dist`, `target`, etc.
2. **Parser building** — `build_parsers` lazily loads only the Tree-sitter
   grammars the project actually uses via `tree-sitter-language-pack`, so a
   Python project never pays to load the Rust grammar.
3. **Per-file extraction** — `parse_file` walks each syntax tree and pulls
   symbols with `extract_symbols_from_node`, plus:
   - `extract_signature` / `extract_parameters` / `extract_return_type`
   - `extract_docstring` and inline `extract_comments_in_body`
   - `calc_cyclomatic_complexity` and `calc_max_nesting` for metrics
   - `extract_semantic_relationships` and `extract_imports` for the call graph
4. **Output** — `generate_markdown` renders a human-readable brief;
   `generate_json_index` / `generate_json_summary` produce the queryable index.

## Installation

Requires Python 3.8+.

```bash
pip install tree-sitter tree-sitter-language-pack
# or, from the repo:
pip install -e .
```

`contx` is also exposed as a console script (`contx`) when installed via the
`pyproject.toml` entry point.

## Usage

Analyze a project into a Markdown brief (auto-detects languages):

```bash
python context-creator.py /path/to/project
python context-creator.py /path/to/project --out CONTEXT.md
```

Produce a JSON index for downstream querying:

```bash
python context-creator.py /path/to/project --format json --out code-index.json
```

Restrict to specific languages:

```bash
python context-creator.py /path/to/project --languages python,javascript
```

List every grammar the bundled language pack can parse:

```bash
python context-creator.py --list-languages
```

### Querying a JSON index

Once you have `code-index.json`, you can ask it questions without re-parsing:

```bash
# full-text search over symbol names + docstrings + signatures
python context-creator.py --query search "authentication" --index code-index.json

# pull the exact source span of a symbol (needs --root to resolve the file)
python context-creator.py --query fetch "processPayment" --index code-index.json --root /path/to/project

# who calls a given function?
python context-creator.py --query callers "processPayment" --index code-index.json

# every symbol in one file
python context-creator.py --query file_symbols "src/api.py" --index code-index.json

# project-wide summary (symbols per directory, duplicates)
python context-creator.py --query summary --index code-index.json
```

`search` ranks by word-overlap score across name/docstring/signature and
returns the top 5; `fetch` reads the exact byte range from disk and returns the
source; `callers` inverts the `calls` edges collected during extraction.

## Supported languages

Any grammar shipped by `tree-sitter-language-pack` — the C/C++/Rust/Zig
systems family, the JVM/CLR languages, the dynamic bunch (Python, Ruby, Lua,
PHP, …), the ML family, shell, SQL, Dockerfile, CMake, Make, Nix, Terraform,
GraphQL, and more. Detection is extension- and filename-driven, so the set
grows as the language pack adds grammars.

## License

MIT
