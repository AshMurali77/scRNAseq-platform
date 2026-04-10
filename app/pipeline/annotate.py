import anndata as ad


def run_marker_genes(adata: ad.AnnData, n_genes: int = 25) -> ad.AnnData:
    """Compute per-cluster marker genes using rank_genes_groups.

    Args:
        adata: Clustered AnnData object with 'leiden' in obs.
        n_genes: Number of top marker genes to compute per cluster.

    Returns:
        AnnData object with rank_genes_groups results stored in uns.

    Raises:
        PipelineStepError: If cluster labels are missing.
    """
    pass


def run_celltypist(adata: ad.AnnData, model: str = "Immune_All_Low.pkl") -> ad.AnnData:
    """Annotate cell types using CellTypist.

    Args:
        adata: AnnData object with normalized counts and cluster labels.
        model: CellTypist model name to use for annotation.

    Returns:
        AnnData object with 'celltypist_cell_type' added to obs.

    Raises:
        PipelineStepError: If CellTypist annotation fails.
    """
    pass
