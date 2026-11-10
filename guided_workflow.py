"""Self-contained guided review examples with fixed searches and criteria.

Each provider starts with its own verified, recorded one-page sample. Optional
live results are isolated in guided-only session keys, never in BYOD state.
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
GUIDED_PROVIDER_RELEASE = 2
GUIDED_ANONYMOUS_RELEASE = 2


GUIDED_DATA_DIR = Path(__file__).resolve().parent / "data" / "guided_fixed"
GUIDED_SNAPSHOT_DIR = GUIDED_DATA_DIR.parent / "guided_provider_snapshots"
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
                      log: dict[str, Any] | None, prefix: str,
                      provider: str = "Crossref", kind: str = "saved") -> None:
    st.markdown("#### 1. Selected retrieval")
    st.warning("This is a bounded one-page teaching sample, not an exhaustive systematic search. Provider matching and coverage vary; results may change over time.")
    if provider == "Crossref":
        st.caption("Crossref relevance matching is not a guaranteed Boolean search.")
    else:
        st.caption(_LIVE_CAVEATS[provider])
    if corpus is None or log is None:
        st.error("The saved snapshot is unavailable or failed verification, and no successful live result is selected. The actual query, source, date and parameters cannot be verified; downstream stages cannot be computed.")
        return
    st.info(f"Using {'verified saved snapshot' if kind == 'saved' else 'successful live retrieval'}: {provider}. This exact sample feeds all four stages.")
    st.write("Actual recorded query:")
    st.code(log["query"], language=None)
    st.write(f"Recorded source: {provider}")
    st.write(f"Recorded endpoint: {log['endpoint']}")
    st.write(f"Retrieval timestamp: {log['retrieved_at_utc']}")
    st.write("Recorded request parameters:")
    st.json(log["parameters"], expanded=True)
    total, truncated = log.get("total_matches"), log.get("possibly_truncated")
    st.write(f"Returned: {len(corpus)}; provider total matches: {total if total is not None else 'Not recorded'}; possibly truncated: {truncated if truncated is not None else 'Not recorded'}.")
    if kind == "saved":
        st.caption("Saved abstracts may be missing because the provider did not supply them or because reuse rights could not be confirmed and text was withheld. A blank does not prove the provider lacked an abstract; missing text can affect screening. Verify source and reuse rights.")
        if isinstance(log.get("abstract_note"), str) and log["abstract_note"]:
            st.caption(log["abstract_note"])
    else:
        st.caption("Live abstracts may be missing; check the original source and reuse rights before using them. Missing text can affect screening.")
    st.caption("Complete selected retrieval log:")
    st.json(log, expanded=False)
    st.download_button(f"Download {'capture' if kind == 'saved' else 'live retrieval'} log (JSON)",
                       json.dumps(log, indent=2, ensure_ascii=False).encode("utf-8"),
                       file_name=f"{prefix}_{provider.lower().replace(' ', '_')}_{kind}_log.json",
                       mime="application/json", key=f"{prefix}_{kind}_log_json")
    st.caption(f"Selected {provider} sample: {len(corpus)} records. These are retrieved records, not validated eligible studies.")
    if kind == "saved":
        st.caption("The log's SHA-256 verifies the original bundled capture; the spreadsheet-safe CSV download is reserialized and may have different bytes.")
    st.dataframe(corpus, use_container_width=True, hide_index=True)
    _download("Download selected records (CSV)", corpus, f"{prefix}_retrieved.csv", f"{prefix}_retrieved_csv")


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
        st.error("No teaching-screen decisions: the selected snapshot is unavailable or failed verification and no successful live sample is selected, or the fixed screening terms are invalid. See Retrieval and the terms above; a live search is optional.")
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
        "Blank fields may be missing from the source or deliberately withheld from a saved capture; check its retrieval log."
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
        st.error("Extraction is unavailable: the selected snapshot did not verify and no successful live sample is selected, or the fixed screening terms are invalid. See Retrieval and Screening.")
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


_NETWORK_AUTOMATIC = "Keyword / concept co-occurrence (automatic)"
_NETWORK_CONCEPTS = "Concept co-occurrence (source metadata)"
_NETWORK_TERMS = "Keyword co-occurrence (title/abstract terms)"
_NETWORK_CHOICES = (_NETWORK_AUTOMATIC, _NETWORK_CONCEPTS, _NETWORK_TERMS,
                    "Co-authorship", "Bibliographic coupling")


def _build_guided_network(included: pd.DataFrame, choice: str, top_n: int,
                          minimum: int) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Choose a real metadata graph when it has links, otherwise use text terms.

    Only automatic mode falls back. The second return value is the attempted
    concept graph in automatic mode, retained so its coverage and any fallback
    can be explained. Both graphs are computed from the same included subset.
    """
    if choice == _NETWORK_AUTOMATIC:
        concepts = day2_networks.build_network(included, kind="concepts", top_n=top_n,
                                                min_cooccurrence=minimum)
        if concepts["edges"]:
            return concepts, concepts
        terms = day2_networks.build_network(included, kind="terms", top_n=top_n,
                                             min_cooccurrence=minimum)
        return terms, concepts
    kind = {_NETWORK_CONCEPTS: "concepts", _NETWORK_TERMS: "terms",
            "Co-authorship": "authors", "Bibliographic coupling": "coupling"}[choice]
    return day2_networks.build_network(included, kind=kind, top_n=top_n,
                                       min_cooccurrence=minimum), None


def _network_tables(graph: dict[str, Any], kind: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    nodes = {node["id"]: node for node in graph["nodes"]}
    frequency = {"concepts": "Included records containing concept",
                 "terms": "Included records with selected term"}.get(kind, "Frequency")
    node_rows = [{"Node ID": node["id"], "Label": node.get("full_label", node["label"]),
                  frequency: node["frequency"], "Record ID": node.get("record_id", ""),
                  "DOI": node.get("doi", "")} for node in graph["nodes"]]
    metric = {"authors": "Shared studies", "coupling": "Shared references",
              "concepts": "Included records containing both concepts",
              "terms": "Included records with both selected terms"}[kind]
    edge_rows = []
    for edge in graph["edges"]:
        source, target = nodes[edge["source"]], nodes[edge["target"]]
        edge_rows.append({"Source node ID": edge["source"], "Source label": source.get("full_label", source["label"]),
                          "Target node ID": edge["target"], "Target label": target.get("full_label", target["label"]),
                          metric: edge["weight"], "Source record ID": source.get("record_id", ""),
                          "Source DOI": source.get("doi", ""), "Target record ID": target.get("record_id", ""),
                          "Target DOI": target.get("doi", "")})
    return pd.DataFrame(node_rows), pd.DataFrame(edge_rows)


def _render_network(included: pd.DataFrame, prefix: str, provider: str = "") -> None:
    st.markdown("##### Bibliographic networks of the same heuristic-included records")
    choice = st.selectbox("Network type", _NETWORK_CHOICES, key=f"{prefix}_network_kind")
    control_kind = {_NETWORK_AUTOMATIC: "automatic", _NETWORK_CONCEPTS: "concepts",
                    _NETWORK_TERMS: "terms", "Co-authorship": "authors",
                    "Bibliographic coupling": "coupling"}[choice]
    if choice == _NETWORK_AUTOMATIC:
        st.caption("Automatic: use the source Concepts metadata when it produces at least one link at the current node cap and minimum weight; otherwise fall back to title/abstract terms from the same included records.")
    if choice in (_NETWORK_AUTOMATIC, _NETWORK_CONCEPTS):
        st.caption("Source metadata: labels are copied from the selected records' semicolon-separated Concepts field. Depending on the provider, these may be concepts, subject headings or keywords; they are not inferred from the title or abstract. Case and spacing are normalized, not disambiguated.")
        provenance = {
            "OpenAlex": "OpenAlex Concepts contains supplied OpenAlex concept display names; these are not necessarily author keywords.",
            "OpenAIRE": "OpenAIRE subjects are mapped to Concepts. These heterogeneous labels may include keywords, classifications and other subjects; they are not uniformly author keywords.",
            "Crossref": "Crossref subjects, when supplied, are mapped to Concepts; they are not necessarily author keywords.",
            "Europe PMC": "The guided Europe PMC adapter currently does not populate Concepts. If a selected snapshot supplies that field, its recorded labels are used as supplied.",
        }.get(provider)
        if provenance:
            st.caption(provenance)
    if choice in (_NETWORK_AUTOMATIC, _NETWORK_TERMS):
        st.caption("Text-derived keywords are not source-assigned concepts. TF-IDF selects up to eight single-word terms per included title/abstract using English and generic research stopwords and at most 5,000 features. No stemming or phrase detection is performed; missing text and non-English language can affect coverage.")
        total = len(included)
        title_count = sum(bool(_text(value).strip()) for value in included["Title"]) if "Title" in included else 0
        abstract_count = sum(bool(_text(value).strip()) for value in included["Abstract"]) if "Abstract" in included else 0
        if not total or not (title_count or abstract_count):
            st.caption(f"TF-IDF input: no included title or abstract-field text is available ({total} included records).")
        elif not abstract_count:
            st.caption(f"TF-IDF input is title-only: {title_count} of {total} included records have recorded titles; none have recorded abstract-field text.")
        else:
            st.caption(f"TF-IDF input is title/abstract: {title_count} of {total} included records have recorded titles and {abstract_count} have recorded abstract-field text. Records without abstracts contribute title text only, if available.")
        if provider == "OpenAIRE":
            st.caption("For OpenAIRE, the Abstract field contains a provider description, not necessarily a formal abstract.")
    if control_kind == "authors":
        st.caption("A link counts included records listing both authors. Author names are semicolon-separated; case and spacing are normalized, but aliases and identities are not disambiguated. Lists can be incomplete. The cap retains the most frequent authors.")
    elif control_kind == "coupling":
        st.caption("A link counts distinct reference identifiers shared by two included records, not direct citations. Only recognized DOI, OpenAlex work ID and explicitly prefixed PMID references count; different namespaces are not cross-linked. Missing reference lists are not inferred. The node cap favors records with the most recognized references and can bias the map.")
    top_n = st.slider("Maximum network nodes", 1, 100, 25, 1, key=f"{prefix}_{control_kind}_top")
    minimum_label = ("Minimum shared references per link" if control_kind == "coupling" else
                     "Minimum shared studies per link" if control_kind == "authors" else
                     "Minimum included records per link")
    minimum = st.slider(minimum_label,
                        1, 20, 1, 1, key=f"{prefix}_{control_kind}_minimum")
    graph, concepts = _build_guided_network(included, choice, top_n, minimum)
    kind = graph["kind"]
    if concepts is not None:
        st.caption(f"Usable source Concepts metadata: {concepts['records_with_data']} of {concepts['total_records']} heuristic-included records; {len(concepts['edges'])} concept links at the current node cap and minimum weight.")
        if kind == "terms":
            reason = ("no usable Concepts metadata was present" if not concepts["records_with_data"]
                      else "the available Concepts metadata produced no link at the current node cap and minimum weight")
            text_input = ("title-only" if title_count and not abstract_count else "title/abstract")
            st.info(f"Automatic fallback to TF-IDF {text_input} keywords: {reason}. These text-derived keywords are not source-assigned concepts.")
        else:
            st.caption("Automatic selection: source Concepts metadata (not text-derived keywords).")
    data_label = {"authors": "author data", "coupling": "reference data", "concepts": "source Concepts metadata",
                  "terms": "TF-IDF title/abstract term data"}[kind]
    if kind == "terms" and title_count and not abstract_count:
        data_label = "TF-IDF title-only term data"
    st.caption(f"Usable {data_label}: {graph['records_with_data']} of {graph['total_records']} heuristic-included records. Displayed: {len(graph['nodes'])} nodes and {len(graph['edges'])} links (node cap {top_n}; minimum link weight {minimum}).")
    if kind == "concepts":
        st.caption("A link counts included records containing both displayed metadata labels; each record contributes at most once to each node or link. The node cap retains the most frequent labels.")
    elif kind == "terms":
        st.caption("A link counts included records for which both terms were selected by TF-IDF; a term merely appearing in a record is not counted if it is not selected for that record. Each record contributes at most once to each node or link. The node cap retains the most frequently selected terms.")
    if graph.get("records_omitted_by_node_limit", 0):
        st.caption(f"{graph['records_omitted_by_node_limit']} records with references were omitted by the node cap.")
    if not graph["total_records"]:
        st.info("There are no heuristic-included records to map.")
    elif not graph["records_with_data"]:
        st.info({"authors": "No usable Authors data in the included records; co-authorship cannot be calculated.",
                 "coupling": "No usable References data in the included records; bibliographic coupling cannot be calculated. Missing references are not invented.",
                 "concepts": "No usable Concepts metadata in the included records; concept co-occurrence cannot be calculated. Metadata are not invented.",
                 "terms": "No usable title/abstract terms in the included records; keyword co-occurrence cannot be calculated. Text or eligible terms may be absent."}[kind])
    elif not graph["edges"]:
        detail = {"authors": "Records may lack co-authors.",
                  "coupling": "Records may lack shared recognized references.",
                  "concepts": "Records may not contain two source Concepts labels together.",
                  "terms": "Records may not contain two selected title/abstract terms together."}[kind]
        st.info(f"No links meet the current node cap and minimum weight. {detail} The graph is not shown.")
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
        st.error("Synthesis is unavailable: the selected snapshot did not verify and no successful live sample is selected, or the fixed screening terms are invalid. See Retrieval and Screening.")
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
    _render_network(included, prefix, provider)


GUIDED_PROVIDERS = ("Crossref", "OpenAlex", "Europe PMC", "OpenAIRE")
_ENDPOINTS = {
    "Crossref": "https://api.crossref.org/works",
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


def _has_secret_field(value: Any) -> bool:
    """Refuse logs with credential-shaped fields, including nested fields."""
    if isinstance(value, dict):
        sensitive = re.compile(r"api.?key|authorization|credential|password|secret|token|e.?mail|mailto", re.I)
        return any(sensitive.search(str(key)) or _has_secret_field(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_has_secret_field(item) for item in value)
    if isinstance(value, str):
        return bool(re.search(r"(?:[?&]|^)(?:api.?key|authorization|credential|password|secret|(?:access.?)?token|email|mailto)=[^&\s]+|\bBearer\s+\S+", value, re.I))
    return False


def load_provider_snapshot(case: dict[str, Any], provider: str, directory: str | Path,
                           *, legacy_override: bool = False
                           ) -> tuple[pd.DataFrame | None, dict[str, Any] | None, list[str]]:
    """Load only the selected case/provider's verified, logged snapshot.

    Manifest-specified historical Crossref files may also be used; they must
    still pass every integrity check. The caller selects that source explicitly.
    No production snapshot or different provider is used as a substitute.
    """
    try:
        key = case.get("key")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", key) or provider not in GUIDED_PROVIDERS:
            raise ValueError("invalid case or provider")
        if legacy_override:
            if provider != "Crossref":
                raise ValueError("no provider-specific snapshot")
            corpus_name, log_name = case.get("corpus_file"), case.get("log_file")
            expected_queries = {_text(case.get("query"))}
        else:
            import guided_provider_search as search
            stem = f"{key}__{provider.lower().replace(' ', '_')}"
            corpus_name, log_name = f"{stem}.csv", f"{stem}.json"
            expected_queries = {search.guided_query(key, provider)}
            # Historical Crossref captures may use the fixed manifest query,
            # rather than the newer live-search query. Both identify this case.
            if provider == "Crossref":
                expected_queries.add(_text(case.get("query")))
        root = Path(directory)
        log = json.loads(_local_file(root, log_name).read_text(encoding="utf-8"))
        if not isinstance(log, dict) or _has_secret_field(log):
            raise ValueError("invalid or credential-bearing log")
        if log.get("case_key") != key:
            raise ValueError("case identifier mismatch")
        sources = [log[name] for name in ("provider", "source") if name in log]
        if not sources or any(source != provider for source in sources):
            raise ValueError("provider mismatch")
        query = log.get("query")
        if not isinstance(query, str) or not query or query not in expected_queries:
            raise ValueError("fixed query mismatch")
        params = log.get("parameters")
        query_key = {"Crossref": "query", "OpenAlex": "search.title_and_abstract.exact",
                     "Europe PMC": "query", "OpenAIRE": "search"}[provider]
        if not isinstance(params, dict) or params.get(query_key) != query:
            raise ValueError("request parameters do not match the logged query")
        if log.get("endpoint") != _ENDPOINTS[provider]:
            raise ValueError("provider endpoint mismatch")
        if _safe_timestamp(log.get("retrieved_at_utc")) == "Not recorded":
            raise ValueError("retrieval timestamp missing or invalid")
        if log.get("corpus_file") != corpus_name:
            raise ValueError("corpus filename mismatch")
        if "log_file" in log and log["log_file"] != log_name:
            raise ValueError("capture log filename mismatch")
        digest = log.get("corpus_sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            raise ValueError("missing or invalid SHA-256")
        corpus_bytes = _local_file(root, corpus_name).read_bytes()
        if hashlib.sha256(corpus_bytes).hexdigest() != digest.lower():
            raise ValueError("SHA-256 mismatch")
        corpus = pd.read_csv(io.BytesIO(corpus_bytes), dtype=str, keep_default_na=False, encoding="utf-8-sig")
        count = _nonnegative_int(log.get("returned"))
        if count is None or count != len(corpus):
            raise ValueError("returned row count mismatch")
        if "Title" not in corpus or "Abstract" not in corpus or "Source" not in corpus:
            raise ValueError("required record fields are missing")
        if not corpus["Source"].eq(provider).all():
            raise ValueError("record source mismatch")
        return corpus, log, []
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, ImportError,
            json.JSONDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        # Keep details useful without displaying arbitrary data or file contents.
        detail = str(exc) if type(exc) is ValueError and str(exc) in {
            "invalid case or provider", "no provider-specific snapshot", "invalid or credential-bearing log",
            "case identifier mismatch", "provider mismatch", "fixed query mismatch",
            "request parameters do not match the logged query", "provider endpoint mismatch",
            "retrieval timestamp missing or invalid", "corpus filename mismatch",
            "capture log filename mismatch", "missing or invalid SHA-256", "SHA-256 mismatch", "returned row count mismatch",
            "required record fields are missing", "record source mismatch",
        } else "file missing or invalid"
        return None, None, [f"Saved {provider} snapshot unavailable or could not be verified ({detail})."]


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
    if metadata.get("endpoint") not in (None, "", _ENDPOINTS[provider]):
        raise ValueError("Provider response endpoint does not match the fixed search")
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
    if "Source" in corpus and not corpus["Source"].map(_text).eq(provider).all():
        raise ValueError("Provider response contains records from another source")
    # No credential-bearing columns are retained, even if supplied unexpectedly.
    forbidden = re.compile(r"(?:api.?key|authorization|credential|password|secret|token|email)", re.I)
    columns = [column for column in corpus.columns if not forbidden.search(str(column))]
    clean = corpus.loc[:, columns].copy(deep=True).reset_index(drop=True)
    # Provenance is attached by this retrieval, not copied from unrelated state.
    clean["Source"] = provider
    log = _live_log(case_key, provider, query, params, metadata, clean)
    return {"status": "ok", "corpus": clean, "log": log}


def _anonymous_openalex_result(case_key: str, query: str,
                               params: dict[str, Any]) -> dict[str, Any]:
    """Fetch only the disclosed fixed OpenAlex page, without credentials."""
    import guided_provider_search as search
    from openalex_client_loader_v2 import fetch_works

    records, metadata = fetch_works(
        query, None, anonymous=True, per_page=50, max_pages=1,
        year_from=None, year_to=None, publication_types=(),
        search_scope="title_abstract_exact", require_abstract=False,
    )
    if not isinstance(records, list) or len(records) > 50 or not isinstance(metadata, dict):
        raise ValueError("Invalid OpenAlex response")
    pages = _nonnegative_int(_first(metadata, "pages_fetched", "pages"))
    if pages is not None and pages != 1:
        raise ValueError("Invalid OpenAlex page count")
    corpus = search.openalex_records_to_frame(records)

    # The shared client's zero count can also mean a missing meta.count. Do not
    # claim it is a recorded zero, or that discarded/unknown records are complete.
    safe_metadata = metadata.copy()
    total = _nonnegative_int(_first(metadata, "total_matches", "returned_total"))
    if total == 0:
        total = None
        safe_metadata["total_matches"] = None
        safe_metadata["returned_total"] = None
    if len(records) != len(corpus) or (total is not None and total != len(corpus)):
        safe_metadata["possibly_truncated"] = True
    elif total is None and records:
        safe_metadata["possibly_truncated"] = True
    result = _prepare_live_result(case_key, "OpenAlex", query, params, corpus, safe_metadata)
    result["log"]["access_mode"] = "Anonymous server request (no API key or email)"
    return result


def _anonymous_openalex_error_reason(error: Exception) -> str:
    """Map known client statuses to a safe code; never display exception text."""
    try:
        from openalex_client_loader_v2 import OpenAlexError
    except Exception:
        return "other"
    if isinstance(error, OpenAlexError):
        match = re.search(r"\bHTTP\s+(401|429)\b", str(error))
        if match:
            return match.group(1)
    return "other"


def _render_live_retrieval(case_key: str, provider: str, prefix: str
                           ) -> tuple[pd.DataFrame | None, dict[str, Any] | None, str]:
    st.markdown("##### Optional: run a new fixed live search")
    st.caption("No search or credential is needed for the saved example. A successful nonempty live result replaces the saved sample for all stages; results can change. A failed, empty or pending attempt uses the verified saved sample instead.")
    try:
        query, params = _live_plan(case_key, provider)
    except (ImportError, AttributeError, ValueError, KeyError):
        st.info(f"The optional fixed {provider} search is unavailable for this case; no search was run.")
        return None, None, "unavailable"
    st.write("Fixed query that would be sent for an optional live search:")
    st.code(query, language=None)
    st.write(f"Endpoint: {_ENDPOINTS[provider]}")
    st.write("Planned live request parameters (one page only; no editable search):")
    st.json(params, expanded=True)
    if provider == "OpenAlex":
        st.warning("Optional no-key LIVE search: clicking below sends this fixed query from the server to OpenAlex without an API key or email. All users share the server IP's request budget, so OpenAlex may reject or rate-limit requests. It is limited to one page of up to 50 works, is not comprehensive, and results may change over time.")
        st.caption("Alternatively, the browser reads your local JSON credential file and calls OpenAlex directly. The key is not uploaded to the Streamlit server, session state, or logs. Both paths use title_abstract_exact, no year/type filter, and do not require an abstract.")
    state_key = f"{prefix}_provider_{provider.lower().replace(' ', '_')}_result"
    active_key = f"{prefix}_openalex_active"
    attempt_key = f"{prefix}_openalex_attempt"
    if st.button("Use saved sample instead", key=f"{prefix}_{provider.lower().replace(' ', '_')}_use_saved"):
        st.session_state.pop(state_key, None)
        st.session_state[active_key] = False
    if provider == "OpenAlex":
        if st.button("Run no-key LIVE OpenAlex search (server)", key=f"{prefix}_openalex_anonymous_run"):
            # A new attempt replaces any prior result, including a pending browser
            # component, so failure cannot silently reuse stale live records.
            st.session_state.pop(state_key, None)
            st.session_state[active_key] = False
            try:
                with st.spinner("Searching OpenAlex without a key…"):
                    st.session_state[state_key] = _anonymous_openalex_result(case_key, query, params)
            except Exception as exc:
                st.session_state[state_key] = {"status": "error", "reason": _anonymous_openalex_error_reason(exc)}
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
    if result is not None and not isinstance(result, dict):
        st.session_state.pop(state_key, None)
        result = {"status": "error"}
    if isinstance(result, dict) and result.get("status") == "ok":
        saved_log = result.get("log")
        if (not isinstance(saved_log, dict) or saved_log.get("case_key") != case_key
                or saved_log.get("provider") != provider or saved_log.get("source") != provider
                or saved_log.get("endpoint") != _ENDPOINTS[provider] or saved_log.get("query") != query
                or saved_log.get("parameters") != params or not isinstance(result.get("corpus"), pd.DataFrame)
                or saved_log.get("returned") != len(result["corpus"])
                or "Source" not in result["corpus"] or not result["corpus"]["Source"].eq(provider).all()):
            st.session_state.pop(state_key, None)
            result = {"status": "error"}
    if not result:
        st.info(f"No optional {provider} live search has completed for this case; the saved sample is used when verified.")
        return None, None, "pending"
    if result.get("status") != "ok":
        if provider == "OpenAlex" and result.get("reason") == "401":
            st.warning("OpenAlex rejected this anonymous request (HTTP 401). Try the browser-key search or another provider. The verified saved sample is used if available; no previous live result is used.")
            return None, None, "error"
        if provider == "OpenAlex" and result.get("reason") == "429":
            st.warning("OpenAlex rate-limited this anonymous request (HTTP 429). Wait and retry, or use the browser-key search or another provider. The verified saved sample is used if available; no previous live result is used.")
            return None, None, "error"
        st.warning(f"The optional {provider} live search failed or its response was invalid. No previous live result is used; the verified saved sample is used if available.")
        return None, None, "error"
    corpus, log = result["corpus"], result["log"]
    if corpus.empty:
        st.info(f"The optional {provider} live search returned no records. No previous live result is used; the verified saved sample is used if available.")
        return None, None, "empty"
    return corpus, log, "ok"


def render_guided_examples(context: str = "day1", *, data_dir: str | Path | None = None,
                           snapshot_dir: str | Path | None = None) -> None:
    """Render every guided case as four self-contained stages.

    ``context`` namespaces all widget keys when used on different pages.
    ``data_dir`` overrides the manifest directory and confines snapshot lookup
    to its ``guided_provider_snapshots`` subdirectory. ``snapshot_dir`` can
    explicitly override that location. With a custom data directory and no
    snapshot subdirectory, verified legacy Crossref fixture names are supported.
    One verified saved or successful live dataset feeds every stage. Live results
    use guided-only session keys; no credentials or BYOD state are read or written.
    """
    directory = Path(data_dir) if data_dir is not None else GUIDED_DATA_DIR
    snapshots = (Path(snapshot_dir) if snapshot_dir is not None else
                 directory / "guided_provider_snapshots" if data_dir is not None else GUIDED_SNAPSHOT_DIR)
    try:
        cases = load_guided_cases(directory)
    except ValueError as exc:
        st.error(str(exc))
        return
    if not cases:
        st.info("No fixed guided cases are available in the manifest.")
        return
    st.caption("Each case is independent: choose a provider to use its verified saved, one-page sample immediately. A new fixed live search is optional where offered; all stages use the same selected sample.")
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
            # Existing Crossref captures predate provider-slug filenames. Prefer a
            # new pair if either half is present (so corruption cannot cause a
            # silent fallback); otherwise verify the case's original capture.
            crossref_stem = f"{case_key}__crossref"
            use_manifest_capture = (provider == "Crossref" and
                not (snapshots / f"{crossref_stem}.csv").exists() and
                not (snapshots / f"{crossref_stem}.json").exists() and
                snapshot_dir is None)
            corpus, log, errors = load_provider_snapshot(
                case, provider, directory if use_manifest_capture else snapshots,
                legacy_override=use_manifest_capture)
            kind = "saved"
            stage_prefix = prefix if provider == "Crossref" else f"{prefix}_{provider.lower().replace(' ', '_')}"
            with retrieval:
                if provider != "Crossref":
                    live_corpus, live_log, live_status = _render_live_retrieval(case_key, provider, prefix)
                    if live_status == "ok":
                        corpus, log, kind = live_corpus, live_log, "live"
                if corpus is None:
                    for error in errors:
                        st.warning(error)
                _render_retrieval(case, corpus, log, stage_prefix, provider, kind)
            inc, exc = _case_terms(case, "inclusion_terms"), _case_terms(case, "exclusion_terms")
            if inc is None or exc is None:
                st.warning("The case's fixed screening terms are invalid; no decisions will be inferred.")
            screened = screen_records(corpus, inc, exc) if corpus is not None and inc is not None and exc is not None else None
            included = included_records(screened) if screened is not None else None
            selected = (f"Data for this stage: {'verified saved snapshot' if kind == 'saved' else 'successful live retrieval'} from {provider}."
                        if corpus is not None else
                        f"Data for this stage: no verified {provider} snapshot or successful live retrieval is available; see Retrieval.")
            with screening:
                st.caption(selected)
                _render_screening(case, screened, stage_prefix, provider)
            with extraction:
                st.caption(selected)
                _render_extraction(included, stage_prefix, provider)
                _render_ai_illustration(case, included, directory, log, provider)
            with synthesis:
                st.caption(selected)
                _render_synthesis(screened, included, stage_prefix, provider)


__all__ = ["render_guided_examples", "screen_records", "included_records", "candidate_finding_excerpt", "extract_bibliography",
           "year_summary", "safe_csv_bytes", "load_guided_cases", "load_case_data", "load_provider_snapshot"]
