import tree_sitter_language_pack as ts_pack
from tree_sitter import Parser, Query, QueryCursor

lang = ts_pack.get_language("css")
parser = Parser(lang)
css_content = b"""
@import url("fonts.css");
@import 'reset.css';
body { background: url('bg.png'); }
"""
tree = parser.parse(css_content)

query_str = """
(import_statement (string_value) @import)
(import_statement (call_expression (arguments (string_value) @import)))
"""

try:
    query = Query(lang, query_str)
    cursor = QueryCursor(query)
    captures = cursor.captures(tree.root_node)
    print("CAPTURES:", captures)
except Exception as e:
    print("ERROR:", e)
