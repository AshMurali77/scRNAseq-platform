"""Scanpy plot generation for the annotation pipeline.

All figures are rendered to in-memory PNG buffers using the non-interactive
Agg backend and returned as base64-encoded strings so they can be embedded
directly in the JSON response.
"""

import base64
import io
import logging

import anndata as ad
import matplotlib
import matplotlib.pyplot as plt
import scanpy as sc

matplotlib.use("Agg")  # non-interactive backend; must precede any pyplot use

logger = logging.getLogger(__name__)


def _fig_to_b64(fig: plt.Figure) -> str:
    """Serialise a matplotlib Figure to a base64-encoded PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def _umap_plot(adata: ad.AnnData, color: str, title: str) -> str:
    """Generate a UMAP coloured by a single obs column.

    Args:
        adata: Fully processed AnnData with UMAP coordinates.
        color: obs column to colour by (e.g. 'leiden', 'celltypist_cell_type').
        title: Figure title.

    Returns:
        Base64-encoded PNG string.
    """
    fig, ax = plt.subplots(figsize=(6, 5))
    sc.pl.umap(adata, color=color, ax=ax, show=False, title=title)
    return _fig_to_b64(fig)


def generate_plots(adata: ad.AnnData) -> dict[str, str]:
    """Generate all diagnostic plots for a completed pipeline run.

    Produces two UMAP plots: one coloured by Leiden cluster ID and one
    coloured by CellTypist majority-vote cell type label.

    Args:
        adata: AnnData object after the full pipeline has run (must have
               X_umap in obsm and 'leiden' / 'celltypist_cell_type' in obs).

    Returns:
        Dict mapping plot name → base64 PNG string.
        Keys: 'umap_clusters', 'umap_celltypes'.
        Empty dict if plot generation fails (non-fatal).
    """
    plots: dict[str, str] = {}

    if "X_umap" not in adata.obsm:
        logger.warning("X_umap not found; skipping plot generation.")
        return plots

    try:
        plots["umap_clusters"] = _umap_plot(adata, "leiden", "Leiden clusters")
    except Exception as exc:
        logger.warning("Failed to generate cluster UMAP: %s", exc)

    if "celltypist_cell_type" in adata.obs.columns:
        try:
            plots["umap_celltypes"] = _umap_plot(
                adata, "celltypist_cell_type", "Cell type annotations"
            )
        except Exception as exc:
            logger.warning("Failed to generate cell-type UMAP: %s", exc)

    return plots
