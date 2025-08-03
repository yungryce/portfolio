from typing import Dict, List, Tuple

def flatten_repo_context_to_natural_language(repo_context: Dict) -> str:
    """
    Converts the repository context bundle (including .repo-context.json, README.md,
    SKILLS-INDEX.md, ARCHITECTURE.md) into a natural-language-like paragraph
    for sentence-transformer embedding and fine-tuning.
    """
    lines = []

    # .repo-context.json (structured)
    identity = repo_context.get("repoContext", {}).get("project_identity", {})
    tech_stack = repo_context.get("repoContext", {}).get("tech_stack", {})
    skills = repo_context.get("repoContext", {}).get("skill_manifest", {})
    outcomes = repo_context.get("repoContext", {}).get("outcomes", {})
    metadata = repo_context.get("repoContext", {}).get("metadata", {})
    assessment = repo_context.get("repoContext", {}).get("assessment", {})

    # Identity block
    name = identity.get('name')
    type_ = identity.get('type')
    scope = identity.get('scope')
    desc = identity.get('description')

    if any([name, type_, scope, desc]):
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

    # Skills
    if skills:
        tech_skills = ", ".join(skills.get("technical", []))
        domain_skills = ", ".join(skills.get("domain", []))
        if tech_skills:
            lines.append(f"Technical skills demonstrated include {tech_skills}.")
        if domain_skills:
            lines.append(f"Domain areas: {domain_skills}.")
        if skills.get('competency_level'):
            lines.append(f"Competency level: {skills.get('competency_level')}.")

    # Outcomes
    if outcomes:
        if (deliverables := outcomes.get("deliverables")):
            lines.append(f"Deliverables include {', '.join(deliverables)}.")
        if (skills_acquired := outcomes.get("skills_acquired")):
            lines.append(f"Skills acquired: {', '.join(skills_acquired)}.")
        if (primary := outcomes.get("primary")):
            lines.append(f"Primary outcomes: {', '.join(primary)}.")

    # Assessment
    if assessment:
        if (diff := assessment.get("difficulty")):
            lines.append(f"Project difficulty is rated as {diff}.")
        if (hours := assessment.get("estimated_hours")):
            lines.append(f"Estimated completion time: {hours} hours.")
        if (criteria := assessment.get("evaluation_criteria")):
            lines.append(f"Success criteria: {', '.join(criteria)}.")

    # Metadata
    if metadata:
        if metadata.get('maintainer'):
            lines.append(f"Maintainer: {metadata.get('maintainer')}.")
        if metadata.get('license'):
            lines.append(f"License: {metadata.get('license')}.")
        if (tags := metadata.get("tags")):
            lines.append(f"Tagged with: {', '.join(tags)}.")

    # README.md
    readme = repo_context.get("readme")
    if readme:
        lines.append("README:")
        lines.append(readme.strip())

    # SKILLS-INDEX.md
    skills_index = repo_context.get("skills_index")
    if skills_index:
        lines.append("Skills Index:")
        lines.append(skills_index.strip())

    # ARCHITECTURE.md
    architecture = repo_context.get("architecture")
    if architecture:
        lines.append("Architecture:")
        lines.append(architecture.strip())

    # If nothing was found, return empty string
    if not lines:
        return ""

    return "\n".join(lines)

def generate_semantic_training_pairs(repo_context: Dict) -> List[Tuple[str, str, float]]:
    """
    Generates (query, context, label) training pairs for semantic model fine-tuning
    using the repository context bundle.
    Returns a list of (query, context, similarity_score) tuples.
    """
    pairs = []

    # Extract relevant fields
    identity = repo_context.get("repoContext", {}).get("project_identity", {})
    tech_stack = repo_context.get("repoContext", {}).get("tech_stack", {})
    skills = repo_context.get("repoContext", {}).get("skill_manifest", {})
    outcomes = repo_context.get("repoContext", {}).get("outcomes", {})
    readme = repo_context.get("readme", "")
    skills_index = repo_context.get("skills_index", "")
    architecture = repo_context.get("architecture", "")

    # 1. Architecture
    if architecture:
        pairs.append((
            "What is the main architecture of this project?",
            architecture,
            1.0
        ))
        if identity.get("name"):
            pairs.append((
                f"Describe the architecture of {identity['name']}.",
                architecture,
                1.0
            ))

    # 2. Skills Index
    if skills_index:
        pairs.append((
            "List the core skills demonstrated in this project.",
            skills_index,
            1.0
        ))
        if identity.get("name"):
            pairs.append((
                f"What skills are shown in {identity['name']}?",
                skills_index,
                1.0
            ))

    # 3. README
    if readme:
        if identity.get("description"):
            pairs.append((
                identity["description"],
                readme,
                1.0
            ))
        pairs.append((
            "Summarize this project.",
            readme,
            1.0
        ))

    # 4. Project Identity
    if identity.get("name") and identity.get("description"):
        pairs.append((
            f"What is {identity['name']}?",
            identity["description"],
            1.0
        ))

    # 5. Tech Stack
    if tech_stack and readme:
        stack_str = ", ".join(tech_stack.get("primary", []))
        if stack_str:
            pairs.append((
                f"Which technologies are used in this project?",
                stack_str,
                1.0
            ))
            pairs.append((
                f"Does this project use {stack_str}?",
                readme,
                0.8
            ))

    # 6. Skills Manifest
    if skills:
        tech_skills = ", ".join(skills.get("technical", []))
        if tech_skills:
            pairs.append((
                "What technical skills are demonstrated?",
                tech_skills,
                1.0
            ))
        domain_skills = ", ".join(skills.get("domain", []))
        if domain_skills:
            pairs.append((
                "What domain skills are demonstrated?",
                domain_skills,
                1.0
            ))

    # 7. Outcomes
    if outcomes:
        deliverables = ", ".join(outcomes.get("deliverables", []))
        if deliverables:
            pairs.append((
                "What are the deliverables of this project?",
                deliverables,
                1.0
            ))
        skills_acquired = ", ".join(outcomes.get("skills_acquired", []))
        if skills_acquired:
            pairs.append((
                "What skills were acquired?",
                skills_acquired,
                1.0
            ))

    # 8. Negative/neutral pairs (optional, for contrastive learning)
    if readme and architecture:
        pairs.append((
            "What is the main architecture of this project?",
            readme,
            0.2
        ))
    if skills_index and readme:
        pairs.append((
            "List the core skills demonstrated in this project.",
            readme,
            0.3
        ))

    return pairs
