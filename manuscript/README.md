# JDIQ Submission Manuscript

This directory contains the complete double-anonymous submission package for the Experience Paper:

- `jdiq_experience_paper.tex` — 10-page ACM `acmsmall` core paper;
- `jdiq_experience_paper.pdf` — compiled core paper;
- `jdiq_online_supplement.tex` — detailed online supplement;
- `jdiq_online_supplement.pdf` — compiled supplement;
- `references.bib` — curated bibliography;
- `figures/denominator_ledger.pdf` and `.png` — core-paper figure.

## Build

```bash
cd manuscript
make all
```

The generated PDFs are copied to the manuscript directory. Build intermediates are written under `build/` and are ignored by Git.

## Submission status

The paper uses the mandatory `Experience:` title prefix and the ACM `acmsmall` class. The core PDF is exactly 10 pages. Both PDFs use anonymous authorship and contain no author name, affiliation, email address, username-bearing repository URL, or placeholder artifact URL. The review artifact should be uploaded as anonymous supplementary material in the submission system; the paper deliberately does not link to the identity-bearing development repository.

The manuscript explicitly discloses that the no-ground-truth research question is a post-outcome amendment. It does not claim screening accuracy, extraction accuracy, evaluator validity, semantic equivalence, historical failure incidence, a valid pooled effect, or calibrated error propagation.
