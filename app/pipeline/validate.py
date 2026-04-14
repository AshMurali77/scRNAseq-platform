import logging
from typing import Literal

import anndata as ad
import anthropic
from pydantic import BaseModel

from app.models.schemas import ClusterValidation
from app.utils.errors import PipelineStepError

logger = logging.getLogger(__name__)

_N_VALIDATION_GENES = 10


# ---------------------------------------------------------------------------
# Internal structured-output schema for the LLM call
# ---------------------------------------------------------------------------

class _ClusterValidationItem(BaseModel):
    cluster_id: str
    status: Literal["confirmed", "uncertain", "conflicting"]
    explanation: str


class _ValidationResponse(BaseModel):
    validations: list[_ClusterValidationItem]


# ---------------------------------------------------------------------------
# Marker-gene extraction helpers
# ---------------------------------------------------------------------------

def _extract_top_markers(
    adata: ad.AnnData,
    n_genes: int,
) -> dict[str, list[tuple[str, float, float]]]:
    """Return top N marker genes per cluster from rank_genes_groups.

    Args:
        adata: AnnData with rank_genes_groups in uns.
        n_genes: Number of top genes to include per cluster.

    Returns:
        Mapping of cluster_id → [(gene, score, logFC), ...].
    """
    rgg = adata.uns["rank_genes_groups"]
    clusters = list(rgg["names"].dtype.names)
    result: dict[str, list[tuple[str, float, float]]] = {}
    for cluster in clusters:
        genes = rgg["names"][cluster][:n_genes]
        scores = rgg["scores"][cluster][:n_genes]
        logfcs = rgg["logfoldchanges"][cluster][:n_genes]
        result[cluster] = [
            (str(g), float(s), float(lfc))
            for g, s, lfc in zip(genes, scores, logfcs)
        ]
    return result


def _build_cluster_block(
    cluster_label_map: dict[str, str],
    markers: dict[str, list[tuple[str, float, float]]],
) -> str:
    """Format cluster info as a compact text block for the LLM prompt.

    Args:
        cluster_label_map: cluster_id → celltypist majority-vote label.
        markers: cluster_id → [(gene, score, logFC), ...].

    Returns:
        Multi-line string describing each cluster.
    """
    lines: list[str] = []
    for cluster_id, label in sorted(cluster_label_map.items(), key=lambda x: int(x[0]) if x[0].isdigit() else x[0]):
        gene_parts = [
            f"{g} (score={s:.1f}, logFC={lfc:.2f})"
            for g, s, lfc in markers.get(cluster_id, [])
        ]
        lines.append(
            f"Cluster {cluster_id} — CellTypist label: \"{label}\"\n"
            f"  Top markers: {', '.join(gene_parts) if gene_parts else 'none'}"
        )
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def validate_cluster_labels(
    adata: ad.AnnData,
    tissue: str,
    organism: str,
) -> list[ClusterValidation]:
    """Validate CellTypist cluster annotations using an LLM expert review.

    Extracts the top marker genes for every Leiden cluster, then asks the LLM
    whether each CellTypist label is biologically consistent with those markers.
    All clusters are validated in a single API call to minimise latency.

    Args:
        adata: AnnData with rank_genes_groups in uns and celltypist_cell_type
               in obs (both set by earlier pipeline steps).
        tissue: Tissue type provided by the user (used as context).
        organism: Organism provided by the user (used as context).

    Returns:
        List of ClusterValidation objects, one per cluster. Empty if the LLM
        call fails — callers should treat this as non-fatal.

    Raises:
        PipelineStepError: If the LLM API call fails (caught by caller).
    """
    if "rank_genes_groups" not in adata.uns:
        raise PipelineStepError(
            "validate",
            "'rank_genes_groups' not found in adata.uns. "
            "Run run_marker_genes() before validate_cluster_labels().",
        )
    if "celltypist_cell_type" not in adata.obs.columns:
        raise PipelineStepError(
            "validate",
            "'celltypist_cell_type' not found in adata.obs. "
            "Run run_celltypist() before validate_cluster_labels().",
        )

    # Build cluster → label map from majority vote
    cluster_label_map: dict[str, str] = (
        adata.obs.groupby("leiden", observed=True)["celltypist_cell_type"]
        .agg(lambda s: s.mode()[0])
        .to_dict()
    )
    cluster_label_map = {str(k): str(v) for k, v in cluster_label_map.items()}

    markers = _extract_top_markers(adata, _N_VALIDATION_GENES)
    cluster_block = _build_cluster_block(cluster_label_map, markers)

    system_prompt = (
        f"You are an expert computational biologist specialising in single-cell "
        f"RNA sequencing and cell type annotation.\n\n"
        f"Dataset context: {organism} — {tissue}\n\n"
        f"Your task is to assess whether each CellTypist cell type annotation is "
        f"biologically consistent with the top marker genes identified by Wilcoxon "
        f"rank-sum testing.\n\n"
        f"For each cluster return:\n"
        f"  - cluster_id: the cluster number as a string (copy exactly as given)\n"
        f"  - status: one of\n"
        f"      'confirmed'   — markers strongly support the label\n"
        f"      'uncertain'   — markers are ambiguous or only partially consistent\n"
        f"      'conflicting' — markers clearly suggest a different cell type\n"
        f"  - explanation: 1–2 sentences citing the specific genes that support or "
        f"contradict the label. Be concise and precise.\n\n"
        f"Base your judgement on established marker gene knowledge from the literature. "
        f"Return one validation object per cluster; do not skip any."
    )

    user_content = (
        f"Validate the following cluster annotations:\n\n{cluster_block}"
    )

    client = anthropic.Anthropic()

    try:
        response = client.messages.parse(
            model="claude-opus-4-6",
            max_tokens=3000,
            thinking={"type": "adaptive"},
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
            output_format=_ValidationResponse,
        )
        items = response.parsed_output.validations
    except anthropic.APIError as exc:
        raise PipelineStepError("validate", f"LLM validation failed: {exc}") from exc

    logger.info(
        "LLM validated %d clusters (%d returned).",
        len(cluster_label_map),
        len(items),
    )

    # Build final objects, merging LLM output with known cluster metadata
    validation_map: dict[str, _ClusterValidationItem] = {
        item.cluster_id: item for item in items
    }

    results: list[ClusterValidation] = []
    for cluster_id, label in sorted(
        cluster_label_map.items(), key=lambda x: int(x[0]) if x[0].isdigit() else x[0]
    ):
        item = validation_map.get(cluster_id)
        results.append(
            ClusterValidation(
                cluster_id=cluster_id,
                celltypist_label=label,
                status=item.status if item else "uncertain",
                explanation=(
                    item.explanation
                    if item
                    else "Validation result not returned by LLM."
                ),
                top_marker_genes=[g for g, _, _ in markers.get(cluster_id, [])],
            )
        )

    return results
