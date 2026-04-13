# Project: scRNA-seq Annotation Platform

## What this is
A web application that lets users upload single-cell RNA sequencing
datasets (.h5ad files), runs a scanpy preprocessing pipeline, and
returns annotated cell type results. Built as a learning project
with iterative phases.

## Current state (Phase 3 complete)
- FastAPI backend: two endpoints — `POST /select-model` and `POST /analyze`
  - `/select-model` runs LLM or rule-based model selection before any file upload
  - `/analyze` accepts a .h5ad upload, runs the full scanpy pipeline, returns JSON
- React + Tailwind frontend:
  - LLM / Rule-based toggle in the upload form
  - LLM mode: free-text tissue input; Rule-based mode: constrained dropdown
  - Clarification card (amber) surfaces LLM questions to the user; capped at
    `_MAX_CLARIFICATION_ROUNDS = 2` — after that the LLM proceeds with its best
    guess regardless of confidence
  - Model info banner shows display_name, description, reasoning, confidence %
    (green ≥85%, amber ≥70%, red <70%)
  - Summary stats strip, cluster annotation table, paginated per-cell results
    (Cell ID, Cluster, Cell Type, UMAP X/Y)
  - UMAP plots rendered inline: 2-column grid of base64 PNG images
- CellTypist annotation running end-to-end with majority_voting=True
- In-memory model cache (_model_cache dict) — models loaded once per process
  lifetime, reused across requests
- ANTHROPIC_API_KEY loaded from `.env` via `python-dotenv`

## Tech stack
- Backend: Python, FastAPI, `anthropic` SDK, `python-dotenv`
- Pipeline: scanpy, anndata, celltypist
- Frontend: React, TypeScript, Tailwind CSS, Vite
- Serving: Vite dev server (:5173) proxies `/analyze` and `/select-model` to FastAPI (:8000)
- Storage: local filesystem for now, S3 later

## Key files
- `app/main.py` — FastAPI app, `/select-model` and `/analyze` endpoints
- `app/models/schemas.py` — Pydantic models: `ModelSelectionRequest`,
  `ModelSelection`, `PipelineParams`, `PipelineResult`, `CellMetadata`,
  `ClusterSummary`, `MarkerGene`, `QCParams`
- `app/pipeline/annotate.py` — `select_model()`, `_llm_select_model()`,
  `_rule_based_select_model()`, `run_celltypist()`, `run_marker_genes()`
- `app/pipeline/plot.py` — `generate_plots()` returns base64 UMAPs; non-fatal
- `app/pipeline/qc.py`, `normalize.py`, `reduce.py`, `cluster.py` — pipeline steps
- `app/utils/errors.py` — `PipelineStepError(step, message)`
- `app/utils/io.py` — `load_h5ad()`, `stage_upload()`
- `frontend/src/App.tsx` — state machine: idle → selecting_model →
  clarification_needed → loading → done / error
- `frontend/src/components/UploadForm.tsx` — file drop, organism/tissue,
  LLM/rule-based toggle
- `frontend/src/components/ResultsTable.tsx` — model banner, UMAPs, cluster
  table, per-cell table with pagination
- `frontend/src/services/api.ts` — `selectModel()`, `analyze()`
- `frontend/src/types/pipeline.ts` — TypeScript interfaces mirroring backend schemas
- `frontend/vite.config.ts` — proxy config (must include all backend routes)
- `.env` / `.env.example` — `ANTHROPIC_API_KEY=`

## Model selection architecture
Two modes toggled per-request via `use_llm: bool`:

**LLM mode** (`use_llm=True`, default)
- Calls `claude-haiku-4-5` via `client.messages.parse()` with structured output
- System prompt includes full `celltypist.models.models_description()` catalog,
  explicit filename allowlist, and a 5-tier confidence calibration scale:
  - 0.95+ exact match, 0.80–0.94 synonym, 0.55–0.79 approximate,
    0.30–0.54 weak, <0.30 no match
- `_CONFIDENCE_THRESHOLD = 0.7` — below this, LLM returns a `clarifying_question`
- `_MAX_CLARIFICATION_ROUNDS = 2` — after this many rounds, question is suppressed
  and best-guess selection is returned with whatever confidence the LLM reported
- Post-hoc validation: returned `model_name` must be in the fetched filename list;
  raises `PipelineStepError` if not (prevents hallucinated filenames reaching pipeline)
- `clarification_round` counter is passed from frontend → request body → annotate.py
  to enforce the cap without session state on the server

**Rule-based mode** (`use_llm=False`)
- Deterministic `_RULE_BASED_LOOKUP` dict: `(tissue_lower, organism_lower)` →
  `(model_name, display_name, description)`
- Supported: human blood/pbmc/spleen/lymph node/thymus/lung/brain/hippocampus/
  colon/colorectal/heart; mouse lung/brain/hippocampus/cortex
- Returns `confidence=1.0`, no clarifying question
- Raises `PipelineStepError` with full supported list on miss

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
9. CellTypist — model pre-selected via `/select-model`, passed as `model_name`
   in `PipelineParams`; majority_voting=True, over_clustering='leiden';
   annotates using full gene matrix (adata.raw), not HVG subset

## Plots
- `app/pipeline/plot.py` — `generate_plots(adata)` called after pipeline
- Uses `matplotlib.use("Agg")` (non-interactive, set at module level)
- Returns `{"umap_clusters": <b64>, "umap_celltypes": <b64>}` or empty dict
- Each plot is generated independently; exceptions are caught and logged,
  so a plot failure never blocks the pipeline result
- `PipelineResult.plots: dict[str, str]` carries the base64 strings to the frontend

## Frontend state machine (App.tsx)
```
idle
  → selecting_model   (on form submit; calls POST /select-model)
  → clarification_needed  (if response.clarifying_question is set)
      round counter increments each time; clarification_round passed to next request
  → loading           (on confident selection; calls POST /analyze)
  → done | error
```

## Key constraints
- Input files are small .h5ad files only (< 500MB for now)
- Pipeline runs synchronously; async job queue in a later phase
- All pipeline code must be modular — each step is a separate function
- `/select-model` and `/analyze` are separate so model selection fails fast
  before a large file upload begins
- LLM is called only in `/select-model`, never in `/analyze`

## Coding preferences
- Type hints on all functions
- Docstrings on all public functions
- Raise descriptive errors at each pipeline step so failures are traceable
- No notebooks — all code in .py files

## Phase roadmap

### Phase 4 — expert validation layer
- For each cluster, take top 10 marker genes from rank_genes_groups,
  the CellTypist label, and tissue context
- Call an LLM to validate whether the label is consistent with known biology
- Return per-cluster: confirmed / uncertain / conflicting + one paragraph explanation
- Surface this in the UI alongside the existing results table

### Phase 5 — interactive querying
- Let the user ask natural language questions about specific clusters in the UI:
  "Why is cluster 4 labeled monocytes?", "What other cell types express these markers?"
- Conversational interface backed by an LLM with access to the current adata state

### Phase 6 — downstream analysis selection
- Based on the annotated dataset, offer selectable downstream analyses:
  differential expression between conditions, trajectory inference if data supports it
- Each analysis is an independent module triggerable from the UI
