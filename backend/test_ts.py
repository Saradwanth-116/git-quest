# pyrefly: ignore [missing-import]
import tree_sitter_language_pack as ts_pack
# pyrefly: ignore [missing-import]
from tree_sitter import Parser, Query

lang = ts_pack.get_language("python")
parser = Parser(lang)
tree = parser.parse(b"import os")

query_str = "(import_statement) @import"
query = Query(lang, query_str)

# Let's see how captures works in v0.22/0.23
try:
    print("Trying query.captures(tree.root_node)...")
    res = query.captures(tree.root_node)
    print("Success:", res)
except AttributeError:
    print("query.captures failed!")
    
try:
    print("Trying query.matches(tree.root_node)...")
    res = query.matches(tree.root_node)
    print("Success:", res)
except AttributeError:
    print("query.matches failed!")

try:
    from tree_sitter import QueryCursor
    cursor = QueryCursor()
    print("Trying cursor.captures(query, tree.root_node)...")
    res = cursor.captures(query, tree.root_node)
    print("Success:", res)
except Exception as e:
    print("cursor.captures(query, node) failed!", e)

try:
    cursor = QueryCursor()
    print("Trying cursor.matches(query, tree.root_node)...")
    res = cursor.matches(query, tree.root_node)
    print("Success:", res)
except Exception as e:
    print("cursor.matches(query, node) failed!", e)
