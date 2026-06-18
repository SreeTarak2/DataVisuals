"""
ThinkerAgent — Deep Reasoning & File Review Agent
==================================================
A production-grade reasoning engine that provides:

1. CHAIN-OF-THOUGHT REASONING
   Steps through problems systematically, producing intermediate reasoning
   states before arriving at a conclusion. Useful for complex analytical
   questions, debugging, and strategic planning.

2. MECE FRAMEWORK ANALYSIS (McKinsey)
   Applies Mutually Exclusive, Collectively Exhaustive decomposition to
   break complex problems into non-overlapping, complete components.

3. FILE / CODE / OUTPUT REVIEW
   Evaluates files, code, prompts, or LLM outputs against quality dimensions
   (correctness, clarity, completeness, safety). Produces structured reports.

4. SYNTHESIS
   Combines reasoning traces and observations into a structured,
   decision-ready conclusion with confidence scoring.

Architecture:
    Standalone service class — called by other agents (ChatAgent, AnalystAgent)
    or used as a LangGraph node. Does NOT extend BaseAgent because it is a
    reasoning tool, not a ReAct agent (it doesn't need a tool-selection loop).

    ThinkerAgent.query_understanding  — Rule-based query classification
    ThinkerAgent.chain_of_thought     — Step-by-step reasoning with thinking traces
    ThinkerAgent.mece_analysis        — McKinsey MECE decomposition
    ThinkerAgent.review_file          — Quality review of code/prompts/outputs

Usage:
    thinker = ThinkerAgent()

    # Deep reasoning about analytical findings
    result = await thinker.chain_of_thought(
        question="Which factors most influence resale value?",
        context={"columns": ["price", "mileage", "age", "model"]},
        observations=[{"tool": "stats", "finding": "r=-0.71 between price and mileage"}],
    )
    # result.thinking_traces  -> list of reasoning steps (surface to user)
    # result.conclusion       -> final answer
    # result.confidence       -> 0.0-1.0

    # File review for quality assurance
    report = await thinker.review_file(
        target_name="prompt_templates.py",
        content=file_text,
        target_type="file",
    )
    # report.findings        -> list of ReviewFinding objects
    # report.overall_score   -> 0-10 quality score
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from core.prompts import extract_json

logger = logging.getLogger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================


class ThinkingStepType(str, Enum):
    """Types of reasoning steps in a thinking trace."""

    DECOMPOSE = "decompose"          # Breaking a problem into parts
    ANALYZE = "analyze"              # Analyzing evidence or data
    HYPOTHESIZE = "hypothesize"      # Forming a hypothesis
    TEST = "test"                    # Testing against evidence
    CRITIQUE = "critique"            # Self-critique of own reasoning
    REVISE = "revise"                # Revising based on critique
    CONCLUDE = "conclude"            # Final conclusion
    UNCERTAIN = "uncertain"          # Acknowledging uncertainty


@dataclass
class ThinkingTrace:
    """
    A single step in the agent's reasoning process.

    These can be surfaced to the user to build trust and show
    the agent is reasoning, not guessing.
    """

    step_number: int
    step_type: ThinkingStepType
    title: str
    content: str
    evidence: list[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class ReasoningResult:
    """
    Complete output from a reasoning session.
    """

    question: str
    conclusion: str
    thinking_traces: list[ThinkingTrace]
    confidence: float
    key_findings: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    suggested_next_steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ReviewSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ReviewFinding:
    """
    A single finding from a file/code review.
    """

    title: str
    description: str
    severity: ReviewSeverity
    location: str = ""
    recommendation: str = ""
    category: str = ""


@dataclass
class ReviewReport:
    """
    Complete review output for a file or code block.
    """

    target_name: str
    target_type: str
    is_valid: bool
    findings: list[ReviewFinding]
    overall_score: float
    summary: str
    suggestions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# PROMPT BUILDERS
# =============================================================================


def _build_chain_of_thought_prompt(
    question: str,
    context: dict[str, Any] | None = None,
    observations: list[dict[str, Any]] | None = None,
) -> str:
    ctx_block = ""
    if context:
        lines = []
        for key, val in context.items():
            val_str = json.dumps(val, indent=2, default=str) if isinstance(val, (list, dict)) else str(val)
            lines.append(f"  {key.upper()}: {val_str[:600]}")
        ctx_block = "\nCONTEXT:\n" + "\n".join(lines)

    obs_block = ""
    if observations:
        obs_block = "\nOBSERVATIONS:\n" + json.dumps(observations, indent=2, default=str)[:2000]

    return f"""\
You are a senior data analyst performing structured reasoning.

Your job is to think through problems step by step, showing your work.
For each thinking step, you must:
1. State what you are doing in this step
2. Do the reasoning (in plain English, no jargon)
3. Cite specific evidence or data you are using
4. State your confidence in this step's conclusion

Rules:
- Be specific. Use actual numbers, column names, and observations.
- Acknowledge uncertainty when data is insufficient.
- Each step must build on the previous one.
- If you find a flaw in your earlier reasoning, flag it and revise.
- End with a clear, decision-ready conclusion.

QUESTION: {question}
{ctx_block}
{obs_block}

Return your response as JSON:
{{
  "thinking_trace": [
    {{
      "step_number": 1,
      "step_type": "decompose|analyze|hypothesize|test|critique|revise|conclude",
      "title": "Short step title",
      "content": "Your reasoning for this step. Be specific with numbers and evidence.",
      "evidence": ["Specific evidence point 1", "Evidence point 2"],
      "confidence": 0.95
    }}
  ],
  "final_conclusion": "Your overall conclusion from all steps",
  "key_findings": ["Finding 1", "Finding 2"],
  "uncertainties": ["What you are not sure about"],
  "confidence": 0.85
}}
"""


def _build_mece_analysis_prompt(
    problem: str,
    data_context: list[dict[str, Any]] | None = None,
) -> str:
    data_block = ""
    if data_context:
        data_block = "\nDATA:\n" + json.dumps(data_context, indent=2, default=str)

    return f"""\
You are a McKinsey-trained analyst applying the MECE framework.
MECE = Mutually Exclusive, Collectively Exhaustive.

Decompose the problem into components that are:
1. MUTUALLY EXCLUSIVE — No overlap between components.
2. COLLECTIVELY EXHAUSTIVE — Together, the components cover the entire problem.

For each component, provide:
- Category name
- The evidence supporting it
- Why it is distinct from other categories
- What decision or action it implies

PROBLEM: {problem}
{data_block}

Return your response as JSON:
{{
  "components": [
    {{
      "category": "Category name",
      "evidence": ["Evidence supporting this category"],
      "why_distinct": "Why this is mutually exclusive from other categories",
      "implied_action": "What decision or action this category implies"
    }}
  ],
  "mece_verification": {{
    "mutually_exclusive": true,
    "collectively_exhaustive": true,
    "overlap_notes": "Any overlap or gaps identified",
    "missing_elements": ["Anything that should be added"]
  }},
  "final_recommendation": "The strategic recommendation based on all components"
}}
"""


def _build_file_review_prompt(
    target_name: str,
    content: str,
    target_type: str = "file",
    project_context: str | None = None,
) -> str:
    ctx_block = f"\nPROJECT CONTEXT:\n{project_context}\n" if project_context else ""

    return f"""\
You are a senior engineer reviewing code, prompts, or configuration files.

Review against these dimensions:
1. CORRECTNESS — Does it do what it claims? Any bugs or logic errors?
2. SAFETY — Any security issues, injection vectors, or data leaks?
3. CLARITY — Is the intent clear? Are names and comments helpful?
4. COMPLETENESS — Are there missing edge cases, error handling, or validation?
5. CONSISTENCY — Does it follow the project's existing patterns and conventions?

Target: {target_name}
Type: {target_type}
{ctx_block}
Content to review:
```
{content[:4000]}
```

Return your response as JSON:
{{
  "is_valid": true,
  "overall_score": 8,
  "summary": "One paragraph summary of the review findings.",
  "findings": [
    {{
      "title": "Short issue title",
      "description": "What is wrong and why it matters",
      "severity": "critical|high|medium|low|info",
      "location": "File path or line number",
      "recommendation": "Concrete fix suggestion",
      "category": "correctness|safety|clarity|completeness|consistency"
    }}
  ],
  "suggestions": ["First improvement suggestion", "Second suggestion"]
}}
"""


def _build_synthesis_prompt(
    question: str,
    thinking_traces: list[dict[str, Any]],
) -> str:
    traces_block = json.dumps(thinking_traces, indent=2, default=str)

    return f"""\
You are synthesizing multiple reasoning traces into a final conclusion.

Given:
- The original question or task
- All reasoning steps (chain-of-thought)
- Supporting evidence
- Identified uncertainties

Produce:
1. CONCLUSION — Direct answer, decision-ready. One paragraph.
2. KEY FINDINGS — The 2-4 most important facts that support the conclusion.
3. UNCERTAINTIES — What is not known or could change the conclusion.
4. NEXT STEPS — What to do next to resolve uncertainties or act on the conclusion.
5. CONFIDENCE — 0.0 to 1.0, with one-sentence justification.

ORIGINAL QUESTION: {question}

REASONING TRACES:
{traces_block}

Return your response as JSON:
{{
  "conclusion": "Direct answer, one paragraph, decision-ready.",
  "key_findings": ["Finding 1 with specific evidence", "Finding 2"],
  "uncertainties": ["What is not yet known"],
  "suggested_next_steps": ["Concrete next action 1", "Next action 2"],
  "confidence": 0.85
}}
"""# =============================================================================
# THINKER AGENT
# =============================================================================


class ThinkerAgent:
    """
    Deep reasoning and file review agent.

    Provides four core capabilities:
        chain_of_thought()  — Step-by-step reasoning with full trace
        mece_analysis()     — McKinsey MECE decomposition
        review_file()       — Code/prompt/output quality review
        synthesize()        — Combine traces into final conclusion

    Designed to be used as:
    - A standalone reasoning engine called from other agents
    - A LangGraph node in quis_graph.py
    - An API endpoint for user-facing thinking traces
    """

    def __init__(self, llm_router: Any | None = None):
        self._llm_router = llm_router

    @property
    def llm_router(self) -> Any:
        """Lazy import of the LLM router to avoid circular imports."""
        if self._llm_router is None:
            from services.llm_router import llm_router as _router
            self._llm_router = _router
        return self._llm_router

    # ------------------------------------------------------------------
    # 1. CHAIN-OF-THOUGHT REASONING
    # ------------------------------------------------------------------

    async def chain_of_thought(
        self,
        question: str,
        context: dict[str, Any] | None = None,
        observations: list[dict[str, Any]] | None = None,
        model_role: str = "complex_analysis",
    ) -> ReasoningResult:
        """
        Perform step-by-step reasoning on a question.

        Args:
            question: The question or problem to reason about
            context: Optional context dict (schema, metadata, etc.)
            observations: Optional tool observations from a ReAct loop
            model_role: LLM role to use (default: complex_analysis)

        Returns:
            ReasoningResult with full thinking trace and conclusion
        """
        prompt = _build_chain_of_thought_prompt(question, context, observations)

        try:
            raw = await self.llm_router.call(
                prompt=prompt,
                model_role=model_role,
                expect_json=True,
                temperature=0.2,
                max_tokens=2048,
            )
        except Exception as e:
            logger.error(f"[ThinkerAgent] chain_of_thought failed: {e}", exc_info=True)
            return ReasoningResult(
                question=question,
                conclusion=f"Reasoning failed: {e}",
                thinking_traces=[],
                confidence=0.0,
                metadata={"error": str(e)},
            )

        parsed = extract_json(raw)
        traces = parsed.get("thinking_trace", [])

        thinking_traces = []
        for t in traces:
            try:
                thinking_traces.append(
                    ThinkingTrace(
                        step_number=t.get("step_number", 0),
                        step_type=ThinkingStepType(t.get("step_type", "analyze")),
                        title=t.get("title", ""),
                        content=t.get("content", ""),
                        evidence=t.get("evidence", []),
                        confidence=t.get("confidence", 1.0),
                    )
                )
            except Exception:
                continue

        return ReasoningResult(
            question=question,
            conclusion=parsed.get("final_conclusion", ""),
            thinking_traces=thinking_traces,
            confidence=parsed.get("confidence", 0.5),
            key_findings=parsed.get("key_findings", []),
            uncertainties=parsed.get("uncertainties", []),
            metadata={"model_role": model_role, "trace_count": len(thinking_traces)},
        )

    # ------------------------------------------------------------------
    # 2. MECE FRAMEWORK ANALYSIS
    # ------------------------------------------------------------------

    async def mece_analysis(
        self,
        problem: str,
        data_context: list[dict[str, Any]] | None = None,
        model_role: str = "complex_analysis",
    ) -> dict[str, Any]:
        """
        Apply MECE (Mutually Exclusive, Collectively Exhaustive) decomposition.

        Args:
            problem: The business problem or analytical question
            data_context: Optional data evidence to ground the analysis
            model_role: LLM role to use

        Returns:
            Dict with components, mece_verification, final_recommendation
        """
        prompt = _build_mece_analysis_prompt(problem, data_context)

        try:
            raw = await self.llm_router.call(
                prompt=prompt,
                model_role=model_role,
                expect_json=True,
                temperature=0.2,
                max_tokens=2048,
            )
        except Exception as e:
            logger.error(f"[ThinkerAgent] mece_analysis failed: {e}", exc_info=True)
            return {
                "components": [],
                "mece_verification": {
                    "mutually_exclusive": False,
                    "collectively_exhaustive": False,
                },
                "error": str(e),
            }

        return extract_json(raw)

    # ------------------------------------------------------------------
    # 3. FILE / CODE / OUTPUT REVIEW
    # ------------------------------------------------------------------

    async def review_file(
        self,
        target_name: str,
        content: str,
        target_type: str = "code_snippet",
        project_context: str | None = None,
        model_role: str = "validation",
    ) -> ReviewReport:
        """
        Review a file, code snippet, prompt, or LLM output for quality issues.

        Args:
            target_name: Name to identify what is being reviewed
            content: The actual text/code to review
            target_type: Type of content: "file", "code_snippet", "prompt", "output"
            project_context: Optional context about project conventions
            model_role: LLM role to use

        Returns:
            ReviewReport with findings, score, and recommendations
        """
        prompt = _build_file_review_prompt(target_name, content, target_type, project_context)

        try:
            raw = await self.llm_router.call(
                prompt=prompt,
                model_role=model_role,
                expect_json=True,
                temperature=0.1,
                max_tokens=2048,
            )
        except Exception as e:
            logger.error(f"[ThinkerAgent] review_file failed: {e}", exc_info=True)
            return ReviewReport(
                target_name=target_name,
                target_type=target_type,
                is_valid=False,
                findings=[
                    ReviewFinding(
                        title="Review failed",
                        description=f"LLM call error: {e}",
                        severity=ReviewSeverity.HIGH,
                    )
                ],
                overall_score=0.0,
                summary=f"Review failed: {e}",
                metadata={"error": str(e)},
            )

        parsed = extract_json(raw)
        findings_raw = parsed.get("findings", [])
        findings = []
        for f in findings_raw:
            try:
                findings.append(
                    ReviewFinding(
                        title=f.get("title", "Untitled"),
                        description=f.get("description", ""),
                        severity=ReviewSeverity(f.get("severity", "info")),
                        location=f.get("location", ""),
                        recommendation=f.get("recommendation", ""),
                        category=f.get("category", ""),
                    )
                )
            except Exception:
                continue

        return ReviewReport(
            target_name=target_name,
            target_type=target_type,
            is_valid=parsed.get("is_valid", False),
            findings=findings,
            overall_score=parsed.get("overall_score", 5.0),
            summary=parsed.get("summary", ""),
            suggestions=parsed.get("suggestions", []),
            metadata={"finding_count": len(findings)},
        )

    # ------------------------------------------------------------------
    # 4. SYNTHESIS
    # ------------------------------------------------------------------

    async def synthesize(
        self,
        question: str,
        thinking_traces: list[dict[str, Any] | ThinkingTrace],
        model_role: str = "narrative_story",
    ) -> dict[str, Any]:
        """
        Combine reasoning traces into a final structured conclusion.

        Args:
            question: The original question or task
            thinking_traces: List of ThinkingTrace objects or dicts
            model_role: LLM role to use

        Returns:
            Dict with conclusion, key_findings, uncertainties,
            suggested_next_steps, confidence
        """
        traces_as_dicts = []
        for t in thinking_traces:
            if isinstance(t, ThinkingTrace):
                traces_as_dicts.append(
                    {
                        "step_number": t.step_number,
                        "step_type": t.step_type.value,
                        "title": t.title,
                        "content": t.content,
                        "evidence": t.evidence,
                        "confidence": t.confidence,
                    }
                )
            else:
                traces_as_dicts.append(t)

        prompt = _build_synthesis_prompt(question, traces_as_dicts)

        try:
            raw = await self.llm_router.call(
                prompt=prompt,
                model_role=model_role,
                expect_json=True,
                temperature=0.3,
                max_tokens=1024,
            )
        except Exception as e:
            logger.error(f"[ThinkerAgent] synthesize failed: {e}", exc_info=True)
            return {
                "conclusion": f"Synthesis failed: {e}",
                "key_findings": [],
                "uncertainties": [],
                "suggested_next_steps": [],
                "confidence": 0.0,
            }

        return extract_json(raw)

    # ------------------------------------------------------------------
    # 5. FULL REASONING PIPELINE
    # ------------------------------------------------------------------

    async def think(
        self,
        question: str,
        context: dict[str, Any] | None = None,
        observations: list[dict[str, Any]] | None = None,
        use_mece: bool = False,
    ) -> ReasoningResult:
        """
        Run the full reasoning pipeline: CoT → optionally MECE → synthesize.

        This is the primary entry point for most use cases.

        Args:
            question: The question or problem to reason about
            context: Optional context
            observations: Optional tool observations
            use_mece: Whether to also run MECE decomposition

        Returns:
            ReasoningResult with complete reasoning
        """
        start = datetime.utcnow()

        # Step 1: Chain of thought
        result = await self.chain_of_thought(question, context, observations)

        # Step 2: Optional MECE analysis (for business/strategic problems)
        if use_mece and result.thinking_traces:
            mece_result = await self.mece_analysis(question, context)
            result.metadata["mece_analysis"] = mece_result

        # Step 3: Synthesize the thinking trace
        if result.thinking_traces:
            synthesis = await self.synthesize(question, result.thinking_traces)
            if synthesis.get("conclusion"):
                result.conclusion = synthesis["conclusion"]
            if synthesis.get("key_findings"):
                result.key_findings = synthesis.get("key_findings", [])
            if synthesis.get("suggested_next_steps"):
                result.suggested_next_steps = synthesis.get("suggested_next_steps", [])
            if synthesis.get("uncertainties"):
                result.uncertainties = synthesis.get("uncertainties", [])

        elapsed = (datetime.utcnow() - start).total_seconds()
        result.metadata["elapsed_seconds"] = elapsed
        logger.info(
            f"[ThinkerAgent] think() completed in {elapsed:.1f}s — "
            f"{len(result.thinking_traces)} traces, confidence={result.confidence:.2f}"
        )

        return result
