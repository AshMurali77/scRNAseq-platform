# Project: scRNA-seq Annotation Platform

## What this is
A web application that lets users upload single-cell RNA sequencing
datasets (.h5ad files), runs a scanpy preprocessing pipeline, and
returns annotated cell type results. Built as a learning project
with iterative phases.

## Current state (Phase 2 complete)
- FastAPI backend accepts a .h5ad upload, runs the full scanpy
  pipeline, and returns structured JSON results
- React + Tailwind frontend: organism + tissue dropdowns, summary
  stats strip, model info banner, cluster annotation table,
  paginated per-cell results table (Cell ID, Cluster, Cell Type, UMAP X/Y)
- CellTypist annotation running end-to-end with majority_voting=True
- select_model(tissue, organism) in annotate.py maps tissue/organism
  to a CellTypist model via a rule-based lookup table; raises a
  descriptive error for unsupported combinations
- ModelSelection dataclass returned by select_model() carries
  model_name, display_name, and description — stable interface
  for the Phase 3 LLM swap
- Per-cluster label summary (cluster_id → celltypist_label) included
  in PipelineResult and displayed in the UI
- In-memory model cache (_model_cache dict) — models loaded once per
  process lifetime, reused across requests

## Tech stack
- Backend: Python, FastAPI
- Pipeline: scanpy, anndata, celltypist
- Frontend: React, TypeScript, Tailwind CSS, Vite
- Serving: Vite dev server (:5173) proxies to FastAPI (:8000)
- Storage: local filesystem for now, S3 later

## Pipeline steps (in order)
1. QC — filter cells by n_genes_by_counts, total_counts, pct_counts_mt;
   filter genes by min_cells to prevent NaN bin edges downstream
2. Normalize — sc.pp.normalize_total(), sc.pp.log1p()
3. HVGs — sc.pp.highly_variable_genes(n_top_genes=2000)
4. PCA — sc.pp.pca()
5. Neighbors — sc.pp.neighbors()
6. UMAP — sc.tl.umap()
7. Leiden clustering — sc.tl.leiden()
8. Marker genes — sc.tl.rank_genes_groups()
9. CellTypist — model selected via select_model(tissue, organism),
   majority_voting=True, over_clustering='leiden',
   annotates using full gene matrix (adata.raw), not HVG subset;
   loaded models cached in-memory for the process lifetime

## Phase roadmap

### Phase 3 — LLM-powered model selection
- Replace the rule-based select_model() with an LLM call
- Pass models.models_description() catalog as context
- Return structured output: recommended model, reasoning, confidence
- If confidence is low, surface a clarifying question to the user
  before proceeding
- No other changes — Phase 3 is a pure swap of select_model() logic

### Phase 4 — expert validation layer
- For each cluster, take top 10 marker genes from rank_genes_groups,
  the CellTypist label, and tissue context
- Call an LLM to validate whether the label is consistent with known
  biology
- Return per-cluster: confirmed / uncertain / conflicting + one
  paragraph explanation
- Surface this in the UI alongside the existing results table

### Phase 5 — interactive querying
- Let the user ask natural language questions about specific clusters
  in the UI: "Why is cluster 4 labeled monocytes?",
  "What other cell types express these markers?"
- Conversational interface backed by an LLM with access to the
  current adata state as context

### Phase 6 — downstream analysis selection
- Based on the annotated dataset, offer selectable downstream analyses:
  differential expression between conditions, trajectory inference
  if data supports it
- Each analysis is an independent module triggerable from the UI

## Key constraints
- Input files are small .h5ad files only (< 500MB for now)
- Pipeline runs synchronously for Phase 1–2; async job queue in a
  later phase
- All pipeline code must be modular — each step is a separate
  function so steps can be re-run independently
- select_model() must have a stable interface (tissue, organism → model
  filename) so the Phase 3 LLM swap requires no changes to callers

## Coding preferences
- Type hints on all functions
- Docstrings on all public functions
- Raise descriptive errors at each pipeline step so failures
  are traceable
- No notebooks — all code in .py files
