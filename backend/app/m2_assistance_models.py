"""Canonical bounded M2 proposals; provider content cannot grant permission."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StringConstraints, field_validator, model_validator

from .models import ClaimDetail, ContractModel, ID, Revision

ProposalText = Annotated[str, StringConstraints(min_length=1, max_length=8000, pattern=r"\S")]
ProposalTarget = Literal[
    "brand_company", "product", "target_audience", "platform", "communication_goal",
    "target_duration_seconds", "available_footage", "presenters", "locations", "tone",
    "production_limits", "approved_messages", "prohibited_claims", "claim",
]
SuggestedField = Literal["target_audience", "communication_goal"]


class M2AssistanceRequest(ContractModel):
    draft_version: Revision
    request_id: ID
    mode: Literal["extract", "suggest_task_field"] = "extract"
    requested_field: SuggestedField | None = None

    @model_validator(mode="after")
    def requested_mode(self):
        if (self.mode == "suggest_task_field") != (self.requested_field is not None):
            raise ValueError("Only task suggestions require a requested audience or goal field")
        return self


class M2ProposedClaim(ContractModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    statement: Annotated[str, StringConstraints(min_length=1, max_length=4000, pattern=r"\S")]
    supporting_notes: ProposalText | None = None
    source_urls: list[ProposalText] = Field(default_factory=list, max_length=10)
    qualification: Annotated[str, StringConstraints(min_length=1, max_length=4000)] | None = None

    _safe_sources = field_validator("source_urls")(ClaimDetail.safe_sources.__func__)


class M2CandidateContent(ContractModel):
    """A proposed editable value, without server identity or approval fields."""
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    target: ProposalTarget
    value: ProposalText | float | list[ProposalText] | M2ProposedClaim
    origin: Literal["extracted", "suggested"]
    source_excerpt: ProposalText | None = None

    @model_validator(mode="after")
    def value_matches_target(self):
        if self.target == "claim":
            valid = isinstance(self.value, M2ProposedClaim)
        elif self.target == "target_duration_seconds":
            valid = type(self.value) in (int, float) and self.value > 0
        elif self.target in {"approved_messages", "prohibited_claims"}:
            valid = isinstance(self.value, list) and 0 < len(self.value) <= 50
        else:
            valid = isinstance(self.value, str)
            if self.target in {"brand_company", "product", "target_audience", "platform", "communication_goal"}:
                valid = valid and len(self.value) <= 4000
        if not valid:
            raise ValueError("Proposal value must match its editable field")
        if self.origin == "extracted" and self.source_excerpt is None:
            raise ValueError("Extracted proposals require an exact source excerpt")
        if self.origin == "suggested" and (self.target not in {"target_audience", "communication_goal"} or self.source_excerpt is not None):
            raise ValueError("Only audience and goal may be suggested without a source excerpt")
        return self


class M2Candidate(M2CandidateContent):
    candidate_id: ID


class M2AssistanceResponse(ContractModel):
    request_id: ID
    source_draft_version: Revision
    provider_mode: Literal["real", "fake"]
    candidates: list[M2Candidate] = Field(max_length=30)
    unresolved_notes: list[ProposalText] = Field(default_factory=list, max_length=10)

    @field_validator("candidates")
    @classmethod
    def unique_candidates(cls, values):
        if len({item.candidate_id for item in values}) != len(values):
            raise ValueError("Proposal identifiers must be unique")
        return values


class M2AdoptRequest(ContractModel):
    source_draft_version: Revision
    request_id: ID
    candidates: list[M2Candidate] = Field(min_length=1, max_length=30)

    _unique_candidates = field_validator("candidates")(M2AssistanceResponse.unique_candidates.__func__)

    @field_validator("candidates")
    @classmethod
    def one_value_per_field(cls, values):
        targets = [item.target for item in values if item.target != "claim"]
        if len(set(targets)) != len(targets):
            raise ValueError("Choose one proposed value per field before using selected details")
        return values
