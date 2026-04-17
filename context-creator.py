import os
import sys
import argparse
import re
import json
from pathlib import Path
from tree_sitter import Language, Parser

# Ensure tree-sitter is available
try:
    from tree_sitter import Language, Parser
except ImportError:
    print("Error: tree_sitter library not found. Please install it using 'pip install tree-sitter'.")
    sys.exit(1)

# Language pack support
try:
    from tree_sitter_language_pack import get_language, get_parser, available_languages, download_all
    HAS_LANGUAGE_PACK = True
except ImportError:
    HAS_LANGUAGE_PACK = False

# Map of language names to their common file extensions
LANGUAGE_EXTENSIONS = {
    # Systems programming
    'c': ['.c', '.h'],
    'cpp': ['.cpp', '.cxx', '.cc', '.c++', '.hpp', '.hxx', '.hh', '.ipp'],
    'rust': ['.rs'],
    'zig': ['.zig'],
    'crystal': ['.cr'],
    # General purpose
    'python': ['.py', '.pyw', '.pyi'],
    'javascript': ['.js', '.mjs', '.cjs', '.jsx'],
    'typescript': ['.ts', '.mts', '.cts', '.tsx'],
    'java': ['.java'],
    'c_sharp': ['.cs'],
    'go': ['.go'],
    'ruby': ['.rb'],
    'php': ['.php', '.phtml', '.php3', '.php4', '.php5'],
    'perl': ['.pl', '.pm', '.t'],
    'lua': ['.lua'],
    'r': ['.r', '.R'],
    'dart': ['.dart'],
    'swift': ['.swift'],
    'kotlin': ['.kt', '.kts', '.ktm'],
    'scala': ['.scala', '.sc'],
    'groovy': ['.groovy', '.gvy', '.gy', '.gsh'],
    'haskell': ['.hs', '.lhs'],
    'ocaml': ['.ml', '.mli'],
    'elixir': ['.ex', '.exs'],
    'erlang': ['.erl', '.hrl', '.escript'],
    'clojure': ['.clj', '.cljs', '.cljc', '.edn'],
    'fsharp': ['.fs', '.fsi', '.fsx'],
    'julia': ['.jl'],
    'd': ['.d', '.di'],
    'v': ['.v'],
    'nim': ['.nim', '.nims'],
    'odin': ['.odin'],
    # Web & markup
    'html': ['.html', '.htm'],
    'css': ['.css', '.scss', '.sass', '.less'],
    'json': ['.json', '.jsonc'],
    'yaml': ['.yaml', '.yml'],
    'xml': ['.xml', '.xsd', '.xslt'],
    'markdown': ['.md', '.markdown'],
    'latex': ['.tex', '.sty', '.cls'],
    'toml': ['.toml'],
    # Scripting & config
    'bash': ['.sh', '.bash', '.zsh', '.fish'],
    'powershell': ['.ps1', '.psm1', '.psd1'],
    'dockerfile': ['Dockerfile', 'docker-compose.yml'],
    'cmake': ['.cmake', 'CMakeLists.txt'],
    'make': ['Makefile', 'GNUmakefile'],
    'sql': ['.sql'],
    # Mobile
    'objc': ['.m', '.mm'],
    # Data & query
    'graphql': ['.graphql', '.gql'],
    'regex': ['.regex'],
    # Infrastructure
    'terraform': ['.tf', '.tfvars'],
    'nix': ['.nix'],
}

PARSERS = {}
LANGUAGES = {}

def detect_languages_in_project(root: Path) -> set:
    """Scan project to detect which languages are actually present. (Feature 10)"""
    detected = set()
    ext_to_lang = {}
    for lang, exts in LANGUAGE_EXTENSIONS.items():
        for ext in exts:
            ext_to_lang[ext.lower()] = lang

    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', 'venv', '.venv', '__pycache__', '.next', 'dist', 'build', 'target']]
        for f in files:
            fp = Path(r) / f
            lang = ext_to_lang.get(fp.suffix.lower())
            if lang:
                detected.add(lang)
            # Check filename-based matches
            for lgn, fnames in LANGUAGE_EXTENSIONS.items():
                if f in fnames:
                    detected.add(lgn)
    return detected

def build_parsers(target_languages=None, project_root=None):
    """Build parsers - lazy loading based on project detection. (Feature 10)"""
    global PARSERS, LANGUAGES

    if not HAS_LANGUAGE_PACK:
        print("Error: tree-sitter-language-pack is required.")
        sys.exit(1)

    # Ensure languages are downloaded
    try:
        langs = available_languages()
        if not langs:
            print("Downloading language models (one-time)...")
            download_all()
            langs = available_languages()
    except Exception as e:
        print(f"Warning: Could not check available languages: {e}")
        return

    # Determine which languages to load
    if target_languages:
        # User specified filter
        languages_to_load = set(target_languages) & set(langs)
    elif project_root:
        # Auto-detect from project (Feature 10: lazy loading)
        languages_to_load = detect_languages_in_project(project_root) & set(langs)
        if languages_to_load:
            print(f"Auto-detected languages: {', '.join(sorted(languages_to_load))}")
    else:
        # Load all
        languages_to_load = set(langs)

    if not languages_to_load:
        print("Warning: No languages detected or specified.")
        return

    print(f"Loading {len(languages_to_load)} language parser(s)...")
    loaded = 0
    for lang_name in sorted(languages_to_load):
        try:
            parser = get_parser(lang_name)
            language = get_language(lang_name)
            PARSERS[lang_name] = parser
            LANGUAGES[lang_name] = language
            loaded += 1
        except Exception as e:
            pass  # Skip silently

    print(f"✓ Loaded {loaded} parser(s)")

def get_parser_for_file(file_path: Path):
    """Get the appropriate parser for a file based on its extension."""
    filename = file_path.name
    ext = file_path.suffix.lower()

    for lang_name, extensions in LANGUAGE_EXTENSIONS.items():
        if filename in extensions and lang_name in PARSERS:
            return PARSERS[lang_name], lang_name, LANGUAGES[lang_name]
    for lang_name, extensions in LANGUAGE_EXTENSIONS.items():
        if ext in extensions and lang_name in PARSERS:
            return PARSERS[lang_name], lang_name, LANGUAGES[lang_name]

    if HAS_LANGUAGE_PACK:
        try:
            from tree_sitter_language_pack import detect_language_from_path
            detected_lang = detect_language_from_path(str(file_path))
            if detected_lang and detected_lang in PARSERS:
                return PARSERS[detected_lang], detected_lang, LANGUAGES[detected_lang]
        except:
            pass
    return None, None, None

def get_node_text(node) -> str:
    return node.text.decode('utf8', errors='ignore').strip()

def find_nodes(node, target_types):
    """Find all nodes of specific types in the AST."""
    if isinstance(target_types, str):
        target_types = [target_types]
    results = []
    if node.type in target_types:
        results.append(node)
    for child in node.children:
        results.extend(find_nodes(child, target_types))
    return results

# ============================================================
# Feature 3, 4, 5: Enhanced symbol extraction helpers
# ============================================================

def extract_byte_range(node) -> dict:
    """Extract byte and line range from a node. (Feature 3)"""
    return {
        'startByte': node.start_byte,
        'endByte': node.end_byte,
        'startLine': node.start_point[0],
        'endLine': node.end_point[0],
        'startColumn': node.start_point[1],
        'endColumn': node.end_point[1],
    }

def extract_signature(node, content: bytes) -> str:
    """Extract the first line (signature) of a symbol. (Feature 4)"""
    text = content[node.start_byte:node.end_byte].decode('utf8', errors='ignore')
    first_line = text.split('\n')[0].strip()
    return first_line[:200]  # Cap length

def extract_docstring(node, lang: str) -> str | None:
    """Extract docstring from a symbol node. (Feature 5)"""
    if lang == 'python':
        # Python: first string literal in body
        body = None
        for child in node.children:
            if child.type == 'block':
                body = child
                break
        if body:
            for child in body.children:
                if child.type in ('string', 'string_literal'):
                    text = get_node_text(child).strip()
                    if text.startswith(('"""', "'''", '"', "'")) and len(text) > 4:
                        return text.strip('\'"')
    elif lang in ('javascript', 'typescript'):
        # JS/TS: JSDoc comment is a 'comment' node before the declaration
        prev = node.prev_named_sibling
        if prev and prev.type == 'comment':
            text = get_node_text(prev)
            if text.startswith('/**'):
                return text
        # Also check first string in body
        for child in node.children:
            if child.type == 'statement_block':
                for gc in child.children:
                    if gc.type in ('string', 'string_literal'):
                        text = get_node_text(gc).strip()
                        if text.startswith(('`', '"', "'")) and len(text) > 4:
                            return text
                break
    elif lang == 'java':
        # Java: comment before method
        prev = node.prev_named_sibling
        if prev and prev.type == 'line_comment':
            return get_node_text(prev)
        if prev and prev.type == 'block_comment':
            return get_node_text(prev)
    elif lang == 'go':
        # Go: comment before func
        prev = node.prev_named_sibling
        if prev and prev.type == 'comment':
            return get_node_text(prev)
    elif lang == 'rust':
        # Rust: doc comment (/// or /** */)
        prev = node.prev_named_sibling
        if prev and prev.type == 'line_comment':
            text = get_node_text(prev)
            if text.startswith('///') or text.startswith('//!'):
                return text
    return None

def extract_comments_in_body(node, lang: str, content: bytes) -> list:
    """Extract TODO, FIXME, HACK comments from symbol body. (Feature 5)"""
    comments = []
    body_text = content[node.start_byte:node.end_byte].decode('utf8', errors='ignore')
    lines = body_text.split('\n')
    markers = ['TODO', 'FIXME', 'HACK', 'XXX', 'BUG', 'NOTE']
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if any(m in line_stripped for m in markers):
            # Extract the comment portion
            for m in markers:
                if m in line_stripped:
                    idx = line_stripped.index(m)
                    comments.append({
                        'line': node.start_point[0] + i + 1,
                        'marker': m,
                        'text': line_stripped[idx:idx+120]
                    })
                    break
    return comments

def extract_parameters(node, lang: str) -> list:
    """Extract parameter info from function node. (Feature 4)"""
    params = []
    if lang == 'python':
        for child in node.children:
            if child.type == 'parameters':
                for param in child.children:
                    if param.type == 'identifier':
                        name = get_node_text(param)
                        if name not in ('self', 'cls'):
                            params.append({'name': name, 'type': None})
                    elif param.type == 'typed_parameter':
                        for gc in param.children:
                            if gc.type == 'identifier':
                                pname = get_node_text(gc)
                            elif gc.type in ('type', 'type_identifier'):
                                ptype = get_node_text(gc)
                        if pname not in ('self', 'cls'):
                            params.append({'name': pname, 'type': ptype if 'ptype' in dir() else None})
                break
    elif lang in ('javascript', 'typescript'):
        for child in node.children:
            if child.type == 'formal_parameters':
                for param in child.children:
                    if param.type == 'identifier':
                        params.append({'name': get_node_text(param), 'type': None})
                    elif param.type == 'assignment_pattern':
                        for gc in param.children:
                            if gc.type == 'identifier':
                                params.append({'name': get_node_text(gc), 'type': None})
                                break
                break
    elif lang == 'go':
        for child in node.children:
            if child.type == 'parameter_list':
                for param in child.children:
                    if param.type == 'parameter_declaration':
                        names = [get_node_text(gc) for gc in param.children if gc.type == 'identifier']
                        type_nodes = [get_node_text(gc) for gc in param.children if gc.type in ('type_identifier', 'slice_type', 'pointer_type')]
                        ptype = type_nodes[0] if type_nodes else None
                        for n in names:
                            params.append({'name': n, 'type': ptype})
                break
    elif lang in ('java', 'c_sharp', 'cpp', 'c'):
        for child in node.children:
            if child.type == 'formal_parameters':
                for param in child.children:
                    if param.type in ('formal_parameter', 'parameter_declaration'):
                        pname = None
                        ptype = None
                        for gc in param.children:
                            if gc.type == 'identifier':
                                pname = get_node_text(gc)
                            elif gc.type in ('type_identifier', 'primitive_type', 'array_type', 'scoped_type_identifier'):
                                ptype = get_node_text(gc)
                        if pname:
                            params.append({'name': pname, 'type': ptype})
                break
    return params

def extract_return_type(node, lang: str) -> str | None:
    """Extract return type from function signature. (Feature 4)"""
    if lang == 'python':
        for child in node.children:
            if child.type == 'type':
                return get_node_text(child)
    elif lang in ('javascript', 'typescript'):
        for child in node.children:
            if child.type == 'return_type':
                return get_node_text(child)
    elif lang == 'go':
        for child in node.children:
            if child.type == 'result':
                return get_node_text(child)
    elif lang in ('java', 'c_sharp', 'c', 'cpp'):
        # Return type is typically the first type child before function name
        for child in node.children:
            if child.type in ('type_identifier', 'primitive_type', 'void_type'):
                return get_node_text(child)
            if child.type == 'identifier':
                break  # Past the return type
    return None

def extract_modifiers(node, lang: str) -> list:
    """Extract modifiers like async, static, public, etc. (Feature 4)"""
    modifiers = []
    if lang in ('javascript', 'typescript'):
        for child in node.children:
            if child.type in ('async', 'generator', 'static', 'abstract', 'override'):
                modifiers.append(get_node_text(child))
            elif child.type == 'accessibility_modifier':
                modifiers.append(get_node_text(child))
    elif lang == 'python':
        for child in node.children:
            if child.type == 'decorator':
                dec_text = get_node_text(child)
                if 'staticmethod' in dec_text:
                    modifiers.append('staticmethod')
                elif 'classmethod' in dec_text:
                    modifiers.append('classmethod')
                elif 'property' in dec_text:
                    modifiers.append('property')
                else:
                    modifiers.append(dec_text)
    elif lang == 'java':
        for child in node.children:
            if child.type in ('modifiers',):
                for gc in child.children:
                    modifiers.append(get_node_text(gc))
    elif lang == 'go':
        if node.child_by_field_name('receiver'):
            modifiers.append('method')
    return modifiers

def calc_cyclomatic_complexity(node) -> int:
    """Estimate cyclomatic complexity from AST branching. (Feature 7)"""
    complexity = 1  # Base
    branch_nodes = ['if_statement', 'elif_clause', 'else_clause', 'for_statement',
                    'while_statement', 'try_statement', 'except_clause',
                    'if', 'elif', 'else', 'for', 'while', 'switch', 'case',
                    'conditional_expression', 'ternary_expression',
                    'catch_clause', 'match', 'when', 'guard']
    logical_ops = ['and', 'or', '&&', '||']

    def count_branches(n):
        nonlocal complexity
        if n.type in branch_nodes:
            complexity += 1
        if n.type == 'binary_expression':
            for child in n.children:
                if child.type == 'and' or child.type == 'or':
                    complexity += 1
        for child in n.children:
            count_branches(child)

    count_branches(node)
    return complexity

def calc_max_nesting(node, lang: str, depth: int = 0) -> int:
    """Calculate maximum nesting depth. (Feature 7)"""
    nest_types = ['block', 'statement_block', 'if_statement', 'for_statement',
                  'while_statement', 'function_definition', 'function_declaration',
                  'class_definition', 'class_declaration', 'try_statement',
                  'switch_statement', 'match_statement']
    max_depth = depth
    for child in node.children:
        if child.type in nest_types:
            child_depth = calc_max_nesting(child, lang, depth + 1)
            max_depth = max(max_depth, child_depth)
        else:
            child_depth = calc_max_nesting(child, lang, depth)
            max_depth = max(max_depth, child_depth)
    return max_depth

# Language-specific symbol extraction patterns
# Maps language to (function_node_types, class_node_types, identifier_node_types)
LANGUAGE_PATTERNS = {
    'python': {
        'functions': ['function_definition'],
        'classes': ['class_definition'],
        'name_nodes': ['identifier'],
        'calls': ['call'],
    },
    'javascript': {
        'functions': ['function_declaration', 'function', 'method_definition', 'arrow_function'],
        'classes': ['class_declaration'],
        'name_nodes': ['identifier', 'property_identifier'],
        'calls': ['call_expression'],
    },
    'typescript': {
        'functions': ['function_declaration', 'function', 'method_definition', 'arrow_function'],
        'classes': ['class_declaration'],
        'name_nodes': ['identifier', 'property_identifier', 'type_identifier'],
        'calls': ['call_expression'],
    },
    'java': {
        'functions': ['method_declaration', 'constructor_declaration'],
        'classes': ['class_declaration', 'interface_declaration', 'enum_declaration'],
        'name_nodes': ['identifier'],
        'calls': ['method_invocation'],
    },
    'c': {
        'functions': ['function_definition'],
        'classes': ['struct_specifier', 'union_specifier'],
        'name_nodes': ['identifier'],
        'calls': ['call_expression'],
    },
    'cpp': {
        'functions': ['function_definition', 'function_declarator'],
        'classes': ['class_specifier', 'struct_specifier'],
        'name_nodes': ['identifier', 'field_identifier', 'type_identifier'],
        'calls': ['call_expression'],
    },
    'c_sharp': {
        'functions': ['method_declaration', 'constructor_declaration'],
        'classes': ['class_declaration', 'interface_declaration', 'struct_declaration'],
        'name_nodes': ['identifier'],
        'calls': ['invocation_expression'],
    },
    'go': {
        'functions': ['function_declaration', 'method_declaration', 'func_literal'],
        'classes': ['type_declaration', 'type_spec'],
        'name_nodes': ['identifier', 'type_identifier', 'field_identifier'],
        'calls': ['call_expression'],
    },
    'ruby': {
        'functions': ['method', 'singleton_method'],
        'classes': ['class', 'module'],
        'name_nodes': ['identifier', 'constant'],
        'calls': ['call'],
    },
    'php': {
        'functions': ['function_definition', 'method_declaration'],
        'classes': ['class_declaration', 'interface_declaration', 'trait_declaration'],
        'name_nodes': ['name', 'variable_name'],
        'calls': ['function_call_expression', 'scoped_call_expression', 'member_call_expression'],
    },
    'rust': {
        'functions': ['function_item', 'function_signature_item'],
        'classes': ['struct_item', 'enum_item', 'trait_item', 'impl_item'],
        'name_nodes': ['identifier'],
        'calls': ['call_expression'],
    },
    'swift': {
        'functions': ['function_declaration'],
        'classes': ['class_declaration', 'struct_declaration', 'enum_declaration', 'protocol_declaration'],
        'name_nodes': ['simple_identifier'],
        'calls': ['call_expression'],
    },
    'kotlin': {
        'functions': ['function_declaration'],
        'classes': ['class_declaration', 'object_declaration', 'interface_declaration'],
        'name_nodes': ['simple_identifier'],
        'calls': ['call_expression'],
    },
    'scala': {
        'functions': ['function_definition'],
        'classes': ['class_definition', 'object_definition', 'trait_definition'],
        'name_nodes': ['identifier'],
        'calls': ['call_expression'],
    },
    'java': {
        'functions': ['method_declaration'],
        'classes': ['class_declaration', 'interface_declaration', 'enum_declaration'],
        'name_nodes': ['identifier'],
        'calls': ['method_invocation'],
    },
    'lua': {
        'functions': ['function_declaration', 'function_definition'],
        'classes': ['table_constructor'],
        'name_nodes': ['identifier'],
        'calls': ['function_call'],
    },
    'dart': {
        'functions': ['function_declaration', 'method_declaration'],
        'classes': ['class_definition'],
        'name_nodes': ['identifier'],
        'calls': ['function_expression_invocation', 'selector_invocation'],
    },
    'elixir': {
        'functions': ['call', 'do_block'],
        'classes': ['alias'],
        'name_nodes': ['identifier', 'alias'],
        'calls': ['call'],
    },
    'haskell': {
        'functions': ['function'],
        'classes': ['data_type', 'class'],
        'name_nodes': ['variable', 'constructor'],
        'calls': ['term'],
    },
    'ocaml': {
        'functions': ['value_definition'],
        'classes': ['class_definition', 'class_type_definition'],
        'name_nodes': ['value_name', 'type_constructor'],
        'calls': ['infix_operator', 'prefix_operator'],
    },
    'julia': {
        'functions': ['function_definition'],
        'classes': ['struct_definition'],
        'name_nodes': ['identifier'],
        'calls': ['call_expression'],
    },
    'r': {
        'functions': ['function_definition'],
        'classes': [],
        'name_nodes': ['identifier'],
        'calls': ['call'],
    },
    'perl': {
        'functions': ['function_definition', 'method_declaration'],
        'classes': ['package_declaration'],
        'name_nodes': ['identifier'],
        'calls': ['function_call_expression'],
    },
    'bash': {
        'functions': ['function_definition'],
        'classes': [],
        'name_nodes': ['variable_name'],
        'calls': ['command'],
    },
    'sql': {
        'functions': ['function_definition'],
        'classes': ['create_table', 'create_view'],
        'name_nodes': ['object_reference', 'identifier'],
        'calls': [],
    },
}

def get_language_patterns(lang):
    """Get AST patterns for a language."""
    # Return language-specific patterns or generic fallback
    return LANGUAGE_PATTERNS.get(lang, {
        'functions': ['function_definition', 'function_declaration', 'function'],
        'classes': ['class_definition', 'class_declaration', 'class', 'struct'],
        'name_nodes': ['identifier', 'name'],
        'calls': ['call', 'call_expression', 'invocation'],
    })

def extract_symbols_from_node(node, lang, patterns, content: bytes) -> dict:
    """Extract comprehensive symbol info: name, calls, byte ranges, signature, params, docstring, metrics. (Features 3,4,5,7)"""
    name_node = None
    for child in node.children:
        if child.type in patterns['name_nodes']:
            name_node = child
            break
    if not name_node:
        for child in find_nodes(node, patterns['name_nodes']):
            name_node = child
            break
    if not name_node:
        return None

    name = get_node_text(name_node)
    if not name or len(name) > 100:
        return None

    # Feature 3: Byte ranges
    byte_range = extract_byte_range(node)

    # Feature 4: Signature, parameters, return type, modifiers
    signature = extract_signature(node, content)
    parameters = extract_parameters(node, lang) if node.type in patterns.get('functions', []) else []
    return_type = extract_return_type(node, lang) if node.type in patterns.get('functions', []) else None
    modifiers = extract_modifiers(node, lang)

    # Feature 5: Docstring and comments
    docstring = extract_docstring(node, lang)
    comments = extract_comments_in_body(node, lang, content)

    # Calls
    calls = []
    call_nodes = find_nodes(node, patterns['calls'])
    for call_node in call_nodes:
        for child in call_node.children:
            if child.type in patterns['name_nodes']:
                call_name = get_node_text(child)
                if call_name and len(call_name) < 100:
                    calls.append(call_name)

    # Feature 7: Metrics
    cyclomatic_complexity = calc_cyclomatic_complexity(node)
    max_nesting = calc_max_nesting(node, lang)

    return {
        'name': name,
        'byteRange': byte_range,
        'signature': signature,
        'parameters': parameters,
        'returnType': return_type,
        'modifiers': modifiers,
        'docstring': docstring,
        'comments': comments,
        'calls': list(set(calls)),
        'metrics': {
            'cyclomaticComplexity': cyclomatic_complexity,
            'maxNestingDepth': max_nesting,
        }
    }


# ============================================================
# Feature 8: Semantic relationship extraction
# ============================================================

def extract_semantic_relationships(node, lang, patterns, content: bytes) -> dict:
    """Extract inheritance, implementation, overrides. (Feature 8)"""
    rels = {'extends': [], 'implements': [], 'overrides': []}

    if lang in ('typescript', 'javascript'):
        # class Foo extends Bar implements Baz
        for child in node.children:
            if child.type == 'class_heritage':
                for hc in child.children:
                    if hc.type == 'extends_clause':
                        for gc in hc.children:
                            if gc.type in ('identifier', 'type_identifier'):
                                rels['extends'].append(get_node_text(gc))
                    elif hc.type == 'implements_clause':
                        for gc in hc.children:
                            if gc.type == 'type_identifier':
                                rels['implements'].append(get_node_text(gc))
    elif lang == 'java':
        for child in node.children:
            if child.type == 'superclass':
                for gc in child.children:
                    if gc.type == 'type_identifier':
                        rels['extends'].append(get_node_text(gc))
            elif child.type == 'superinterfaces':
                for gc in child.children:
                    if gc.type == 'type_identifier':
                        rels['implements'].append(get_node_text(gc))
    elif lang == 'python':
        # class Foo(Bar, Baz)
        for child in node.children:
            if child.type == 'argument_list':
                for gc in child.children:
                    if gc.type == 'identifier':
                        rels['extends'].append(get_node_text(gc))
    elif lang == 'go':
        # Embedding (implicit inheritance)
        for child in node.children:
            if child.type == 'field_declaration_list':
                for gc in child.children:
                    if gc.type == 'field_declaration' and gc.child_count > 0:
                        first = gc.child(0)
                        if first.type == 'type_identifier':
                            rels['extends'].append(get_node_text(first))
    elif lang == 'rust':
        # impl Trait for Type
        if node.type == 'impl_item':
            for child in node.children:
                if child.type == 'type_identifier':
                    rels['implements'].append(get_node_text(child))

    return rels

def extract_inheritance_info(data: dict):
    """Build inheritance graph from collected symbols. (Feature 8)"""
    inheritance = []
    for sym_id, sym in data['symbols'].items():
        rels = sym.get('semanticRelations', {})
        if rels.get('extends'):
            for parent in rels['extends']:
                # Try to resolve parent to actual symbol
                parent_id = None
                for sid, s in data['symbols'].items():
                    if s['name'] == parent and s['type'] == 'class':
                        parent_id = sid
                        break
                inheritance.append({
                    'child': sym_id,
                    'parent': parent,
                    'parentResolved': parent_id
                })
        if rels.get('implements'):
            for iface in rels['implements']:
                iface_id = None
                for sid, s in data['symbols'].items():
                    if s['name'] == iface and s['type'] == 'class':
                        iface_id = sid
                        break
                inheritance.append({
                    'child': sym_id,
                    'parent': iface,
                    'parentResolved': iface_id,
                    'relation': 'implements'
                })
    return inheritance


def extract_imports(tree, lang):
    """Extract import/dependency statements from the AST."""
    imports = []
    import_node_types = [
        'import_statement', 'import_from_statement', 'import_declaration',
        'import_spec', 'namespace_import_declaration', 'named_imports',
        'require_expression', 'include_statement',
        'package_declaration', 'use_statement'
    ]
    import_nodes = find_nodes(tree.root_node, import_node_types)
    for node in import_nodes:
        string_nodes = find_nodes(node, ['string', 'string_literal', 'raw_string_literal'])
        for str_node in string_nodes:
            imp = get_node_text(str_node).strip("'\"`@")
            if imp and len(imp) < 200:
                imports.append(imp)
        if not string_nodes:
            id_nodes = find_nodes(node, ['identifier', 'module', 'dotted_name', 'scoped_identifier'])
            for id_node in id_nodes:
                imp = get_node_text(id_node)
                if imp and len(imp) < 200:
                    imports.append(imp)
    return list(set(imports))


def calc_file_metrics(symbols: list, content: bytes) -> dict:
    """Calculate file-level quality metrics. (Feature 7)"""
    total_complexity = sum(s.get('metrics', {}).get('cyclomaticComplexity', 0) for s in symbols)
    total_funcs = len([s for s in symbols if s['type'] in ('function', 'method')])
    total_classes = len([s for s in symbols if s['type'] == 'class'])
    return {
        'totalFunctions': total_funcs,
        'totalClasses': total_classes,
        'avgComplexity': round(total_complexity / total_funcs, 1) if total_funcs > 0 else 0,
        'maxComplexity': max((s.get('metrics', {}).get('cyclomaticComplexity', 0) for s in symbols), default=0),
    }


def sanitize_name(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_]', '_', name).lower().strip('_')

def get_symbol_id(file_path: str, symbol_name: str) -> str:
    return f"{sanitize_name(file_path)}_{sanitize_name(symbol_name)}"

def parse_file(file_path: Path, project_root: Path, data: dict):
    """Parse a single file and extract symbols, imports, relationships. (Features 3,4,5,7,8)"""
    parser, lang, language = get_parser_for_file(file_path)
    if not parser:
        return

    rel_path = str(file_path.relative_to(project_root))
    try:
        content = file_path.read_bytes()
    except Exception as e:
        print(f"  Warning: Could not read {rel_path}: {e}")
        return

    try:
        tree = parser.parse(content)
    except Exception as e:
        print(f"  Warning: Could not parse {rel_path}: {e}")
        return

    if not tree or not tree.root_node:
        return

    data['files'][rel_path] = {
        'path': rel_path,
        'language': lang,
        'symbols': [],
        'imports': [],
        'used_by': [],
        'metrics': {}
    }

    patterns = get_language_patterns(lang)

    # Extract functions/methods
    func_nodes = find_nodes(tree.root_node, patterns['functions'])
    for func_node in func_nodes:
        info = extract_symbols_from_node(func_node, lang, patterns, content)
        if info:
            sym_type = 'function'
            class_node_types = patterns.get('classes', [])
            parent = func_node.parent
            while parent:
                if parent.type in class_node_types:
                    sym_type = 'method'
                    break
                parent = parent.parent

            # Feature 8: Semantic relationships
            semantic = extract_semantic_relationships(func_node, lang, patterns, content) if sym_type == 'class' else {}

            sym_id = get_symbol_id(rel_path, info['name'])
            if sym_id not in data['symbols']:
                data['symbols'][sym_id] = {
                    'name': info['name'],
                    'type': sym_type,
                    'file': rel_path,
                    'language': lang,
                    'byteRange': info['byteRange'],           # Feature 3
                    'signature': info['signature'],            # Feature 4
                    'parameters': info['parameters'],          # Feature 4
                    'returnType': info['returnType'],          # Feature 4
                    'modifiers': info['modifiers'],            # Feature 4
                    'docstring': info['docstring'],            # Feature 5
                    'comments': info['comments'],              # Feature 5
                    'calls': info['calls'],
                    'called_by': [],
                    'metrics': info['metrics'],               # Feature 7
                    'semanticRelations': semantic,             # Feature 8
                }
                data['files'][rel_path]['symbols'].append(sym_id)

    # Extract classes/structs/interfaces
    class_nodes = find_nodes(tree.root_node, patterns['classes'])
    for class_node in class_nodes:
        info = extract_symbols_from_node(class_node, lang, patterns, content)
        if info:
            # Feature 8: Semantic relationships for classes
            semantic = extract_semantic_relationships(class_node, lang, patterns, content)

            sym_id = get_symbol_id(rel_path, info['name'])
            if sym_id not in data['symbols']:
                data['symbols'][sym_id] = {
                    'name': info['name'],
                    'type': 'class',
                    'file': rel_path,
                    'language': lang,
                    'byteRange': info['byteRange'],
                    'signature': info['signature'],
                    'docstring': info['docstring'],
                    'comments': info['comments'],
                    'calls': [],
                    'called_by': [],
                    'metrics': info['metrics'],
                    'semanticRelations': semantic,
                }
                data['files'][rel_path]['symbols'].append(sym_id)

    # Extract imports
    data['files'][rel_path]['imports'] = extract_imports(tree, lang)

    # Feature 7: File-level metrics
    file_symbols = [data['symbols'][sid] for sid in data['files'][rel_path]['symbols'] if sid in data['symbols']]
    data['files'][rel_path]['metrics'] = calc_file_metrics(file_symbols, content)

def extract_relations(data: dict):
    """Resolve symbol calls to actual symbol IDs."""
    # Build a name-to-symbol-id index
    name_to_sym_id = {}
    for sym_id, sym in data['symbols'].items():
        if sym['name'] not in name_to_sym_id:
            name_to_sym_id[sym['name']] = []
        name_to_sym_id[sym['name']].append(sym_id)
    
    # Resolve calls - first collect all call resolutions
    for sym_id, sym in list(data['symbols'].items()):
        call_names = sym.get('calls', [])  # Get call names
        sym['calls'] = []  # Reset to store resolved symbol IDs
        
        for call_name in call_names:
            if call_name in name_to_sym_id:
                for target_id in name_to_sym_id[call_name]:
                    if target_id != sym_id:  # Don't add self-references
                        if target_id not in sym['calls']:
                            sym['calls'].append(target_id)
                        if sym_id not in data['symbols'][target_id]['called_by']:
                            data['symbols'][target_id]['called_by'].append(sym_id)
    
    # Build file-level dependencies from imports
    for path, info in data['files'].items():
        for imp in info['imports']:
            for target_path in data['files']:
                if path != target_path:  # Don't add self-references
                    # Match if import path is in target path or vice versa
                    imp_base = imp.split('.')[-1] if '.' in imp else imp
                    target_base = Path(target_path).stem
                    if imp_base == target_base or imp in target_path or target_path in imp:
                        if path not in data['files'][target_path]['used_by']:
                            data['files'][target_path]['used_by'].append(path)

def generate_markdown(out: Path, data: dict):
    """Generate markdown files with enhanced symbol info. (Features 3,4,5,7,8,14)"""
    if not data['files']:
        print("Warning: No files found to generate markdown.")
        return

    print(f"\nGenerating markdown files...")

    # Feature 14: Build domain groups
    domain_groups = build_domain_groups(data)

    # Generate meta overview
    from datetime import datetime
    (out / "00_meta").mkdir(parents=True, exist_ok=True)
    lang_dist = {}
    for path, info in data['files'].items():
        lang = info.get('language', 'unknown')
        lang_dist[lang] = lang_dist.get(lang, 0) + 1

    meta_content = f"""# Project Meta

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Overview
- **Total Files:** {len(data['files'])}
- **Total Symbols:** {len(data['symbols'])}
- **Languages:** {', '.join(sorted(lang_dist.keys()))}

## Language Distribution
{chr(10).join(f'- **{lang}:** {count} files' for lang, count in sorted(lang_dist.items(), key=lambda x: -x[1]))}

## Symbol Breakdown
- **Functions/Methods:** {sum(1 for s in data['symbols'].values() if s['type'] in ('function', 'method'))}
- **Classes:** {sum(1 for s in data['symbols'].values() if s['type'] == 'class')}

## Directory Structure
```
00_meta/          ← This file (project overview)
01_files/         ← Per-file documentation
02_symbols/       ← Function and class details
  functions/
  classes/
03_relations/     ← Call graph, dependency graph, inheritance
04_indexes/       ← Global indexes and domain groups
```
"""
    (out / "00_meta" / "project_overview.md").write_text(meta_content)

    # Generate file docs
    file_count = 0
    for path, info in data['files'].items():
        f = out / "01_files" / f"file_{sanitize_name(path)}.md"
        lang = info.get('language', 'unknown')
        metrics = info.get('metrics', {})

        c = f"# File: {path}\n\n"
        c += f"**Language:** `{lang}`\n\n"

        # Feature 7: Metrics
        if metrics:
            c += f"**Functions:** {metrics.get('totalFunctions', 0)} | "
            c += f"**Classes:** {metrics.get('totalClasses', 0)} | "
            c += f"**Avg Complexity:** {metrics.get('avgComplexity', 0)}\n\n"

        if info['symbols']:
            c += "## Contains\n" + "\n".join([
                f"- [[{'class' if data['symbols'][s]['type']=='class' else 'fn'}_{s}]]"
                for s in info['symbols']
            ]) + "\n\n"

        if info['imports']:
            c += "## Imports\n" + "\n".join([f"- `{imp}`" for imp in sorted(info['imports'])[:50]]) + "\n\n"

        if info['used_by']:
            c += "## Used By\n" + "\n".join([f"- [[file_{sanitize_name(p)}]]" for p in info['used_by']]) + "\n"

        f.write_text(c)
        file_count += 1
    print(f"  ✓ Created {file_count} file docs")

    # Generate symbol docs
    func_count = 0
    class_count = 0
    for sid, sym in data['symbols'].items():
        pre = 'class' if sym['type'] == 'class' else 'fn'
        sym_dir = "classes" if sym['type'] == 'class' else "functions"
        f = out / "02_symbols" / sym_dir / f"{pre}_{sid}.md"

        lang = sym.get('language', 'unknown')
        c = f"# {sym['type'].capitalize()}: {sym['name']}\n\n"
        c += f"**Language:** `{lang}`  \n"
        c += f"**Defined In:** [[file_{sanitize_name(sym['file'])}]]\n\n"

        # Feature 4: Signature
        if sym.get('signature'):
            c += f"```{lang}\n{sym['signature']}\n```\n\n"

        # Feature 4: Parameters
        if sym.get('parameters'):
            c += "## Parameters\n"
            for p in sym['parameters']:
                type_str = f": `{p['type']}`" if p.get('type') else ""
                c += f"- `{p['name']}`{type_str}\n"
            c += "\n"

        # Feature 4: Return type
        if sym.get('returnType'):
            c += f"**Returns:** `{sym['returnType']}`\n\n"

        # Feature 4: Modifiers
        if sym.get('modifiers'):
            c += f"**Modifiers:** {', '.join(f'`{m}`' for m in sym['modifiers'])}\n\n"

        # Feature 5: Docstring
        if sym.get('docstring'):
            doc_preview = sym['docstring'][:300]
            c += f"## Docstring\n{doc_preview}\n\n"

        # Feature 5: TODO/FIXME comments
        if sym.get('comments'):
            c += "## Notes\n"
            for cm in sym['comments']:
                c += f"- Line {cm['line']}: {cm['text']}\n"
            c += "\n"

        # Feature 3: Byte range
        if sym.get('byteRange'):
            br = sym['byteRange']
            c += f"**Location:** Lines {br['startLine']+1}-{br['endLine']+1}\n\n"

        # Feature 7: Metrics
        if sym.get('metrics'):
            m = sym['metrics']
            c += f"**Complexity:** {m.get('cyclomaticComplexity', '?')} | "
            c += f"**Nesting:** {m.get('maxNestingDepth', '?')}\n\n"

        if sym['calls']:
            c += "## Calls\n" + "\n".join([
                f"- [[{'class' if data['symbols'][x]['type']=='class' else 'fn'}_{x}]]"
                for x in sym['calls'][:50]
            ]) + "\n\n"

        if sym['called_by']:
            c += "## Called By\n" + "\n".join([
                f"- [[{'class' if data['symbols'][x]['type']=='class' else 'fn'}_{x}]]"
                for x in sym['called_by'][:50]
            ]) + "\n\n"

        # Feature 8: Semantic relationships
        if sym.get('semanticRelations'):
            rels = sym['semanticRelations']
            if rels.get('extends'):
                c += f"**Extends:** {', '.join(f'`{e}`' for e in rels['extends'])}\n\n"
            if rels.get('implements'):
                c += f"**Implements:** {', '.join(f'`{i}`' for i in rels['implements'])}\n\n"

        c += f"## Tags\n`{sym['type']}` `{lang}`\n"
        f.write_text(c)

        if sym['type'] == 'class':
            class_count += 1
        else:
            func_count += 1

    print(f"  ✓ Created {func_count} function/method docs")
    print(f"  ✓ Created {class_count} class/struct docs")

    # Generate relation graphs
    call_graph_lines = []
    for s, sym in data['symbols'].items():
        if sym['type'] != 'class':
            for c in sym['calls']:
                call_graph_lines.append(f"- [[fn_{s}]] -> [[fn_{c}]]")

    call_graph_content = "# Call Graph\n\n"
    if call_graph_lines:
        call_graph_content += "\n".join(call_graph_lines)
    else:
        call_graph_content += "No call relationships found."
    (out / "03_relations" / "call_graph.md").write_text(call_graph_content)

    dep_graph_lines = []
    for p, info in data['files'].items():
        for u in info['used_by']:
            dep_graph_lines.append(f"- [[file_{sanitize_name(p)}]] -> [[file_{sanitize_name(u)}]]")
    dep_graph_content = "# Dependency Graph\n\n"
    if dep_graph_lines:
        dep_graph_content += "\n".join(dep_graph_lines)
    else:
        dep_graph_content += "No dependencies found."
    (out / "03_relations" / "dependency_graph.md").write_text(dep_graph_content)

    # Feature 8: Inheritance graph
    inheritance = extract_inheritance_info(data)
    if inheritance:
        inh_lines = [f"- `{i['child'].split('_')[-1]}` → `{i['parent']}`" + (f" (implements)" if i.get('relation') == 'implements' else "") for i in inheritance]
        (out / "03_relations" / "inheritance_graph.md").write_text("# Inheritance Graph\n\n" + "\n".join(inh_lines))

    # Feature 14: Domain grouping
    if domain_groups:
        domain_content = "# Domain Groups\n\n"
        for domain, files in sorted(domain_groups.items()):
            domain_content += f"## {domain}\n\n"
            for fp in sorted(files):
                domain_content += f"- [[file_{sanitize_name(fp)}]]\n"
            domain_content += "\n"
        (out / "04_indexes" / "domain_groups.md").write_text(domain_content)

    # Generate indexes
    (out / "04_indexes" / "all_files.md").write_text(
        "# All Files\n\n" + "\n".join([f"- [[file_{sanitize_name(p)}]] ({data['files'][p].get('language', 'unknown')})" for p in sorted(data['files'].keys())])
    )
    (out / "04_indexes" / "all_functions.md").write_text(
        "# All Functions\n\n" + "\n".join([
            f"- [[fn_{s}]] ({sym.get('language', 'unknown')})"
            for s, sym in data['symbols'].items()
            if sym['type'] in ['function', 'method']
        ])
    )
    (out / "04_indexes" / "all_classes.md").write_text(
        "# All Classes\n\n" + "\n".join([
            f"- [[class_{s}]] ({sym.get('language', 'unknown')})"
            for s, sym in data['symbols'].items()
            if sym['type'] == 'class'
        ])
    )


def build_domain_groups(data: dict) -> dict:
    """Group files by directory/domain. (Feature 14)"""
    domains = {}
    for path in data['files'].keys():
        parts = Path(path).parts
        if len(parts) > 1:
            domain = parts[0]  # Top-level directory as domain
            if domain not in domains:
                domains[domain] = []
            domains[domain].append(path)
        else:
            if 'root' not in domains:
                domains['root'] = []
            domains['root'].append(path)
    return domains


# ============================================================
# JSON output mode and query interface (for pipeline integration)
# ============================================================

def generate_json_index(data: dict) -> list:
    """Generate JSON index matching ast_indexer.py format. For pipeline integration."""
    index = []
    for sym_id, sym in data['symbols'].items():
        entry = {
            'name': sym['name'],
            'filePath': sym['file'],
            'type': sym['type'],
            'language': sym.get('language', 'unknown'),
        }
        # Feature 3: Byte ranges
        if sym.get('byteRange'):
            entry.update(sym['byteRange'])
        # Feature 4: Signature
        if sym.get('signature'):
            entry['signature'] = sym['signature']
        if sym.get('parameters'):
            entry['parameters'] = sym['parameters']
        if sym.get('returnType'):
            entry['returnType'] = sym['returnType']
        # Feature 5: Docstring
        if sym.get('docstring'):
            entry['docstring'] = sym['docstring']
        # Calls
        entry['calls'] = sym.get('calls', [])
        # Feature 7: Metrics
        if sym.get('metrics'):
            entry['metrics'] = sym['metrics']
        # Feature 8: Semantic relationships
        if sym.get('semanticRelations'):
            entry['semanticRelations'] = sym['semanticRelations']
        index.append(entry)
    return index


def generate_json_summary(data: dict) -> dict:
    """Generate JSON summary matching ast_indexer summary format."""
    dirs = {}
    for sym_id, sym in data['symbols'].items():
        d = str(Path(sym['file']).parent)
        dirs[d] = dirs.get(d, 0) + 1

    symbol_counts = {}
    for sym_id, sym in data['symbols'].items():
        symbol_counts[sym['name']] = symbol_counts.get(sym['name'], 0) + 1
    top_symbols = sorted(symbol_counts.items(), key=lambda x: -x[1])[:5]

    return {
        'totalFiles': len(data['files']),
        'totalSymbols': len(data['symbols']),
        'directories': dirs,
        'topSymbols': [name for name, count in top_symbols],
        'languages': {},
    }


def get_symbol_code(sym_id: str, data: dict, project_root: Path) -> dict:
    """Extract actual source code for a symbol using byte ranges."""
    sym = data['symbols'].get(sym_id)
    if not sym:
        return {'error': f'Symbol {sym_id} not found'}
    if not sym.get('byteRange'):
        return {'error': 'No byte range available'}

    file_path = project_root / sym['file']
    try:
        with open(file_path, 'rb') as f:
            br = sym['byteRange']
            f.seek(br['startByte'])
            code = f.read(br['endByte'] - br['startByte']).decode('utf-8', errors='replace')
        return {
            'name': sym['name'],
            'filePath': sym['file'],
            'startLine': br['startLine'] + 1,
            'endLine': br['endLine'] + 1,
            'signature': sym.get('signature'),
            'docstring': sym.get('docstring'),
            'code': code,
            'calls': sym.get('calls', []),
        }
    except FileNotFoundError:
        return {'error': f'File not found: {file_path}'}
    except Exception as e:
        return {'error': str(e)}


def search_symbols_json(query: str, data: dict) -> list:
    """Search symbols by query words in name, docstring, signature."""
    matches = []
    query_words = query.lower().split()
    for sym_id, sym in data['symbols'].items():
        score = 0
        text = f"{sym.get('name', '')} {sym.get('docstring', '')} {sym.get('signature', '')}".lower()
        for word in query_words:
            if word in text:
                score += 1
        if score > 0:
            matches.append({'score': score, 'id': sym_id, 'name': sym['name'],
                          'file': sym['file'], 'type': sym['type'],
                          'language': sym.get('language', 'unknown')})
    matches.sort(key=lambda x: (-x['score'], x['name']))
    return matches[:5]


def find_callers_json(symbol_name: str, data: dict) -> list:
    """Find all symbols that call the given symbol."""
    callers = []
    for sym_id, sym in data['symbols'].items():
        if symbol_name in sym.get('calls', []):
            callers.append({
                'name': sym['name'],
                'filePath': sym['file'],
                'type': sym['type'],
            })
    return callers


# ============================================================
# Main
# ============================================================

def main():
    arg_parser = argparse.ArgumentParser(
        description="Analyze code and generate context markdown/JSON files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze entire project (auto-detect languages, markdown output)
  python context-creator.py /path/to/project

  # Generate JSON index (pipeline-compatible)
  python context-creator.py /path/to/project --format json --out ./code-index.json

  # Analyze only Python and JavaScript files
  python context-creator.py /path/to/project --languages python,javascript

  # Query a JSON index
  python context-creator.py --query search "authentication" --index ./code-index.json
  python context-creator.py --query callers "processPayment" --index ./code-index.json
  python context-creator.py --query summary --index ./code-index.json
  python context-creator.py --query fetch "myFunc" --index ./code-index.json --root /path/to/project

  # List all supported languages
  python context-creator.py --list-languages
        """
    )
    arg_parser.add_argument("root", type=str, nargs='?', help="Root directory of the project to analyze")
    arg_parser.add_argument("--out", type=str, default=None, help="Output directory or file")
    arg_parser.add_argument("--format", choices=['markdown', 'json'], default='markdown', help="Output format")
    arg_parser.add_argument("--languages", type=str, default=None, help="Comma-separated language filter")
    arg_parser.add_argument("--list-languages", action='store_true', help="List all supported languages")
    arg_parser.add_argument("--query", type=str, choices=['search', 'fetch', 'callers', 'file_symbols', 'summary'],
                           help="Query mode: action to perform on an existing JSON index")
    arg_parser.add_argument("--query-arg", type=str, help="Query argument (symbol name, search term, or file path)")
    arg_parser.add_argument("--index", type=str, help="Path to code-index.json for query mode")

    args = arg_parser.parse_args()

    # List languages mode
    if args.list_languages:
        if not HAS_LANGUAGE_PACK:
            print("Error: tree-sitter-language-pack not installed")
            sys.exit(1)
        try:
            langs = available_languages()
            if not langs:
                print("Downloading language list...")
                download_all()
                langs = available_languages()
            print(f"\nSupported Languages ({len(langs)} total):\n")
            for lang in sorted(langs):
                exts = [ext for l, exts in LANGUAGE_EXTENSIONS.items() for ext in exts if l == lang]
                ext_str = f" ({', '.join(exts[:5])})" if exts else ""
                print(f"  {lang}{ext_str}")
            print()
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
        return

    # Query mode
    if args.query:
        if not args.index:
            print("Error: --index required for query mode")
            sys.exit(1)
        try:
            with open(args.index) as f:
                index_data = json.load(f)
        except FileNotFoundError:
            print(f"Error: Index file not found: {args.index}")
            sys.exit(1)

        if args.query == 'search':
            if not args.query_arg:
                print("Error: --query-arg required for search")
                sys.exit(1)
            results = []
            query_words = args.query_arg.lower().split()
            for sym in index_data:
                score = 0
                text = f"{sym.get('name', '')} {sym.get('docstring', '')} {sym.get('signature', '')}".lower()
                for word in query_words:
                    if word in text:
                        score += 1
                if score > 0:
                    results.append({'score': score, **sym})
            results.sort(key=lambda x: (-x['score'], x.get('name', '')))
            print(json.dumps(results[:5], indent=2))

        elif args.query == 'fetch':
            if not args.query_arg:
                print("Error: --query-arg required for fetch")
                sys.exit(1)
            found = None
            for sym in index_data:
                if sym['name'] == args.query_arg:
                    found = sym
                    break
            if not found:
                print(json.dumps({'error': f"Symbol '{args.query_arg}' not found"}))
                return
            root = Path(args.root).resolve() if args.root else Path('.').resolve()
            file_path = root / found['filePath']
            try:
                with open(file_path, 'rb') as f:
                    f.seek(found['startByte'])
                    code = f.read(found['endByte'] - found['startByte']).decode('utf-8', errors='replace')
                found['code'] = code
            except:
                pass
            print(json.dumps(found, indent=2))

        elif args.query == 'callers':
            if not args.query_arg:
                print("Error: --query-arg required for callers")
                sys.exit(1)
            callers = []
            for sym in index_data:
                if args.query_arg in sym.get('calls', []):
                    callers.append({'name': sym['name'], 'filePath': sym['filePath'], 'type': sym.get('type', 'function')})
            print(json.dumps(callers, indent=2))

        elif args.query == 'file_symbols':
            if not args.query_arg:
                print("Error: --query-arg required for file_symbols")
                sys.exit(1)
            file_syms = [sym for sym in index_data if sym['filePath'] == args.query_arg]
            print(json.dumps(file_syms, indent=2))

        elif args.query == 'summary':
            dirs = {}
            symbol_counts = {}
            for sym in index_data:
                d = str(Path(sym['filePath']).parent)
                dirs[d] = dirs.get(d, 0) + 1
                symbol_counts[sym['name']] = symbol_counts.get(sym['name'], 0) + 1
            top = sorted(symbol_counts.items(), key=lambda x: -x[1])[:5]
            print(json.dumps({
                'totalFiles': len(set(sym['filePath'] for sym in index_data)),
                'totalSymbols': len(index_data),
                'directories': dirs,
                'topSymbols': [name for name, count in top]
            }, indent=2))
        return

    # Index mode (default)
    if not args.root:
        arg_parser.print_help()
        sys.exit(1)

    root = Path(args.root).resolve()

    if not root.exists():
        print(f"Error: Root directory does not exist: {root}")
        sys.exit(1)
    if not root.is_dir():
        print(f"Error: Root path is not a directory: {root}")
        sys.exit(1)

    # Default output: ~/contx/<project-name>/
    out_str = args.out if args.out else None
    if out_str:
        out = Path(out_str).expanduser().resolve()
    else:
        project_name = sanitize_name(root.name) or "unnamed_project"
        out = Path.home() / "contx" / project_name
    out = out.resolve()

    target_languages = None
    if args.languages:
        target_languages = [l.strip().lower() for l in args.languages.split(',')]
        print(f"Language filter: {', '.join(target_languages)}\n")

    print(f"Analyzing: {root}")
    print(f"Output to: {out}")
    print(f"Format: {args.format}\n")

    # Create output directories (for markdown mode)
    if args.format == 'markdown':
        for p in ["00_meta", "01_files", "02_symbols/functions", "02_symbols/classes", "03_relations", "04_indexes"]:
            (out / p).mkdir(parents=True, exist_ok=True)

    # Build parsers with lazy loading (Feature 10)
    build_parsers(target_languages, project_root=root)

    if not PARSERS:
        print("Error: No parsers loaded.")
        sys.exit(1)

    # Initialize data
    data = {'files': {}, 'symbols': {}}

    supported_exts = set()
    for exts in LANGUAGE_EXTENSIONS.values():
        supported_exts.update(exts)

    # Walk and parse files
    file_count = 0
    lang_stats = {}

    print(f"\nScanning files...")
    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', 'venv', '.venv', '__pycache__',
                                                 '.next', 'dist', 'build', 'target', 'bin', 'obj',
                                                 '.cache', '.idea', '.vscode', '.obsidian']]
        if str(out).startswith(r):
            continue

        for file in files:
            file_path = Path(r) / file
            if file_path.suffix.lower() in supported_exts or file_path.name in LANGUAGE_EXTENSIONS.get('dockerfile', []) or file_path.name in LANGUAGE_EXTENSIONS.get('make', []):
                parse_file(file_path, root, data)
                file_count += 1
                if file_path.suffix.lower() in supported_exts:
                    for lang, exts in LANGUAGE_EXTENSIONS.items():
                        if file_path.suffix.lower() in exts:
                            lang_stats[lang] = lang_stats.get(lang, 0) + 1
                            break

    print(f"\n📊 Statistics:")
    print(f"  Files scanned: {file_count}")
    print(f"  Files with symbols: {len(data['files'])}")
    print(f"  Total symbols: {len(data['symbols'])}")
    if lang_stats:
        print(f"\n  Files by language:")
        for lang, count in sorted(lang_stats.items(), key=lambda x: x[1], reverse=True)[:20]:
            print(f"    {lang}: {count}")
        if len(lang_stats) > 20:
            print(f"    ... and {len(lang_stats) - 20} more languages")

    # Build relations
    print(f"\nExtracting relations...")
    extract_relations(data)

    # Generate output
    if args.format == 'json':
        # JSON output (pipeline-compatible)
        if str(out).endswith('.json'):
            index_path = out
        else:
            out.mkdir(parents=True, exist_ok=True)
            index_path = out / 'code-index.json'
        index_data = generate_json_index(data)
        with open(index_path, 'w') as f:
            json.dump(index_data, f, indent=2)
        print(f"\n✓ Wrote {len(index_data)} symbols to {index_path}")

        # Also write summary
        summary_path = index_path.parent / 'code-summary.json'
        summary = generate_json_summary(data)
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"✓ Wrote summary to {summary_path}")
    else:
        # Markdown output
        generate_markdown(out, data)
        print(f"\n✓ Done. Context generated at: {out}")

if __name__ == "__main__":
    main()
