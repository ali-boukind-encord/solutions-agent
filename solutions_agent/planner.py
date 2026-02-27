import anthropic

from .schemas import DemoPlan

SYSTEM_PROMPT = """\
You are a solutions engineer assistant for Encord, a data labeling and annotation platform.

Given a sales solution script describing a prospect's use case, you must produce
a complete demo project plan. Your output must include:

1. NAMING: Descriptive names for the project, dataset, and ontology that reflect
   the prospect's company and use case. Format: "[Company] - [Use Case] Demo" for
   the project name.

2. ONTOLOGY: Design classification(s) that match the annotation task described.
   Think about what a human annotator would need to label. For example:
   - Email sorting -> Radio: "Email Type" with options like "Marketing", "Important", "Spam"
   - Document classification -> Radio: "Document Category" with relevant options
   Each classification should have 1 attribute with 2-6 options that cover the
   labeling categories relevant to the use case.

3. SYNTHETIC FILES: Generate realistic synthetic .txt files that represent the
   data modality described. Each file should:
   - Have a descriptive filename (snake_case, .txt extension)
   - Contain realistic content (150-400 words) that a human could plausibly annotate
   - Vary across the classification options so the demo showcases all labels
   - Include metadata with a 'category' key indicating the ground truth label

4. SUMMARY: A one-sentence description of the demo project.

Be creative but realistic. The synthetic data should feel genuine enough to
demonstrate the labeling workflow to a prospect during a live demo.
"""


def generate_demo_plan(solution_script: str, num_files: int) -> DemoPlan:
    """Parse a solution script and generate a complete demo plan.

    Makes a single Claude API call with structured outputs to produce
    a DemoPlan that can be executed deterministically against the Encord SDK.

    Args:
        solution_script: Raw text of the sales solution script.
        num_files: Number of synthetic files to generate.

    Returns:
        A fully populated DemoPlan ready for execution.

    Raises:
        anthropic.APIError: If the Claude API call fails.
        ValueError: If the response cannot be parsed into a DemoPlan.
    """
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    response = client.messages.parse(
        model="claude-sonnet-4-6",
        max_tokens=16384,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Here is the solution script for a prospect demo:\n\n"
                    f"---\n{solution_script}\n---\n\n"
                    f"Generate a complete demo project plan with exactly "
                    f"{num_files} synthetic .txt files."
                ),
            }
        ],
        output_format=DemoPlan,
    )

    plan = response.parsed_output
    if plan is None:
        raise ValueError(
            f"Claude returned a response but it could not be parsed into a DemoPlan. "
            f"Stop reason: {response.stop_reason}"
        )

    return plan
