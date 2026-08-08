"""backend.graph — dependency graph extraction, storage, and query engine.

Public API (consumed by backend.main and mutagent eval harness):
    extract:          extract_file, identifiers, imports, definitions
    store:            build_graph, save_graph, load_graph
    blast_radius:     blast_radius  (exported wrapper matching main.py call-site)
    query_dsl:        execute_query
    test_selection:   select_tests
    reviewer_routing: suggest_reviewers
"""
