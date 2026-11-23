"""The typed contract for a single Markdown card's YAML frontmatter."""

from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints
from pydantic import field_validator, model_validator

NodeType = Literal["case", "myth_corpus", "motif_index", "mechanism", "theory"]
Genre = Literal[
    "myth", "fabulate", "memorate", "folktale", "urban_legend", "creepypasta_ostension",
    "historical_archive", "academic_model", "unclassified",
]
CredibilityTier = Literal["S", "A", "B", "C", "F"]
SpatialPrecision = Literal["exact", "city", "province", "culture_region", "global"]
ExplanationStatus = Literal["confirmed", "contested", "unverified", "refuted"]
RelationType = Literal[
    "INSTANCE_OF", "HAS_MOTIF", "TAGGED_OCM", "MIGRATED_TO", "EVOLVED_INTO",
    "VARIANT_OF", "COMPARED_WITH", "EXPLAINED_BY", "DEBUNKED_BY", "ATTESTS_MOTIF",
    "PART_OF_MACRO_TREND", "OSTENSION_OF",
]

LAYER_BY_TYPE: dict[NodeType, int] = {
    "case": 1,
    "myth_corpus": 2,
    "motif_index": 3,
    "mechanism": 4,
    "theory": 4,
}
CREDIBILITY_WEIGHT: dict[CredibilityTier, float] = {
    "S": 1.0, "A": 0.85, "B": 0.6, "C": 0.3, "F": 0.0,
}

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
NodeId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")]
UnitInterval = Annotated[float, Field(ge=0, le=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)


class Spatial(StrictModel):
    lat: Annotated[float, Field(ge=-90, le=90)] | None = None
    lng: Annotated[float, Field(ge=-180, le=180)] | None = None
    precision: SpatialPrecision
    location_name: NonBlank
    culture_region: NonBlank | None = None

    @model_validator(mode="after")
    def check_coordinates(self) -> Self:
        if (self.lat is None) != (self.lng is None):
            raise ValueError("spatial.lat 和 spatial.lng 须同时提供或同时留空")
        if self.precision == "exact" and self.lat is None:
            raise ValueError("spatial.precision 为 exact 时须提供坐标")
        if self.precision == "global" and self.lat is not None:
            raise ValueError("spatial.precision 为 global 时坐标须留空")
        return self


class Temporal(StrictModel):
    year_start: int | None = None
    year_end: int | None = None
    era_label: NonBlank
    uncertainty_note: NonBlank | None = None

    @model_validator(mode="after")
    def check_year_order(self) -> Self:
        if self.year_start is not None and self.year_end is not None:
            if self.year_start > self.year_end:
                raise ValueError("temporal.year_start 须小于或等于 temporal.year_end")
        return self


class Standards(StrictModel):
    atu_types: list[NonBlank] = Field(default_factory=list)
    thompson_motifs: list[NonBlank] = Field(default_factory=list)
    berezkin_codes: list[NonBlank] = Field(default_factory=list)
    ocm_codes: list[NonBlank] = Field(default_factory=list)
    macro_phylogeny: Literal["Laurasian", "Gondwanan"] | None = None


class MechanismReference(StrictModel):
    target_id: NodeId
    status: ExplanationStatus
    evidence_note: NonBlank


class Relation(StrictModel):
    type: RelationType
    target: NodeId
    weight: UnitInterval = 1.0
    note: NonBlank | None = None
    status: ExplanationStatus | None = None

    @model_validator(mode="after")
    def check_explanation(self) -> Self:
        if self.type == "EXPLAINED_BY":
            if self.status is None or self.note is None:
                raise ValueError("EXPLAINED_BY 须填写 status 和证据说明 note")
        elif self.status is not None:
            raise ValueError("status 只适用于 EXPLAINED_BY")
        return self


class Source(StrictModel):
    citation: NonBlank
    type: NonBlank
    url: HttpUrl | None = None
    doi: NonBlank | None = None
    locator: NonBlank | None = None
    local_path: NonBlank | None = None
    content_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")] | None = None


class Audit(StrictModel):
    created_at: date
    reviewed_by_human: bool
    ai_confidence: UnitInterval | None = None
    is_sample: bool = False
    reviewer: NonBlank | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    public_release: bool = False
    public_rights_note: NonBlank | None = None
    public_content_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")] | None = None

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_date(cls, value: object) -> object:
        if isinstance(value, str):
            parsed = date.fromisoformat(value)
            if parsed.isoformat() != value:
                raise ValueError("created_at 须使用 YYYY-MM-DD")
            return parsed
        return value

    @field_validator("reviewed_at", mode="before")
    @classmethod
    def parse_review_time(cls, value: object) -> object:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, datetime) and value.utcoffset() is None:
            raise ValueError("reviewed_at 须包含时区")
        return value

    @model_validator(mode="after")
    def check_public_release(self) -> Self:
        if self.public_release:
            if (not self.reviewed_by_human or self.is_sample or not self.reviewer or not self.reviewed_at
                    or not self.public_rights_note or not self.public_content_sha256):
                raise ValueError("公开资料须由人工复核并记录许可依据及内容哈希")
        elif self.public_rights_note or self.public_content_sha256:
            raise ValueError("未确认公开的资料不能附带公开许可签核")
        return self


class NodeMetadata(StrictModel):
    id: NodeId
    title: NonBlank
    aliases: list[NonBlank] = Field(default_factory=list)
    node_type: NodeType
    z_layer: Annotated[int, Field(ge=1, le=4)]
    genre: Genre
    credibility_tier: CredibilityTier
    is_fictional_quarantine: bool
    spatial: Spatial | None
    temporal: Temporal | None
    standards: Standards
    mechanisms: list[MechanismReference] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    sources: list[Source]
    audit: Audit

    @model_validator(mode="after")
    def check_node_constraints(self) -> Self:
        expected_layer = LAYER_BY_TYPE[self.node_type]
        if self.z_layer != expected_layer:
            raise ValueError(f"{self.node_type} 对应 z_layer={expected_layer}")
        if self.is_fictional_quarantine != (self.credibility_tier == "F"):
            raise ValueError("F 级与 is_fictional_quarantine 须一致")
        if self.genre == "creepypasta_ostension" and not self.is_fictional_quarantine:
            raise ValueError("creepypasta_ostension 须标为 F 级")
        if self.genre == "unclassified" and (self.audit.reviewed_by_human or self.audit.is_sample):
            raise ValueError("签核前须将 genre 改为已复核的体裁")
        if self.credibility_tier in {"S", "A"} and not self.sources:
            raise ValueError("S/A 级须提供至少一条来源")
        return self
