import anndata as ad
import scanpy as sc

from app.utils.errors import PipelineStepError


def run_reduce(
    adata: ad.AnnData,
    n_pcs: int = 50,
    n_neighbors: int = 15,
) -> ad.AnnData:
    """Run PCA, compute neighbor graph, and generate UMAP embedding.

    Args:
        adata: Normalized AnnData object subsetted to HVGs.
        n_pcs: Number of principal components to compute.
        n_neighbors: Number of neighbors for the kNN graph.

    Returns:
        AnnData object with obsm['X_pca'], obsp['connectivities'], and
        obsm['X_umap'] populated.

    Raises:
        PipelineStepError: If any dimensionality reduction step fails.
    """
    try:
        sc.pp.pca(adata, n_comps=n_pcs)
    except Exception as e:
        raise PipelineStepError("reduce", f"PCA failed: {e}") from e

    try:
        sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=n_pcs)
    except Exception as e:
        raise PipelineStepError("reduce", f"Neighbor graph failed: {e}") from e

    try:
        sc.tl.umap(adata)
    except Exception as e:
        raise PipelineStepError("reduce", f"UMAP failed: {e}") from e

    return adata
