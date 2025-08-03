---
applyTo: 'ai/semantic_score.py'
---
# Fine-Tuning Sentence Transformers for Portfolio Domain

## Overview
To improve semantic search and matching for portfolio queries, fine-tune a Sentence Transformer model using project-specific documentation and metadata. Use `.repo-context.json`, `README.md`, `SKILLS-INDEX.md`, and `ARCHITECTURE.md` from each repository as the training corpus.

## Workflow

1. **Data Collection**
   - For each repository, collect the following files if present:
     - `.repo-context.json` # Sample: `Samples/repo-context/.repo-context.json`
     - `README.md` # Sample: `Samples/repo-context/README.md`
     - `SKILLS-INDEX.md` # Sample: `Samples/repo-context/SKILLS-INDEX.md`
     - `ARCHITECTURE.md` # Sample: `Samples/repo-context/ARCHITECTURE.md`
   - Use `flatten_repo_context_to_natural_language` to convert repository context into natural language.

2. **Pair Generation**
   - Use `generate_semantic_training_pairs` to create semantic training pairs.

3. **Fine-Tuning**
   - Use `fine_tune_sentence_transformer` to fine-tune the Sentence Transformer model.

4. **Integration**
   - Update `SemanticScorer`, `calculate_repo_scores`, and `process_query_results` to use the fine-tuned model.