"""Self-contained guided review examples with fixed searches and criteria.

Crossref uses verified captures; other providers are searched only on demand.
Live results are isolated in guided-only session keys, never in BYOD state.
Screening is a simple teaching heuristic, not a validated review process.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import day2_networks
import day2_network_view
from openaire_notice import OPENAIRE_LIMITATIONS

# The Streamlit host can retain imported modules while syncing newer page files.
# Pages require this release marker and reload a stale cached renderer once.
GUIDED_PROVIDER_RELEASE = 1


GUIDED_DATA_DIR = Path(__file__).resolve().parent / "data" / "guided_fixed"
SCREEN_DECISION = "Screening decision"
INCLUSION_MATCHES = "Inclusion matches"
EXCLUSION_MATCHES = "Exclusion matches"


def _text(value: Any) -> str:
    """Turn a scalar into text without turning missing values into 'nan'."""
    if value is None:
        return ""
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _normalise(value: Any) -> str:
    return " ".join(_text(value).split()).casefold()


def _terms(values: Iterable[str] | None) -> list[tuple[str, str]]:
    """Keep the first spelling of each nonblank term, in the supplied order."""
    if values is None or isinstance(values, (str, bytes)):
        return []
    result = []
    seen = set()
    for value in values:
        if not isinstance(value, str):
            continue
        original = " ".join(value.split())
        key = original.casefold()
        if key and key not in seen:
            result.append((original, key))
            seen.add(key)
    return result


def _matches(title: str, abstract: str, terms: list[tuple[str, str]]) -> str:
    matches = []
    for term, key in terms:
        fields = []
        if key in title:
            fields.append("title")
        if key in abstract:
            fields.append("abstract")
        if fields:
            matches.append(f"{term} [{', '.join(fields)}]")
    return " | ".join(matches)


def screen_records(records: pd.DataFrame, inclusion_terms: Iterable[str],
                   exclusion_terms: Iterable[str]) -> pd.DataFrame:
    """Return a copy with deterministic, auditable teaching-screen decisions.

    A term is a case-insensitive, whitespace-normalized literal substring in
    *either* title or abstract. Include if at least one inclusion term matches
    and no exclusion term matches; any exclusion overrides inclusion. Blank
    terms never match; no inclusion terms or no matching text means exclude.
    The original DataFrame and term collections are not modified.
    """
    result = records.copy(deep=True)
    includes, excludes = _terms(inclusion_terms), _terms(exclusion_terms)
    decisions, found_includes, found_excludes = [], [], []
    for record in result.to_dict(orient="records"):
        title, abstract = _normalise(record.get("Title")), _normalise(record.get("Abstract"))
        inc = _matches(title, abstract, includes)
        exc = _matches(title, abstract, excludes)
        found_includes.append(inc)
        found_excludes.append(exc)
        decisions.append("Include" if inc and not exc else "Exclude")
    result[SCREEN_DECISION] = decisions
    result[INCLUSION_MATCHES] = found_includes
    result[EXCLUSION_MATCHES] = found_excludes
    return result


def included_records(screened: pd.DataFrame) -> pd.DataFrame:
    """Select exactly the rows marked Include, preserving their metadata and order."""
    if SCREEN_DECISION not in screened:
        return screened.iloc[0:0].copy()
    return screened.loc[screened[SCREEN_DECISION].eq("Include")].copy()


def candidate_finding_excerpt(abstract: Any) -> str:
    """Return the first literal, cue-containing sentence, or 'Not available'.

    A sentence boundary is punctuation . ! or ? followed by whitespace or the
    end of text. Cue matching is case-insensitive literal substring matching;
    surrounding whitespace alone is removed. This intentionally simple rule
    may select methods or qualified statements and does not validate findings.
    """
    text = _text(abstract)
    cues = ("result", "finding", "conclusion", "associated", "increase", "decrease")
    for part in re.split(r"(?<=[.!?])(?=\s|$)", text):
        sentence = part.strip()
        if sentence and any(cue in sentence.casefold() for cue in cues):
            return sentence
    return "Not available"


def extract_bibliography(included: pd.DataFrame) -> pd.DataFrame:
    """Copy auditable fields for precisely the selected rows; never infer content."""
    fields = ["Title", "Year", "DOI", "Authors", "Abstract", "Abstract_License"]
    # Preserve these when present without changing the schema of simple fixtures.
    fields += [field for field in ("ID", "Source", "Abstract Source") if field in included]
    result = pd.DataFrame(index=included.index)
    for field in fields:
        result[field] = included[field].map(_text) if field in included else ""
    result["Abstract availability"] = result["Abstract"].map(
        lambda value: "Available" if value.strip() else "Not available"
    )
    result["Candidate finding excerpt"] = result["Abstract"].map(candidate_finding_excerpt)
    for field in (INCLUSION_MATCHES, EXCLUSION_MATCHES):
        result[field] = included[field].map(_text) if field in included else ""
    return result.reset_index(drop=True)


def year_summary(included: pd.DataFrame) -> pd.DataFrame:
    """Count recorded four-digit years; preserve an explicit unknown bucket."""
    values = included["Year"] if "Year" in included else pd.Series("", index=included.index)
    years = [_text(value).strip() for value in values]
    counts: dict[str, int] = {}
    for year in years:
        key = year if re.fullmatch(r"[0-9]{4}", year) else "Not recorded / not a four-digit year"
        counts[key] = counts.get(key, 0) + 1
    order = sorted(key for key in counts if key != "Not recorded / not a four-digit year")
    if "Not recorded / not a four-digit year" in counts:
        order.append("Not recorded / not a four-digit year")
    return pd.DataFrame([{"Year": key, "Included records": counts[key]} for key in order],
                        columns=["Year", "Included records"])


def _spreadsheet_safe(value: Any) -> str:
    """Prevent formula execution when exported text is opened in a spreadsheet."""
    text = _text(value)
    # Leading whitespace/control characters can conceal a spreadsheet formula.
    if text.startswith(("\t", "\r", "\n")) or text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def safe_csv_bytes(frame: pd.DataFrame) -> bytes:
    """Serialize a copy as UTF-8 CSV with spreadsheet formulas neutralized.

    A leading apostrophe is added only to potentially dangerous text (including
    column headers); underlying data shown in the app is never changed.
    """
    safe = frame.copy(deep=True).astype(object)
    for position in range(len(safe.columns)):
        # Positional assignment also handles duplicate column names.
        safe.iloc[:, position] = safe.iloc[:, position].map(_spreadsheet_safe)
    safe.columns = [_spreadsheet_safe(column) for column in safe.columns]
    return safe.to_csv(index=False).encode("utf-8-sig")


def _local_file(directory: Path, filename: Any) -> Path:
    """Accept only a plain filename resolving within the guided data directory."""
    if (not isinstance(filename, str) or not filename or filename in {".", ".."}
            or "/" in filename or "\\" in filename):
        raise ValueError("Expected a filename in the guided data directory")
    root = directory.resolve()
    path = (root / filename).resolve()
    if path.parent != root:
        raise ValueError("Guided data file resolves outside the guided data directory")
    return path


def load_guided_cases(data_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """Read the fixed cases manifest, raising a descriptive error if invalid."""
    directory = Path(data_dir) if data_dir is not None else GUIDED_DATA_DIR
    path = directory / "cases.json"
    try:
        with path.open(encoding="utf-8") as handle:
            cases = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not load the guided cases manifest: {exc}") from exc
    if not isinstance(cases, list) or any(not isinstance(case, dict) for case in cases):
        raise ValueError("The guided cases manifest must be an array of case objects.")
    return cases


def load_case_data(case: dict[str, Any], data_dir: str | Path | None = None
                   ) -> tuple[pd.DataFrame | None, dict[str, Any] | None, list[str]]:
    """Load one case's independent CSV and JSON log; report either failure."""
    directory = Path(data_dir) if data_dir is not None else GUIDED_DATA_DIR
    corpus, log, errors = None, None, []
    corpus_bytes = None
    try:
        corpus_path = _local_file(directory, case.get("corpus_file"))
        corpus_bytes = corpus_path.read_bytes()
        corpus = pd.read_csv(io.BytesIO(corpus_bytes), dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except (ValueError, OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        errors.append(f"Captured corpus unavailable or invalid: {exc}")
    try:
        path = _local_file(directory, case.get("log_file"))
        with path.open(encoding="utf-8") as handle:
            loaded = json.load(handle)
        if not isinstance(loaded, dict):
            raise ValueError("the log must be a JSON object")
        log = loaded
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"Capture log unavailable or invalid: {exc}")
    if corpus is not None and log is not None:
        logged_file = log.get("corpus_file")
        if logged_file and logged_file != case.get("corpus_file"):
            errors.append("Captured corpus filename does not match the capture log; computation is disabled pending verification.")
            corpus = None
        expected_hash = log.get("corpus_sha256")
        if corpus is not None and expected_hash:
            try:
                actual_hash = hashlib.sha256(corpus_bytes).hexdigest()
                if not isinstance(expected_hash, str) or actual_hash != expected_hash.strip().casefold():
                    raise ValueError("SHA-256 does not match the capture log")
            except ValueError as exc:
                errors.append(f"Captured corpus integrity check failed: {exc}; computation is disabled pending verification.")
                corpus = None
    return corpus, log, errors


def _first(log: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = log.get(name)
        if value is not None and value != "":
            return value
    return None


def _logged_query(log: dict[str, Any]) -> str:
    query = _first(log, "query", "search_query", "query_string")
    if isinstance(query, str):
        return query
    for name in ("params", "parameters", "request_params", "request_parameters"):
        params = log.get(name)
        if isinstance(params, dict) and isinstance(params.get("query"), str):
            return params["query"]
    return ""


def _case_terms(case: dict[str, Any], name: str) -> list[str] | None:
    values = case.get(name)
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        return None
    return values


def _download(label: str, frame: pd.DataFrame, filename: str, key: str) -> None:
    st.download_button(label, safe_csv_bytes(frame), file_name=filename, mime="text/csv", key=key)


def _render_retrieval(case: dict[str, Any], corpus: pd.DataFrame | None,
                      log: dict[str, Any] | None, prefix: str) -> None:
    st.markdown("#### 1. Captured retrieval")
    st.warning(
        "This Crossref relevance search is an incomplete, one-page sample, not a "
        "comprehensive systematic search. Crossref relevance matching is not a "
        "guaranteed Boolean search; the same query may yield different results later."
    )
    if log is None:
        st.error("The capture log is unavailable: the actual query, source, date and parameters cannot be verified.")
    else:
        logged_query = _logged_query(log)
        if logged_query:
            st.write("Actual captured query:")
            st.code(logged_query, language=None)
        else:
            st.warning("The actual query was not recorded in a recognized log field; see the complete log below.")
        configured_query = _text(case.get("query"))
        if configured_query and logged_query and configured_query != logged_query:
            st.warning("The case query differs from the capture log. The logged query above is the captured query; check provenance before using this example.")
            st.write("Query listed in the case manifest:")
            st.code(configured_query, language=None)
        endpoint = _first(log, "endpoint", "url", "source")
        timestamp = _first(log, "timestamp_utc", "retrieved_at_utc", "utc_timestamp", "timestamp", "retrieved_at", "date_utc", "date")
        source = _first(log, "source", "provider")
        st.write(f"Recorded source: {_text(source) or 'Not recorded'}")
        st.write(f"Captured endpoint/source: {_text(endpoint) or 'Not recorded'}")
        st.write(f"Capture timestamp: {_text(timestamp) or 'Not recorded'} (see log for timezone)")
        parameters = _first(log, "parameters", "params", "request_params", "request_parameters")
        st.write("Recorded request parameters:")
        if isinstance(parameters, (dict, list)):
            st.json(parameters, expanded=True)
        else:
            st.write(_text(parameters) if parameters is not None else "Not recorded separately; see the capture log.")
        returned = _first(log, "returned", "records_returned", "returned_count")
        total = _first(log, "total_matches", "total", "total_results")
        truncated = _first(log, "possibly_truncated", "truncated", "truncation")
        st.write(f"Returned: {returned if returned is not None else 'Not recorded'}; provider total matches: {total if total is not None else 'Not recorded'}; truncation indicator: {truncated if truncated is not None else 'Not recorded'}.")
        st.caption("Complete capture log (including any additional parameters and licensing notes):")
        st.json(log, expanded=False)
        st.download_button("Download capture log (JSON)", json.dumps(log, indent=2, ensure_ascii=False).encode("utf-8"),
                           file_name=f"{prefix}_crossref_capture_log.json", mime="application/json",
                           key=f"{prefix}_capture_log_json")
        st.caption("The saved sample retains abstracts only where a CC BY or CC0 license was found in Crossref metadata. Missing abstracts can reflect this reuse check; verify the source and license terms before reuse.")
        if corpus is not None and returned is not None:
            try:
                if int(returned) != len(corpus):
                    st.warning(f"The log reports {returned} returned records, but the CSV contains {len(corpus)} rows. Check this capture's provenance.")
            except (TypeError, ValueError):
                st.warning("The returned-record count in the capture log is not a usable integer.")
    if corpus is None:
        st.error("The captured record file could not be loaded; the downstream stages cannot be computed.")
        return
    st.caption(f"Captured CSV: {len(corpus)} records. These are retrieved records, not validated eligible studies.")
    st.dataframe(corpus, use_container_width=True, hide_index=True)
    _download("Download captured records (CSV)", corpus, f"{prefix}_retrieved.csv", f"{prefix}_retrieved_csv")


def _render_screening(case: dict[str, Any], screened: pd.DataFrame | None, prefix: str,
                      provider: str = "Crossref") -> None:
    st.markdown("#### 2. Fixed teaching screen")
    st.caption(
        "Nonvalidated deterministic heuristic, not an LLM or human review: a case-insensitive, "
        "whitespace-normalized literal substring match against title OR abstract. "
        "Include when ANY inclusion term matches and NO exclusion term matches; exclusion overrides inclusion. "
        "Blank/missing text cannot match, and a missing abstract is not itself an exclusion if the title matches. "
        "No stemming or semantic interpretation is used."
    )
    inc = _case_terms(case, "inclusion_terms")
    exc = _case_terms(case, "exclusion_terms")
    st.write("Fixed inclusion terms (any):", inc if inc is not None else "Not recorded or invalid")
    st.write("Fixed exclusion terms (any overrides inclusion):", exc if exc is not None else "Not recorded or invalid")
    if screened is None:
        st.error("No teaching-screen decisions are available because the corpus or fixed terms could not be loaded.")
        return
    included = included_records(screened)
    label = "Captured records" if provider == "Crossref" else f"{provider} retrieved records"
    st.caption(f"{label}: {len(screened)}; heuristic includes: {len(included)}; heuristic excludes: {len(screened) - len(included)}. These are not validated eligibility decisions.")
    columns = [name for name in ("Source", "ID", "DOI", "Title", "Abstract", SCREEN_DECISION,
                                   INCLUSION_MATCHES, EXCLUSION_MATCHES) if name in screened]
    st.dataframe(screened[columns], use_container_width=True, hide_index=True)
    st.caption("Each displayed matching term is followed by the field(s) in which it occurs.")
    _download("Download teaching-screen decisions (CSV)", screened,
              f"{prefix}_screened.csv", f"{prefix}_screened_csv")


def _render_extraction(included: pd.DataFrame | None, prefix: str,
                       provider: str = "Crossref") -> None:
    st.markdown("#### 3. Direct bibliographic extraction")
    st.caption(
        f"Fields below are copied from the selected {provider} records included by the nonvalidated teaching screen. "
        "This table is not AI-generated: no PICO elements, outcomes, effects, or other absent facts are inferred or invented. "
        "Blank fields were not recorded in the source metadata."
    )
    st.caption(
        "Candidate finding excerpt: the first literal sentence in the recorded abstract containing "
        "result, finding, conclusion, associated, increase, or decrease (case-insensitive substrings). "
        "The simple rule splits after . ! or ? followed by whitespace or the end of text; it may capture "
        "a method or a qualified statement. 'Not available' means no abstract or no matching sentence. "
        "Verify the candidate manually in context using the original abstract and DOI shown beside it; "
        "it is not an AI-generated or validated finding."
    )
    if included is None:
        st.error("Extraction is unavailable because the selected corpus or fixed teaching-screen terms could not be loaded.")
        return
    extracted = extract_bibliography(included)
    st.caption(f"Bibliographic rows: {len(extracted)}; exactly the heuristic-included records from stage 2.")
    if extracted.empty:
        st.info("The fixed teaching screen included no records, so there are no bibliographic fields to extract.")
    st.dataframe(extracted, use_container_width=True, hide_index=True)
    _download("Download included bibliographic fields (CSV)", extracted,
              f"{prefix}_bibliography.csv", f"{prefix}_bibliography_csv")


def load_ai_illustration(case: dict[str, Any], included: pd.DataFrame,
                         data_dir: str | Path | None = None) -> tuple[dict[str, Any] | None, str]:
    """Verify a precomputed demonstration against a current included source.

    The stored inference-time corpus hash may differ from a later capture; the
    selected record, abstract and every non-missing excerpt must still match.
    """
    directory = Path(data_dir) if data_dir is not None else GUIDED_DATA_DIR
    key = _text(case.get("key"))
    if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
        return None, "The AI illustration has no valid case identifier."
    try:
        path = _local_file(directory, f"{key}.ai.json")
        demo = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(demo, dict) or demo.get("case_key") != key:
            raise ValueError("case identifier mismatch")
        source, prompt = demo["source"], demo["prompt"]["messages"]
        if not isinstance(source, dict) or not isinstance(prompt, list) or len(prompt) != 2:
            raise ValueError("source or prompt is missing")
        if any(name not in included.columns for name in ("ID", "DOI", "Title", "Abstract")):
            raise ValueError("included records lack source fields")
        matching = included.loc[
            included["ID"].map(_text).eq(_text(source.get("record_id")))
            & included["DOI"].map(_text).eq(_text(source.get("doi")))
            & included["Title"].map(_text).eq(_text(source.get("title")))
        ]
        if len(matching) != 1:
            raise ValueError("source record is not uniquely present among the included records")
        abstract = _text(matching.iloc[0]["Abstract"])
        if (not abstract or source.get("abstract") != abstract or
                source.get("abstract_sha256") != hashlib.sha256(abstract.encode("utf-8")).hexdigest()):
            raise ValueError("source abstract or checksum does not match")
        if (not all(isinstance(message, dict) for message in prompt) or
                prompt[0].get("role") != "system" or not isinstance(prompt[0].get("content"), str) or
                prompt[1].get("role") != "user" or
                prompt[1].get("content") != "Provided abstract:\n<<<BEGIN ABSTRACT>>>\n" + abstract + "\n<<<END ABSTRACT>>>"):
            raise ValueError("recorded prompt does not match the source abstract")
        raw = json.loads(demo["response"]["raw_text"])
        parsed, validation = demo["parsed_output"], demo["validation"]
        if not all(isinstance(item, dict) for item in (raw, parsed, validation)):
            raise ValueError("recorded response is invalid")
        for field in ("objective", "methods", "results"):
            value = parsed.get(field)
            status = validation.get(field, {}).get("status")
            if value == "Not reported" and raw.get(field) == value and status == "not_reported":
                continue
            if (isinstance(value, str) and value.strip() and value in abstract and
                    raw.get(field) == value and status == "exact_substring"):
                continue
            raise ValueError(f"the {field} excerpt is missing or inconsistent")
        return demo, ""
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return None, f"The saved AI illustration could not be verified: {exc}"


def _render_ai_illustration(case: dict[str, Any], included: pd.DataFrame | None,
                            directory: Path, log: dict[str, Any] | None,
                            provider: str = "Crossref") -> None:
    st.markdown("##### Fixed AI extraction illustration — one included record")
    if provider != "Crossref":
        st.info(f"No saved, provider-matched AI illustration is available for {provider}. The Crossref illustration is not reused.")
        return
    st.caption(
        "A real AI request was made once when this teaching illustration was prepared. "
        "The exact prompt and response below are saved read-only; no request is made now. "
        "This illustrates one record, not an AI extraction or synthesis of the entire corpus. "
        "Matching an excerpt to the abstract does not verify its relevance or accuracy. "
        "Review it and the source in context; Crossref records can include preprints and non-empirical works."
    )
    if included is None:
        st.info("The illustration is unavailable because the included records could not be verified.")
        return
    demo, error = load_ai_illustration(case, included, directory)
    if error:
        st.info(error)
        return
    source = demo["source"]
    st.write("Illustrated source:", source["title"])
    st.write("DOI:", source["doi"])
    matching = included.loc[included["ID"].map(_text).eq(_text(source["record_id"]))]
    if "Abstract_License" in matching and not matching.empty:
        license_url = _text(matching.iloc[0]["Abstract_License"])
        st.write("License reported in Crossref metadata:", license_url or "Not recorded")
    model = demo.get("model", {})
    st.write("Recorded model:", _text(model.get("returned")) or _text(model.get("requested")) or "Not recorded")
    st.write("Recorded generation time (UTC):", _text(demo.get("generated_at_utc")) or "Not recorded")
    if log and source.get("corpus_sha256") != log.get("corpus_sha256"):
        st.caption("The saved corpus changed after the AI request; the illustrated source record and its abstract have been verified against this capture.")
    st.write("Fixed system instructions used:")
    st.code(demo["prompt"]["messages"][0]["content"], language=None)
    st.write("Fixed user message and source abstract used:")
    st.code(demo["prompt"]["messages"][1]["content"], language=None)
    st.write("Recorded AI output (verbatim excerpts):")
    for field in ("objective", "methods", "results"):
        value = demo["parsed_output"][field]
        st.write(f"{field.title()}:", value)
        st.caption("Not reported by the model; verify the source." if value == "Not reported" else
                   "The excerpt matches the saved abstract exactly; semantic accuracy still requires review.")


def _network_tables(graph: dict[str, Any], kind: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    nodes = {node["id"]: node for node in graph["nodes"]}
    node_rows = [{"Node ID": node["id"], "Label": node.get("full_label", node["label"]),
                  "Frequency": node["frequency"], "Record ID": node.get("record_id", ""),
                  "DOI": node.get("doi", "")} for node in graph["nodes"]]
    metric = "Shared studies" if kind == "authors" else "Shared references"
    edge_rows = []
    for edge in graph["edges"]:
        source, target = nodes[edge["source"]], nodes[edge["target"]]
        edge_rows.append({"Source node ID": edge["source"], "Source label": source.get("full_label", source["label"]),
                          "Target node ID": edge["target"], "Target label": target.get("full_label", target["label"]),
                          metric: edge["weight"], "Source record ID": source.get("record_id", ""),
                          "Source DOI": source.get("doi", ""), "Target record ID": target.get("record_id", ""),
                          "Target DOI": target.get("doi", "")})
    return pd.DataFrame(node_rows), pd.DataFrame(edge_rows)


def _render_network(included: pd.DataFrame, prefix: str) -> None:
    st.markdown("##### Bibliographic networks of the same heuristic-included records")
    choice = st.selectbox("Network type", ["Co-authorship", "Bibliographic coupling"], key=f"{prefix}_network_kind")
    kind = "authors" if choice == "Co-authorship" else "coupling"
    if kind == "authors":
        st.caption("A link counts included records listing both authors. Author names are semicolon-separated; case and spacing are normalized, but aliases and identities are not disambiguated. Lists can be incomplete. The cap retains the most frequent authors.")
    else:
        st.caption("A link counts distinct reference identifiers shared by two included records, not direct citations. Only recognized DOI, OpenAlex work ID and explicitly prefixed PMID references count; different namespaces are not cross-linked. Missing reference lists are not inferred. The node cap favors records with the most recognized references and can bias the map.")
    top_n = st.slider("Maximum network nodes", 1, 100, 25, 1, key=f"{prefix}_{kind}_top")
    minimum = st.slider("Minimum shared studies per link" if kind == "authors" else "Minimum shared references per link",
                        1, 20, 1, 1, key=f"{prefix}_{kind}_minimum")
    graph = day2_networks.build_network(included, kind=kind, top_n=top_n, min_cooccurrence=minimum)
    st.caption(f"Usable {'author' if kind == 'authors' else 'reference'} data: {graph['records_with_data']} of {graph['total_records']} heuristic-included records. Displayed: {len(graph['nodes'])} nodes and {len(graph['edges'])} links (node cap {top_n}; minimum link weight {minimum}).")
    if graph.get("records_omitted_by_node_limit", 0):
        st.caption(f"{graph['records_omitted_by_node_limit']} records with references were omitted by the node cap.")
    if not graph["total_records"]:
        st.info("There are no heuristic-included records to map.")
    elif not graph["records_with_data"]:
        st.info("No usable Authors data in the included records; co-authorship cannot be calculated." if kind == "authors" else "No usable References data in the included records; bibliographic coupling cannot be calculated. Missing references are not invented.")
    elif not graph["edges"]:
        st.info("No links meet the current node cap and minimum weight. Records may lack co-authors or shared recognized references; the graph is not shown.")
    else:
        try:
            html = day2_network_view.make_network_html(graph)
        except (ValueError, OSError) as exc:
            st.warning(f"The local network visualization is unavailable: {exc}")
        else:
            components.html(html, height=590, scrolling=False)
    nodes, edges = _network_tables(graph, kind)
    if not nodes.empty:
        st.caption("Network exports contain only displayed nodes and links after the cap and threshold; coupling node IDs identify rows of the included subset.")
        _download("Download network nodes (CSV)", nodes, f"{prefix}_{kind}_nodes.csv", f"{prefix}_{kind}_nodes_csv")
    if not edges.empty:
        st.dataframe(edges, use_container_width=True, hide_index=True)
        _download("Download network links (CSV)", edges, f"{prefix}_{kind}_links.csv", f"{prefix}_{kind}_links_csv")


def _render_synthesis(screened: pd.DataFrame | None, included: pd.DataFrame | None, prefix: str,
                      provider: str = "Crossref") -> None:
    st.markdown("#### 4. Descriptive synthesis and networks")
    st.caption(f"Descriptive counts of this {provider} one-page sample and the same nonvalidated teaching-screen includes; not a meta-analysis, PRISMA flow, treatment effect, or claim of comprehensive evidence.")
    st.info("The sample does not contain verified, compatible effect sizes and full-text screening counts, so no pooled forest plot or full PRISMA flow is invented for this example.")
    if screened is None or included is None:
        st.error("Synthesis is unavailable because the selected corpus or fixed teaching-screen terms could not be loaded.")
        return
    label = "Captured records" if provider == "Crossref" else f"{provider} retrieved records"
    st.write(f"{label}: {len(screened)}; heuristic-included: {len(included)}; heuristic-excluded: {len(screened) - len(included)}.")
    years = year_summary(included)
    st.caption("Publication year counts among the heuristic-included records; missing/non-four-digit values are reported separately.")
    if years.empty:
        st.info("No included records are available for a year summary.")
    else:
        st.dataframe(years, use_container_width=True, hide_index=True)
    _download("Download included year counts (CSV)", years, f"{prefix}_years.csv", f"{prefix}_years_csv")
    _render_network(included, prefix)


GUIDED_PROVIDERS = ("Crossref", "OpenAlex", "Europe PMC", "OpenAIRE")
_ENDPOINTS = {
    "OpenAlex": "https://api.openalex.org/works",
    "Europe PMC": "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
    "OpenAIRE": "https://api.openaire.eu/graph/v3/research-products",
}
_LIVE_CAVEATS = {
    "OpenAlex": "OpenAlex title-and-abstract exact search and provider ranking determine matches. Abstracts are reconstructed from inverted indexes and may be missing; references include only supplied OpenAlex work IDs. No date, type or abstract filter is applied. Check abstract reuse rights.",
    "Europe PMC": "Europe PMC has life-sciences-oriented coverage and its own Boolean search semantics. Core metadata and abstracts can be incomplete; this retrieval does not supply reference lists. No date, type or abstract filter is applied. Check abstract reuse rights.",
    "OpenAIRE": "OpenAIRE searches broad research-product metadata, not just titles and abstracts. The first description may not be a formal abstract. Reference lists are not supplied here. No date, specific publication-type or abstract filter is applied; verify reuse rights and acknowledge OpenAIRE.",
}


def _live_plan(case_key: str, provider: str) -> tuple[str, dict[str, Any]]:
    """Build the exact, non-editable request plan from the backend contract."""
    import guided_provider_search as search

    query = search.guided_query(case_key, provider)
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Fixed provider query is unavailable")
    if provider == "OpenAlex":
        params = {"search.title_and_abstract.exact": query, "per-page": 50,
                  "cursor": "*", "select": search.OPENALEX_SELECT}
    elif provider == "Europe PMC":
        params = {"query": query, "resultType": "core", "pageSize": search.PAGE_SIZE,
                  "format": "json", "cursorMark": "*"}
    elif provider == "OpenAIRE":
        params = {"search": query, "type": "publication", "pageSize": search.PAGE_SIZE, "cursor": "*"}
    else:
        raise ValueError("Unsupported live provider")
    return query, params


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    return None


def _safe_timestamp(value: Any) -> str:
    # Do not copy arbitrary provider strings (which could contain secrets) into
    # a log. Missing/unrecognized timestamps are honestly marked unavailable.
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?(?:Z|[+-]\d\d:\d\d)", value):
        return value
    return "Not recorded"


def _live_log(case_key: str, provider: str, query: str, params: dict[str, Any],
              metadata: Any, corpus: pd.DataFrame) -> dict[str, Any]:
    """Construct a log from trusted configuration and a small scalar allowlist."""
    if not isinstance(metadata, dict):
        raise ValueError("Invalid provider metadata")
    for name, expected in (("case_key", case_key), ("provider", provider), ("source", provider), ("query", query)):
        if name in metadata and metadata[name] not in (None, "", expected):
            raise ValueError("Provider response does not match the fixed search")
    if "parameters" in metadata and metadata["parameters"] != params:
        raise ValueError("Provider parameters do not match the fixed search")
    timestamp = _first(metadata, "timestamp_utc", "fetched_at_utc", "retrieved_at_utc")
    pages = _nonnegative_int(_first(metadata, "pages_fetched", "pages"))
    total = _nonnegative_int(_first(metadata, "total_matches", "returned_total", "numFound"))
    truncated = metadata.get("possibly_truncated")
    if not isinstance(truncated, bool):
        truncated = None
    return {
        "case_key": case_key, "provider": provider, "source": provider,
        "endpoint": _ENDPOINTS[provider], "query": query, "parameters": params,
        "max_pages": 1, "retrieved_at_utc": _safe_timestamp(timestamp),
        "returned": len(corpus), "total_matches": total,
        "pages_fetched": pages, "possibly_truncated": truncated,
        "limitations": _LIVE_CAVEATS[provider],
        "sample_note": "Bounded live one-page sample, not a comprehensive search or saved reproducible snapshot; results can change.",
    }


def _prepare_live_result(case_key: str, provider: str, query: str,
                         params: dict[str, Any], corpus: Any, metadata: Any) -> dict[str, Any]:
    if not isinstance(corpus, pd.DataFrame):
        raise ValueError("Invalid provider corpus")
    # No credential-bearing columns are retained, even if supplied unexpectedly.
    forbidden = re.compile(r"(?:api.?key|authorization|credential|password|secret|token|email)", re.I)
    columns = [column for column in corpus.columns if not forbidden.search(str(column))]
    clean = corpus.loc[:, columns].copy(deep=True).reset_index(drop=True)
    # Provenance is attached by this retrieval, not copied from unrelated state.
    clean["Source"] = provider
    log = _live_log(case_key, provider, query, params, metadata, clean)
    return {"status": "ok", "corpus": clean, "log": log}


def _render_live_retrieval(case_key: str, provider: str, prefix: str
                           ) -> tuple[pd.DataFrame | None, dict[str, Any] | None]:
    st.markdown("#### 1. Live fixed retrieval")
    st.warning("This is a bounded, one-page live teaching sample, not an exhaustive systematic search or a saved reproducible snapshot. Results can change over time.")
    st.caption(_LIVE_CAVEATS[provider])
    try:
        query, params = _live_plan(case_key, provider)
    except (ImportError, AttributeError, ValueError, KeyError):
        st.error(f"The fixed {provider} search is unavailable for this case; no search was run.")
        return None, None
    st.write("Fixed query sent to this provider:")
    st.code(query, language=None)
    st.write(f"Endpoint: {_ENDPOINTS[provider]}")
    st.write("Exact request parameters (one page only; no editable search):")
    st.json(params, expanded=True)
    if provider == "OpenAlex":
        st.caption("The browser reads your local JSON credential file and calls OpenAlex directly. The key is not uploaded to the Streamlit server, session state, or logs. The fixed search uses title_abstract_exact, no year/type filter, and does not require an abstract.")
    state_key = f"{prefix}_provider_{provider.lower().replace(' ', '_')}_result"
    active_key = f"{prefix}_openalex_active"
    attempt_key = f"{prefix}_openalex_attempt"
    if provider == "OpenAlex":
        if st.button("Start a new OpenAlex browser search", key=f"{prefix}_openalex_start"):
            # Clear first: a failed or abandoned retry must never show stale results.
            st.session_state.pop(state_key, None)
            st.session_state[attempt_key] = st.session_state.get(attempt_key, 0) + 1
            st.session_state[active_key] = True
        if st.session_state.get(active_key, False):
            try:
                from browser_openalex import render_browser_openalex
                from guided_provider_search import openalex_records_to_frame
                response = render_browser_openalex(
                    query, key=f"{prefix}_openalex_browser_{st.session_state[attempt_key]}",
                    per_page=50, max_pages=1, year_from=None, year_to=None,
                    publication_types=(), search_scope="title_abstract_exact", require_abstract=False,
                )
                if response is not None:
                    records, metadata = response
                    if not isinstance(records, list) or not isinstance(metadata, dict) or metadata.get("error"):
                        raise ValueError("Invalid browser search response")
                    corpus = openalex_records_to_frame(records)
                    st.session_state[state_key] = _prepare_live_result(case_key, provider, query, params, corpus, metadata)
                    st.session_state[active_key] = False
                    # Unmount the component so an old event cannot initiate a retry
                    # or be mistaken for a later request on the next rerun.
                    st.rerun()
            except Exception:
                st.session_state[active_key] = False
                st.session_state[state_key] = {"status": "error"}
    elif st.button(f"Run fixed {provider} search", key=f"{prefix}_{provider.lower().replace(' ', '_')}_run"):
        st.session_state.pop(state_key, None)
        try:
            from guided_provider_search import fetch_guided
            with st.spinner(f"Searching {provider}…"):
                corpus, metadata = fetch_guided(case_key, provider)
            st.session_state[state_key] = _prepare_live_result(case_key, provider, query, params, corpus, metadata)
        except Exception:
            # Never echo raw exception text, which can contain request URLs or credentials.
            st.session_state[state_key] = {"status": "error"}
    result = st.session_state.get(state_key)
    if isinstance(result, dict) and result.get("status") == "ok":
        saved_log = result.get("log")
        if (not isinstance(saved_log, dict) or saved_log.get("case_key") != case_key
                or saved_log.get("provider") != provider or saved_log.get("query") != query
                or saved_log.get("parameters") != params or not isinstance(result.get("corpus"), pd.DataFrame)):
            st.session_state.pop(state_key, None)
            result = None
    if not result:
        st.info(f"No {provider} search has completed for this case. Run the fixed search to populate all four stages.")
        return None, None
    if result.get("status") != "ok":
        st.error(f"The {provider} search failed or the response was invalid. No previous result is displayed; retry when ready.")
        return None, None
    corpus, log = result["corpus"], result["log"]
    st.write(f"Recorded source: {provider}; retrieval timestamp (UTC): {log['retrieved_at_utc']}; returned: {len(corpus)}; provider total: {log['total_matches'] if log['total_matches'] is not None else 'Not recorded'}; possibly truncated: {log['possibly_truncated'] if log['possibly_truncated'] is not None else 'Unknown'}.")
    st.caption("Sanitized live retrieval log (fixed request, source, date, cap and limitations):")
    st.json(log, expanded=False)
    st.download_button("Download live retrieval log (JSON)", json.dumps(log, indent=2, ensure_ascii=False).encode("utf-8"),
                       file_name=f"{prefix}_{provider.lower().replace(' ', '_')}_log.json", mime="application/json",
                       key=f"{prefix}_{provider.lower().replace(' ', '_')}_log_json")
    if corpus.empty:
        st.info(f"The {provider} search returned no records. The fixed screen and synthesis therefore contain no records.")
    else:
        st.caption(f"{provider} returned {len(corpus)} records; these are not validated eligible studies.")
    st.dataframe(corpus, use_container_width=True, hide_index=True)
    _download("Download retrieved records (CSV)", corpus, f"{prefix}_{provider.lower().replace(' ', '_')}_retrieved.csv", f"{prefix}_{provider.lower().replace(' ', '_')}_retrieved_csv")
    return corpus, log


def render_guided_examples(context: str = "day1", *, data_dir: str | Path | None = None) -> None:
    """Render every guided case as four self-contained stages.

    ``context`` namespaces all widget keys when used on different pages.
    ``data_dir`` optionally overrides the default ``data/guided_fixed`` directory
    (useful for tests). Captured Crossref files or the selected provider's live
    data feed every later stage. Live results use guided-only session keys; no
    credentials or BYOD state are read or written. Returns ``None``.
    """
    directory = Path(data_dir) if data_dir is not None else GUIDED_DATA_DIR
    try:
        cases = load_guided_cases(directory)
    except ValueError as exc:
        st.error(str(exc))
        return
    if not cases:
        st.info("No fixed guided cases are available in the manifest.")
        return
    st.caption("Each case is independent: choose a provider for its fixed search and fixed teaching screen. Crossref is a saved capture; the other sources are live on demand.")
    for position, case in enumerate(cases):
        case_key = _text(case.get("key")) or f"case_{position + 1}"
        prefix = f"guided_{context}_{case_key}_{position + 1}"
        label = _text(case.get("label")) or case_key
        with st.expander(label):
            provider = st.selectbox("Provider", GUIDED_PROVIDERS, key=f"{prefix}_provider")
            if provider == "OpenAIRE":
                # Above the tabs, so the caveat stays visible during every stage.
                st.warning(OPENAIRE_LIMITATIONS)
            question = _text(case.get("question"))
            if question:
                st.write("Fixed research question:", question)
            retrieval, screening, extraction, synthesis = st.tabs([
                "1 · Retrieval", "2 · Screening", "3 · Extraction", "4 · Synthesis & networks"
            ])
            with retrieval:
                if provider == "Crossref":
                    corpus, log, errors = load_case_data(case, directory)
                    for error in errors:
                        st.warning(error)
                    if log is None:
                        # Without provenance the captured data cannot be verified.
                        corpus = None
                    if corpus is not None and "Source" not in corpus:
                        corpus["Source"] = "Crossref"
                    _render_retrieval(case, corpus, log, prefix)
                else:
                    corpus, log = _render_live_retrieval(case_key, provider, prefix)
            inc, exc = _case_terms(case, "inclusion_terms"), _case_terms(case, "exclusion_terms")
            if inc is None or exc is None:
                st.warning("The case's fixed screening terms are invalid; no decisions will be inferred.")
            screened = screen_records(corpus, inc, exc) if corpus is not None and inc is not None and exc is not None else None
            included = included_records(screened) if screened is not None else None
            stage_prefix = prefix if provider == "Crossref" else f"{prefix}_{provider.lower().replace(' ', '_')}"
            with screening:
                _render_screening(case, screened, stage_prefix, provider)
            with extraction:
                _render_extraction(included, stage_prefix, provider)
                _render_ai_illustration(case, included, directory, log, provider)
            with synthesis:
                _render_synthesis(screened, included, stage_prefix, provider)


__all__ = ["render_guided_examples", "screen_records", "included_records", "candidate_finding_excerpt", "extract_bibliography",
           "year_summary", "safe_csv_bytes", "load_guided_cases", "load_case_data"]
