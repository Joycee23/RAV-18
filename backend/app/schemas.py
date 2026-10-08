import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Decision(StrEnum):
    approve = "approve"
    reject = "reject"


class ClaimType(StrEnum):
    observation = "observation"


class StepRead(BaseModel):
    name: str
    status: str
    started_at: datetime
    finished_at: datetime
    message: str


class EvidenceRead(BaseModel):
    id: uuid.UUID
    timestamp: datetime
    evidence_type: str
    label: str
    description: str
    metadata: dict = Field(validation_alias="metadata_json")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class SignedMediaUrl(BaseModel):
    url: str
    expires_at: datetime


class VideoFindingDraft(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    timestamp_seconds: float = Field(ge=0)
    evidence_ids: list[uuid.UUID] = Field(min_length=1)
    claim_type: ClaimType = ClaimType.observation


class EventRead(BaseModel):
    id: uuid.UUID
    timestamp: datetime
    source: str
    event_type: str
    message: str
    details: dict
    model_config = ConfigDict(from_attributes=True)


class FindingRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    confidence: float
    evidence_ids: list[uuid.UUID]
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)


class ReviewActionRead(BaseModel):
    id: uuid.UUID
    decision: str
    actor_role: str
    actor_name: str
    note: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AnalysisRunRead(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    status: str
    steps: list[StepRead]
    warning: str | None
    started_at: datetime
    finished_at: datetime | None
    findings: list[FindingRead]
    reviews: list[ReviewActionRead] = []
    model_config = ConfigDict(from_attributes=True)


class IncidentSummary(BaseModel):
    id: uuid.UUID
    title: str
    severity: str
    status: str
    occurred_at: datetime
    vehicle_id: str
    summary: str
    model_config = ConfigDict(from_attributes=True)


class IncidentDetail(IncidentSummary):
    metadata: dict = Field(validation_alias="metadata_json")
    events: list[EventRead]
    evidence: list[EvidenceRead]
    runs: list[AnalysisRunRead]
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class IncidentList(BaseModel):
    items: list[IncidentSummary]


class ReviewActionCreate(BaseModel):
    decision: Decision
    actor_role: str
    actor_name: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("actor_name")
    @classmethod
    def actor_name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("actor_name must not be blank")
        return value.strip()


class HealthRead(BaseModel):
    status: str
