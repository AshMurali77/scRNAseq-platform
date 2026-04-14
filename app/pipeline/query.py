"""Natural-language querying of pipeline results via an LLM.

Builds a rich text context from a QueryContext (compressed PipelineResult),
then answers the user's question in a multi-turn conversation backed by
claude-opus-4-6.
"""

import logging

import anthropic

from app.models.schemas import ConversationMessage, QueryContext
from app.utils.errors import PipelineStepError

logger = logging.getLogger(__name__)

_MAX_TOKENS = 1024


def _build_context_text(ctx: QueryContext) -> str:
    """Serialize a QueryContext into a structured text block for the system prompt.

    Args:
        ctx: Compressed pipeline result.

    Returns:
        Multi-section markdown-style string describing the analysis.
    """
    lines: list[str] = [
        "## Dataset Summary",
        f"- Organism: {ctx.organism}",
        f"- Tissue: {ctx.tissue}",
        f"- Cells before QC: {ctx.n_cells_input}",
        f"- Cells after QC: {ctx.n_cells_after_qc}",
        f"- Highly variable genes: {ctx.n_hvgs}",
        f"- Leiden clusters: {ctx.n_clusters}",
        f"- CellTypist model: {ctx.model_display_name}",
        "",
    ]

    if ctx.dataset_metadata:
        dm = ctx.dataset_metadata
        lines += [
            "## File Metadata",
            f"- Organism in file: {dm.organism_in_file or 'not found'}",
            f"- Tissue in file: {dm.tissue_in_file or 'not found'}",
        ]
        if dm.organism_mismatch:
            lines.append(
                "- WARNING: Organism in file does not match user-provided organism."
            )
        lines.append("")

    # Build marker gene map: cluster → list of MarkerGene sorted by score desc
    marker_map: dict[str, list] = {}
    for mg in ctx.marker_genes:
        marker_map.setdefault(mg.cluster, []).append(mg)
    for cid in marker_map:
        marker_map[cid].sort(key=lambda m: m.score, reverse=True)

    # Build validation map: cluster → ClusterValidation
    val_map = {cv.cluster_id: cv for cv in ctx.cluster_validations}

    lines.append("## Cluster Annotations")

    for cs in sorted(
        ctx.cluster_summaries,
        key=lambda c: int(c.cluster_id) if c.cluster_id.isdigit() else c.cluster_id,
    ):
        cid = cs.cluster_id
        lines.append(f"\n### Cluster {cid}: {cs.celltypist_label}")

        if cid in val_map:
            cv = val_map[cid]
            lines.append(f"Expert review status: {cv.status}")
            lines.append(f"Expert explanation: {cv.explanation}")

        genes = marker_map.get(cid, [])[:10]
        if genes:
            gene_parts = [
                f"{m.gene} (score={m.score:.2f}, logFC={m.log_fold_change:.2f})"
                for m in genes
            ]
            lines.append(f"Top marker genes: {', '.join(gene_parts)}")

    return "\n".join(lines)


def answer_query(
    question: str,
    conversation_history: list[ConversationMessage],
    context: QueryContext,
) -> str:
    """Answer a natural-language question about a pipeline result using an LLM.

    Builds a structured context string from the QueryContext and passes it as
    the system prompt. Prior conversation turns are included so the model can
    handle follow-up questions.

    Args:
        question: The user's current question.
        conversation_history: Prior turns in the conversation (user + assistant),
            not including the current question.
        context: Compressed pipeline result used as the knowledge base.

    Returns:
        The LLM's plain-text answer.

    Raises:
        PipelineStepError: If the API call fails.
    """
    context_text = _build_context_text(context)

    system_prompt = (
        "You are a bioinformatics expert assistant helping a researcher understand "
        "their single-cell RNA sequencing analysis results.\n\n"
        "You have access to the following analysis results:\n\n"
        f"{context_text}\n\n"
        "Answer the researcher's questions concisely and accurately. Focus on "
        "biological interpretation. If asked about something not present in the "
        "data above, say so clearly. Use markdown formatting when it aids clarity."
    )

    messages = [
        {"role": msg.role, "content": msg.content}
        for msg in conversation_history
    ]
    messages.append({"role": "user", "content": question})

    client = anthropic.Anthropic()

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=_MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        )
    except anthropic.APIError as exc:
        raise PipelineStepError("query", f"LLM query failed: {exc}") from exc

    for block in response.content:
        if block.type == "text":
            return block.text

    logger.warning("LLM returned no text block for query.")
    return "No response generated."
