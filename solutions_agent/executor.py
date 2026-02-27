import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from encord.user_client import EncordUserClient
from encord.objects.ontology_structure import OntologyStructure
from encord.objects.attributes import RadioAttribute, ChecklistAttribute, TextAttribute
from encord.objects.common import Shape
from encord.orm.dataset import StorageLocation

from .schemas import DemoPlan, OntologyAttribute, NestedAttribute


SHAPE_MAP = {
    "bounding_box": Shape.BOUNDING_BOX,
    "polygon": Shape.POLYGON,
    "polyline": Shape.POLYLINE,
    "point": Shape.POINT,
    "rotatable_bounding_box": Shape.ROTATABLE_BOUNDING_BOX,
    "bitmask": Shape.BITMASK,
    "text": Shape.TEXT,
}

ATTRIBUTE_TYPE_MAP = {
    "radio": RadioAttribute,
    "checklist": ChecklistAttribute,
    "text": TextAttribute,
}


@dataclass
class ExecutionResult:
    """Summary of what was created in Encord."""

    project_hash: str
    dataset_hash: str
    ontology_hash: str
    files_uploaded: int
    project_url: str


def _get_client() -> EncordUserClient:
    """Create an authenticated Encord client.

    Tries these env vars in order:
    - ENCORD_SSH_KEY_FILE / ENCORD_SSH_KEY_PATH: path to the private key file
    - ENCORD_SSH_KEY: the raw private key content
    """
    domain = os.environ.get("ENCORD_DOMAIN", None)
    key_path = os.environ.get("ENCORD_SSH_KEY_FILE") or os.environ.get("ENCORD_SSH_KEY_PATH")

    if key_path:
        return EncordUserClient.create_with_ssh_private_key(
            ssh_private_key_path=key_path,
            **({"domain": domain} if domain else {}),
        )

    key_content = os.environ.get("ENCORD_SSH_KEY")
    if key_content:
        return EncordUserClient.create_with_ssh_private_key(
            ssh_private_key=key_content,
            **({"domain": domain} if domain else {}),
        )

    raise RuntimeError(
        "No Encord credentials found. Set one of: "
        "ENCORD_SSH_KEY_FILE, ENCORD_SSH_KEY_PATH, or ENCORD_SSH_KEY"
    )


def _add_attribute(parent, attr_spec: OntologyAttribute):
    """Add a top-level attribute (radio/checklist/text) to an object or classification.

    For radio attributes, options can have one level of nested attributes.
    """
    attr_cls = ATTRIBUTE_TYPE_MAP[attr_spec.attribute_type]
    attribute = parent.add_attribute(
        attr_cls,
        attr_spec.name,
        required=attr_spec.required,
    )
    if attr_spec.attribute_type == "radio":
        for option_spec in attr_spec.options:
            option = attribute.add_option(option_spec.label)
            for nested_attr_spec in option_spec.nested_attributes:
                _add_nested_attribute(option, nested_attr_spec)
    elif attr_spec.attribute_type == "checklist":
        for option_spec in attr_spec.options:
            attribute.add_option(option_spec.label)
    return attribute


def _add_nested_attribute(option, attr_spec: NestedAttribute):
    """Add a nested attribute (leaf level) to a NestableOption."""
    attr_cls = ATTRIBUTE_TYPE_MAP[attr_spec.attribute_type]
    attribute = option.add_nested_attribute(
        attr_cls,
        attr_spec.name,
        required=attr_spec.required,
    )
    if attr_spec.attribute_type in ("radio", "checklist"):
        for option_spec in attr_spec.options:
            attribute.add_option(option_spec.label)
    return attribute


def execute_plan(plan: DemoPlan, on_status: callable = None) -> ExecutionResult:
    """Execute a DemoPlan against the Encord SDK.

    Sequence:
    1. Create dataset (with backing folder)
    2. Write synthetic files to temp dir, upload via StorageFolder
    3. Create ontology with objects and classifications
    4. Create project linking dataset + ontology

    Args:
        plan: A fully populated DemoPlan from the planner.
        on_status: Optional callback for status updates, called with a string message.

    Returns:
        ExecutionResult with hashes and URLs of created resources.
    """

    def status(msg: str) -> None:
        if on_status:
            on_status(msg)

    client = _get_client()

    # --- Step 1: Create Dataset ---
    status("Creating dataset...")
    dataset_response = client.create_dataset(
        dataset_title=plan.naming.dataset_name,
        dataset_type=StorageLocation.CORD_STORAGE,
        create_backing_folder=True,
    )
    dataset_hash = dataset_response.dataset_hash
    backing_folder_uuid = dataset_response.backing_folder_uuid

    if backing_folder_uuid is None:
        raise RuntimeError(
            "Dataset was created without a backing folder. "
            "Cannot upload text files without a StorageFolder."
        )

    # Get the StorageFolder for uploading files
    storage_folder = client.get_storage_folder(backing_folder_uuid)

    # --- Step 2: Upload Synthetic Files ---
    status(f"Uploading {len(plan.synthetic_files)} synthetic files...")
    files_uploaded = 0
    with tempfile.TemporaryDirectory() as tmp_dir:
        for sf in plan.synthetic_files:
            file_path = Path(tmp_dir) / sf.filename
            file_path.write_text(sf.content, encoding="utf-8")

            storage_folder.upload_text(
                file_path=str(file_path),
                title=sf.filename,
                client_metadata=sf.metadata if sf.metadata else None,
            )
            files_uploaded += 1

    status(f"Uploaded {files_uploaded} files.")

    # --- Step 3: Create Ontology ---
    status("Creating ontology...")
    ontology_structure = OntologyStructure()

    # Add objects
    for obj_spec in plan.objects:
        shape = SHAPE_MAP[obj_spec.shape]
        obj = ontology_structure.add_object(name=obj_spec.name, shape=shape)
        for attr_spec in obj_spec.attributes:
            _add_attribute(obj, attr_spec)

    # Add classifications (each has exactly one attribute)
    for cls_spec in plan.classifications:
        classification = ontology_structure.add_classification()
        _add_attribute(classification, cls_spec.attribute)

    ontology = client.create_ontology(
        title=plan.naming.ontology_name,
        structure=ontology_structure,
    )
    ontology_hash = ontology.ontology_hash

    # --- Step 4: Create Project ---
    status("Creating project...")
    project_hash = client.create_project(
        project_title=plan.naming.project_name,
        dataset_hashes=[dataset_hash],
        ontology_hash=ontology_hash,
    )

    project_url = f"https://app.encord.com/projects/view/{project_hash}/summary"

    status("Done!")
    return ExecutionResult(
        project_hash=project_hash,
        dataset_hash=dataset_hash,
        ontology_hash=ontology_hash,
        files_uploaded=files_uploaded,
        project_url=project_url,
    )
