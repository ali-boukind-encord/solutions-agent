from __future__ import annotations

from pydantic import BaseModel, Field


class SyntheticFile(BaseModel):
    """A single synthetic data file to be created and uploaded."""

    filename: str = Field(
        description="Filename with .txt extension, e.g. 'marketing_email_001.txt'"
    )
    content: str = Field(description="Full text content of the synthetic file")
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Key-value metadata to attach to the file in Encord, "
            "e.g. {'category': 'marketing', 'source': 'synthetic'}"
        ),
    )


class OntologyOption(BaseModel):
    """A single option within a classification attribute."""

    label: str = Field(
        description="Display label for this option, e.g. 'Marketing'"
    )


class OntologyAttribute(BaseModel):
    """A classification attribute."""

    name: str = Field(description="Attribute name, e.g. 'Email Type'")
    attribute_type: str = Field(
        default="radio",
        description="Attribute type: 'radio', 'checklist', or 'text'",
    )
    required: bool = Field(default=True)
    options: list[OntologyOption] = Field(
        default_factory=list,
        description="List of options (for radio/checklist attributes)",
    )


class OntologyClassification(BaseModel):
    """A top-level classification in the ontology."""

    name: str = Field(
        description="Classification name, e.g. 'Email Classification'"
    )
    attributes: list[OntologyAttribute] = Field(
        description="Attributes within this classification"
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
        description="Ontology classifications to create"
    )
    synthetic_files: list[SyntheticFile] = Field(
        description="Synthetic data files to generate and upload"
    )
    summary: str = Field(
        description="Brief human-readable summary of what this demo project covers"
    )
