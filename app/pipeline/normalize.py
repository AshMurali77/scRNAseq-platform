import anndata as ad


def run_normalize(adata: ad.AnnData, n_top_genes: int = 2000) -> ad.AnnData:
    """Normalize counts, log-transform, and select highly variable genes.

    Runs sc.pp.normalize_total(), sc.pp.log1p(), and
    sc.pp.highly_variable_genes() in sequence.

    Args:
        adata: QC-filtered AnnData object.
        n_top_genes: Number of highly variable genes to select.

    Returns:
        Normalized AnnData object with HVGs flagged.

    Raises:
        PipelineStepError: If normalization produces invalid values.
    """
    pass
