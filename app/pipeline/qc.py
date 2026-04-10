import logging
import anndata as ad
import scanpy as sc

from app.utils.errors import PipelineStepError

logger = logging.getLogger(__name__)


def run_qc(
    adata: ad.AnnData,
    min_genes: int = 200,
    max_genes: int = 5000,
    max_pct_mt: float = 20.0,
    min_cells: int = 3,
) -> ad.AnnData:
    """Filter cells by gene count and mitochondrial content, and genes by cell count.

    Annotates mitochondrial genes via the 'mt' flag, computes per-cell QC
    metrics, filters cells on n_genes_by_counts and pct_counts_mt, then
    removes genes expressed in fewer than min_cells cells. Gene filtering
    is required to prevent NaN bin edges during HVG selection downstream.

    Args:
        adata: Input AnnData object.
        min_genes: Minimum number of genes expressed per cell.
        max_genes: Maximum number of genes expressed per cell.
        max_pct_mt: Maximum percentage of mitochondrial counts per cell.
        min_cells: Minimum number of cells a gene must be expressed in.

    Returns:
        Filtered AnnData object.

    Raises:
        PipelineStepError: If QC filtering removes all cells.
    """
    logger.info("QC input: %d cells x %d genes", adata.n_obs, adata.n_vars)

    try:
        adata.var["mt"] = adata.var_names.str.startswith("MT-")
        sc.pp.calculate_qc_metrics(
            adata, qc_vars=["mt"], percent_top=None, log1p=False, inplace=True
        )
        adata = adata[
            (adata.obs["n_genes_by_counts"] >= min_genes)
            & (adata.obs["n_genes_by_counts"] <= max_genes)
            & (adata.obs["pct_counts_mt"] <= max_pct_mt)
        ].copy()
        logger.info("QC after cell filter: %d cells remaining", adata.n_obs)
        sc.pp.filter_genes(adata, min_cells=min_cells)
        logger.info("QC after gene filter (min_cells=%d): %d genes remaining", min_cells, adata.n_vars)
    except PipelineStepError:
        raise
    except Exception as e:
        raise PipelineStepError("qc", f"QC metrics failed: {e}") from e

    if adata.n_obs == 0:
        raise PipelineStepError(
            "qc",
            f"All cells were filtered out (min_genes={min_genes}, "
            f"max_genes={max_genes}, max_pct_mt={max_pct_mt}). "
            "Loosen QC thresholds.",
        )

    return adata
