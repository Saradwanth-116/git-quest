import os
from graph_builder import extract_imports_with_treesitter, resolve_import_to_path, get_language_from_path

html_content = """
<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
  <link rel="stylesheet" href="style.css" />
  <script src="js/script.js" defer></script>
</head>
<body>
</body>
</html>
"""

all_files = [
    "index.html",
    "style.css",
    "js/script.js",
    "js/words.js",
    "img/bg.svg",
    "img/image.jpeg"
]

lang = get_language_from_path("index.html")
print("LANG:", lang)

imports = extract_imports_with_treesitter(html_content, lang)
print("EXTRACTED IMPORTS:", imports)

for imp in imports:
    resolved = resolve_import_to_path("index.html", imp, all_files)
    print(f"'{imp}' RESOLVED TO: {resolved}")
