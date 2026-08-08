"""Graph query DSL — the contract interface between the two streams.

Implements the six operations from docs/GRAPH_QUERY_CONTRACT.md:
    blast_radius, importers_of, imports_of, definition_of, occurrences_of, neighbors

Public API:
    execute_query(query: dict, graph: Any) -> dict

Rules from the contract:
    - Never raises for a bad query — returns result with `error` set
    - Deterministic: identical (query, graph) yields identical result
    - Sort order: (kind_rank, hops, path)
    - Unknown fields are ignored, unknown ops return error
    - max_hops hard cap 10, limit hard cap 1000
"""
from __future__ import annotations

from collections import deque
from typing import Any

import networkx as nx

from graph.blast_radius import _blast_radius_core, _weakest_tier

# ---------------------------------------------------------------------------
# Valid operations
# ---------------------------------------------------------------------------

_VALID_OPS = frozenset({
    "blast_radius", "importers_of", "imports_of",
    "definition_of", "occurrences_of", "neighbors",
})

# Ops that require `targets` (path-based)
_PATH_OPS = frozenset({"blast_radius", "importers_of", "imports_of", "neighbors"})

# Ops that require `symbol` (identifier-based)
_SYMBOL_OPS = frozenset({"definition_of", "occurrences_of"})


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

def _error(msg: str) -> dict:
    return {
        "nodes": [],
        "coverage_tier": "unparseable",
        "truncated": False,
        "error": msg,
    }


def _result(nodes: list[dict], graph: nx.DiGraph, targets: list[str],
            limit: int) -> dict:
    """Build a result dict with proper sorting, truncation, and tier."""
    # Sort: kind_rank (import=0, occurrence=1), then hops, then path
    def sort_key(n):
        kind_rank = 0 if n.get("kind", "import") == "import" else 1
        return (kind_rank, n.get("hops", 0), n["path"])

    nodes.sort(key=sort_key)

    truncated = len(nodes) > limit
    nodes = nodes[:limit]

    # Coverage tier from the targets
    tiers = []
    for t in targets:
        if t in graph:
            tiers.append(graph.nodes[t].get("tier", "unparseable"))
    tier = _weakest_tier(tiers) if tiers else "deep"

    return {
        "nodes": nodes,
        "coverage_tier": tier,
        "truncated": truncated,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Individual operations
# ---------------------------------------------------------------------------

def _op_blast_radius(query: dict, graph: nx.DiGraph) -> dict:
    max_hops = min(query.get("max_hops", 3), 10)
    limit = min(query.get("limit", 200), 1000)
    return _blast_radius_core(query["targets"], graph, max_hops=max_hops,
                              limit=limit)


def _op_importers_of(query: dict, graph: nx.DiGraph) -> dict:
    """Who depends on these targets, up to max_hops (reverse edges only)."""
    targets = query["targets"]
    max_hops = min(query.get("max_hops", 3), 10)
    limit = min(query.get("limit", 200), 1000)

    missing = [t for t in targets if t not in graph]
    if missing:
        return _error(f"targets not in graph: {', '.join(missing)}")

    reverse = graph.reverse(copy=False)
    nodes: list[dict] = []
    visited: set[str] = set(targets)
    queue: deque[tuple[str, int, str]] = deque()

    for target in targets:
        for pred in reverse.neighbors(target):
            if pred not in visited:
                visited.add(pred)
                queue.append((pred, 1, target))
                nodes.append({
                    "path": pred,
                    "kind": "import",
                    "hops": 1,
                    "reason": f"imports {target}",
                })

    while queue:
        node, hops, via = queue.popleft()
        if hops >= max_hops:
            continue
        for pred in reverse.neighbors(node):
            if pred not in visited:
                visited.add(pred)
                queue.append((pred, hops + 1, node))
                nodes.append({
                    "path": pred,
                    "kind": "import",
                    "hops": hops + 1,
                    "reason": f"imports {node}",
                })

    return _result(nodes, graph, targets, limit)


def _op_imports_of(query: dict, graph: nx.DiGraph) -> dict:
    """What these targets depend on (forward edges, one hop)."""
    targets = query["targets"]
    limit = min(query.get("limit", 200), 1000)

    missing = [t for t in targets if t not in graph]
    if missing:
        return _error(f"targets not in graph: {', '.join(missing)}")

    nodes: list[dict] = []
    seen: set[str] = set(targets)

    for target in targets:
        for succ in graph.neighbors(target):
            if succ not in seen:
                seen.add(succ)
                nodes.append({
                    "path": succ,
                    "kind": "import",
                    "hops": 1,
                    "reason": f"imported by {target}",
                })

    return _result(nodes, graph, targets, limit)


def _op_definition_of(query: dict, graph: nx.DiGraph) -> dict:
    """Where a symbol is defined."""
    symbol = query["symbol"]
    limit = min(query.get("limit", 200), 1000)

    nodes: list[dict] = []
    for node_path in graph.nodes:
        node_data = graph.nodes[node_path]
        for d in node_data.get("defs", []):
            if d["name"] == symbol:
                nodes.append({
                    "path": node_path,
                    "kind": "import",  # structural — a real parsed fact
                    "hops": 0,
                    "reason": f"defines {symbol} ({d['kind']}, line {d['line']})",
                })
                break  # one hit per file

    # Tier reflects the files that actually matched, not an arbitrary
    # unrelated file — a symbol op has no real path "target" to ask about,
    # so _result's targets-based lookup must be pointed at the matches
    # themselves. Zero matches means nothing to be confident about, so
    # that case reports unparseable rather than the "deep" _result would
    # default to for an empty targets list (its else-branch is correct for
    # importers_of/imports_of/neighbors, where empty results still carry a
    # real queried target; it is not correct here, where there is none).
    result = _result(nodes, graph, [n["path"] for n in nodes], limit)
    if not nodes:
        result["coverage_tier"] = "unparseable"
    return result


def _op_occurrences_of(query: dict, graph: nx.DiGraph) -> dict:
    """Every place a symbol appears (all 371 languages)."""
    symbol = query["symbol"]
    limit = min(query.get("limit", 200), 1000)

    nodes: list[dict] = []
    for node_path in graph.nodes:
        node_data = graph.nodes[node_path]
        idents = node_data.get("idents", [])
        if symbol in idents:
            nodes.append({
                "path": node_path,
                "kind": "occurrence",
                "hops": 0,
                "reason": f"identifier occurrence: {symbol}",
            })

    result = _result(nodes, graph, [n["path"] for n in nodes], limit)
    if not nodes:
        result["coverage_tier"] = "unparseable"
    return result


def _op_neighbors(query: dict, graph: nx.DiGraph) -> dict:
    """One hop, both directions."""
    targets = query["targets"]
    limit = min(query.get("limit", 200), 1000)

    missing = [t for t in targets if t not in graph]
    if missing:
        return _error(f"targets not in graph: {', '.join(missing)}")

    nodes: list[dict] = []
    seen: set[str] = set(targets)

    for target in targets:
        # Forward edges (what this file imports)
        for succ in graph.neighbors(target):
            if succ not in seen:
                seen.add(succ)
                nodes.append({
                    "path": succ,
                    "kind": "import",
                    "hops": 1,
                    "reason": f"imported by {target}",
                })
        # Reverse edges (who imports this file)
        for pred in graph.predecessors(target):
            if pred not in seen:
                seen.add(pred)
                nodes.append({
                    "path": pred,
                    "kind": "import",
                    "hops": 1,
                    "reason": f"imports {target}",
                })

    return _result(nodes, graph, targets, limit)


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH = {
    "blast_radius":  _op_blast_radius,
    "importers_of":  _op_importers_of,
    "imports_of":    _op_imports_of,
    "definition_of": _op_definition_of,
    "occurrences_of": _op_occurrences_of,
    "neighbors":     _op_neighbors,
}


# ---------------------------------------------------------------------------
# Public API — the contract function
# ---------------------------------------------------------------------------

def execute_query(query: dict, graph: Any) -> dict:
    """Execute a query object against a loaded graph. Returns the result dict.

    Never raises for a bad query — returns a result with `error` set.
    Deterministic: identical (query, graph) yields an identical result.

    This is the contract signature from docs/GRAPH_QUERY_CONTRACT.md.
    """
    # --- Validate query is a dict ---
    if not isinstance(query, dict):
        return _error(f"query must be a dict, got {type(query).__name__}")

    # --- Validate op ---
    op = query.get("op")
    if op is None:
        return _error("missing required field: op")
    if op not in _VALID_OPS:
        return _error(f"unknown op '{op}'")

    # --- Validate required fields ---
    if op in _PATH_OPS:
        targets = query.get("targets")
        if not targets or not isinstance(targets, list):
            return _error(f"op '{op}' requires a non-empty 'targets' list")

    if op in _SYMBOL_OPS:
        symbol = query.get("symbol")
        if not symbol or not isinstance(symbol, str):
            return _error(f"op '{op}' requires a non-empty 'symbol' string")

    # --- Dispatch ---
    handler = _DISPATCH[op]
    return handler(query, graph)
