import anthropic

from .schemas import DemoPlan

SYSTEM_PROMPT = """\
You are a solutions engineer assistant for Encord, a data labeling and annotation platform.

Given a sales solution script describing a prospect's use case, you must produce
a complete demo project plan. Your output must include:

1. NAMING: Descriptive names for the project, dataset, and ontology that reflect
   the prospect's company and use case. Format: "[Company] - [Use Case] Demo" for
   the project name.

2. ONTOLOGY: Design the ontology using the appropriate mix of objects and
   classifications based on the use case:

   CLASSIFICATIONS (global labels applied to the whole file/frame):
   - Use for document-level or frame-level labeling tasks
   - Each classification has exactly ONE attribute (radio, checklist, or text)
   - To have multiple classification attributes, create multiple classifications
   - Example: Email sorting -> classification with radio attribute "Email Type"
     with options "Marketing", "Important", "Spam"

   OBJECTS (shape annotations drawn on specific regions):
   - Use when the task involves locating/marking regions in images, video, or documents
   - Supported shapes: bounding_box, polygon, polyline, point, rotatable_bounding_box, bitmask, text
   - Objects can have zero or more attributes (radio, checklist, text) for sub-classification
   - Example: Object detection -> object "Vehicle" with shape bounding_box and
     radio attribute "Vehicle Type" with options "Car", "Truck", "Bus"

   NESTED ATTRIBUTES (conditional follow-up questions):
   - Radio attribute options can have nested_attributes that appear when that option is selected
   - Use nested attributes when selecting a category should reveal follow-up questions
   - Example: "Email Type" radio with option "Marketing" that has a nested radio
     "Campaign Type" with options "Newsletter", "Promotion", "Product Launch"
   - Checklist options do NOT support nesting
   - Nesting can go multiple levels deep (up to 7)

   Choose the right combination based on the prospect's annotation task. For pure
   text/document classification, use classifications only. For spatial annotation
   tasks, use objects. Many use cases need both. Use nested attributes when the
   labeling task has conditional/hierarchical categories.

3. SYNTHETIC FILES: Generate realistic synthetic .txt files that represent the
   data modality described. Each file should:
   - Have a descriptive filename (snake_case, .txt extension)
   - Contain realistic content (150-400 words) that a human could plausibly annotate
   - Vary across the classification/object options so the demo showcases all labels
   - Include metadata with a 'category' key indicating the ground truth label

4. SUMMARY: A one-sentence description of the demo project.

Be creative but realistic. The synthetic data should feel genuine enough to
demonstrate the labeling workflow to a prospect during a live demo.
"""


def generate_demo_plan(solution_script: str, num_files: int, context: str = "") -> DemoPlan:
    """Parse a solution script and generate a complete demo plan.

    Makes a single Claude API call with structured outputs to produce
    a DemoPlan that can be executed deterministically against the Encord SDK.

    Args:
        solution_script: Raw text of the sales solution script.
        num_files: Number of synthetic files to generate.
        context: Optional additional context to inform the plan.

    Returns:
        A fully populated DemoPlan ready for execution.

    Raises:
        anthropic.APIError: If the Claude API call fails.
        ValueError: If the response cannot be parsed into a DemoPlan.
    """
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    user_message = (
        f"Here is the solution script for a prospect demo:\n\n"
        f"---\n{solution_script}\n---\n\n"
    )
    if context:
        user_message += (
            f"Here is additional context to consider:\n\n"
            f"---\n{context}\n---\n\n"
        )
    user_message += (
        f"Generate a complete demo project plan with exactly "
        f"{num_files} synthetic .txt files."
    )

    response = client.messages.parse(
        model="claude-sonnet-4-6",
        max_tokens=16384,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": user_message,
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


INSTRUCTIONS_SYSTEM_PROMPT = """\
You are an SE coach at Encord (data labeling platform). Write a SHORT demo cheat sheet.

Keep the ENTIRE output under 40 lines. Plain text, no markdown. Use these sections:

CONTEXT (2-3 lines)
Who we're talking to, what they care about.

DEMO FLOW (numbered, 5-7 steps max)
Brief steps: what to show in Encord and why it matters to them.

THINGS TO KEEP IN MIND (3-5 bullets)
Key points to emphasize, pitfalls to avoid, what to highlight.

INDUSTRY/TECHNICAL CONTEXT (3-5 bullets)
Domain-specific knowledge relevant to this client's industry and use case
that would make the SE sound informed during the demo.

Be punchy. No filler.
"""


def generate_demo_instructions(
    plan: DemoPlan, solution_script: str, context: str = ""
) -> str:
    """Generate demo instructions for the SE based on the plan and solution script."""
    client = anthropic.Anthropic()

    plan_summary = plan.model_dump_json(indent=2)

    user_message = (
        f"Here is the original solution script:\n\n"
        f"---\n{solution_script}\n---\n\n"
    )
    if context:
        user_message += (
            f"Additional context:\n\n"
            f"---\n{context}\n---\n\n"
        )
    user_message += (
        f"Here is the demo project plan that was created:\n\n"
        f"---\n{plan_summary}\n---\n\n"
        f"Generate the demo instruction guide for the SE."
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=INSTRUCTIONS_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": user_message,
            }
        ],
    )

    return response.content[0].text
