from pydantic import BaseModel, Field


class QCParams(BaseModel):
    min_genes: int = Field(200, description="Minimum genes expressed per cell.")
    max_genes: int = Field(5000, description="Maximum genes expressed per cell.")
    max_pct_mt: float = Field(20.0, description="Maximum mitochondrial count percentage.")
    min_cells: int = Field(3, description="Minimum cells a gene must be expressed in.")


class PipelineParams(BaseModel):
    tissue: str = Field(..., description="Tissue type (e.g. 'blood', 'lung', 'brain').")
    organism: str = Field(..., description="Source organism (e.g. 'human', 'mouse').")
    model_name: str = Field(..., description="CellTypist model filename selected by /select-model.")
    qc: QCParams = Field(default_factory=QCParams)
    n_top_genes: int = Field(2000, description="Number of highly variable genes.")
    n_pcs: int = Field(50, description="Number of principal components.")
    n_neighbors: int = Field(15, description="Neighbors for kNN graph.")
    leiden_resolution: float = Field(0.5, description="Leiden clustering resolution.")
    n_marker_genes: int = Field(25, description="Top marker genes per cluster.")


class ModelSelectionRequest(BaseModel):
    tissue: str = Field(..., description="Tissue type (e.g. 'blood', 'lung', 'brain').")
    organism: str = Field(..., description="Source organism (e.g. 'human', 'mouse').")
    clarification: str | None = Field(None, description="Optional user response to a clarifying question.")
    use_llm: bool = Field(True, description="Use LLM selection; False uses deterministic lookup table.")
    clarification_round: int = Field(0, description="Number of clarification rounds already completed. When this reaches the backend maximum, no further questions will be asked.")


class ModelSelection(BaseModel):
    """Result of LLM-powered model selection.

    Returned by POST /select-model. If clarifying_question is set, the caller
    should surface it to the user and re-submit with the answer as clarification.

    Attributes:
        model_name: CellTypist model filename (e.g. 'Immune_All_Low.pkl').
        display_name: Short human-readable name shown in the UI.
        description: One-sentence description of the model's scope.
        reasoning: LLM's explanation for choosing this model.
        confidence: 0.0–1.0 confidence score from the LLM.
        clarifying_question: Set when confidence is low; question to ask the user.
    """

    model_name: str
    display_name: str
    description: str
    reasoning: str
    confidence: float
    clarifying_question: str | None = None


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


class ClusterSummary(BaseModel):
    cluster_id: str
    celltypist_label: str


class PipelineResult(BaseModel):
    n_cells_input: int
    n_cells_after_qc: int
    n_hvgs: int
    n_clusters: int
    model_display_name: str
    model_description: str
    cluster_summaries: list[ClusterSummary]
    cells: list[CellMetadata]
    marker_genes: list[MarkerGene]
    plots: dict[str, str] = Field(
        default_factory=dict,
        description="Base64-encoded PNG plots keyed by name (e.g. 'umap_clusters').",
    )
