"""
corrections — User-editable semantic overrides (Metric Correction Store)
=======================================================================

Allows users to correct the system's semantic classification (SemanticRole,
BehavioralRole, AggregationSuitability) on a per-column, per-dataset basis.
Corrections are persisted in MongoDB and cached in Redis, then merged into
SemanticClassifier.classify() results at query time.

This is DataSage's Semantic Correction Memory applied to the profiling layer.
"""
