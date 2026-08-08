import tree_sitter_language_pack as ts_pack
from tree_sitter import Parser, Query, QueryCursor

lang = ts_pack.get_language("html")
parser = Parser(lang)
html_content = b"""
<html>
<head>
  <link rel="stylesheet" href="style.css" />
  <script src="js/script.js"></script>
</head>
</html>
"""
tree = parser.parse(html_content)

query_str = """
(attribute
  (attribute_name) @attr_name
  (quoted_attribute_value (attribute_value) @import)
  (#match? @attr_name "^(href|src)$")
)
"""

try:
    query = Query(lang, query_str)
    cursor = QueryCursor(query)
    captures = cursor.captures(tree.root_node)
    print("CAPTURES:", captures)
    
    imports = []
    if isinstance(captures, dict):
        # newer tree-sitter returns a dict: {'attr_name': [Node, Node], 'import': [Node, Node]}
        if 'import' in captures:
            for node in captures['import']:
                imports.append(node.text.decode('utf8'))
    print("IMPORTS:", imports)

except Exception as e:
    print("ERROR:", e)
