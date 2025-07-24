from typing import Dict

def flatten_repo_context_to_natural_language(repo_context: Dict) -> str:
    """
    Converts structured .repo-context.json into a natural-language-like paragraph
    for sentence-transformer embedding.
    """
    lines = []
    identity = repo_context.get("project_identity", {})
    tech_stack = repo_context.get("tech_stack", {})
    skills = repo_context.get("skill_manifest", {})
    outcomes = repo_context.get("outcomes", {})
    metadata = repo_context.get("metadata", {})
    assessment = repo_context.get("assessment", {})

    # Identity block
    name = identity.get('name')
    type_ = identity.get('type')
    scope = identity.get('scope')
    desc = identity.get('description')

    # If all identity fields are missing, and no other context, return empty string
    if not any([name, type_, scope, desc]):
        return ""

    lines.append(f"Project Name: {name}.")
    lines.append(f"Type: {type_}. Scope: {scope}.")
    if desc:
        lines.append(f"Description: {desc}")

    # Tech stack block
    if tech_stack:
        if (primary := tech_stack.get("primary")):
            lines.append(f"Primary technologies include {', '.join(primary)}.")
        if (secondary := tech_stack.get("secondary")):
            lines.append(f"Secondary tools include {', '.join(secondary)}.")
        if (libs := tech_stack.get("key_libraries")):
            lines.append(f"Key libraries: {', '.join(libs)}.")
        if (tools := tech_stack.get("development_tools")):
            lines.append(f"Development tools used: {', '.join(tools)}.")

    # # Skills
    # if skills:
    #     tech_skills = ", ".join(skills.get("technical", []))
    #     domain_skills = ", ".join(skills.get("domain", []))
    #     lines.append(f"Technical skills demonstrated include {tech_skills}.")
    #     lines.append(f"Domain areas: {domain_skills}.")
    #     lines.append(f"Competency level: {skills.get('competency_level')}.")

    # # Outcomes
    # if outcomes:
    #     if (deliverables := outcomes.get("deliverables")):
    #         lines.append(f"Deliverables include {', '.join(deliverables)}.")
    #     if (skills_acquired := outcomes.get("skills_acquired")):
    #         lines.append(f"Skills acquired: {', '.join(skills_acquired)}.")
    #     if (primary := outcomes.get("primary")):
    #         lines.append(f"Primary outcomes: {', '.join(primary)}.")

    # # Assessment
    # if assessment:
    #     if (diff := assessment.get("difficulty")):
    #         lines.append(f"Project difficulty is rated as {diff}.")
    #     if (hours := assessment.get("estimated_hours")):
    #         lines.append(f"Estimated completion time: {hours} hours.")
    #     if (criteria := assessment.get("evaluation_criteria")):
    #         lines.append(f"Success criteria: {', '.join(criteria)}.")

    # # Metadata
    # if metadata:
    #     lines.append(f"Maintainer: {metadata.get('maintainer')}.")
    #     lines.append(f"License: {metadata.get('license')}.")
    #     if (tags := metadata.get("tags")):
    #         lines.append(f"Tagged with: {', '.join(tags)}.")

    return " ".join(lines)
