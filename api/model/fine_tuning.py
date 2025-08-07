from typing import Tuple, List, Dict, Any
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
        
    def load_model_from_storage(self, model_info: Dict[str, Any]) -> bool:
        """
        Loads a fine-tuned model from Azure Blob Storage.
        
        Args:
            model_info: Dictionary containing model storage information
            
        Returns:
            bool: True if model was successfully loaded, False otherwise
        """
        import tempfile
        import zipfile
        import os
        import shutil
        from azure.storage.blob import BlobServiceClient
        
        try:
            # Extract model storage information
            container = model_info.get("container", "ai-models")
            blob_name = model_info.get("blob_name")
            
            if not blob_name:
                logger.error("Missing blob_name in model_info")
                return False
            
            # Download model from Azure Blob Storage
            connection_string = os.getenv('AzureWebJobsStorage')
            if not connection_string:
                logger.error("AzureWebJobsStorage connection string not found")
                return False
                
            blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            container_client = blob_service_client.get_container_client(container)
            blob_client = container_client.get_blob_client(blob_name)
            
            # Create a temporary directory to extract the model
            temp_dir = tempfile.mkdtemp()
            zip_path = os.path.join(temp_dir, "model.zip")
            
            # Download the blob
            with open(zip_path, "wb") as download_file:
                download_file.write(blob_client.download_blob().readall())
            
            # Extract the zip file
            model_dir = os.path.join(temp_dir, "model")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(model_dir)
            
            # Load the model
            self.model = SentenceTransformer(model_dir)
            logger.info(f"Successfully loaded model from {container}/{blob_name}")
            
            # Cleanup temporary files
            shutil.rmtree(temp_dir)
            
            return True
        except Exception as e:
            logger.error(f"Error loading model from storage: {str(e)}", exc_info=True)
            return False
        
    def train_from_repositories(self, repo_contexts: List[Dict], output_path: str) -> bool:
        """
        Trains a semantic model using a list of repository contexts and persists it to Azure Blob Storage.
        
        Args:
            repo_contexts (List[Dict]): List of repository context bundles
            output_path (str): Path identifier for the model (used for both temp storage and blob name)
        
        Returns:
            bool: True if training was successful, False otherwise
        """
        import uuid
        import zipfile
        import tempfile
        import os
        from azure.storage.blob import BlobServiceClient, ContentSettings
        
        logger.info(f"Training semantic model from {len(repo_contexts)} repositories")
        
        # Generate training pairs from all repositories
        training_pairs = []
        for repo_context in repo_contexts:
            repo_name = repo_context.get('name', 'Unknown')
            logger.debug(f"Generating training pairs for repository: {repo_name}")
            try:
                pairs = self.generate_semantic_training_pairs(repo_context)
                training_pairs.extend(pairs)
                logger.debug(f"Generated {len(pairs)} training pairs for {repo_name}")
            except Exception as e:
                logger.error(f"Error generating training pairs for {repo_name}: {str(e)}")
                continue
        
        # Fine-tune the model if we have training pairs
        if not training_pairs:
            logger.warning("No training pairs generated, skipping fine-tuning")
            return False
        
        try:
            # Create a temporary directory for the model
            temp_dir = tempfile.mkdtemp()
            temp_model_path = os.path.join(temp_dir, "model")
            
            # Fine-tune the model and save to temp location
            self.fine_tune_model(training_pairs, temp_model_path)
            logger.info(f"Successfully trained model with {len(training_pairs)} pairs to temporary location")
            
            # Create a zip file of the model
            model_id = os.path.basename(output_path)
            zip_path = os.path.join(temp_dir, f"{model_id}.zip")
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(temp_model_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_model_path)
                        zipf.write(file_path, arcname)
            
            # Upload zip to Azure Blob Storage
            connection_string = os.getenv('AzureWebJobsStorage')
            if not connection_string:
                logger.error("AzureWebJobsStorage connection string not found")
                return False
                
            blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            
            # Use a dedicated container for models
            container_name = "ai-models"
            container_client = blob_service_client.get_container_client(container_name)
            
            # Create container if it doesn't exist
            try:
                container_client.create_container()
                logger.info(f"Created models container: {container_name}")
            except Exception as e:
                if "ContainerAlreadyExists" not in str(e):
                    logger.warning(f"Container creation issue: {str(e)}")
            
            # Upload the model zip file to blob storage
            blob_name = f"{model_id}.zip"
            blob_client = container_client.get_blob_client(blob_name)
            
            with open(zip_path, "rb") as data:
                blob_client.upload_blob(
                    data, 
                    overwrite=True,
                    content_settings=ContentSettings(
                        content_type='application/zip',
                        content_encoding='utf-8'
                    )
                )
                
            logger.info(f"Model uploaded to Azure Blob Storage: container={container_name}, blob={blob_name}")
            
            # Cleanup temporary files
            import shutil
            shutil.rmtree(temp_dir)
            
            return True
        except Exception as e:
            logger.error(f"Error during model training and storage: {str(e)}", exc_info=True)
            return False