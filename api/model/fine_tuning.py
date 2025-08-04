from typing import Tuple, List, Dict
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader
import logging

logger = logging.getLogger('portfolio.api')

class SemanticModel:
    """
    A class to handle semantic scoring using a fine-tuned Sentence Transformer model.
    """
    def __init__(self, model_path: str):
        """
        Initializes the SemanticModel with a pretrained Sentence Transformer model.

        Args:
            model_path (str): Path to the pretrained Sentence Transformer model.
        """
        logger.info(f"Initializing SemanticModel with model path: {model_path}")
        self.model = SentenceTransformer(model_path)
        
    def fine_tune_model(self, training_pairs: List[Tuple[str, str, float]], output_path: str):
        """
        Fine-tunes the Sentence Transformer model using semantic training pairs.

        Args:
            training_pairs (List[Tuple[str, str, float]]): List of (query, context, similarity_score) tuples.
            output_path (str): Path to save the fine-tuned model.
        """
        logger.info(f"Starting fine-tuning process with {len(training_pairs)} training pairs.")
        try:
            # Prepare training data
            train_examples = [InputExample(texts=[pair[0], pair[1]], label=pair[2]) for pair in training_pairs]
            train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=16)

            # Define a loss function
            train_loss = losses.CosineSimilarityLoss(self.model)

            # Fine-tune the model
            self.model.fit(train_objectives=[(train_dataloader, train_loss)], epochs=3, warmup_steps=100)

            # Save the fine-tuned model
            self.model.save(output_path)
            logger.info(f"Fine-tuned model saved to: {output_path}")
        except Exception as e:
            logger.error(f"Error during fine-tuning: {str(e)}", exc_info=True)
        
    def flatten_repo_context_to_natural_language(self, repo_context: Dict) -> str:
        """
        Converts the repository context bundle (including .repo-context.json, README.md,
        SKILLS-INDEX.md, ARCHITECTURE.md) into a natural-language-like paragraph
        for sentence-transformer embedding and fine-tuning.

        Args:
            repo_context (Dict): Repository context bundle.

        Returns:
            str: Flattened natural-language representation of the repository context.
        """
        logger.debug("Flattening repository context into natural language.")
        lines = []

        # Extract structured fields from repo-context.json
        identity = repo_context.get("repoContext", {}).get("project_identity", {})
        tech_stack = repo_context.get("repoContext", {}).get("tech_stack", {})
        skills = repo_context.get("repoContext", {}).get("skill_manifest", {})
        outcomes = repo_context.get("repoContext", {}).get("outcomes", {})
        metadata = repo_context.get("repoContext", {}).get("metadata", {})
        assessment = repo_context.get("repoContext", {}).get("assessment", {})

        # Build natural language representation
        if identity.get('name'):
            lines.append(f"Project Name: {identity['name']}.")
        if identity.get('description'):
            lines.append(f"Description: {identity['description']}.")
        if identity.get('type'):
            lines.append(f"Type: {identity['type']}.")
        if identity.get('scope'):
            lines.append(f"Scope: {identity['scope']}.")

        if tech_stack.get("primary"):
            lines.append(f"Primary technologies include {', '.join(tech_stack['primary'])}.")
        if tech_stack.get("secondary"):
            lines.append(f"Secondary tools include {', '.join(tech_stack['secondary'])}.")
        if tech_stack.get("key_libraries"):
            lines.append(f"Key libraries: {', '.join(tech_stack['key_libraries'])}.")
        if tech_stack.get("development_tools"):
            lines.append(f"Development tools used: {', '.join(tech_stack['development_tools'])}.")

        if skills.get("technical"):
            lines.append(f"Technical skills demonstrated include {', '.join(skills['technical'])}.")
        if skills.get("domain"):
            lines.append(f"Domain-specific knowledge areas: {', '.join(skills['domain'])}.")
        if skills.get("competency_level"):
            lines.append(f"Competency level: {skills['competency_level']}.")

        if outcomes.get("deliverables"):
            lines.append(f"Deliverables include {', '.join(outcomes['deliverables'])}.")
        if outcomes.get("skills_acquired"):
            lines.append(f"Skills acquired: {', '.join(outcomes['skills_acquired'])}.")
        if outcomes.get("primary"):
            lines.append(f"Primary outcomes: {', '.join(outcomes['primary'])}.")

        if assessment.get("difficulty"):
            lines.append(f"Difficulty level: {assessment['difficulty']}.")
        if assessment.get("evaluation_criteria"):
            lines.append(f"Evaluation criteria: {', '.join(assessment['evaluation_criteria'])}.")

        if metadata.get("tags"):
            lines.append(f"Tags: {', '.join(metadata['tags'])}.")
        if metadata.get("maintainer"):
            lines.append(f"Maintainer: {metadata['maintainer']}.")
        if metadata.get("license"):
            lines.append(f"License: {metadata['license']}.")

        # Add README, SKILLS-INDEX, and ARCHITECTURE content
        for key in ["readme", "skills_index", "architecture"]:
            content = repo_context.get(key)
            if content:
                lines.append(f"{key.capitalize()}: {content.strip()}")

        flattened_context = "\n".join(lines)
        logger.debug(f"Flattened context: {flattened_context[:500]}")  # Log first 500 characters
        return flattened_context

    def generate_semantic_training_pairs(self, repo_context: Dict) -> List[Tuple[str, str, float]]:
        """
        Generates (query, context, label) training pairs for semantic model fine-tuning
        using the repository context bundle.

        Args:
            repo_context (Dict): Repository context bundle.

        Returns:
            List[Tuple[str, str, float]]: List of (query, context, similarity_score) tuples.
        """
        logger.debug("Generating semantic training pairs from repository context.")
        pairs = []

        # Extract relevant fields
        identity = repo_context.get("repoContext", {}).get("project_identity", {})
        tech_stack = repo_context.get("repoContext", {}).get("tech_stack", {})
        skills = repo_context.get("repoContext", {}).get("skill_manifest", {})
        outcomes = repo_context.get("repoContext", {}).get("outcomes", {})
        readme = repo_context.get("readme", "")
        skills_index = repo_context.get("skills_index", "")
        architecture = repo_context.get("architecture", "")

        # Generate pairs based on schema fields
        if identity.get("name"):
            pairs.append((f"What is {identity['name']}?", identity.get("description", ""), 1.0))
        if identity.get("description"):
            pairs.append(("Summarize this project.", identity["description"], 1.0))

        if tech_stack.get("primary"):
            pairs.append(("Which technologies are used in this project?", ", ".join(tech_stack["primary"]), 1.0))
        if tech_stack.get("secondary"):
            pairs.append(("What supporting tools are used?", ", ".join(tech_stack["secondary"]), 0.8))

        if skills.get("technical"):
            pairs.append(("What technical skills are demonstrated?", ", ".join(skills["technical"]), 1.0))
        if skills.get("domain"):
            pairs.append(("What domain-specific knowledge areas are covered?", ", ".join(skills["domain"]), 1.0))

        if outcomes.get("deliverables"):
            pairs.append(("What are the deliverables of this project?", ", ".join(outcomes["deliverables"]), 1.0))
        if outcomes.get("skills_acquired"):
            pairs.append(("What skills were acquired?", ", ".join(outcomes["skills_acquired"]), 1.0))

        # Include README, SKILLS-INDEX, and ARCHITECTURE content
        if readme:
            pairs.append(("Summarize the README content.", readme, 1.0))
        if skills_index:
            pairs.append(("List the core skills demonstrated in this project.", skills_index, 1.0))
        if architecture:
            pairs.append(("Describe the architecture of this project.", architecture, 1.0))

        logger.debug(f"Generated {len(pairs)} training pairs.")
        return pairs