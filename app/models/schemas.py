from pydantic import BaseModel, Field


class QCParams(BaseModel):
    min_genes: int = Field(200, description="Minimum genes expressed per cell.")
    max_genes: int = Field(5000, description="Maximum genes expressed per cell.")
    max_pct_mt: float = Field(20.0, description="Maximum mitochondrial count percentage.")
    min_cells: int = Field(3, description="Minimum cells a gene must be expressed in.")


class PipelineParams(BaseModel):
    qc: QCParams = Field(default_factory=QCParams)
    n_top_genes: int = Field(2000, description="Number of highly variable genes.")
    n_pcs: int = Field(50, description="Number of principal components.")
    n_neighbors: int = Field(15, description="Neighbors for kNN graph.")
    leiden_resolution: float = Field(0.5, description="Leiden clustering resolution.")
    n_marker_genes: int = Field(25, description="Top marker genes per cluster.")
    celltypist_model: str = Field("Immune_All_Low.pkl", description="CellTypist model name.")


class CellMetadata(BaseModel):
    cell_id: str
    leiden_cluster: str
    celltypist_cell_type: str
    umap_x: float
    umap_y: float


class MarkerGene(BaseModel):
    gene: str
    cluster: str
    score: float
    log_fold_change: float
    pval_adj: float


class PipelineResult(BaseModel):
    n_cells_input: int
    n_cells_after_qc: int
    n_hvgs: int
    n_clusters: int
    cells: list[CellMetadata]
    marker_genes: list[MarkerGene]
