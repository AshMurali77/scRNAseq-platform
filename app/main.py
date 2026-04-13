import logging
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

load_dotenv()

from app.models.schemas import (
    CellMetadata,
    ClusterSummary,
    MarkerGene,
    ModelSelection,
    ModelSelectionRequest,
    PipelineParams,
    PipelineResult,
)
from app.pipeline.annotate import run_celltypist, run_marker_genes, select_model
from app.pipeline.plot import generate_plots
from app.pipeline.cluster import run_cluster
from app.pipeline.normalize import run_normalize
from app.pipeline.qc import run_qc
from app.pipeline.reduce import run_reduce
from app.utils.errors import PipelineStepError
from app.utils.io import load_h5ad, stage_upload

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="scRNA-seq Annotation Platform")


@app.post("/select-model", response_model=ModelSelection)
async def select_model_endpoint(body: ModelSelectionRequest) -> ModelSelection:
    """Select the best CellTypist model for a tissue and organism using an LLM.

    If the LLM is confident (confidence >= threshold), returns a ModelSelection
    with clarifying_question set to null — the caller can proceed directly to
    POST /analyze with the returned model_name.

    If the LLM is not confident, clarifying_question is populated with a
    specific question to surface to the user. Re-submit with the user's answer
    as the clarification field to obtain a confident selection.

    Args:
        body: ModelSelectionRequest with tissue, organism, and optional clarification.

    Returns:
        ModelSelection with model_name, display_name, description, reasoning,
        confidence, and optionally clarifying_question.

    Raises:
        400: If the LLM API call fails.
    """
    try:
        return select_model(body.tissue, body.organism, body.clarification, body.use_llm, body.clarification_round)
    except PipelineStepError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/analyze", response_model=PipelineResult)
async def analyze(
    file: UploadFile = File(...),
    params: str = Form(default="{}"),
) -> PipelineResult:
    """Accept a .h5ad upload, run the full preprocessing pipeline, and return results.

    Expects model_name to be pre-selected via POST /select-model. The pipeline
    runs the model directly without an additional LLM call.

    Args:
        file: The .h5ad file to process.
        params: JSON string of PipelineParams fields. tissue, organism, and
                model_name are required; all other fields are optional.

    Returns:
        PipelineResult containing per-cell metadata, cluster assignments,
        UMAP coordinates, and marker genes.

    Raises:
        422: If params JSON is malformed or required fields are missing.
        400: If any pipeline step fails.
    """
    try:
        pipeline_params = PipelineParams.model_validate_json(params)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid params: {e}")

    tmp_path = stage_upload(file)

    try:
        adata = load_h5ad(tmp_path)
        n_cells_input = adata.n_obs

        adata = run_qc(
            adata,
            min_genes=pipeline_params.qc.min_genes,
            max_genes=pipeline_params.qc.max_genes,
            max_pct_mt=pipeline_params.qc.max_pct_mt,
            min_cells=pipeline_params.qc.min_cells,
        )
        n_cells_after_qc = adata.n_obs

        adata = run_normalize(adata, n_top_genes=pipeline_params.n_top_genes)
        n_hvgs = int(adata.n_vars)

        adata = run_reduce(
            adata,
            n_pcs=pipeline_params.n_pcs,
            n_neighbors=pipeline_params.n_neighbors,
        )
        adata = run_cluster(adata, resolution=pipeline_params.leiden_resolution)
        adata = run_marker_genes(adata, n_genes=pipeline_params.n_marker_genes)
        adata = run_celltypist(adata, model=pipeline_params.model_name)

    except PipelineStepError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        tmp_path.unlink(missing_ok=True)

    plots = generate_plots(adata)
    return _build_result(
        adata,
        n_cells_input,
        n_cells_after_qc,
        n_hvgs,
        pipeline_params.model_name,
        plots,
    )


def _build_result(
    adata,
    n_cells_input: int,
    n_cells_after_qc: int,
    n_hvgs: int,
    model_name: str,
    plots: dict[str, str],
) -> PipelineResult:
    """Assemble a PipelineResult from a fully annotated AnnData object.

    Args:
        adata: Fully processed AnnData object.
        n_cells_input: Cell count before QC filtering.
        n_cells_after_qc: Cell count after QC filtering.
        n_hvgs: Number of highly variable genes selected.
        model_name: CellTypist model filename that was used.

    Returns:
        PipelineResult ready for serialization.
    """
    umap_coords = adata.obsm["X_umap"]

    cells = [
        CellMetadata(
            cell_id=cell_id,
            leiden_cluster=str(adata.obs.loc[cell_id, "leiden"]),
            celltypist_cell_type=str(adata.obs.loc[cell_id, "celltypist_cell_type"]),
            umap_x=float(umap_coords[i, 0]),
            umap_y=float(umap_coords[i, 1]),
        )
        for i, cell_id in enumerate(adata.obs_names)
    ]

    cluster_summaries = _extract_cluster_summaries(adata)
    marker_genes = _extract_marker_genes(adata)

    return PipelineResult(
        n_cells_input=n_cells_input,
        n_cells_after_qc=n_cells_after_qc,
        n_hvgs=n_hvgs,
        n_clusters=int(adata.obs["leiden"].nunique()),
        model_display_name=model_name,
        model_description="",
        cluster_summaries=cluster_summaries,
        cells=cells,
        marker_genes=marker_genes,
        plots=plots,
    )


def _extract_cluster_summaries(adata) -> list[ClusterSummary]:
    """Build a per-cluster label summary from majority-voted CellTypist labels.

    With majority_voting=True all cells in the same Leiden cluster share the
    same label, so we take the mode per cluster as a safe fallback.

    Args:
        adata: AnnData object with 'leiden' and 'celltypist_cell_type' in obs.

    Returns:
        List of ClusterSummary sorted by cluster id.
    """
    summary = (
        adata.obs.groupby("leiden", observed=True)["celltypist_cell_type"]
        .agg(lambda s: s.mode()[0])
        .reset_index()
    )
    return [
        ClusterSummary(
            cluster_id=str(row["leiden"]),
            celltypist_label=str(row["celltypist_cell_type"]),
        )
        for _, row in summary.iterrows()
    ]


def _extract_marker_genes(adata) -> list[MarkerGene]:
    """Extract marker gene results from adata.uns['rank_genes_groups'].

    Args:
        adata: AnnData object with rank_genes_groups results in uns.

    Returns:
        Flat list of MarkerGene records across all clusters.
    """
    rgg = adata.uns["rank_genes_groups"]
    clusters = list(rgg["names"].dtype.names)

    records = []
    for cluster in clusters:
        genes = rgg["names"][cluster]
        scores = rgg["scores"][cluster]
        logfcs = rgg["logfoldchanges"][cluster]
        padjs = rgg["pvals_adj"][cluster]

        for gene, score, lfc, padj in zip(genes, scores, logfcs, padjs):
            records.append(
                MarkerGene(
                    gene=str(gene),
                    cluster=str(cluster),
                    score=float(score),
                    log_fold_change=float(lfc),
                    pval_adj=float(padj),
                )
            )

    return records
