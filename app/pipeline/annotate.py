import logging

import anndata as ad
import anthropic
import celltypist
import scanpy as sc
from pydantic import BaseModel

from app.models.schemas import ModelSelection
from app.utils.errors import PipelineStepError

logger = logging.getLogger(__name__)

# Confidence below this threshold triggers a clarifying question instead of
# proceeding directly to annotation.
_CONFIDENCE_THRESHOLD = 0.7

# After this many clarification rounds, stop asking and proceed with the best
# available selection regardless of confidence.
_MAX_CLARIFICATION_ROUNDS = 2


# ---------------------------------------------------------------------------
# Rule-based model selection (deterministic fallback)
# ---------------------------------------------------------------------------

# Mapping of (tissue_lower, organism_lower) → ModelSelection.
# Tissue and organism inputs are normalised to lowercase before lookup.
_RULE_BASED_LOOKUP: dict[tuple[str, str], tuple[str, str, str]] = {
    # (tissue, organism): (model_name, display_name, description)
    # Human immune / blood
    ("blood",       "human"): ("Immune_All_Low.pkl",  "Immune All Low",  "Pan-human immune atlas, fine-grained labels."),
    ("pbmc",        "human"): ("Immune_All_Low.pkl",  "Immune All Low",  "Pan-human immune atlas, fine-grained labels."),
    ("bone marrow", "human"): ("Immune_All_High.pkl", "Immune All High", "Pan-human immune atlas, coarse labels."),
    ("spleen",      "human"): ("Immune_All_Low.pkl",  "Immune All Low",  "Pan-human immune atlas, fine-grained labels."),
    ("lymph node",  "human"): ("Immune_All_Low.pkl",  "Immune All Low",  "Pan-human immune atlas, fine-grained labels."),
    ("thymus",      "human"): ("Immune_All_High.pkl", "Immune All High", "Pan-human immune atlas, coarse labels."),
    # Human lung
    ("lung",        "human"): ("Human_Lung_Atlas.pkl", "Human Lung Atlas", "Human lung cell atlas covering healthy and disease states."),
    # Human brain
    ("brain",       "human"): ("Human_AdultAged_Hippocampus.pkl", "Human Hippocampus", "Adult and aged human hippocampus."),
    ("hippocampus", "human"): ("Human_AdultAged_Hippocampus.pkl", "Human Hippocampus", "Adult and aged human hippocampus."),
    # Human colon
    ("colon",       "human"): ("Human_Colorectal_Cancer.pkl", "Human Colorectal", "Human colorectal tissue including cancer."),
    ("colorectal",  "human"): ("Human_Colorectal_Cancer.pkl", "Human Colorectal", "Human colorectal tissue including cancer."),
    # Human heart
    ("heart",       "human"): ("Healthy_Adult_Heart.pkl", "Healthy Adult Heart", "Healthy adult human heart."),
    # Mouse lung
    ("lung",        "mouse"): ("Mouse_Lung.pkl", "Mouse Lung", "Mouse lung cell atlas."),
    # Mouse brain
    ("brain",       "mouse"): ("Mouse_Isocortex_Hippocampus.pkl", "Mouse Brain", "Mouse isocortex and hippocampus."),
    ("hippocampus", "mouse"): ("Mouse_Isocortex_Hippocampus.pkl", "Mouse Brain", "Mouse isocortex and hippocampus."),
    ("cortex",      "mouse"): ("Mouse_Isocortex_Hippocampus.pkl", "Mouse Brain", "Mouse isocortex and hippocampus."),
}


def _rule_based_select_model(tissue: str, organism: str) -> ModelSelection:
    """Select a CellTypist model via deterministic lookup table.

    Args:
        tissue: Tissue type (e.g. 'blood', 'lung').
        organism: Source organism (e.g. 'human', 'mouse').

    Returns:
        ModelSelection with confidence=1.0 and no clarifying_question.

    Raises:
        PipelineStepError: If no entry exists for the combination.
    """
    key = (tissue.strip().lower(), organism.strip().lower())
    entry = _RULE_BASED_LOOKUP.get(key)

    if entry is None:
        supported = sorted(f"{t} / {o}" for t, o in _RULE_BASED_LOOKUP)
        raise PipelineStepError(
            "annotate",
            f"No model found for tissue='{tissue}' organism='{organism}'. "
            f"Supported combinations: {', '.join(supported)}.",
        )

    model_name, display_name, description = entry
    logger.info(
        "Rule-based selection: '%s' for tissue='%s' organism='%s'.",
        model_name, tissue, organism,
    )
    return ModelSelection(
        model_name=model_name,
        display_name=display_name,
        description=description,
        reasoning=f"Deterministic lookup matched '{tissue}' / '{organism}' to {display_name}.",
        confidence=1.0,
        clarifying_question=None,
    )


# ---------------------------------------------------------------------------
# LLM model selection
# ---------------------------------------------------------------------------

class _ModelRecommendation(BaseModel):
    """Structured output schema for the LLM model-selection call."""

    model_name: str
    display_name: str
    description: str
    reasoning: str
    confidence: float
    clarifying_question: str | None = None


def _llm_select_model(
    tissue: str,
    organism: str,
    clarification: str | None = None,
    clarification_round: int = 0,
) -> ModelSelection:
    """Select a CellTypist model using an LLM with structured output.

    Args:
        tissue: Tissue type supplied by the user.
        organism: Source organism.
        clarification: Optional user response to a prior clarifying question.
        clarification_round: Number of clarification rounds already completed.
            When this reaches _MAX_CLARIFICATION_ROUNDS, the clarifying_question
            is suppressed and the best available selection is returned directly.

    Returns:
        ModelSelection with LLM reasoning and confidence score.

    Raises:
        PipelineStepError: If the LLM API call fails or returns an invalid model name.
    """
    valid_model_names: list[str] = []
    try:
        df = celltypist.models.models_description()
        if hasattr(df, "Model"):
            valid_model_names = df["Model"].tolist()
        models_catalog = str(df)
    except Exception as exc:
        logger.warning("Could not fetch CellTypist model catalog: %s", exc)
        models_catalog = "(catalog unavailable)"

    filenames_block = (
        "\n".join(f"  - {name}" for name in valid_model_names)
        if valid_model_names
        else "  (see catalog above)"
    )

    system_prompt = f"""You are an expert in single-cell RNA sequencing data analysis \
specialising in cell type annotation with CellTypist.

Select the most appropriate CellTypist model for the provided tissue and organism.

Full model catalog:
{models_catalog}

Valid model filenames — model_name MUST be copied verbatim from this list:
{filenames_block}

Confidence calibration (0.0–1.0) — be precise, not generous:
  0.95+  Exact or near-exact match: tissue name appears directly in the model name
         and the organism matches (e.g. tissue="PBMC", organism="human" → Immune_All_Low.pkl).
  0.80–0.94  Synonym match: tissue is a well-known synonym for the model's scope
             (e.g. "blood" → immune model), organism matches.
  0.55–0.79  Approximate match: tissue is a broader category than the model covers,
             or the model covers only a sub-region (e.g. tissue="brain" but the only
             available model targets hippocampus specifically).
  0.30–0.54  Weak match: tissue is related but the model is for a different species
             or a different disease context than the data likely represents.
  <0.30      No reasonable match found.

Rules:
- model_name must be an exact filename from the list above. Do not invent filenames.
- If confidence >= {_CONFIDENCE_THRESHOLD}: set clarifying_question to null and proceed.
- If confidence < {_CONFIDENCE_THRESHOLD}: set clarifying_question to a short, specific
  question whose answer would let you make a confident selection (e.g. ask which brain
  region, which disease context, or which species strain)."""

    user_content = f"Tissue: {tissue}\nOrganism: {organism}"
    if clarification:
        user_content += f"\nAdditional context: {clarification}"

    client = anthropic.Anthropic()

    try:
        response = client.messages.parse(
            model="claude-haiku-4-5",
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
            output_format=_ModelRecommendation,
        )
        rec = response.parsed_output
    except anthropic.APIError as exc:
        raise PipelineStepError("annotate", f"LLM model selection failed: {exc}") from exc

    logger.info(
        "LLM selected model '%s' (confidence=%.2f) for tissue='%s' organism='%s'.",
        rec.model_name, rec.confidence, tissue, organism,
    )

    if valid_model_names and rec.model_name not in valid_model_names:
        raise PipelineStepError(
            "annotate",
            f"LLM returned an unrecognised model name '{rec.model_name}'. "
            f"Valid filenames: {', '.join(valid_model_names)}.",
        )

    force_selection = clarification_round >= _MAX_CLARIFICATION_ROUNDS
    clarifying_question = (
        None
        if force_selection or rec.confidence >= _CONFIDENCE_THRESHOLD
        else rec.clarifying_question
    )
    if force_selection and rec.confidence < _CONFIDENCE_THRESHOLD:
        logger.info(
            "Max clarification rounds (%d) reached; proceeding with confidence=%.2f.",
            _MAX_CLARIFICATION_ROUNDS,
            rec.confidence,
        )

    return ModelSelection(
        model_name=rec.model_name,
        display_name=rec.display_name,
        description=rec.description,
        reasoning=rec.reasoning,
        confidence=rec.confidence,
        clarifying_question=clarifying_question,
    )


# ---------------------------------------------------------------------------
# Public selection entry point
# ---------------------------------------------------------------------------

def select_model(
    tissue: str,
    organism: str,
    clarification: str | None = None,
    use_llm: bool = True,
    clarification_round: int = 0,
) -> ModelSelection:
    """Select a CellTypist model for a given tissue and organism.

    Dispatches to either the LLM-powered or rule-based implementation depending
    on the use_llm flag.

    Args:
        tissue: Tissue type (e.g. 'blood', 'lung', 'brain').
        organism: Source organism (e.g. 'human', 'mouse').
        clarification: User response to a prior clarifying question (LLM only).
        use_llm: If True, use the LLM; if False, use the deterministic lookup table.
        clarification_round: Number of clarification rounds already completed.
            Passed through to the LLM implementation to enforce a question cap.

    Returns:
        ModelSelection with model_name, display_name, description, reasoning,
        confidence, and optionally clarifying_question.

    Raises:
        PipelineStepError: On lookup miss (rule-based) or API failure (LLM).
    """
    if use_llm:
        return _llm_select_model(tissue, organism, clarification, clarification_round)
    return _rule_based_select_model(tissue, organism)


# ---------------------------------------------------------------------------
# Model cache
# ---------------------------------------------------------------------------

_model_cache: dict[str, celltypist.models.Model] = {}


def _get_model(model_name: str) -> celltypist.models.Model:
    """Return a loaded CellTypist model, loading it on first use.

    Args:
        model_name: CellTypist model filename (e.g. 'Immune_All_Low.pkl').

    Returns:
        Loaded celltypist.models.Model instance.

    Raises:
        PipelineStepError: If the model file cannot be loaded.
    """
    if model_name not in _model_cache:
        try:
            _model_cache[model_name] = celltypist.models.Model.load(model=model_name)
            logger.info("Loaded and cached CellTypist model '%s'.", model_name)
        except Exception as e:
            raise PipelineStepError(
                "annotate", f"Failed to load CellTypist model '{model_name}': {e}"
            ) from e
    else:
        logger.info("Using cached CellTypist model '%s'.", model_name)
    return _model_cache[model_name]


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def run_marker_genes(adata: ad.AnnData, n_genes: int = 25) -> ad.AnnData:
    """Compute per-cluster marker genes using rank_genes_groups.

    Args:
        adata: Clustered AnnData object with 'leiden' in obs.
        n_genes: Number of top marker genes to compute per cluster.

    Returns:
        AnnData with rank_genes_groups results in uns.

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
    """Annotate cell types using CellTypist with majority voting.

    Args:
        adata: AnnData with normalized counts and 'leiden' in obs.
        model: CellTypist model filename.

    Returns:
        AnnData with 'celltypist_cell_type' added to obs.

    Raises:
        PipelineStepError: If the model cannot be loaded or annotation fails.
    """
    if "leiden" not in adata.obs.columns:
        raise PipelineStepError(
            "annotate",
            "'leiden' column not found in adata.obs. Run run_cluster() first.",
        )

    ct_model = _get_model(model)

    adata_full = adata.raw.to_adata()
    adata_full.obs["leiden"] = adata.obs["leiden"]

    try:
        predictions = celltypist.annotate(
            adata_full, model=ct_model, majority_voting=True, over_clustering="leiden"
        )
        adata.obs["celltypist_cell_type"] = predictions.predicted_labels["majority_voting"]
    except Exception as e:
        raise PipelineStepError("annotate", f"CellTypist annotation failed: {e}") from e

    return adata
