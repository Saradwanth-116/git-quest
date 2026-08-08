"""Blast radius — reverse-transitive closure + identifier occurrence union.

The hero feature: "what breaks if these files change?"

Per the updated contract (af7a2fb), results include:
  - kind: "import" (parsed edge) or "occurrence" (identifier name match)
  - Sort order: (kind_rank, hops, path) — parsed edges rank above name matches
  - Occurrences use hops=0

Exported function matches the main.py call-site:
    blast_radius(repo_url, targets, max_hops=3)
Internal core takes an already-loaded graph for the eval harness.
"""
from __future__ import annotations

import re
from collections import deque
from typing import Any

import networkx as nx


# ---------------------------------------------------------------------------
# Internal core — takes an already-loaded graph
# ---------------------------------------------------------------------------

def _blast_radius_core(
    changed_files: list[str],
    graph: nx.DiGraph,
    max_hops: int = 3,
    limit: int = 200,
) -> dict:
    """Compute the blast radius for a set of changed files.

    Union of:
      1. Reverse BFS on import edges (files that transitively import the targets)
      2. Identifier-occurrence hits (files sharing identifiers with the targets)

    Returns the contract result shape.
    """
    max_hops = min(max_hops, 10)    # hard cap from contract
    limit = min(limit, 1000)        # hard cap from contract

    # Resolve targets (support partial paths like 'conf.py' for 'docs/conf.py')
    resolved_targets = []
    missing = []
    for t in changed_files:
        if t in graph:
            resolved_targets.append(t)
            continue
        
        matches = [n for n in graph.nodes if n == t or str(n).endswith(f"/{t}")]
        if len(matches) == 1:
            resolved_targets.append(matches[0])
        elif len(matches) > 1:
            return _error_result(f"target is ambiguous: {t} (matches {', '.join(matches)})")
        else:
            missing.append(t)

    if missing:
        return _error_result(
            f"targets not in graph: {', '.join(missing)}"
        )

    # Determine coverage tier — weakest of all targets
    tiers = [graph.nodes[t].get("tier", "unparseable") for t in resolved_targets]
    tier = _weakest_tier(tiers)

    # --- 1. Reverse BFS on import edges ---
    import_hits: dict[str, tuple[int, str]] = {}  # path -> (hops, reason)
    reverse = graph.reverse(copy=False)

    queue: deque[tuple[str, int]] = deque()
    visited: set[str] = set(resolved_targets)

    for target in resolved_targets:
        for pred in reverse.neighbors(target):
            if pred not in visited:
                visited.add(pred)
                queue.append((pred, 1))
                import_hits[pred] = (1, f"imports {target}")

    while queue:
        node, hops = queue.popleft()
        if hops >= max_hops:
            continue
        for pred in reverse.neighbors(node):
            if pred not in visited:
                visited.add(pred)
                queue.append((pred, hops + 1))
                import_hits[pred] = (hops + 1, f"imports {node}")

    # --- 2. Identifier-occurrence hits ---
    # Collect identifiers defined/used in the changed files
    target_idents: set[str] = set()
    for target in resolved_targets:
        node_data = graph.nodes.get(target, {})
        idents = node_data.get("idents", [])
        target_idents.update(idents)
        # Also add definition names
        for d in node_data.get("defs", []):
            target_idents.add(d["name"])

    occurrence_hits: dict[str, str] = {}  # path -> reason (first matching ident)
    if target_idents:
        for node_path in graph.nodes:
            if node_path in resolved_targets or node_path in import_hits:
                continue  # skip targets and already-found import hits
            node_data = graph.nodes[node_path]
            node_idents = set(node_data.get("idents", []))
            shared = target_idents & node_idents
            if shared:
                # Pick the first shared identifier alphabetically for determinism
                first = sorted(shared)[0]
                occurrence_hits[node_path] = f"identifier occurrence: {first}"

    # --- Build result nodes ---
    nodes: list[dict] = []

    for path, (hops, reason) in import_hits.items():
        nodes.append({
            "path": path,
            "kind": "import",
            "hops": hops,
            "reason": reason,
        })

    for path, reason in occurrence_hits.items():
        nodes.append({
            "path": path,
            "kind": "occurrence",
            "hops": 0,
            "reason": reason,
        })

    # Sort: kind_rank (import=0, occurrence=1), then hops, then path
    def sort_key(n):
        kind_rank = 0 if n["kind"] == "import" else 1
        return (kind_rank, n["hops"], n["path"])

    nodes.sort(key=sort_key)

    # Apply limit
    truncated = len(nodes) > limit
    nodes = nodes[:limit]

    return {
        "nodes": nodes,
        "coverage_tier": tier,
        "truncated": truncated,
        "error": None,
    }


def _weakest_tier(tiers: list[str]) -> str:
    """Return the weakest coverage tier from a list."""
    _RANK = {"unparseable": 0, "occurrence-only": 1, "deep": 2}
    if not tiers:
        return "unparseable"
    return min(tiers, key=lambda t: _RANK.get(t, 0))


def _error_result(msg: str) -> dict:
    """Return an error result per the contract — errors are values, not exceptions."""
    return {
        "nodes": [],
        "coverage_tier": "unparseable",
        "truncated": False,
        "error": msg,
    }


# ---------------------------------------------------------------------------
# Exported wrapper — matches main.py call-site:
#     blast_radius(repo_url, targets, max_hops=3)
# ---------------------------------------------------------------------------

def blast_radius(
    repo_url: str,
    targets: list[str],
    max_hops: int = 3,
) -> dict:
    """What breaks if these files change.

    Args:
        repo_url: GitHub repo URL (used to derive repo_id)
        targets:  list of repo-relative file paths (POSIX separators)
        max_hops: max traversal depth (default 3, hard cap 10)

    Returns:
        Contract result dict with nodes, coverage_tier, truncated, error.

    This wrapper resolves repo_url -> repo_id -> load_graph, then delegates
    to _blast_radius_core. The eval harness calls _blast_radius_core directly
    with an already-loaded graph.
    """
    from graph.store import load_graph

    # Derive repo_id from URL (same logic as indexing/store.py)
    slug = repo_url.rstrip("/").split("github.com/")[-1].removesuffix(".git")
    repo_id = slug.replace("/", "__")

    try:
        graph = load_graph(repo_id)
    except FileNotFoundError as e:
        return _error_result(str(e))

    return _blast_radius_core(targets, graph, max_hops=max_hops)
