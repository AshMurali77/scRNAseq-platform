import anndata as ad
import celltypist
import scanpy as sc

from app.utils.errors import PipelineStepError


def run_marker_genes(adata: ad.AnnData, n_genes: int = 25) -> ad.AnnData:
    """Compute per-cluster marker genes using rank_genes_groups.

    Uses the Wilcoxon rank-sum test, comparing each cluster against all
    others. Results are stored in adata.uns['rank_genes_groups'].

    Args:
        adata: Clustered AnnData object with 'leiden' in obs.
        n_genes: Number of top marker genes to compute per cluster.

    Returns:
        AnnData object with rank_genes_groups results stored in uns.

    Raises:
        PipelineStepError: If cluster labels are missing or the test fails.
    """
    if "leiden" not in adata.obs.columns:
        raise PipelineStepError(
            "annotate",
            "'leiden' column not found in adata.obs. Run run_cluster() first.",
        )

    try:
        sc.tl.rank_genes_groups(
            adata, groupby="leiden", method="wilcoxon", n_genes=n_genes
        )
    except Exception as e:
        raise PipelineStepError("annotate", f"rank_genes_groups failed: {e}") from e

    return adata


def run_celltypist(adata: ad.AnnData, model: str = "Immune_All_Low.pkl") -> ad.AnnData:
    """Annotate cell types using CellTypist.

    Expects log1p-normalized counts (target sum 10,000) as produced by
    run_normalize(). Majority-vote prediction is used to assign a single
    cell type label per Leiden cluster.

    Args:
        adata: AnnData object with normalized counts and 'leiden' in obs.
        model: CellTypist model name to use for annotation.

    Returns:
        AnnData object with 'celltypist_cell_type' added to obs.

    Raises:
        PipelineStepError: If the model cannot be loaded or annotation fails.
    """
    if "leiden" not in adata.obs.columns:
        raise PipelineStepError(
            "annotate",
            "'leiden' column not found in adata.obs. Run run_cluster() first.",
        )

    try:
        ct_model = celltypist.models.Model.load(model=model)
    except Exception as e:
        raise PipelineStepError(
            "annotate", f"Failed to load CellTypist model '{model}': {e}"
        ) from e

    # Use the full log-normalized matrix stored in adata.raw so CellTypist
    # sees all genes, not just the HVG subset used for clustering.
    adata_full = adata.raw.to_adata()
    adata_full.obs["leiden"] = adata.obs["leiden"]

    try:
        predictions = celltypist.annotate(
            adata_full, model=ct_model, majority_voting=True, over_clustering="leiden"
        )
        adata.obs["celltypist_cell_type"] = predictions.predicted_labels[
            "majority_voting"
        ]
    except Exception as e:
        raise PipelineStepError("annotate", f"CellTypist annotation failed: {e}") from e

    return adata
