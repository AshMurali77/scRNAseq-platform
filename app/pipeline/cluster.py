import anndata as ad
import scanpy as sc

from app.utils.errors import PipelineStepError


def run_cluster(adata: ad.AnnData, resolution: float = 0.5) -> ad.AnnData:
    """Assign cluster labels using the Leiden algorithm.

    Args:
        adata: AnnData object with a computed neighbor graph.
        resolution: Leiden resolution parameter (higher = more clusters).

    Returns:
        AnnData object with 'leiden' column added to obs.

    Raises:
        PipelineStepError: If neighbor graph is missing or clustering fails.
    """
    if "neighbors" not in adata.uns:
        raise PipelineStepError(
            "cluster",
            "Neighbor graph not found in adata.uns. Run run_reduce() first.",
        )

    try:
        sc.tl.leiden(adata, resolution=resolution)
    except Exception as e:
        raise PipelineStepError("cluster", f"Leiden clustering failed: {e}") from e

    return adata
