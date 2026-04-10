import anndata as ad


def run_qc(
    adata: ad.AnnData,
    min_genes: int = 200,
    max_genes: int = 5000,
    max_pct_mt: float = 20.0,
) -> ad.AnnData:
    """Filter cells by gene count and mitochondrial content.

    Args:
        adata: Input AnnData object.
        min_genes: Minimum number of genes expressed per cell.
        max_genes: Maximum number of genes expressed per cell.
        max_pct_mt: Maximum percentage of mitochondrial counts per cell.

    Returns:
        Filtered AnnData object.

    Raises:
        PipelineStepError: If QC filtering removes all cells.
    """
    pass
