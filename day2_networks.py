"""Build weighted undirected networks from bibliographic records.

The public :func:`build_network` function accepts a pandas-like DataFrame and
returns JSON-friendly dictionaries.  Rows are the unit of co-occurrence: a
node is counted at most once per row, and an edge is counted at most once per
row even when a source field repeats a value.

For ``kind='coupling'``, nodes are distinct rows (studies); each undirected edge
is weighted by the number of distinct reference identifiers shared by two rows.
DOIs, OpenAlex work IDs and explicitly prefixed PMIDs are distinct namespaces;
no unverified crosswalk between them is inferred. Only the records with the
largest reference lists are retained when the requested node limit is reached.

Term policy
-----------
For ``kind='terms'``, a TF-IDF model over the selected records picks at most
eight single-word terms per title and abstract, after English and generic
research stopwords. The vocabulary is limited to 5,000 features. This is a
lexical policy: it does not perform stemming, phrase detection, or non-English
stopword removal, and the selection depends on the chosen record set.

Author limitation
-----------------
Authors are split only on semicolons.  Comma-separated names are intentionally
not split, so aliases, name-order variants, and ambiguous identities remain a
limitation for the UI to explain.
"""

from __future__ import annotations

from collections import Counter
import json
import math
from numbers import Real
import re
from typing import Any
from urllib.parse import unquote, urlsplit
import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer


NETWORK_COMMUNITY_RELEASE = 1
SUPPORTED_KINDS = {"terms", "authors", "concepts", "coupling"}
_TERM_LIMIT = 8

# Deliberately modest and stable: this is not intended to be a full NLP model.
_STOPWORDS = frozenset(ENGLISH_STOP_WORDS) | frozenset(
    "a an and are as at be been being by can could did do does for from had has "
    "have he her here hers him his how i if in into is it its itself me more most "
    "my no not of on or our ours she should so than that the their theirs them "
    "then there these they this those to too under up us was we were what when "
    "where which who why will with you your yours study studies research result results "
    "data paper article review analysis based using used method methods findings "
    "conclusion conclusions objective objectives introduction discussion aim aims".split()
)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _text(value: Any) -> str:
    return "" if _is_missing(value) else str(value)


def _normalise(value: Any) -> str:
    return " ".join(_text(value).split()).casefold()


def _cell(row: Any, column: str) -> Any:
    try:
        return row[column]
    except (KeyError, TypeError, IndexError):
        return None


def _split_semicolon(value: Any) -> set[str]:
    if _is_missing(value):
        return set()
    return {
        item
        for raw in str(value).split(";")
        if (item := _normalise(raw))
    }


def canonical_reference(value: Any) -> str:
    """Canonicalize recognized DOI, OpenAlex work or explicitly prefixed PMID.

    The result never assumes that identifiers in different namespaces are equal.
    Unrecognized raw citation text is excluded rather than guessed to be an ID.
    """
    raw = _text(value).strip()
    raw = re.sub(r"^(doi|pmid|openalex):\s*", r"\1:", raw, flags=re.I)
    if any(not char.isprintable() or char.isspace() for char in raw):
        return ""
    if re.match(r"^https?://", raw, flags=re.I):
        try:
            parsed = urlsplit(raw)
            if parsed.query or parsed.fragment or re.search(r"%(?![0-9a-fA-F]{2})", parsed.path):
                return ""
            host = parsed.netloc.casefold()
            path = unquote(parsed.path, encoding="utf-8", errors="strict")
            if host in {"doi.org", "dx.doi.org"}:
                raw = path.lstrip("/")
            elif host in {"openalex.org", "www.openalex.org"}:
                raw = path.lstrip("/")
            elif host == "api.openalex.org" and path.lower().startswith("/works/"):
                raw = path[len("/works/"):]
            else:
                return ""
        except (UnicodeDecodeError, ValueError):
            return ""
    raw = re.sub(r"^doi:", "", raw, flags=re.I).casefold()
    if re.fullmatch(r"10\.\d+/\S+", raw):
        return "doi:" + raw
    match = re.fullmatch(r"(?:openalex:)?(w\d+)/?", raw)
    if match:
        return "openalex:" + match.group(1)
    match = re.fullmatch(r"pmid:(\d+)", raw)
    return "pmid:" + match.group(1) if match else ""


def _reference_set(value: Any) -> set[str]:
    if _is_missing(value):
        return set()
    if isinstance(value, (list, tuple)):
        values = value
    else:
        text = _text(value).strip()
        if text.startswith("["):
            try:
                values = json.loads(text)
            except (ValueError, TypeError):
                return set()  # Never invent identifiers from malformed JSON.
            if not isinstance(values, list):
                return set()
        else:
            values = text.split(";")
    return {ref for raw in values if isinstance(raw, str) and (ref := canonical_reference(raw))}


def _coupling_network(records: list[Any], top_n: int, minimum: int) -> dict[str, Any]:
    candidates = []
    for index, row in enumerate(records):
        references = _reference_set(_cell(row, "References"))
        if not references:
            continue
        title = " ".join(_text(_cell(row, "Title")).split())
        record_id = " ".join(_text(_cell(row, "ID")).split())
        doi = " ".join(_text(_cell(row, "DOI")).split())
        label = title or record_id or doi or f"Untitled study {index + 1}"
        candidates.append((index, references, label, record_id, doi))

    # A cap is necessary for responsive rendering; the selection is explicit,
    # deterministic and does not pretend to represent the whole corpus.
    chosen = sorted(candidates, key=lambda item: (-len(item[1]), item[0]))[:top_n]
    nodes = []
    for index, references, label, record_id, doi in chosen:
        display = label if len(label) <= 28 else label[:25] + "..."
        nodes.append({"id": f"study:{index}", "label": f"{index + 1}. {display}",
                      "full_label": f"{index + 1}. {label}", "frequency": len(references),
                      "record_id": record_id, "doi": doi, "title": label})
    edges = []
    for i, (left_index, left_refs, *_rest) in enumerate(chosen):
        for right_index, right_refs, *_ in chosen[i + 1:]:
            weight = len(left_refs & right_refs)
            if weight and weight >= minimum:
                edges.append({"source": f"study:{left_index}", "target": f"study:{right_index}", "weight": weight})
    return {"nodes": nodes, "edges": edges, "records_with_data": len(candidates),
            "total_records": len(records), "kind": "coupling",
            "records_omitted_by_node_limit": max(0, len(candidates) - len(chosen))}


def _term_sets(records: list[Any]) -> list[set[str]]:
    texts = [(_text(_cell(row, "Title")) + " " + _text(_cell(row, "Abstract"))).casefold()
             for row in records]
    if not any(text.strip() for text in texts):
        return [set() for _ in texts]
    vectorizer = TfidfVectorizer(
        stop_words=sorted(_STOPWORDS), max_features=5000,
        token_pattern=r"(?u)\b[^\W\d_][^\W_]+\b", ngram_range=(1, 1),
    )
    try:
        matrix = vectorizer.fit_transform(texts)
    except ValueError:  # Empty vocabulary, e.g. text consisting only of stopwords.
        return [set() for _ in texts]
    names = vectorizer.get_feature_names_out()
    result = []
    for row_index in range(matrix.shape[0]):
        row = matrix.getrow(row_index)
        weighted = sorted(zip(row.data, row.indices), key=lambda pair: (-pair[0], names[pair[1]]))
        result.append({str(names[index]) for _, index in weighted[:_TERM_LIMIT]})
    return result


def _items(row: Any, kind: str) -> set[str]:
    column = "Authors" if kind == "authors" else "Concepts"
    return _split_semicolon(_cell(row, column))


def _rows(df: Any) -> list[Any]:
    if df is None:
        raise TypeError("df must be a pandas-like tabular object, not None")
    try:
        return list(df.to_dict(orient="records"))
    except (AttributeError, TypeError):
        try:
            return list(df)
        except TypeError as exc:
            raise TypeError("df must provide to_dict(orient='records') or be iterable") from exc


def build_network(df: Any, kind: str, top_n: int = 40, min_cooccurrence: int = 1) -> dict[str, Any]:
    """Return a weighted undirected term, author, concept or coupling network.

    ``top_n`` retains the most frequent nodes, with deterministic alphabetical
    tie-breaking. Edges count pairs of retained nodes, after frequencies have
    been counted across all rows. ``min_cooccurrence`` is inclusive.
    """
    if kind not in SUPPORTED_KINDS:
        raise ValueError(f"kind must be one of {sorted(SUPPORTED_KINDS)}")
    if isinstance(top_n, bool) or not isinstance(top_n, int) or top_n < 0:
        raise ValueError("top_n must be a non-negative integer")
    if isinstance(min_cooccurrence, bool) or not isinstance(min_cooccurrence, int) or min_cooccurrence < 0:
        raise ValueError("min_cooccurrence must be a non-negative integer")

    records = _rows(df)
    if kind == "coupling":
        return _coupling_network(records, top_n, min_cooccurrence)
    frequencies: Counter[str] = Counter()
    item_sets: list[set[str]] = []
    labels: dict[str, str] = {}
    records_with_data = 0

    term_sets = _term_sets(records) if kind == "terms" else None
    for row_index, row in enumerate(records):
        items = term_sets[row_index] if term_sets is not None else _items(row, kind)
        item_sets.append(items)
        if not items:
            continue
        records_with_data += 1
        frequencies.update(items)
        if kind != "terms":
            column = "Authors" if kind == "authors" else "Concepts"
            for raw in _text(_cell(row, column)).split(";"):
                display = " ".join(raw.split())
                if display:
                    labels.setdefault(display.casefold(), display)

    chosen = sorted(frequencies, key=lambda item: (-frequencies[item], item))[:top_n]
    chosen_set = set(chosen)
    edge_counts: Counter[tuple[str, str]] = Counter()
    for items in item_sets:
        ordered = sorted(items & chosen_set)
        for index, source in enumerate(ordered):
            for target in ordered[index + 1 :]:
                edge_counts[(source, target)] += 1

    nodes = [
        {"id": item, "label": labels.get(item, item), "frequency": int(frequencies[item])}
        for item in chosen
    ]
    edges = [
        {"source": source, "target": target, "weight": int(weight)}
        for (source, target), weight in sorted(edge_counts.items())
        if weight >= min_cooccurrence and source in chosen_set and target in chosen_set
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "records_with_data": records_with_data,
        "total_records": len(records),
        "kind": kind,
    }


def community_partition(network: dict[str, Any], seed: int = 42) -> dict[str, int]:
    """Return a deterministic, 1-based community ID for every displayed node.

    The input uses the same ``nodes``/``edges`` structure as :func:`build_network`.
    Node IDs must be unique strings; each undirected edge must appear once, have
    distinct known endpoints, and a finite positive numeric ``weight``. Edge
    weights are *link* counts (co-occurring records or shared reference IDs), not
    node frequencies. This also supports other co-occurrence graphs, e.g. legacy
    keyword networks, without requiring a particular ``kind`` value.

    NetworkX weighted Louvain is run on the displayed graph with resolution 1
    and the supplied integer seed. Node/edge insertion order is canonicalized,
    including using integer IDs internally so Python's hash seed cannot change
    the traversal order. Communities are numbered in lexicographic order of
    their sorted member IDs. Isolates are singleton communities. An edgeless or
    empty graph needs no Louvain optimization and returns singletons or {},
    respectively. IDs are local to this graph and may change when it changes.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")

    node_ids = [node["id"] for node in network["nodes"]]
    if any(not isinstance(node_id, str) for node_id in node_ids):
        raise ValueError("node IDs must be strings")
    if len(set(node_ids)) != len(node_ids):
        raise ValueError("node IDs must be unique")
    node_ids.sort()
    index_by_id = {node_id: index for index, node_id in enumerate(node_ids)}
    weighted_edges = []
    pairs = set()
    for edge in network["edges"]:
        source, target, weight = edge["source"], edge["target"], edge["weight"]
        if source not in index_by_id or target not in index_by_id:
            raise ValueError("edge endpoints must refer to displayed nodes")
        if source == target:
            raise ValueError("self-links are not supported")
        if isinstance(weight, bool) or not isinstance(weight, Real) or not math.isfinite(weight) or weight <= 0:
            raise ValueError("edge weights must be finite positive numbers")
        pair = tuple(sorted((index_by_id[source], index_by_id[target])))
        if pair in pairs:
            raise ValueError("each undirected edge must appear only once")
        pairs.add(pair)
        weighted_edges.append((*pair, weight))

    if not weighted_edges:
        return {node_id: index + 1 for index, node_id in enumerate(node_ids)}
    try:
        import networkx as nx
    except ImportError as exc:
        raise ValueError("NetworkX is required for Louvain community detection.") from exc
    if not hasattr(nx.community, "louvain_communities"):
        raise ValueError("NetworkX with Louvain support is required for community detection.")
    graph = nx.Graph()
    graph.add_nodes_from(range(len(node_ids)))
    graph.add_weighted_edges_from(sorted(weighted_edges))
    communities = nx.community.louvain_communities(graph, weight="weight", seed=seed)
    ordered = sorted(tuple(sorted(node_ids[index] for index in community)) for community in communities)
    return {node_id: community_id for community_id, members in enumerate(ordered, 1) for node_id in members}


def annotate_communities(network: dict[str, Any], seed: int = 42) -> dict[str, Any]:
    """Return a copy with node ``community`` IDs and method metadata added.

    Original nodes and the existing builder/export schema are not modified.
    The returned 1-based IDs are shared by the renderer and export callers.
    Edges and any other existing top-level values are retained unchanged.
    ``community_detection.method`` is ``weighted_louvain``, ``isolates``, or
    ``empty``; no optimization is claimed for graphs without links.
    """
    partition = community_partition(network, seed=seed)
    method = "weighted_louvain" if network["edges"] else "isolates" if network["nodes"] else "empty"
    return {
        **network,
        "nodes": [{**node, "community": partition[node["id"]]} for node in network["nodes"]],
        "community_detection": {"method": method, "seed": seed, "edge_weight": "weight",
                                "resolution": 1, "count": len(set(partition.values()))},
    }


__all__ = ["build_network", "canonical_reference", "community_partition", "annotate_communities"]
