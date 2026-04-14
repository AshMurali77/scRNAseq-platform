# Project: scRNA-seq Annotation Platform

## What this is
A web application that lets users upload single-cell RNA sequencing
datasets (.h5ad files), runs a scanpy preprocessing pipeline, and
returns annotated cell type results. Built as a learning project
with iterative phases.

## Current state (Phase 5 complete)
- FastAPI backend: three endpoints — `POST /select-model`, `POST /analyze`, `POST /query`
  - `/select-model` runs LLM or rule-based model selection before any file upload
  - `/analyze` accepts a .h5ad upload, runs the full scanpy pipeline, returns JSON
  - `/query` accepts a natural-language question + conversation history + compressed
    context; returns an LLM-generated answer about the pipeline results
- React + Tailwind frontend:
  - LLM / Rule-based toggle in the upload form gates ALL LLM calls (model
    selection + expert validation + chat); rule-based mode makes zero API calls
  - "Dataset is pre-filtered" checkbox skips QC cell filtering; normalization
    is auto-detected separately
  - Clarification card (amber) surfaces LLM questions to the user; capped at
    `_MAX_CLARIFICATION_ROUNDS = 2` — after that the LLM proceeds with its best
    guess regardless of confidence
  - Model info banner: display_name, description, reasoning, confidence %
    (green ≥85%, amber ≥70%, red <70%)
  - Dataset metadata banner: shows organism/tissue found in h5ad file (or
    "not found" if absent); turns red if organism doesn't match user selection
  - Cluster annotations table with expert review badges (Confirmed / Uncertain /
    Conflicting); click a row to expand the LLM explanation + marker genes used
  - Interactive UMAP plots rendered client-side via Canvas from cell coordinates;
    clicking a per-cell table row highlights that cell on both UMAPs simultaneously
  - Per-cell table: compact rows, Cluster / Annotation / Cell Type columns,
    cluster + cell type filter dropdowns, paginated (50 per page)
  - Chat panel (LLM mode only): conversational interface below results; supports
    multi-turn questions about clusters, marker genes, and annotations; assistant
    responses rendered as GFM markdown (bold, lists, tables, code blocks)
- CellTypist annotation running end-to-end with majority_voting=True
- In-memory model cache (_model_cache dict) — models loaded once per process
  lifetime, reused across requests
- ANTHROPIC_API_KEY loaded from `.env` via `python-dotenv`

## Tech stack
- Backend: Python, FastAPI, `anthropic` SDK, `python-dotenv`
- Pipeline: scanpy, anndata, celltypist
- Frontend: React, TypeScript, Tailwind CSS, Vite
- Frontend deps: `react-markdown`, `remark-gfm` (markdown rendering in chat)
- Serving: Vite dev server (:5173) proxies `/analyze`, `/select-model`, `/query`
  to FastAPI (:8000)
- Storage: local filesystem for now, S3 later

## Key files
- `app/main.py` — FastAPI app; `logger = logging.getLogger(__name__)` defined here
- `app/models/schemas.py` — Pydantic models: `ModelSelectionRequest`,
  `ModelSelection`, `PipelineParams`, `PipelineResult`, `CellMetadata`,
  `ClusterSummary`, `MarkerGene`, `QCParams`, `ClusterValidation`, `DatasetMetadata`,
  `ConversationMessage`, `QueryContext`, `QueryRequest`, `QueryResponse`
- `app/pipeline/annotate.py` — `select_model()`, `_llm_select_model()`,
  `_rule_based_select_model()`, `run_celltypist()`, `run_marker_genes()`
- `app/pipeline/validate.py` — `validate_cluster_labels()`: batches all clusters
  into one `claude-opus-4-6` call with adaptive thinking; non-fatal
- `app/pipeline/query.py` — `answer_query(question, history, context)`: builds
  structured context text from `QueryContext`, calls `claude-opus-4-6` (no
  thinking), supports multi-turn via `conversation_history`
- `app/pipeline/metadata.py` — `extract_and_check_metadata()`: reads h5ad uns/obs
  for organism/tissue, normalises scientific names, flags organism mismatches
- `app/pipeline/plot.py` — `generate_plots()` returns base64 UMAPs; non-fatal
- `app/pipeline/qc.py` — `run_qc(skip=False)`: skip=True bypasses cell filtering
- `app/pipeline/normalize.py` — auto-detects log-normalization via
  `adata.uns['log1p']` + max-value heuristic; skips normalize/log1p if detected
- `app/pipeline/reduce.py`, `cluster.py` — PCA/neighbors/UMAP, Leiden clustering
- `app/utils/errors.py` — `PipelineStepError(step, message)`
- `app/utils/io.py` — `load_h5ad()`, `stage_upload()`
- `frontend/src/App.tsx` — state machine (see below); `done` state carries
  `tissue`, `organism`, `useLlm` for the chat panel
- `frontend/src/components/UploadForm.tsx` — file drop, organism/tissue,
  LLM/rule-based toggle, pre-filtered checkbox
- `frontend/src/components/ResultsTable.tsx` — metadata banner, model banner,
  cluster table with validation badges, interactive Canvas UMAPs, per-cell table
- `frontend/src/components/UmapPlot.tsx` — Canvas-based UMAP; ResizeObserver
  for responsive sizing; highlighted cell drawn last with amber+white halo
- `frontend/src/components/ChatPanel.tsx` — multi-turn chat UI; builds
  `QueryContext` via `useMemo` from result prop; assistant messages rendered
  with `ReactMarkdown` + `remark-gfm` (tables, bold, lists, code, headings)
- `frontend/src/services/api.ts` — `selectModel()`, `analyze()`, `queryPipeline()`
- `frontend/src/types/pipeline.ts` — TypeScript interfaces mirroring backend schemas
- `frontend/vite.config.ts` — proxy config (must include all backend routes)
- `.env` / `.env.example` — `ANTHROPIC_API_KEY=`

## LLM cost gating
`use_llm: bool` flows from the UI toggle → `PipelineParams` → `/analyze`.
When `use_llm=False` (rule-based mode), **zero** LLM calls are made anywhere:
- `/select-model` uses the deterministic lookup table
- `/analyze` skips `validate_cluster_labels()` entirely
- Chat panel is not rendered (hidden entirely in rule-based mode)

When `use_llm=True`:
- `/select-model` calls `claude-haiku-4-5` for model selection
- `/analyze` calls `claude-opus-4-6` with adaptive thinking for expert validation
- `/query` calls `claude-opus-4-6` (no thinking) for each chat turn

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

## Expert validation (Phase 4)
- `app/pipeline/validate.py` — `validate_cluster_labels(adata, tissue, organism)`
- Extracts top 10 Wilcoxon marker genes per cluster (gene, score, logFC)
- All clusters sent in a single `claude-opus-4-6` prompt with adaptive thinking
- Structured output: `_ValidationResponse` containing list of `_ClusterValidationItem`
- Each item: `cluster_id`, `status` (confirmed/uncertain/conflicting), `explanation`
- Post-merge: missing cluster IDs default to `uncertain` with a placeholder message
- Non-fatal: any exception returns empty list; pipeline result still returned

## Interactive querying (Phase 5)
- `app/pipeline/query.py` — `answer_query(question, history, context)`
- `_build_context_text(ctx)`: serializes `QueryContext` into a structured markdown
  block covering dataset stats, file metadata, and per-cluster annotations
  (CellTypist label + expert review status + explanation + top 10 marker genes)
- Uses `claude-opus-4-6` without adaptive thinking (queries are direct; no
  complex reasoning needed; avoids multi-turn thinking-block state management)
- `QueryContext` is a compressed subset of `PipelineResult` — excludes `cells`
  (per-cell coordinates) and `plots` (base64 images) to keep payload small
- Stateless: full context + conversation history travel with every request;
  no server-side session state
- `POST /query` endpoint in `app/main.py`; raises 400 on API failure
- Frontend `ChatPanel.tsx`:
  - `QueryContext` built once via `useMemo` from the result prop
  - Message list auto-scrolls to bottom on new message
  - User messages: plain text, right-aligned, blue background
  - Assistant messages: rendered via `ReactMarkdown` + `remark-gfm`
    (supports bold, italic, lists, inline code, code blocks, headings, GFM tables)
  - Loading state shown as animated "Thinking…" bubble
  - Enter key sends; Shift+Enter does nothing (single-line input)
  - Only rendered when `useLlm=true` (hidden entirely in rule-based mode)

## Dataset metadata validation (Phase 4)
- `app/pipeline/metadata.py` — `extract_and_check_metadata(adata, tissue, organism)`
- Called immediately after `load_h5ad`, before QC, on the unmodified object
- Checks `adata.uns` then modal `adata.obs` column for priority-ordered key lists:
  - Organism: `organism`, `species`, `organism_ontology_term_id`, etc.
  - Tissue: `tissue`, `tissue_type`, `organ`, `tissue_ontology_term_id`, etc.
- Normalises scientific names via `_ORGANISM_SYNONYMS` map
  (e.g. `Homo sapiens`, `NCBITaxon:9606` → `human`)
- Sets `organism_mismatch=True` when normalised file organism ≠ provided organism
- Tissue is reported but not flagged — too many synonyms for reliable comparison
- UI shows both fields always; "not found" in muted italic if absent

## Pre-filtered dataset support
- `PipelineParams.skip_qc: bool = False` — passed via form checkbox
- `run_qc(skip=True)`: skips cell filtering; gene filtering (`min_cells`) still runs
  (required to prevent NaN bin edges in HVG selection)
- `run_normalize()` auto-detects log-normalization:
  1. Checks `adata.uns.get('log1p')` (set by `sc.pp.log1p()`) — most reliable
  2. Heuristic: max value < 30 → treat as log-normalized
  - If detected: skips `normalize_total` + `log1p`; preserves existing `adata.raw`
  - If not detected: runs full normalization pipeline as before

## Interactive UMAP (Canvas-based)
- `frontend/src/components/UmapPlot.tsx` — replaces static backend PNG images
- Renders all cells as 2px circles from `result.cells` umap_x/umap_y coordinates
- `ResizeObserver` redraws on container resize; `devicePixelRatio` for retina
- Highlighted cell: 8px white halo + 6px amber fill, drawn last (always on top)
- Color map: Tableau-20 palette, HSL fallback for >20 categories
- Per-cluster and per-cell-type views rendered simultaneously; both update on row click
- Backend still generates PNG plots but they are no longer rendered in the UI

## Pipeline steps (in order)
1. QC — filter cells by n_genes_by_counts, pct_counts_mt (skippable);
   filter genes by min_cells always runs
2. Normalize — auto-detects if already log-normalized; stores full matrix in
   adata.raw before HVG subsetting
3. HVGs — sc.pp.highly_variable_genes(n_top_genes=2000)
4. PCA — sc.pp.pca()
5. Neighbors — sc.pp.neighbors()
6. UMAP — sc.tl.umap()
7. Leiden clustering — sc.tl.leiden()
8. Marker genes — sc.tl.rank_genes_groups() (Wilcoxon)
9. CellTypist — model pre-selected via `/select-model`, majority_voting=True,
   over_clustering='leiden'; annotates using adata.raw (full gene matrix)
10. Expert validation — `validate_cluster_labels()` (LLM mode only, non-fatal)

## Frontend state machine (App.tsx)
```
idle
  → selecting_model   (on form submit; calls POST /select-model)
  → clarification_needed  (if response.clarifying_question is set)
      stores: file, tissue, organism, useLlm, skipQc, round
      round increments each submit; clarification_round sent to backend
  → loading           (on confident selection; calls POST /analyze)
  → done | error
      done stores: result, modelSelection, tissue, organism, useLlm
```
`useLlm` and `skipQc` are carried through every state transition and passed
into `analyze()` at the end. `tissue` and `organism` are stored in `done`
so `ChatPanel` can include them in the `QueryContext`.

## Key constraints
- Input files are small .h5ad files only (< 500MB for now)
- Pipeline runs synchronously; async job queue in a later phase
- All pipeline code must be modular — each step is a separate function
- `/select-model` and `/analyze` are separate so model selection fails fast
  before a large file upload begins

## Coding preferences
- Type hints on all functions
- Docstrings on all public functions
- Raise descriptive errors at each pipeline step so failures are traceable
- No notebooks — all code in .py files

## Phase roadmap

### Phase 6 — downstream analysis selection
- Based on the annotated dataset, offer selectable downstream analyses:
  differential expression between conditions, trajectory inference if data supports it
- Each analysis is an independent module triggerable from the UI
