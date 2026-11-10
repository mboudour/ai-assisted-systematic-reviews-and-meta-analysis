"""Build weighted undirected networks from Day 2 tabular records.

The public :func:`build_network` function accepts a pandas-like DataFrame and
returns JSON-friendly dictionaries.  Rows are the unit of co-occurrence: a
node is counted at most once per row, and an edge is counted at most once per
row even when a source field repeats a value.

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
from typing import Any
import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer


SUPPORTED_KINDS = {"terms", "authors", "concepts"}
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
    """Return a weighted undirected network for ``terms``, ``authors``, or ``concepts``.

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


__all__ = ["build_network"]
