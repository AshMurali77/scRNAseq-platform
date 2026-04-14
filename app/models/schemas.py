from typing import Literal

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
    skip_qc: bool = Field(False, description="Skip cell-level QC filtering for pre-filtered datasets. Gene filtering is still applied.")
    use_llm: bool = Field(True, description="If True, run LLM-based expert validation of cluster labels. Set to False to skip LLM calls and reduce token cost.")


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


class ClusterValidation(BaseModel):
    """LLM expert review of a single cluster's CellTypist annotation.

    Attributes:
        cluster_id: Leiden cluster identifier.
        celltypist_label: Majority-voted CellTypist label for this cluster.
        status: 'confirmed', 'uncertain', or 'conflicting'.
        explanation: 1–2 sentence biological rationale from the LLM.
        top_marker_genes: Gene names used as evidence (in score order).
    """

    cluster_id: str
    celltypist_label: str
    status: Literal["confirmed", "uncertain", "conflicting"]
    explanation: str
    top_marker_genes: list[str]


class DatasetMetadata(BaseModel):
    """Metadata extracted from the uploaded h5ad file.

    Attributes:
        organism_in_file: Raw organism string found in the file, or None.
        tissue_in_file: Raw tissue string found in the file, or None.
        organism_mismatch: True when the file organism does not match the
            user-provided organism after normalisation.
    """

    organism_in_file: str | None = None
    tissue_in_file: str | None = None
    organism_mismatch: bool = False


class ConversationMessage(BaseModel):
    """A single turn in a chat conversation.

    Attributes:
        role: Either 'user' or 'assistant'.
        content: Plain text content of the message.
    """

    role: Literal["user", "assistant"]
    content: str


class QueryContext(BaseModel):
    """Compressed pipeline result passed with every chat query.

    Contains everything the LLM needs to answer questions about the analysis,
    but excludes per-cell coordinates and plot images to keep the payload small.

    Attributes:
        n_cells_input: Cells before QC.
        n_cells_after_qc: Cells after QC.
        n_hvgs: Highly variable genes selected.
        n_clusters: Leiden clusters.
        model_display_name: CellTypist model used.
        tissue: Tissue type provided by the user.
        organism: Organism provided by the user.
        cluster_summaries: Cluster-level CellTypist labels.
        cluster_validations: LLM expert review per cluster (if run).
        marker_genes: Top marker genes per cluster.
        dataset_metadata: Organism/tissue found in the h5ad file.
    """

    n_cells_input: int
    n_cells_after_qc: int
    n_hvgs: int
    n_clusters: int
    model_display_name: str
    tissue: str
    organism: str
    cluster_summaries: list[ClusterSummary]
    cluster_validations: list[ClusterValidation]
    marker_genes: list[MarkerGene]
    dataset_metadata: DatasetMetadata | None = None


class QueryRequest(BaseModel):
    """Request body for POST /query.

    Attributes:
        question: The user's natural-language question.
        conversation_history: Prior turns (excludes the current question).
        context: Compressed pipeline result used as LLM context.
    """

    question: str
    conversation_history: list[ConversationMessage] = Field(default_factory=list)
    context: QueryContext


class QueryResponse(BaseModel):
    """Response from POST /query.

    Attributes:
        answer: The LLM's plain-text answer.
    """

    answer: str


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
    cluster_validations: list[ClusterValidation] = Field(
        default_factory=list,
        description="LLM expert review of each cluster's CellTypist label.",
    )
    dataset_metadata: DatasetMetadata | None = Field(
        None,
        description="Organism/tissue metadata extracted from the h5ad file.",
    )
