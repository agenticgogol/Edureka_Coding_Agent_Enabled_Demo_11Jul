#!/usr/bin/env python3
"""Validate Coding_Agent_Enabled_Demo/projects, /concepts, and /teaching folders.

Checks, per unit:
- projects/<slug>/: project_brief.md, design.md, plan.md, README.md exist;
  at least one of frontend/ or backend/ exists (unless brief is notebook-only);
  plan.md references run-tests, integrate-and-assemble, run-and-verify.
- concepts/<slug>/: concept_brief.md, design.md, plan.md, README.md exist;
  notebook.ipynb or app.py exists; same plan.md checks as projects.
- teaching/<slug>/ (lightweight track, no design.md/plan.md required):
  teaching_brief.md, README.md exist; notebook.ipynb, app.py, or steps/
  exists.
- No obvious TODO placeholders in brief/design/plan.

Exits non-zero with a printed report if anything fails.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"
CONCEPTS = ROOT / "concepts"
TEACHING = ROOT / "teaching"

TODO_MARKERS = ("TODO", "TBD", "FIXME", "XXX")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def check_no_placeholders(path: Path, errors: list[str]) -> None:
    text = read(path)
    for marker in TODO_MARKERS:
        if marker in text:
            errors.append(f"{path}: contains placeholder marker '{marker}'")


def validate_unit(unit_dir: Path, brief_name: str, code_options: list[str]) -> list[str]:
    """Full pipeline check — used for projects/ and concepts/."""
    errors: list[str] = []
    slug = unit_dir.name

    brief = unit_dir / brief_name
    design = unit_dir / "design.md"
    plan = unit_dir / "plan.md"
    readme = unit_dir / "README.md"

    for required in (brief, design, plan, readme):
        if not required.exists():
            errors.append(f"{slug}: missing required file {required.relative_to(ROOT)}")

    if plan.exists():
        plan_text = read(plan)
        if "integrate-and-assemble" not in plan_text:
            errors.append(f"{slug}: plan.md does not reference integrate-and-assemble")
        if "run-and-verify" not in plan_text:
            errors.append(f"{slug}: plan.md does not reference run-and-verify")
        if "run-tests" not in plan_text:
            errors.append(f"{slug}: plan.md does not reference run-tests")

    for f in (brief, design, plan):
        check_no_placeholders(f, errors)

    if code_options and not any((unit_dir / opt).exists() for opt in code_options):
        errors.append(
            f"{slug}: none of the expected code paths exist ({', '.join(code_options)})"
        )

    return errors


def validate_teaching_unit(unit_dir: Path) -> list[str]:
    """Lightweight check — teaching/ has no design.md/plan.md requirement."""
    errors: list[str] = []
    slug = unit_dir.name

    brief = unit_dir / "teaching_brief.md"
    readme = unit_dir / "README.md"

    for required in (brief, readme):
        if not required.exists():
            errors.append(f"{slug}: missing required file {required.relative_to(ROOT)}")

    check_no_placeholders(brief, errors)

    code_options = ["notebook.ipynb", "app.py", "steps"]
    if not any((unit_dir / opt).exists() for opt in code_options):
        errors.append(
            f"{slug}: none of the expected teaching artifacts exist ({', '.join(code_options)})"
        )

    return errors


def main() -> int:
    all_errors: list[str] = []

    if PROJECTS.exists():
        for unit_dir in sorted(p for p in PROJECTS.iterdir() if p.is_dir()):
            all_errors.extend(
                validate_unit(unit_dir, "project_brief.md", ["frontend", "backend", "notebook.ipynb"])
            )

    if CONCEPTS.exists():
        for unit_dir in sorted(p for p in CONCEPTS.iterdir() if p.is_dir()):
            all_errors.extend(
                validate_unit(unit_dir, "concept_brief.md", ["notebook.ipynb", "app.py"])
            )

    if TEACHING.exists():
        for unit_dir in sorted(p for p in TEACHING.iterdir() if p.is_dir()):
            all_errors.extend(validate_teaching_unit(unit_dir))

    if not PROJECTS.exists() and not CONCEPTS.exists() and not TEACHING.exists():
        print("No projects/, concepts/, or teaching/ directories found — nothing to validate.")
        return 0

    project_count = len([p for p in PROJECTS.iterdir() if p.is_dir()]) if PROJECTS.exists() else 0
    concept_count = len([p for p in CONCEPTS.iterdir() if p.is_dir()]) if CONCEPTS.exists() else 0
    teaching_count = len([p for p in TEACHING.iterdir() if p.is_dir()]) if TEACHING.exists() else 0

    if project_count == 0 and concept_count == 0 and teaching_count == 0:
        print("No project, concept, or teaching folders yet — nothing to validate.")
        return 0

    if all_errors:
        print(f"FAILED — {len(all_errors)} issue(s) found:\n")
        for e in all_errors:
            print(f"  - {e}")
        return 1

    print(
        f"OK — {project_count} project(s), {concept_count} concept(s), "
        f"{teaching_count} teaching demo(s) validated, no issues."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
