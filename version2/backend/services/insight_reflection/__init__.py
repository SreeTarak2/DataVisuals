"""
insight_reflection — Self-improving critic for AI-generated content quality.

Architecture:
    ├── QualityScorer          → Rates insights on novelty, actionability, specificity
    ├── PromptAdjuster         → Adjusts prompt parameters based on failure patterns
    ├── FeedbackLoopStore      → Persists quality scores per dataset type
    ├── ThresholdCalibrator    → Adjusts confidence thresholds based on history
    ├── ConversationLearner    → Per-conversation instruction memory (MongoDB-backed)
    ├── DomainPromptAdjuster   → Per-domain quality aggregation and prompt tuning
    └── HarnessValidator       → Self-Harness-style validation gate before promotion

Runs after every insight/KPI/chart generation to close the quality feedback loop.
"""

from .reflector import InsightReflectionAgent
from .conversation_learner import ConversationLearner, conversation_learner
from .domain_prompt_adjuster import DomainPromptAdjuster, domain_prompt_adjuster
from .harness_validator import HarnessValidator, harness_validator

__all__ = [
    "InsightReflectionAgent",
    "ConversationLearner",
    "conversation_learner",
    "DomainPromptAdjuster",
    "domain_prompt_adjuster",
    "HarnessValidator",
    "harness_validator",
]
