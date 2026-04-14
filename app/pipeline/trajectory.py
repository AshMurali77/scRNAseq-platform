"""PAGA-based trajectory inference.

Computes partition-based graph abstraction (PAGA) connectivity between Leiden
clusters. Returns nodes (clusters with cell-type labels and sizes) and edges
(cluster-cluster connections with weights) for frontend visualization.
"""

import logging

import anndata as ad
import numpy as np
import scanpy as sc

from app.models.schemas import TrajectoryEdge, TrajectoryNode
from app.utils.errors import PipelineStepError

logger = logging.getLogger(__name__)

_MIN_EDGE_WEIGHT = 0.05  # edges below this threshold are omitted


def run_trajectory(
    adata: ad.AnnData,
) -> tuple[list[TrajectoryNode], list[TrajectoryEdge]]:
    """Run PAGA and extract cluster connectivity.

    Requires the kNN neighbor graph (from sc.pp.neighbors) stored in
    adata.obsp, which is preserved when the AnnData is saved as h5ad.

    Args:
        adata: Processed AnnData with 'leiden' in obs, neighbor graph in
               obsp, and 'celltypist_cell_type' in obs.

    Returns:
        Tuple of (nodes, edges):
          - nodes: One TrajectoryNode per Leiden cluster, with the majority
            cell-type label and cluster size.
          - edges: Cluster-cluster connections with weight > _MIN_EDGE_WEIGHT,
            sorted descending by weight.

    Raises:
        PipelineStepError: If fewer than 2 clusters exist or PAGA fails.
    """
    n_clusters = int(adata.obs["leiden"].nunique())
    if n_clusters < 2:
        raise PipelineStepError(
            "trajectory",
            f"Trajectory inference requires at least 2 clusters; got {n_clusters}.",
        )

    logger.info("Running PAGA on %d clusters.", n_clusters)

    try:
        sc.tl.paga(adata, groups="leiden")
    except Exception as exc:
        raise PipelineStepError("trajectory", f"PAGA failed: {exc}") from exc

    # Extract connectivity matrix (n_clusters × n_clusters, sparse)
    conn = adata.uns["paga"]["connectivities"]
    conn_array = np.asarray(conn.todense())

    # Build ordered cluster list to align with the connectivity matrix
    # PAGA stores clusters in the order from adata.obs['leiden'].cat.categories
    cluster_categories = list(adata.obs["leiden"].cat.categories)

    # Build nodes
    nodes: list[TrajectoryNode] = []
    for cluster_id in cluster_categories:
        mask = adata.obs["leiden"] == cluster_id
        n_cells = int(mask.sum())
        if "celltypist_cell_type" in adata.obs.columns:
            label = str(adata.obs.loc[mask, "celltypist_cell_type"].mode()[0])
        else:
            label = f"Cluster {cluster_id}"
        nodes.append(
            TrajectoryNode(cluster_id=str(cluster_id), label=label, size=n_cells)
        )

    # Build edges from upper triangle of connectivity matrix
    edges: list[TrajectoryEdge] = []
    n = len(cluster_categories)
    for i in range(n):
        for j in range(i + 1, n):
            weight = float(conn_array[i, j])
            if weight >= _MIN_EDGE_WEIGHT:
                edges.append(
                    TrajectoryEdge(
                        source=str(cluster_categories[i]),
                        target=str(cluster_categories[j]),
                        weight=round(weight, 4),
                    )
                )

    edges.sort(key=lambda e: e.weight, reverse=True)

    logger.info("PAGA complete: %d nodes, %d edges (weight >= %.2f).",
                len(nodes), len(edges), _MIN_EDGE_WEIGHT)
    return nodes, edges
