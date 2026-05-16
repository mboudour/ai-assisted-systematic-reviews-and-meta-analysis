# Day 2 — Active Learning and LLM Screening
# AI-Assisted Systematic Reviews and Meta-Analysis — instats Seminar
#
# This script is the R equivalent of scripts/python/day2/Day2_Screening.py
# It applies TF-IDF + Logistic Regression Active Learning and LLM zero-shot
# screening (via Ollama) for the four guided case studies.
#
# Run from the repository root:
#   Rscript scripts/R/day2/Day2_Screening.R
#
# Required packages: tidyverse, tidytext, glmnet, httr2, jsonlite
# Install with: install.packages(c("tidyverse", "tidytext", "glmnet", "httr2", "jsonlite"))
#
# For local LLM: install Ollama from https://ollama.com and run:
#   ollama pull llama3:8b

library(tidyverse)
library(tidytext)
library(glmnet)
library(httr2)
library(jsonlite)

# ── Configuration ──────────────────────────────────────────────────────────────

data_dir <- file.path(dirname(sys.frame(1)$ofile), "..", "..", "..", "data", "cache")
OLLAMA_URL   <- "http://localhost:11434/api/generate"
OLLAMA_MODEL <- "llama3:8b"

case_studies <- list(
  list(
    id = "ex1_health", label = "Health Inequalities in Chronic Disease Care",
    corpus_file = "day1_ex1_health_corpus.csv",
    inclusion_criteria = paste(
      "Include empirical studies (observational, experimental, or mixed-methods)",
      "that measure health outcomes or access to care for patients with chronic diseases",
      "(diabetes, hypertension, cardiovascular disease) and report differences by",
      "socioeconomic status, race, ethnicity, or geographic area.",
      "Exclude editorials, opinion pieces, conference abstracts, and purely theoretical papers."
    ),
    include_terms = c("socioeconomic disparities", "health inequality", "chronic disease outcomes",
                      "diabetes management", "access to care", "racial disparities"),
    exclude_terms = c("editorial", "letter to the editor", "conference abstract", "review protocol")
  ),
  list(
    id = "ex2_ubi", label = "Universal Basic Income (UBI) Policy Outcomes",
    corpus_file = "day1_ex2_ubi_corpus.csv",
    inclusion_criteria = paste(
      "Include empirical evaluations (quantitative, qualitative, or mixed-methods)",
      "of Universal Basic Income programmes or pilots that report measured outcomes",
      "on employment, poverty, well-being, or social behaviour.",
      "Exclude opinion pieces, editorials, theoretical proposals, and grey literature."
    ),
    include_terms = c("randomized controlled trial", "pilot programme", "employment outcomes",
                      "poverty reduction", "well-being", "quasi-experimental"),
    exclude_terms = c("opinion", "commentary", "book review", "policy proposal")
  ),
  list(
    id = "ex3_microplastics", label = "Microplastic Pollution in Aquatic Environments",
    corpus_file = "day1_ex3_microplastics_corpus.csv",
    inclusion_criteria = paste(
      "Include experimental or observational studies that measure microplastic",
      "concentrations, distribution, or ecological impact in freshwater or marine",
      "aquatic environments. Studies must report quantitative measurements.",
      "Exclude purely laboratory studies with no environmental relevance, reviews,",
      "and studies focused on terrestrial environments only."
    ),
    include_terms = c("microplastic concentration", "marine environment", "freshwater",
                      "aquatic organisms", "polymer identification", "field study"),
    exclude_terms = c("terrestrial", "soil contamination", "atmospheric", "review article")
  ),
  list(
    id = "ex4_csr", label = "CSR and Firm Financial Performance",
    corpus_file = "day1_ex4_csr_corpus.csv",
    inclusion_criteria = paste(
      "Include empirical studies that quantitatively measure the relationship between",
      "Corporate Social Responsibility (CSR) activities and firm financial performance",
      "metrics (ROA, ROE, Tobin's Q, stock returns, or similar).",
      "Exclude purely conceptual or theoretical papers, qualitative case studies without",
      "quantitative financial performance data, and editorials."
    ),
    include_terms = c("CSR", "corporate social responsibility", "ROA", "ROE", "Tobin's Q",
                      "financial performance", "empirical", "regression analysis"),
    exclude_terms = c("conceptual framework", "literature review", "qualitative", "editorial")
  )
)

# ── Active Learning ────────────────────────────────────────────────────────────

run_active_learning <- function(df, include_terms, exclude_terms) {
  texts <- paste(
    str_replace_na(df$Title, ""),
    str_replace_na(df$Abstract, ""),
    sep = " "
  )

  # Keyword-seeded labels
  labels <- case_when(
    str_detect(str_to_lower(texts), paste(str_to_lower(include_terms), collapse = "|")) ~ 1L,
    str_detect(str_to_lower(texts), paste(str_to_lower(exclude_terms), collapse = "|")) ~ 0L,
    TRUE ~ -1L
  )

  labelled_idx <- which(labels != -1)
  if (length(labelled_idx) < 4) {
    df$Relevance_Score <- 0.5
    df$AL_Decision     <- "Unlabelled"
    return(df)
  }

  # TF-IDF via tidytext
  text_df <- tibble(doc_id = seq_along(texts), text = texts)
  tfidf <- text_df |>
    unnest_tokens(word, text) |>
    anti_join(stop_words, by = "word") |>
    count(doc_id, word) |>
    bind_tf_idf(word, doc_id, n)

  # Build sparse matrix
  word_list <- tfidf |> distinct(word) |> pull(word)
  doc_word  <- tfidf |> select(doc_id, word, tf_idf) |>
    pivot_wider(names_from = word, values_from = tf_idf, values_fill = 0)

  X <- as.matrix(doc_word[, -1])
  X_train <- X[labelled_idx, , drop = FALSE]
  y_train <- factor(labels[labelled_idx])

  # Logistic Regression via glmnet
  fit <- cv.glmnet(X_train, y_train, family = "binomial", alpha = 0.5)
  probs <- predict(fit, X, s = "lambda.min", type = "response")[, 1]
  preds <- ifelse(probs >= 0.5, "Include", "Exclude")

  df$Relevance_Score <- round(probs, 3)
  df$AL_Decision     <- preds
  df |> arrange(desc(Relevance_Score))
}

# ── LLM Screening via Ollama ───────────────────────────────────────────────────

check_ollama <- function() {
  tryCatch({
    resp <- request("http://localhost:11434/api/tags") |> req_perform()
    resp_status(resp) == 200
  }, error = function(e) FALSE)
}

llm_screen_ollama <- function(title, abstract, inclusion_criteria, model = OLLAMA_MODEL) {
  prompt <- sprintf(
    "You are a systematic review screener. Apply the following inclusion/exclusion criteria.\nRespond with exactly two lines:\nLine 1: Decision: Include OR Decision: Exclude\nLine 2: Justification: [one sentence]\n\nCriteria:\n%s\n\nTitle: %s\nAbstract: %s\n\nYour response:",
    inclusion_criteria, title, substr(abstract, 1, 500)
  )
  tryCatch({
    resp <- request(OLLAMA_URL) |>
      req_body_json(list(model = model, prompt = prompt, stream = FALSE)) |>
      req_timeout(60) |>
      req_perform()
    text <- resp_body_json(resp)$response |> str_trim()
    lines <- str_split(text, "\n")[[1]]
    decision      <- if_else(str_detect(lines[1], "Include"), "Include", "Exclude")
    justification <- if (length(lines) > 1) str_remove(lines[2], "Justification:") |> str_trim() else ""
    list(decision = decision, justification = justification)
  }, error = function(e) {
    list(decision = "Exclude", justification = paste("LLM error:", conditionMessage(e)))
  })
}

# ── Main ───────────────────────────────────────────────────────────────────────

ollama_available <- check_ollama()
if (!ollama_available) {
  cat("⚠️  Ollama is not running. LLM screening will be skipped.\n")
  cat("   To enable: install Ollama from https://ollama.com, then run: ollama pull llama3:8b\n")
}

for (cs in case_studies) {
  cat(sprintf("\n%s\nCase Study: %s\n%s\n", strrep("=", 60), cs$label, strrep("=", 60)))

  corpus_path <- file.path(data_dir, cs$corpus_file)
  if (!file.exists(corpus_path)) {
    cat(sprintf("  ⚠️  Corpus not found: %s. Run Day 1 script first.\n", corpus_path))
    next
  }

  df <- read_csv(corpus_path, show_col_types = FALSE)
  cat(sprintf("  Corpus loaded: %d records.\n", nrow(df)))

  # Active Learning
  cat("  Running Active Learning...\n")
  df_al <- run_active_learning(df, cs$include_terms, cs$exclude_terms)
  n_inc <- sum(df_al$AL_Decision == "Include", na.rm = TRUE)
  n_exc <- sum(df_al$AL_Decision == "Exclude", na.rm = TRUE)
  cat(sprintf("  AL result: %d included, %d excluded.\n", n_inc, n_exc))

  al_path <- file.path(data_dir, sprintf("day2_%s_al_ranked.csv", cs$id))
  write_csv(df_al, al_path)
  cat(sprintf("  AL-ranked corpus saved: %s\n", al_path))

  # LLM Screening
  if (ollama_available) {
    cat(sprintf("  Running LLM screening (Ollama / %s)...\n", OLLAMA_MODEL))
    decisions <- vector("list", nrow(df))
    for (i in seq_len(nrow(df))) {
      if (i %% 10 == 0) cat(sprintf("    Screening record %d/%d...\n", i, nrow(df)))
      decisions[[i]] <- llm_screen_ollama(
        df$Title[i] %||% "", df$Abstract[i] %||% "", cs$inclusion_criteria
      )
      Sys.sleep(0.1)
    }
    df_llm <- df |>
      mutate(
        LLM_Decision      = map_chr(decisions, "decision"),
        LLM_Justification = map_chr(decisions, "justification")
      )
    llm_path <- file.path(data_dir, sprintf("day2_%s_llm_screening.csv", cs$id))
    write_csv(df_llm, llm_path)
    cat(sprintf("  LLM screening saved: %s\n", llm_path))
  }
}

cat("\n✅ Day 2 screening complete.\n")
