import anndata as ad


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
    pass
