"""Deterministic temporal knowledge authority and projection contracts."""

from knowledge.domain import (
    ApplicabilityDimension,
    ApplicabilityTerm,
    ConflictStatus,
    KnowledgeApplicability,
    KnowledgeCatalog,
    KnowledgeConflict,
    KnowledgeDomainError,
    KnowledgeObject,
    KnowledgeQuery,
    KnowledgeSelection,
    KnowledgeSelectionStatus,
    KnowledgeSupersession,
    KnowledgeTemporalOverlap,
    KnowledgeVersion,
    TimeRange,
)
from knowledge.projection import (
    KnowledgeProjectionBinding,
    ProjectionBindingMismatch,
    bind_projection_manifest,
    verify_projection_manifest,
)

__all__ = [
    "ApplicabilityDimension",
    "ApplicabilityTerm",
    "ConflictStatus",
    "KnowledgeApplicability",
    "KnowledgeCatalog",
    "KnowledgeConflict",
    "KnowledgeDomainError",
    "KnowledgeObject",
    "KnowledgeProjectionBinding",
    "KnowledgeQuery",
    "KnowledgeSelection",
    "KnowledgeSelectionStatus",
    "KnowledgeSupersession",
    "KnowledgeTemporalOverlap",
    "KnowledgeVersion",
    "ProjectionBindingMismatch",
    "TimeRange",
    "bind_projection_manifest",
    "verify_projection_manifest",
]
