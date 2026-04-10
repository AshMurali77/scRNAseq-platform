# Project: scRNA-seq Annotation Platform

## What this is
A web application that lets users upload single-cell RNA sequencing 
datasets (.h5ad files), runs a scanpy preprocessing pipeline, and 
returns annotated cell type results. Built as a learning project 
with iterative phases.

## Current phase
Phase 1 — pipeline wrapper with no AI. Goal is a working 
FastAPI backend that accepts a .h5ad upload, runs the scanpy 
pipeline, and returns results. No frontend yet.

## Tech stack
- Backend: Python, FastAPI
- Pipeline: scanpy, anndata, celltypist
- Frontend (later phases): TBD, likely React
- Storage: local filesystem for now, S3 later

## Pipeline steps (in order)
1. QC — filter cells by n_genes_by_counts, total_counts, pct_counts_mt
2. Normalize — sc.pp.normalize_total(), sc.pp.log1p()
3. HVGs — sc.pp.highly_variable_genes(n_top_genes=2000)
4. PCA — sc.pp.pca()
5. Neighbors — sc.pp.neighbors()
6. UMAP — sc.tl.umap()
7. Leiden clustering — sc.tl.leiden()
8. Marker genes — sc.tl.rank_genes_groups()

## Key constraints
- Input files are small .h5ad files only (< 500MB for now)
- Pipeline runs synchronously for Phase 1, async job queue later
- All pipeline code must be modular — each step is a separate 
  function so steps can be re-run independently

## What I already know
I have completed the full scanpy pipeline manually on PBMC 3k.
I understand AnnData structure, all preprocessing steps, and 
CellTypist annotation. Do not over-explain these concepts.

## Coding preferences
- Type hints on all functions
- Docstrings on all public functions
- Raise descriptive errors at each pipeline step so failures 
  are traceable
- No notebooks — all code in .py files