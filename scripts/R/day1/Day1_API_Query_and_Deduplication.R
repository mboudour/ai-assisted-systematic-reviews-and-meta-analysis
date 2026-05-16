# Day 1 — API Query and Deduplication
# AI-Assisted Systematic Reviews and Meta-Analysis — instats Seminar
#
# This script is the R equivalent of scripts/python/day1/Day1_API_Query_and_Deduplication.py
# It queries OpenAlex and Semantic Scholar for the four guided case studies and
# deduplicates the resulting corpora.
#
# Run from the repository root:
#   Rscript scripts/R/day1/Day1_API_Query_and_Deduplication.R
#
# Required packages: httr2, jsonlite, dplyr, readr, stringr
# Install with: install.packages(c("httr2", "jsonlite", "dplyr", "readr", "stringr"))

library(httr2)
library(jsonlite)
library(dplyr)
library(readr)
library(stringr)

# ── Configuration ──────────────────────────────────────────────────────────────

output_dir <- file.path(dirname(sys.frame(1)$ofile), "..", "..", "..", "data", "cache")
dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

case_studies <- list(
  list(id = "ex1_health",       label = "Health Inequalities in Chronic Disease Care",
       api = "openalex",        query = "health inequalities diabetes care socioeconomic",
       per_page = 50, max_pages = 2),
  list(id = "ex2_ubi",          label = "Universal Basic Income (UBI) Policy Outcomes",
       api = "semantic_scholar", query = "universal basic income policy evaluation outcomes",
       limit = 50),
  list(id = "ex3_microplastics", label = "Microplastic Pollution in Aquatic Environments",
       api = "openalex",        query = "microplastics aquatic marine pollution concentration",
       per_page = 50, max_pages = 2),
  list(id = "ex4_csr",          label = "CSR and Firm Financial Performance",
       api = "openalex",        query = "corporate social responsibility firm financial performance empirical",
       per_page = 50, max_pages = 2)
)

# ── OpenAlex query ─────────────────────────────────────────────────────────────

query_openalex <- function(search_query, per_page = 50, max_pages = 2) {
  records <- list()
  cursor  <- "*"
  for (page in seq_len(max_pages)) {
    cat(sprintf("  Fetching page %d...\n", page))
    resp <- request("https://api.openalex.org/works") |>
      req_url_query(
        search   = search_query,
        filter   = "has_abstract:true,type:article",
        per_page = per_page,
        select   = "id,doi,title,publication_year,authorships,host_venue,abstract_inverted_index,cited_by_count,concepts",
        cursor   = cursor
      ) |>
      req_perform()
    data    <- resp_body_json(resp, simplifyVector = FALSE)
    batch   <- data$results
    records <- c(records, batch)
    cursor  <- data$meta$next_cursor
    if (is.null(cursor)) break
    Sys.sleep(0.5)
  }
  records
}

# ── Semantic Scholar query ─────────────────────────────────────────────────────

query_semantic_scholar <- function(search_query, limit = 50) {
  resp <- request("https://api.semanticscholar.org/graph/v1/paper/search") |>
    req_url_query(
      query  = search_query,
      limit  = limit,
      fields = "paperId,externalIds,title,year,authors,venue,abstract,citationCount,fieldsOfStudy"
    ) |>
    req_perform()
  resp_body_json(resp, simplifyVector = FALSE)$data
}

# ── Flatten OpenAlex records ───────────────────────────────────────────────────

reconstruct_abstract <- function(inv) {
  if (is.null(inv) || length(inv) == 0) return("")
  all_positions <- unlist(inv)
  max_pos <- max(all_positions)
  words <- rep("", max_pos + 1)
  for (word in names(inv)) {
    for (pos in inv[[word]]) {
      words[pos + 1] <- word
    }
  }
  paste(words, collapse = " ") |> str_squish()
}

openalex_to_df <- function(records) {
  rows <- lapply(records, function(r) {
    abstract <- reconstruct_abstract(r$abstract_inverted_index)
    authors  <- paste(
      sapply(head(r$authorships %||% list(), 5),
             function(a) a$author$display_name %||% ""),
      collapse = "; "
    )
    venue    <- r$host_venue$display_name %||% ""
    concepts <- paste(
      sapply(head(r$concepts %||% list(), 5),
             function(c) c$display_name %||% ""),
      collapse = "; "
    )
    data.frame(
      ID        = r$id %||% "",
      DOI       = r$doi %||% "",
      Title     = r$title %||% "",
      Year      = r$publication_year %||% NA_integer_,
      Authors   = authors,
      Venue     = venue,
      Abstract  = abstract,
      Citations = r$cited_by_count %||% 0L,
      Concepts  = concepts,
      stringsAsFactors = FALSE
    )
  })
  bind_rows(rows)
}

semantic_scholar_to_df <- function(records) {
  rows <- lapply(records, function(r) {
    authors <- paste(
      sapply(head(r$authors %||% list(), 5), function(a) a$name %||% ""),
      collapse = "; "
    )
    fields <- paste(unlist(r$fieldsOfStudy %||% list()), collapse = "; ")
    doi    <- r$externalIds$DOI %||% ""
    data.frame(
      ID        = r$paperId %||% "",
      DOI       = doi,
      Title     = r$title %||% "",
      Year      = r$year %||% NA_integer_,
      Authors   = authors,
      Venue     = r$venue %||% "",
      Abstract  = r$abstract %||% "",
      Citations = r$citationCount %||% 0L,
      Fields    = fields,
      stringsAsFactors = FALSE
    )
  })
  bind_rows(rows)
}

# ── Deduplication ──────────────────────────────────────────────────────────────

deduplicate_df <- function(df) {
  has_doi  <- df |> filter(str_trim(DOI) != "")
  no_doi   <- df |> filter(str_trim(DOI) == "")
  has_doi  <- has_doi |> distinct(DOI, .keep_all = TRUE)
  no_doi   <- no_doi  |> mutate(.title_norm = str_to_lower(str_trim(Title))) |>
                          distinct(.title_norm, .keep_all = TRUE) |>
                          select(-.title_norm)
  bind_rows(has_doi, no_doi)
}

# Null-coalescing helper
`%||%` <- function(a, b) if (!is.null(a)) a else b

# ── Main ───────────────────────────────────────────────────────────────────────

for (cs in case_studies) {
  cat(sprintf("\n%s\nCase Study: %s\nAPI: %s  |  Query: %s\n%s\n",
              strrep("=", 60), cs$label, cs$api, cs$query, strrep("=", 60)))

  raw_path <- file.path(output_dir, sprintf("day1_%s_raw.json", cs$id))
  csv_path <- file.path(output_dir, sprintf("day1_%s_corpus.csv", cs$id))

  if (file.exists(raw_path)) {
    cat(sprintf("  Loading from cache: %s\n", raw_path))
    records <- fromJSON(raw_path, simplifyVector = FALSE)
  } else {
    cat(sprintf("  Fetching from %s...\n", cs$api))
    if (cs$api == "openalex") {
      records <- query_openalex(cs$query, cs$per_page, cs$max_pages)
    } else {
      records <- query_semantic_scholar(cs$query, cs$limit)
    }
    write_json(records, raw_path, pretty = TRUE, auto_unbox = TRUE)
    cat(sprintf("  Saved raw JSON: %s\n", raw_path))
  }

  if (cs$api == "openalex") {
    df <- openalex_to_df(records)
  } else {
    df <- semantic_scholar_to_df(records)
  }

  before <- nrow(df)
  df     <- deduplicate_df(df)
  after  <- nrow(df)
  cat(sprintf("  Records retrieved: %d  |  After deduplication: %d\n", before, after))

  write_csv(df, csv_path)
  cat(sprintf("  Corpus saved: %s\n", csv_path))
}

cat("\n✅ All four case study corpora generated successfully.\n")
