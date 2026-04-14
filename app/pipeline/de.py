"""Pairwise differential expression between two Leiden clusters.

Uses the Wilcoxon rank-sum test via scanpy. All genes from adata.raw are
tested (not just HVGs), giving a comprehensive view of cluster differences.
"""

import logging

import anndata as ad
import scanpy as sc

from app.models.schemas import DEGene
from app.utils.errors import PipelineStepError

logger = logging.getLogger(__name__)

_N_TOP_GENES = 50  # genes returned per direction (upregulated in each group)


def run_differential_expression(
    adata: ad.AnnData,
    group1: str,
    group2: str,
) -> list[DEGene]:
    """Run pairwise Wilcoxon DE between two Leiden clusters.

    Tests group1 against group2. Positive logFC means the gene is higher in
    group1; negative means higher in group2. Returns the top genes by |score|
    across both directions, capped at _N_TOP_GENES per direction.

    Args:
        adata: Processed AnnData with 'leiden' in obs and adata.raw set.
        group1: Leiden cluster ID for the first group.
        group2: Leiden cluster ID for the second group.

    Returns:
        List of DEGene sorted by descending score (genes upregulated in
        group1 first, then genes upregulated in group2).

    Raises:
        PipelineStepError: If either cluster ID is not found or DE fails.
    """
    available = set(adata.obs["leiden"].unique().tolist())
    for g in (group1, group2):
        if g not in available:
            raise PipelineStepError(
                "de",
                f"Cluster '{g}' not found. Available clusters: {sorted(available)}",
            )
    if group1 == group2:
        raise PipelineStepError("de", "group1 and group2 must be different clusters.")

    mask = adata.obs["leiden"].isin([group1, group2])
    sub = adata[mask].copy()

    logger.info(
        "Running DE: cluster %s (%d cells) vs cluster %s (%d cells)",
        group1,
        int((sub.obs["leiden"] == group1).sum()),
        group2,
        int((sub.obs["leiden"] == group2).sum()),
    )

    try:
        sc.tl.rank_genes_groups(
            sub,
            groupby="leiden",
            groups=[group1],
            reference=group2,
            method="wilcoxon",
            use_raw=True,
        )
    except Exception as exc:
        raise PipelineStepError("de", f"Wilcoxon test failed: {exc}") from exc

    try:
        df = sc.get.rank_genes_groups_df(sub, group=group1)
    except Exception as exc:
        raise PipelineStepError("de", f"Failed to extract DE results: {exc}") from exc

    # Top N upregulated in group1 (positive logFC, highest scores first)
    top_up = df[df["logfoldchanges"] > 0].head(_N_TOP_GENES)
    # Top N upregulated in group2 (negative logFC from group1 perspective)
    top_down = df[df["logfoldchanges"] < 0].head(_N_TOP_GENES)

    results: list[DEGene] = []
    for row in top_up.itertuples(index=False):
        results.append(
            DEGene(
                gene=str(row.names),
                score=float(row.scores),
                log_fold_change=float(row.logfoldchanges),
                pval_adj=float(row.pvals_adj),
            )
        )
    for row in top_down.itertuples(index=False):
        results.append(
            DEGene(
                gene=str(row.names),
                score=float(row.scores),
                log_fold_change=float(row.logfoldchanges),
                pval_adj=float(row.pvals_adj),
            )
        )

    logger.info(
        "DE complete: %d genes upregulated in %s, %d in %s",
        len(top_up),
        group1,
        len(top_down),
        group2,
    )
    return results
