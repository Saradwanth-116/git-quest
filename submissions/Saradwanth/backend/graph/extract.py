"""Tree-sitter based extraction of imports, definitions, and identifiers.

Uses the verified per-language queries from docs/GRAPH_EXTRACTION.md.
Two bugs in the naive rules are addressed here:
  1. PHP uses `name` not `identifier` — use is_named + IDENT_RE instead
  2. Ruby `require` is a call node, not an import statement

Supports three coverage tiers:
  - deep:            14 languages with hand-written import + definition queries
  - occurrence-only: grammar loads but no import query — identifiers still extracted
  - unparseable:     grammar not in the language pack (rare — 371 covered)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Optional

from tree_sitter_language_pack import get_parser

# ---------------------------------------------------------------------------
# Universal identifier rule — verified on 16/16 languages
# The design doc's "identifier in node.type" fails on PHP.
# ---------------------------------------------------------------------------

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _walk(node):
    """Depth-first walk of all nodes in a tree-sitter tree."""
    yield node
    for child in node.children:
        yield from _walk(child)


def _leaves(node):
    """Yield only leaf nodes (no children)."""
    if not node.children:
        yield node
    for c in node.children:
        yield from _leaves(c)


def identifiers(source: bytes, lang: str) -> set[str]:
    """Grammar-agnostic identifier extraction. Works on all 371 languages.

    Uses is_named to skip punctuation/anonymous tokens, then IDENT_RE to
    filter out strings, numbers, and operators the grammar exposes as leaves.
    """
    try:
        parser = get_parser(lang)
    except Exception:
        return set()
    root = parser.parse(source).root_node
    out: set[str] = set()
    for leaf in _leaves(root):
        if not leaf.is_named:
            continue
        text = source[leaf.start_byte:leaf.end_byte].decode(errors="replace")
        if IDENT_RE.match(text):
            out.add(text)
    return out


# ---------------------------------------------------------------------------
# Language detection from file extension
# ---------------------------------------------------------------------------

_EXT_TO_LANG: dict[str, str] = {
    ".py":    "python",
    ".js":    "javascript",
    ".jsx":   "javascript",
    ".ts":    "typescript",
    ".tsx":   "tsx",
    ".java":  "java",
    ".go":    "go",
    ".rs":    "rust",
    ".c":     "c",
    ".h":     "c",
    ".cpp":   "cpp",
    ".cc":    "cpp",
    ".cxx":   "cpp",
    ".hpp":   "cpp",
    ".hxx":   "cpp",
    ".cs":    "c_sharp",
    ".rb":    "ruby",
    ".php":   "php",
    ".kt":    "kotlin",
    ".kts":   "kotlin",
    ".swift": "swift",
    ".scala": "scala",
    ".lua":   "lua",
    ".ex":    "elixir",
    ".exs":   "elixir",
    ".html":  "html",
    ".htm":   "html",
    ".css":   "css",
}

# The 14 deep-tier languages that have hand-written import + definition queries.
# Swift, Scala, Lua, Elixir have grammars but no import queries — occurrence-only.
DEEP_TIER_LANGS = frozenset({
    "python", "javascript", "typescript", "tsx", "java", "go", "rust",
    "c", "cpp", "c_sharp", "ruby", "php", "kotlin", "html", "css",
})


def detect_language(path: str) -> Optional[str]:
    """Detect tree-sitter language name from file extension. Returns None if unknown."""
    ext = PurePosixPath(path).suffix.lower()
    return _EXT_TO_LANG.get(ext)


def coverage_tier(lang: Optional[str]) -> str:
    """Return the coverage tier for a language."""
    if lang is None:
        return "unparseable"
    if lang in DEEP_TIER_LANGS:
        return "deep"
    # Check if the grammar can actually load
    try:
        get_parser(lang)
        return "occurrence-only"
    except Exception:
        return "unparseable"


# ---------------------------------------------------------------------------
# Import extraction — per-language, verified node types from GRAPH_EXTRACTION.md
# ---------------------------------------------------------------------------

def _text(source: bytes, node) -> str:
    """Extract text content of a tree-sitter node."""
    return source[node.start_byte:node.end_byte].decode(errors="replace")


def _python_imports(source: bytes, root) -> list[str]:
    """Extract Python imports: import_statement, import_from_statement."""
    results = []
    for node in _walk(root):
        if node.type == "import_statement":
            # import foo, bar  →  dotted names are children
            for child in node.children:
                if child.type == "dotted_name":
                    results.append(_text(source, child))
        elif node.type == "import_from_statement":
            # from foo.bar import baz  →  the module is the first dotted_name
            module = node.child_by_field_name("module_name")
            if module:
                results.append(_text(source, module))
            else:
                # Fallback: look for the first dotted_name child
                for child in node.children:
                    if child.type in ("dotted_name", "relative_import"):
                        results.append(_text(source, child))
                        break
    return results


def _js_imports(source: bytes, root) -> list[str]:
    """Extract JS/TS imports: import_statement + require() calls."""
    results = []
    for node in _walk(root):
        if node.type == "import_statement":
            # import ... from "module"  →  string child is the source
            src = node.child_by_field_name("source")
            if src:
                raw = _text(source, src).strip("'\"")
                results.append(raw)
        elif node.type == "call_expression":
            # require("module")
            fn = node.child_by_field_name("function")
            if fn and _text(source, fn) == "require":
                args = node.child_by_field_name("arguments")
                if args and args.child_count > 0:
                    for arg_child in args.children:
                        if arg_child.type == "string":
                            raw = _text(source, arg_child).strip("'\"")
                            results.append(raw)
                            break
    return results


def _java_imports(source: bytes, root) -> list[str]:
    """Extract Java imports: import_declaration."""
    results = []
    for node in _walk(root):
        if node.type == "import_declaration":
            # import com.example.Foo;
            for child in node.children:
                if child.type == "scoped_identifier":
                    results.append(_text(source, child))
                    break
    return results


def _go_imports(source: bytes, root) -> list[str]:
    """Extract Go imports: import_declaration, import_spec."""
    results = []
    for node in _walk(root):
        if node.type == "import_spec":
            # The path is an interpreted_string_literal child
            path_node = node.child_by_field_name("path")
            if path_node:
                raw = _text(source, path_node).strip('"')
                results.append(raw)
    return results


def _rust_imports(source: bytes, root) -> list[str]:
    """Extract Rust imports: use_declaration."""
    results = []
    for node in _walk(root):
        if node.type == "use_declaration":
            # use std::io::Read;  →  the argument is the path
            for child in node.children:
                if child.type not in ("use", ";"):
                    results.append(_text(source, child))
                    break
    return results


def _c_cpp_imports(source: bytes, root) -> list[str]:
    """Extract C/C++ includes: preproc_include."""
    results = []
    for node in _walk(root):
        if node.type == "preproc_include":
            # #include <header> or #include "header"
            path_node = node.child_by_field_name("path")
            if path_node:
                raw = _text(source, path_node).strip('<>"')
                results.append(raw)
    return results


def _csharp_imports(source: bytes, root) -> list[str]:
    """Extract C# imports: using_directive."""
    results = []
    for node in _walk(root):
        if node.type == "using_directive":
            # using System.IO;
            for child in node.children:
                if child.type in ("qualified_name", "identifier"):
                    results.append(_text(source, child))
                    break
    return results


def _ruby_imports(source: bytes, root) -> list[str]:
    """Extract Ruby imports: require/require_relative/load/autoload calls.

    Ruby's grammar treats these as call nodes, not import statements.
    This is the special case documented in GRAPH_EXTRACTION.md.
    """
    results = []
    for node in _walk(root):
        if node.type != "call":
            continue
        method = node.child_by_field_name("method")
        if method is None:
            continue
        name = _text(source, method)
        if name in ("require", "require_relative", "load", "autoload"):
            args = node.child_by_field_name("arguments")
            if args and args.child_count > 0:
                for arg_child in args.children:
                    if arg_child.is_named:
                        raw = _text(source, arg_child).strip("'\"")
                        results.append(raw)
                        break
    return results


def _php_imports(source: bytes, root) -> list[str]:
    """Extract PHP imports: namespace_use_declaration + require/include calls."""
    results = []
    for node in _walk(root):
        if node.type == "namespace_use_declaration":
            for child in _walk(node):
                if child.type == "qualified_name":
                    results.append(_text(source, child))
        elif node.type == "call_expression":
            # require_once, include, include_once
            fn = node.child_by_field_name("function")
            if fn and _text(source, fn) in (
                "require", "require_once", "include", "include_once",
            ):
                args = node.child_by_field_name("arguments")
                if args:
                    for child in args.children:
                        if child.is_named:
                            raw = _text(source, child).strip("'\"")
                            results.append(raw)
                            break
    return results


def _kotlin_imports(source: bytes, root) -> list[str]:
    """Extract Kotlin imports: import_header."""
    results = []
    for node in _walk(root):
        if node.type == "import_header":
            # import com.example.Foo
            ident = node.child_by_field_name("identifier")
            if ident:
                results.append(_text(source, ident))
    return results


def _html_imports(source: bytes, root) -> list[str]:
    """Extract HTML imports: <link href="..."> and <script src="...">"""
    results = []
    for node in _walk(root):
        if node.type == "attribute":
            attr_name = node.child_by_field_name("attribute_name")
            if attr_name and _text(source, attr_name) in ("href", "src"):
                val = node.child_by_field_name("quoted_attribute_value")
                if val:
                    inner = val.child_by_field_name("attribute_value")
                    if inner:
                        results.append(_text(source, inner))
    return results


def _css_imports(source: bytes, root) -> list[str]:
    """Extract CSS imports: @import url(...) and @import '...'"""
    results = []
    for node in _walk(root):
        if node.type == "import_statement":
            for child in _walk(node):
                if child.type == "string_value":
                    results.append(_text(source, child).strip("'\""))
                    break
    return results


_IMPORT_EXTRACTORS: dict[str, callable] = {
    "python":     _python_imports,
    "javascript": _js_imports,
    "typescript":  _js_imports,
    "tsx":         _js_imports,
    "java":       _java_imports,
    "go":         _go_imports,
    "rust":       _rust_imports,
    "c":          _c_cpp_imports,
    "cpp":        _c_cpp_imports,
    "c_sharp":    _csharp_imports,
    "ruby":       _ruby_imports,
    "php":        _php_imports,
    "kotlin":     _kotlin_imports,
    "html":       _html_imports,
    "css":        _css_imports,
}


def imports(source: bytes, lang: str) -> list[str]:
    """Extract import paths/modules from source in the given language.

    Returns an empty list for occurrence-only and unparseable languages.
    """
    extractor = _IMPORT_EXTRACTORS.get(lang)
    if extractor is None:
        return []
    try:
        parser = get_parser(lang)
    except Exception:
        return []
    root = parser.parse(source).root_node
    return extractor(source, root)


# ---------------------------------------------------------------------------
# Definition extraction — per-language, verified node types
# ---------------------------------------------------------------------------

# Maps language → set of node types that represent definitions
_DEFINITION_TYPES: dict[str, set[str]] = {
    "python":      {"function_definition", "class_definition"},
    "javascript":  {"function_declaration", "class_declaration", "method_definition"},
    "typescript":  {"function_declaration", "class_declaration", "method_definition"},
    "tsx":         {"function_declaration", "class_declaration", "method_definition"},
    "java":        {"class_declaration", "method_declaration", "interface_declaration"},
    "go":          {"function_declaration", "method_declaration", "type_declaration"},
    "rust":        {"function_item", "struct_item", "impl_item", "trait_item", "enum_item"},
    "c":           {"function_definition", "struct_specifier"},
    "cpp":         {"function_definition", "class_specifier", "struct_specifier"},
    "c_sharp":     {"class_declaration", "method_declaration", "interface_declaration"},
    "ruby":        {"method", "class", "module"},
    "php":         {"function_definition", "class_declaration", "method_declaration"},
    "kotlin":      {"function_declaration", "class_declaration"},
}


@dataclass
class Definition:
    """A symbol definition extracted from source."""
    name: str
    kind: str       # "function", "class", "method", etc.
    line: int       # 1-indexed


def definitions(source: bytes, lang: str) -> list[Definition]:
    """Extract symbol definitions from source in the given language."""
    types = _DEFINITION_TYPES.get(lang)
    if types is None:
        return []
    try:
        parser = get_parser(lang)
    except Exception:
        return []
    root = parser.parse(source).root_node
    results: list[Definition] = []
    for node in _walk(root):
        if node.type not in types:
            continue
        # Try common field names for the definition name
        name_node = (
            node.child_by_field_name("name")
            or node.child_by_field_name("declarator")
        )
        if name_node is None:
            continue
        name = _text(source, name_node)
        # Simplify node type to a human-readable kind
        kind = node.type.replace("_declaration", "").replace("_definition", "")
        kind = kind.replace("_item", "").replace("_specifier", "")
        results.append(Definition(
            name=name,
            kind=kind,
            line=node.start_point[0] + 1,  # tree-sitter is 0-indexed
        ))
    return results


# ---------------------------------------------------------------------------
# Combined extraction — the main entry point
# ---------------------------------------------------------------------------

@dataclass
class FileNode:
    """Extraction result for a single file."""
    path: str                            # repo-relative, POSIX separators
    lang: Optional[str]                  # tree-sitter language name
    tier: str                            # "deep", "occurrence-only", "unparseable"
    import_paths: list[str] = field(default_factory=list)
    defs: list[Definition] = field(default_factory=list)
    idents: set[str] = field(default_factory=set)


def extract_file(source: bytes, path: str, lang: Optional[str] = None) -> FileNode:
    """Extract imports, definitions, and identifiers from a single file.

    Args:
        source: raw file content as bytes
        path:   repo-relative path (POSIX separators)
        lang:   tree-sitter language name; auto-detected from extension if None

    Returns:
        FileNode with all extraction results and coverage tier.
    """
    if lang is None:
        lang = detect_language(path)

    tier = coverage_tier(lang)

    if tier == "unparseable":
        return FileNode(path=path, lang=lang, tier=tier)

    idents = identifiers(source, lang) if lang else set()
    import_paths = imports(source, lang) if lang and tier == "deep" else []
    defs = definitions(source, lang) if lang and tier == "deep" else []

    return FileNode(
        path=path,
        lang=lang,
        tier=tier,
        import_paths=import_paths,
        defs=defs,
        idents=idents,
    )
