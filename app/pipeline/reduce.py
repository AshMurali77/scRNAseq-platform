import anndata as ad


def run_reduce(
    adata: ad.AnnData,
    n_pcs: int = 50,
    n_neighbors: int = 15,
) -> ad.AnnData:
    """Run PCA, compute neighbor graph, and generate UMAP embedding.

    Args:
        adata: Normalized AnnData object with HVGs.
        n_pcs: Number of principal components to compute.
        n_neighbors: Number of neighbors for the kNN graph.

    Returns:
        AnnData object with PCA, neighbors, and UMAP results stored.

    Raises:
        PipelineStepError: If dimensionality reduction fails.
    """
    pass
