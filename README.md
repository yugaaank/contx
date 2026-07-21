# contx

A Tree-sitter-based code analyzer that turns a source tree into structured context for LLM prompts. Walks your project, parses every file, and extracts symbols, signatures, docstrings, and call relationships -- then outputs a Markdown brief or a queryable JSON index.

Instead of dumping whole files into a prompt, you get a symbol-level map: what functions, classes, and types exist, where they live, what they call, and how complex they are.

## Install

```bash
pip install tree-sitter tree-sitter-language-pack
pip install -e .
```

Requires Python 3.8+.

## Usage

### Generate a Markdown brief

```bash
contx /path/to/project
contx /path/to/project --out CONTEXT.md
```

### Generate a JSON index

```bash
contx /path/to/project --format json --out code-index.json
```

### Restrict languages

```bash
contx /path/to/project --languages python,javascript
```

### Query the JSON index

```bash
# search symbols by name/docstring
contx --query search "authentication" --index code-index.json

# get the source of a specific symbol
contx --query fetch "processPayment" --index code-index.json --root /path/to/project

# find all callers of a function
contx --query callers "processPayment" --index code-index.json

# all symbols in one file
contx --query file_symbols "src/api.py" --index code-index.json

# project summary
contx --query summary --index code-index.json
```

### List supported languages

```bash
contx --list-languages
```

Works with any grammar from `tree-sitter-language-pack`: Python, TypeScript, Rust, Go, Java, C/C++, Ruby, PHP, Shell, SQL, Dockerfile, Terraform, Nix, and many more.

## License

MIT
