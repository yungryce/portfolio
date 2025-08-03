from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader

def fine_tune_sentence_transformer(training_pairs: List[Tuple[str, str, float]], model_path: str, output_path: str):
    """
    Fine-tunes a Sentence Transformer model using semantic training pairs.

    Args:
        training_pairs (List[Tuple[str, str, float]]): List of (query, context, similarity_score) tuples.
        model_path (str): Path to the pretrained Sentence Transformer model.
        output_path (str): Path to save the fine-tuned model.
    """
    # Load the base model
    model = SentenceTransformer(model_path)

    # Prepare training data
    train_examples = [InputExample(texts=[pair[0], pair[1]], label=pair[2]) for pair in training_pairs]
    train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=16)

    # Define a loss function
    train_loss = losses.CosineSimilarityLoss(model)

    # Fine-tune the model
    model.fit(train_objectives=[(train_dataloader, train_loss)], epochs=3, warmup_steps=100)

    # Save the fine-tuned model
    model.save(output_path)