import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv


def _print_box(title: str, lines: list[str]) -> None:
    """Print a bordered box with a title and content lines."""
    max_width = max(len(title), *(len(line) for line in lines)) + 4
    border = "+" + "-" * (max_width + 2) + "+"

    print(border)
    print(f"| {title:<{max_width}} |")
    print("|" + "-" * (max_width + 2) + "|")
    for line in lines:
        print(f"| {line:<{max_width}} |")
    print(border)


def _print_attribute(attr, indent: int = 4) -> None:
    """Print an attribute and its options, recursing into nested attributes."""
    pad = " " * indent
    print(f"{pad}{attr.name} ({attr.attribute_type})")
    for i, opt in enumerate(attr.options):
        connector = "└─" if i == len(attr.options) - 1 else "├─"
        print(f"{pad}  {connector} {opt.label}")
        for nested in getattr(opt, "nested_attributes", []):
            _print_attribute(nested, indent=indent + 6)


def _print_plan_preview(plan) -> None:
    """Print a rich confirmation preview of the demo plan."""
    # Header
    header_lines = [
        f"Project:   {plan.naming.project_name}",
        f"Dataset:   {plan.naming.dataset_name}",
        f"Ontology:  {plan.naming.ontology_name}",
        f"Files:     {len(plan.synthetic_files)} synthetic .{plan.synthetic_files[0].filename.rsplit('.', 1)[-1] if plan.synthetic_files else 'txt'} files",
        "",
        f"Summary:   {plan.summary}",
    ]
    _print_box("Demo Plan", header_lines)

    # Ontology preview
    print("\nOntology Structure:")
    if plan.objects:
        print("  Objects:")
        for obj in plan.objects:
            print(f"    [{obj.shape}] {obj.name}")
            for attr in obj.attributes:
                _print_attribute(attr, indent=6)
        print()
    if plan.classifications:
        print("  Classifications:")
        for cls in plan.classifications:
            _print_attribute(cls.attribute, indent=4)
        print()

    # Example file preview
    if plan.synthetic_files:
        example = plan.synthetic_files[0]
        print(f"Example file: {example.filename}")
        if example.metadata:
            meta_str = ", ".join(f"{k}={v}" for k, v in example.metadata.items())
            print(f"  Metadata: {meta_str}")
        print("  " + "-" * 60)
        # Show first 15 lines of the example file
        content_lines = example.content.split("\n")
        for line in content_lines[:15]:
            print(f"  {line}")
        if len(content_lines) > 15:
            print(f"  ... ({len(content_lines) - 15} more lines)")
        print("  " + "-" * 60)
        print()


def _read_multiline(prompt: str) -> str:
    """Read multiline input from stdin until an empty line is entered."""
    print(prompt)
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "":
            if lines:  # Only stop on blank line if we have content
                break
            continue  # Skip leading blank lines
        lines.append(line)
    return "\n".join(lines)


def _load_env() -> None:
    """Load environment variables from .env and the ingestion agent's credentials."""
    # Load from local .env first
    load_dotenv()

    # Also try the ingestion agent's credentials as a fallback
    ingestion_creds = Path.home() / "data-ingestion-agent" / ".credentials" / "dev.env"
    if ingestion_creds.exists():
        load_dotenv(ingestion_creds, override=False)


def main() -> None:
    """Interactive CLI entrypoint for the solutions agent."""
    _load_env()

    # --- Validate environment ---
    has_anthropic = "ANTHROPIC_API_KEY" in os.environ
    has_encord = any(
        var in os.environ
        for var in ["ENCORD_SSH_KEY_FILE", "ENCORD_SSH_KEY_PATH", "ENCORD_SSH_KEY"]
    )

    missing = []
    if not has_anthropic:
        missing.append("ANTHROPIC_API_KEY")
    if not has_encord:
        missing.append("ENCORD_SSH_KEY_FILE (or ENCORD_SSH_KEY_PATH or ENCORD_SSH_KEY)")
    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}")
        print("Set them in a .env file, export in your shell,")
        print("or ensure ~/data-ingestion-agent/.credentials/dev.env exists.")
        sys.exit(1)

    # --- Step 1: Gather inputs (hardcoded for demo) ---
    print("=" * 60)
    print("  Encord Solutions Agent - Demo Project Setup")
    print("=" * 60)
    print()

    script_file = Path("script.txt")
    context_file = Path("context.txt")
    num_files = 5
    file_format = "html"

    if not script_file.exists():
        print(f"Error: File not found: {script_file}")
        sys.exit(1)
    solution_script = script_file.read_text()
    if not solution_script.strip():
        print("Error: Empty solution script.")
        sys.exit(1)

    context = context_file.read_text() if context_file.exists() else ""

    print(f"  Script:      {script_file}")
    print(f"  Context:     {context_file}")
    print(f"  Files:       {num_files}")
    print(f"  Format:      {file_format}")
    print()

    # --- Step 2: Generate plan ---
    from .planner import generate_demo_plan

    print("Analyzing solution script and generating demo plan...")
    print("(This may take 15-30 seconds)\n")

    plan = generate_demo_plan(solution_script, num_files, context=context, file_format=file_format)

    # --- Step 3: Rich confirmation preview ---
    _print_plan_preview(plan)

    # --- Step 4: Confirm or regenerate ---
    while True:
        choice = input("Proceed? [Y/n/regenerate]: ").strip().lower()
        if choice in ("", "y", "yes"):
            break
        elif choice in ("n", "no"):
            print("Aborted.")
            sys.exit(0)
        elif choice in ("r", "regenerate"):
            print("\nRegenerating plan...\n")
            plan = generate_demo_plan(solution_script, num_files, context=context, file_format=file_format)
            _print_plan_preview(plan)
        else:
            print("Please enter Y, n, or regenerate.")

    # --- Step 5: Execute ---
    print()
    from .executor import execute_plan

    result = execute_plan(plan, on_status=lambda msg: print(f"  {msg}"))

    # --- Step 6: Generate demo instructions ---
    print()
    from .planner import generate_demo_instructions

    print("  Generating demo instructions...")
    instructions = generate_demo_instructions(plan, solution_script, context)

    # Extract company name from project name (e.g. "Fyxer - Email Sorting Demo" -> "fyxer")
    company = plan.naming.project_name.split(" - ")[0].strip().lower().replace(" ", "-")
    instructions_dir = Path("demo-instructions")
    instructions_dir.mkdir(exist_ok=True)
    instructions_filename = f"{company}-{date.today().isoformat()}.txt"
    instructions_path = instructions_dir / instructions_filename
    instructions_path.write_text(instructions, encoding="utf-8")

    print()
    print("=" * 60)
    print("  Demo project created successfully!")
    print("=" * 60)
    print(f"  Project URL:    {result.project_url}")
    print(f"  Project hash:   {result.project_hash}")
    print(f"  Dataset hash:   {result.dataset_hash}")
    print(f"  Ontology hash:  {result.ontology_hash}")
    print(f"  Files uploaded: {result.files_uploaded}")
    print(f"  Instructions:   {instructions_path}")
    print("=" * 60)
