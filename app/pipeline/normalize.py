import logging
import numpy as np
import anndata as ad
import scanpy as sc

from app.utils.errors import PipelineStepError

logger = logging.getLogger(__name__)


def run_normalize(adata: ad.AnnData, n_top_genes: int = 2000) -> ad.AnnData:
    """Normalize counts, log-transform, and select highly variable genes.

    Runs sc.pp.normalize_total(), sc.pp.log1p(), then filters out zero-mean
    genes before HVG selection. The zero-mean filter is required because
    sc.pp.highly_variable_genes (seurat flavor) bins genes by mean expression
    using pd.cut() — genes with zero mean after normalization produce NaN bin
    edges and cause a hard failure. The full log-normalized matrix is stored
    in adata.raw before subsetting so all genes remain accessible downstream
    (e.g. CellTypist).

    Args:
        adata: QC-filtered AnnData object with raw integer counts in X.
        n_top_genes: Number of highly variable genes to select.

    Returns:
        Normalized AnnData object subsetted to HVGs, with full log-normalized
        matrix preserved in adata.raw.

    Raises:
        PipelineStepError: If normalization or HVG selection fails, or if no
            HVGs are found.
    """
    logger.info("Normalize input: %d cells x %d genes", adata.n_obs, adata.n_vars)

    try:
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)
    except Exception as e:
        raise PipelineStepError("normalize", f"Normalization failed: {e}") from e

    # Store the full log-normalized matrix before any subsetting so that
    # CellTypist can access all genes via adata.raw.to_adata().
    adata.raw = adata

    # Remove genes with zero mean — these cause NaN bin edges in HVG selection.
    gene_means = np.asarray(adata.X.mean(axis=0)).flatten()
    n_nonzero = int((gene_means > 0).sum())
    logger.info("Normalize: %d / %d genes have mean > 0 after log1p", n_nonzero, adata.n_vars)

    if n_nonzero == 0:
        raise PipelineStepError(
            "normalize",
            "All genes have zero mean after normalization. "
            "The input data may already be normalized or log-transformed.",
        )

    adata = adata[:, gene_means > 0].copy()

    try:
        sc.pp.highly_variable_genes(adata, n_top_genes=n_top_genes)
    except Exception as e:
        raise PipelineStepError("normalize", f"HVG selection failed: {e}") from e

    n_hvg = int(adata.var["highly_variable"].sum())
    if n_hvg == 0:
        raise PipelineStepError(
            "normalize",
            f"No highly variable genes found with n_top_genes={n_top_genes}.",
        )

    adata = adata[:, adata.var.highly_variable].copy()
    return adata
