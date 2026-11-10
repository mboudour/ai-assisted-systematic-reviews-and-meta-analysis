"""User-facing OpenAIRE limitations shared across the workshop pages."""

OPENAIRE_LIMITATIONS = (
    "**OpenAIRE limitations:** No participant API key or email is required, but anonymous "
    "requests are limited to up to 60 per hour under OpenAIRE's policy; participants using "
    "one hosted app may share the limit and can encounter HTTP 429. Results may be truncated "
    "by the selected page limit. Coverage varies; publications can include preprints, theses "
    "and other non-peer-reviewed material. Abstracts, DOIs and other metadata may be missing; "
    "descriptions shown as abstracts may not be formal abstracts. The Concepts column contains "
    "OpenAIRE subject labels, not OpenAlex concepts. Search is across broad "
    "metadata, not just titles and abstracts. This app does not apply year, specific publication-"
    "type or abstract filters to OpenAIRE. Check eligibility and acknowledge OpenAIRE as the "
    "data source. OpenAIRE records are exported as generic RIS entries, not verified journal "
    "articles. [OpenAIRE terms and limits](https://graph.openaire.eu/docs/apis/terms)."
)


def source_column_mentions_openaire(frame):
    """Identify an explicit Source column, without claiming it proves provenance."""
    if frame is None or 'Source' not in frame.columns:
        return False
    return bool(frame['Source'].fillna('').astype(str).str.strip().str.casefold().eq('openaire').any())
