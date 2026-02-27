from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SyntheticFile(BaseModel):
    """A single synthetic data file to be created and uploaded."""

    filename: str = Field(
        description="Filename with .txt or .html extension, e.g. 'marketing_email_001.txt' or 'marketing_email_001.html'"
    )
    content: str = Field(description="Full text content of the synthetic file")
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Key-value metadata to attach to the file in Encord, "
            "e.g. {'category': 'marketing', 'source': 'synthetic'}"
        ),
    )


# --- Nested level (leaf): options with no further nesting ---

class LeafOption(BaseModel):
    """A leaf option (no further nesting)."""

    label: str = Field(description="Display label for this option")


class NestedAttribute(BaseModel):
    """An attribute at the nested level (under a radio option). Cannot nest further."""

    name: str = Field(description="Attribute name")
    attribute_type: Literal["radio", "checklist", "text"] = Field(default="radio")
    required: bool = Field(default=True)
    options: list[LeafOption] = Field(
        default_factory=list,
        description="Options for this nested attribute (no further nesting)",
    )


# --- Top level: options that can have one level of nested attributes ---

class OntologyOption(BaseModel):
    """An option within a top-level attribute.

    For radio attributes, options can have nested_attributes that appear when selected.
    """

    label: str = Field(description="Display label for this option, e.g. 'Marketing'")
    nested_attributes: list[NestedAttribute] = Field(
        default_factory=list,
        description="Nested attributes revealed when this option is selected (radio options only)",
    )


class OntologyAttribute(BaseModel):
    """An attribute (radio, checklist, or text) that can be attached to objects or classifications."""

    name: str = Field(description="Attribute name, e.g. 'Email Type'")
    attribute_type: Literal["radio", "checklist", "text"] = Field(
        default="radio",
        description="Attribute type: 'radio', 'checklist', or 'text'",
    )
    required: bool = Field(default=True)
    options: list[OntologyOption] = Field(
        default_factory=list,
        description="List of options (for radio/checklist attributes, ignored for text)",
    )


class OntologyClassification(BaseModel):
    """A top-level classification in the ontology.

    IMPORTANT: Each classification has exactly ONE attribute (Encord constraint).
    To have multiple classification attributes, create multiple classifications.
    """

    attribute: OntologyAttribute = Field(
        description="The single root attribute for this classification"
    )


class OntologyObject(BaseModel):
    """An object (shape annotation) in the ontology, e.g. bounding box, polygon."""

    name: str = Field(description="Object name, e.g. 'Vehicle', 'Person'")
    shape: Literal[
        "bounding_box",
        "polygon",
        "polyline",
        "point",
        "rotatable_bounding_box",
        "bitmask",
        "text",
    ] = Field(
        description="Shape type for this object annotation"
    )
    attributes: list[OntologyAttribute] = Field(
        default_factory=list,
        description="Optional attributes to attach to this object (e.g. radio for sub-classification)",
    )


class NamingInfo(BaseModel):
    """Names for the Encord resources to be created."""

    project_name: str = Field(description="Human-readable project name")
    dataset_name: str = Field(description="Human-readable dataset name")
    ontology_name: str = Field(description="Human-readable ontology name")


class DemoPlan(BaseModel):
    """Complete plan for setting up an Encord demo project.

    This is the top-level structured output that Claude must produce.
    It contains everything needed to deterministically execute the
    Encord SDK calls.
    """

    naming: NamingInfo
    classifications: list[OntologyClassification] = Field(
        default_factory=list,
        description="Ontology classifications to create (each has exactly one attribute)",
    )
    objects: list[OntologyObject] = Field(
        default_factory=list,
        description="Ontology objects (shape annotations) to create",
    )
    synthetic_files: list[SyntheticFile] = Field(
        description="Synthetic data files to generate and upload"
    )
    summary: str = Field(
        description="Brief human-readable summary of what this demo project covers"
    )
