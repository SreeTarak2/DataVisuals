# TODO: REMOVE after Phase 9 — re-export shim
from agents.belief.belief_store import (  # noqa: F401
    BeliefStore, BayesianTracker, PassiveBeliefIngestion,
    get_belief_store, get_bayesian_tracker,
)
