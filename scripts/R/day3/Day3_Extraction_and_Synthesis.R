# Day 3 — Structured Data Extraction and Synthesis
# AI-Assisted Systematic Reviews and Meta-Analysis — instats Seminar
#
# This script is the R equivalent of scripts/python/day3/Day3_Extraction_and_Synthesis.py
# It demonstrates LLM-assisted extraction (via Ollama) and meta-analysis synthesis
# using the metafor package for the four guided case studies.
#
# Run from the repository root:
#   Rscript scripts/R/day3/Day3_Extraction_and_Synthesis.R
#
# Required packages: tidyverse, httr2, jsonlite, metafor
# Install with: install.packages(c("tidyverse", "httr2", "jsonlite", "metafor"))
#
# For local LLM: install Ollama from https://ollama.com and run:
#   ollama pull llama3:8b

library(tidyverse)
library(httr2)
library(jsonlite)

# metafor is optional — used for meta-analysis only
meta_available <- requireNamespace("metafor", quietly = TRUE)
if (meta_available) library(metafor)

# ── Configuration ──────────────────────────────────────────────────────────────

data_dir     <- file.path(dirname(sys.frame(1)$ofile), "..", "..", "..", "data", "cache")
OLLAMA_URL   <- "http://localhost:11434/api/generate"
OLLAMA_MODEL <- "llama3:8b"

case_studies <- list(
  list(
    id = "ex1_health", label = "Health Inequalities in Chronic Disease Care",
    included_file = "day2_ex1_health_included.csv",
    synthesis_type = "meta_analysis",
    effect_col = "Effect_Size", ci_lower = "CI_Lower", ci_upper = "CI_Upper",
    effect_label = "Risk Ratio (RR)",
    extraction_schema = list(
      Title = "string", Year = "integer", Country = "string",
      Population = "string", Intervention = "string", Comparator = "string",
      Outcome = "string", Effect_Size = "float (risk ratio or odds ratio)",
      CI_Lower = "float (lower 95% CI)", CI_Upper = "float (upper 95% CI)",
      Sample_Size = "integer", Study_Design = "string"
    )
  ),
  list(
    id = "ex2_ubi", label = "Universal Basic Income (UBI) Policy Outcomes",
    included_file = "day2_ex2_ubi_included.csv",
    synthesis_type = "narrative",
    extraction_schema = list(
      Title = "string", Year = "integer", Country = "string",
      Programme_Name = "string", Methodology = "string", Sample_Size = "integer",
      Duration_Months = "integer", Key_Finding_Employment = "string",
      Key_Finding_Wellbeing = "string", Key_Finding_Poverty = "string"
    )
  ),
  list(
    id = "ex3_microplastics", label = "Microplastic Pollution in Aquatic Environments",
    included_file = "day2_ex3_microplastics_included.csv",
    synthesis_type = "quantitative_summary",
    extraction_schema = list(
      Title = "string", Year = "integer", Country = "string",
      Environment_Type = "string", Concentration_Mean = "float",
      Concentration_Unit = "string", Polymer_Types = "string",
      Sample_Size = "integer", Detection_Method = "string"
    )
  ),
  list(
    id = "ex4_csr", label = "CSR and Firm Financial Performance",
    included_file = "day2_ex4_csr_included.csv",
    synthesis_type = "meta_analysis",
    effect_col = "Correlation_r", ci_lower = "CI_Lower", ci_upper = "CI_Upper",
    effect_label = "Correlation Coefficient (r)",
    extraction_schema = list(
      Title = "string", Year = "integer", Country = "string",
      CSR_Measure = "string", FP_Measure = "string",
      Correlation_r = "float", CI_Lower = "float", CI_Upper = "float",
      Sample_Size = "integer", Industry_Sector = "string"
    )
  )
)

# ── LLM Extraction via Ollama ──────────────────────────────────────────────────

check_ollama <- function() {
  tryCatch({
    resp <- request("http://localhost:11434/api/tags") |> req_perform()
    resp_status(resp) == 200
  }, error = function(e) FALSE)
}

llm_extract_ollama <- function(title, abstract, schema, model = OLLAMA_MODEL) {
  schema_str <- paste(
    sprintf("  - %s: %s", names(schema), unlist(schema)),
    collapse = "\n"
  )
  prompt <- sprintf(
    "You are a systematic review data extractor. Extract the following fields.\nReturn a valid JSON object with exactly these keys:\n%s\n\nIf a field cannot be determined, use null.\n\nTitle: %s\nAbstract: %s\n\nJSON output:",
    schema_str, title, substr(abstract, 1, 600)
  )
  tryCatch({
    resp <- request(OLLAMA_URL) |>
      req_body_json(list(model = model, prompt = prompt, stream = FALSE)) |>
      req_timeout(90) |>
      req_perform()
    text <- resp_body_json(resp)$response |> str_trim()
    start <- str_locate(text, "\\{")[1]
    end   <- str_locate_all(text, "\\}")[[1]]
    end   <- end[nrow(end), 2]
    if (!is.na(start) && !is.na(end)) {
      fromJSON(substr(text, start, end))
    } else {
      setNames(rep(list(NULL), length(schema)), names(schema))
    }
  }, error = function(e) {
    setNames(rep(list(NULL), length(schema)), names(schema))
  })
}

# ── Forest Plot via metafor ────────────────────────────────────────────────────

draw_forest_metafor <- function(df, effect_col, ci_lower, ci_upper, effect_label, output_path) {
  if (!meta_available) {
    cat("  metafor not installed. Skipping forest plot.\n")
    cat("  Install with: install.packages('metafor')\n")
    return(invisible(NULL))
  }

  # Compute SE from CI
  df <- df |>
    mutate(
      yi = .data[[effect_col]],
      sei = (.data[[ci_upper]] - .data[[ci_lower]]) / 3.92
    ) |>
    filter(!is.na(yi), !is.na(sei), sei > 0)

  if (nrow(df) < 2) {
    cat("  Not enough studies for meta-analysis.\n")
    return(invisible(NULL))
  }

  res <- metafor::rma(yi = yi, sei = sei, data = df, method = "REML")
  cat(sprintf("  Pooled %s: %.3f [%.3f, %.3f]\n",
              effect_label, res$b[1], res$ci.lb, res$ci.ub))

  png(output_path, width = 900, height = max(400, nrow(df) * 60 + 150), res = 120)
  metafor::forest(res,
    slab    = str_trunc(df$Title, 55),
    xlab    = effect_label,
    header  = c("Study", effect_label),
    refline = if (str_detect(effect_label, "Ratio")) 1 else 0
  )
  dev.off()
  cat(sprintf("  Forest plot saved: %s\n", output_path))
  invisible(res)
}

# ── Main ───────────────────────────────────────────────────────────────────────

ollama_available <- check_ollama()
if (!ollama_available) {
  cat("⚠️  Ollama is not running. LLM extraction will be skipped.\n")
  cat("   To enable: install Ollama from https://ollama.com, then run: ollama pull llama3:8b\n")
}

for (cs in case_studies) {
  cat(sprintf("\n%s\nCase Study: %s\n%s\n", strrep("=", 60), cs$label, strrep("=", 60)))

  included_path <- file.path(data_dir, cs$included_file)
  if (!file.exists(included_path)) {
    cat(sprintf("  ⚠️  Included studies file not found: %s. Run Day 2 script first.\n", included_path))
    next
  }

  df <- read_csv(included_path, show_col_types = FALSE)
  cat(sprintf("  Included studies loaded: %d records.\n", nrow(df)))

  # LLM Extraction
  if (ollama_available) {
    cat(sprintf("  Running LLM extraction (Ollama / %s)...\n", OLLAMA_MODEL))
    extracted_rows <- vector("list", nrow(df))
    for (i in seq_len(nrow(df))) {
      if (i %% 5 == 0) cat(sprintf("    Extracting record %d/%d...\n", i, nrow(df)))
      extracted_rows[[i]] <- llm_extract_ollama(
        df$Title[i] %||% "", df$Abstract[i] %||% "", cs$extraction_schema
      )
    }
    df_extracted <- bind_rows(lapply(extracted_rows, as_tibble))
    extract_path <- file.path(data_dir, sprintf("day3_%s_extraction.csv", cs$id))
    write_csv(df_extracted, extract_path)
    cat(sprintf("  Extraction saved: %s\n", extract_path))
  } else {
    cat("  Skipping LLM extraction (Ollama not available).\n")
    df_extracted <- df
  }

  # Forest plot for meta-analysis cases
  if (cs$synthesis_type == "meta_analysis") {
    required_cols <- c(cs$effect_col, cs$ci_lower, cs$ci_upper, "Title")
    if (all(required_cols %in% names(df_extracted))) {
      forest_path <- file.path(data_dir, sprintf("day3_%s_forest.png", cs$id))
      draw_forest_metafor(df_extracted, cs$effect_col, cs$ci_lower, cs$ci_upper,
                          cs$effect_label, forest_path)
    }
  }
}

cat("\n✅ Day 3 extraction and synthesis complete.\n")

`%||%` <- function(a, b) if (!is.null(a) && !is.na(a)) a else b
