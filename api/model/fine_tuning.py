from typing import Tuple, List, Dict, Any, Optional
from github.cache_client import GitHubCache
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader
import logging
import os
import tempfile
import zipfile
import shutil
from azure.storage.blob import BlobServiceClient, ContentSettings

logger = logging.getLogger('portfolio.api')

class SemanticModel:
    """
    A class to handle semantic scoring using a fine-tuned Sentence Transformer model.
    """
    def __init__(self):
        """
        Initializes the SemanticModel with a pretrained Sentence Transformer model.

        Args:
            model_path (str): Path to the pretrained Sentence Transformer model.
        """
        logger.info(f"Initializing SemanticModel")
        self.model = None
        self.cache_client = GitHubCache(use_cache=True)

    def _ensure_base_model(self):
        """
        Lazily loads the base sentence transformer if not already loaded.
        """
        if self.model is None:
            try:
                logger.info("Loading base sentence transformer model (all-MiniLM-L6-v2)")
                self.model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception as e:
                logger.error(f"Failed to load base model: {e}", exc_info=True)
                self.model = None

    def get_model(self) -> SentenceTransformer:
        """
        Returns the current model (tuned or base). If no model is loaded, initializes the base model.
        
        Returns:
            SentenceTransformer: The current model instance.
        """
        if self.model is None:
            self._ensure_base_model()
        return self.model
    
    def _generate_repo_fingerprint(self, repos_bundle: List[Dict]) -> str:
        """
        Generates a unique fingerprint of repositories to determine if retraining is needed.
        
        Args:
            repos_bundle: List of repository context bundles
            
        Returns:
            str: SHA-256 hash representing the current state of repositories
        """
        import hashlib
        import json
        
        # Extract essential data for fingerprinting
        fingerprint_data = []
        for repo in repos_bundle:
            if not repo.get("has_documentation", False):
                continue
                
            # Include repo name, last modified, and other key metadata
            repo_data = {
                "name": repo.get("name", ""),
                "last_modified": repo.get("last_updated", ""),
                # Include hashes of key content fields to detect changes
                "readme_hash": hashlib.sha256(repo.get("readme", "").encode()).hexdigest()[:16],
                "skills_hash": hashlib.sha256(repo.get("skills_index", "").encode()).hexdigest()[:16],
                "arch_hash": hashlib.sha256(repo.get("architecture", "").encode()).hexdigest()[:16]
            }
            fingerprint_data.append(repo_data)
        
        # Sort to ensure consistent order
        fingerprint_data.sort(key=lambda x: x["name"])
        
        # Generate hash from the serialized data
        fingerprint_str = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()
        
    def ensure_model_ready(self, all_repos_bundle: List[Dict]) -> bool:
        """
        Ensures a fine-tuned model is ready for use. Checks cache first, loads existing model,
        or trains a new one if necessary.
        
        Args:
            all_repos_bundle: List of repository contexts for training if needed
            cache_client: Cache client for model metadata storage

        Returns:
            bool: True if model is ready for use, False otherwise
        """
        import datetime

        # Filter documented repositories
        documented_repos = [repo for repo in all_repos_bundle if repo.get("has_documentation", False)]
        if not documented_repos:
            logger.warning("No documented repositories available for training. Using base model.")
            return False
    
        # Generate fingerprint of current repositories
        fingerprint = self._generate_repo_fingerprint(documented_repos)
        logger.info(f"Generated repository fingerprint: {fingerprint[:8]}...")
        
        # Check local disk cache first
        local_cache_dir = os.path.join(tempfile.gettempdir(), "semantic_models")
        local_model_path = os.path.join(local_cache_dir, f"model_{fingerprint}")
        
        if os.path.exists(local_model_path):
            try:
                logger.info(f"Found matching model in local disk cache: {fingerprint[:8]}")
                self.model = SentenceTransformer(local_model_path)
                return True
            except Exception as e:
                logger.warning(f"Failed to load model from disk cache: {str(e)}")

        cache_key = "fine_tuned_model_metadata"
        cache_result = self.cache_client._get_from_cache(cache_key)

        if cache_result['status'] == 'valid':
            model_metadata = cache_result['data']

            # Check if we have a model matching the current fingerprint
            if model_metadata.get("fingerprint") == fingerprint:
                logger.info("Found model with matching repository fingerprint")
                
                load_success = self.load_model_from_storage(model_metadata, local_cache_dir)
                if load_success:
                    return True

        
        # No matching model found - train new model
        logger.info(f"No model found with matching fingerprint. Training with {len(documented_repos)} repositories")

        # Train model using the documented repositories
        model_path = f"model_{fingerprint}"
        success = self.train_from_repositories(documented_repos, model_path, local_cache_dir)
        
        # Save model metadata to cache if training was successful
        if success:
            model_info = {
                "storage_type": "blob",
                "container": "ai-models",
                "blob_name": f"{model_path}.zip",
                "fingerprint": fingerprint,
                "training_timestamp": datetime.datetime.now().isoformat(),
                "training_repos_count": len(documented_repos),
                "repo_names": [repo.get("name", "Unknown") for repo in documented_repos]
            }
            
            self.cache_client._save_to_cache(
                cache_key, 
                model_metadata,
                ttl=None  # No expiration - models valid until repos change
            )
            logger.info("Fine-tuned model metadata saved to cache.")
            return True

        return False

    def load_model_from_storage(self, model_info: Dict[str, Any], local_cache_dir: Optional[str] = None) -> bool:
        """
        Loads a fine-tuned model from Azure Blob Storage.
        
        Args:
            model_info: Dictionary containing model storage information
            
        Returns:
            bool: True if model was successfully loaded, False otherwise
        """        
        try:
            # Extract model storage information
            container = model_info.get("container", "ai-models")
            blob_name = model_info.get("blob_name")
            fingerprint = model_info.get("fingerprint", "")
            
            if not blob_name:
                logger.error("Missing blob_name in model_info")
                return False
            
            # Check if we already have this model in local cache
            if local_cache_dir and fingerprint:
                local_model_path = os.path.join(local_cache_dir, f"model_{fingerprint}")
                if os.path.exists(local_model_path):
                    try:
                        logger.info(f"Loading model from local cache: {local_model_path}")
                        self.model = SentenceTransformer(local_model_path)
                        return True
                    except Exception as local_e:
                        logger.warning(f"Failed to load from local cache: {str(local_e)}")
            
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

            # Save to local cache if requested
            if local_cache_dir and fingerprint:
                os.makedirs(local_cache_dir, exist_ok=True)
                local_model_path = os.path.join(local_cache_dir, f"model_{fingerprint}")
                
                # Copy model files to local cache
                if os.path.exists(local_model_path):
                    shutil.rmtree(local_model_path)
                shutil.copytree(model_dir, local_model_path)
                logger.info(f"Model saved to local cache: {local_model_path}")
        
            # Cleanup temporary files
            shutil.rmtree(temp_dir)
            logger.info(f"Successfully loaded model from {container}/{blob_name}")
            
            return True
        except Exception as e:
            logger.error(f"Error loading model from storage: {str(e)}", exc_info=True)
            return False        
        
    def train_from_repositories(self, repos_bundle: List[Dict], output_path: str, local_cache_dir: Optional[str] = None) -> bool:
        """
        Trains a semantic model using a list of repository contexts and persists it to Azure Blob Storage.
        
        Args:
            repos_bundle (List[Dict]): List of repository context bundles
            output_path (str): Path identifier for the model (used for both temp storage and blob name)
        
        Returns:
            bool: True if training was successful, False otherwise
        """
        logger.info(f"Training semantic model from {len(repos_bundle)} repositories")
        
        # Generate training pairs from all repositories
        training_pairs = []
        for repo_bundle in repos_bundle:
            repo_name = repo_bundle.get('name', 'Unknown')
            logger.debug(f"Generating training pairs for repository: {repo_name}")
            try:
                pairs = self.generate_semantic_training_pairs(repo_bundle)
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
            training_success = self.fine_tune_model(training_pairs, temp_model_path)
            if not training_success:
                logger.error("Fine-tuning failed.")
                return False
            
            # Load the trained model into self.model
            self.model = SentenceTransformer(temp_model_path)
            logger.info("Trained model loaded into memory for immediate use.")
            
            # After successful training, save to local cache if requested
            if local_cache_dir:
                os.makedirs(local_cache_dir, exist_ok=True)
                local_model_path = os.path.join(local_cache_dir, output_path)
                
                if os.path.exists(local_model_path):
                    shutil.rmtree(local_model_path)
                shutil.copytree(temp_model_path, local_model_path)
                logger.info(f"Model saved to local cache: {local_model_path}")
            
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
                            
            # Cleanup temporary files
            shutil.rmtree(temp_dir)
            logger.info(f"Model uploaded to Azure Blob Storage: container={container_name}, blob={blob_name}")
            
            return True
        except Exception as e:
            logger.error(f"Error during model training and storage: {str(e)}", exc_info=True)
            return False
        
    def fine_tune_model(self, training_pairs: List[Tuple[str, str, float]], output_path: str):
        """
        Fine-tunes the Sentence Transformer model using semantic training pairs.

        Args:
            training_pairs (List[Tuple[str, str, float]]): List of (query, context, similarity_score) tuples.
            output_path (str): Path to save the fine-tuned model.
        """
        logger.info(f"Starting fine-tuning process with {len(training_pairs)} training pairs.")

        self._ensure_base_model()
        if self.model is None:
            logger.error("Cannot fine-tune: base model failed to load.")
            return False

        if not training_pairs:
            logger.warning("No training pairs provided; skipping fine-tune.")
            return False

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
            return True
        except Exception as e:
            logger.error(f"Error during fine-tuning: {str(e)}", exc_info=True)
            return False

    def generate_semantic_training_pairs(self, repo_bundle: Dict) -> List[Tuple[str, str, float]]:
        """
        Generates (query, context, label) training pairs for semantic model fine-tuning
        using the repository context bundle.

        Args:
            repo_bundle (Dict): Repository context bundle.

        Returns:
            List[Tuple[str, str, float]]: List of (query, context, similarity_score) tuples.
        """
        logger.debug("Generating semantic training pairs from repository context.")
        pairs = []

        # Extract relevant fields
        identity = repo_bundle.get("repoContext", {}).get("project_identity", {})
        tech_stack = repo_bundle.get("repoContext", {}).get("tech_stack", {})
        skills = repo_bundle.get("repoContext", {}).get("skill_manifest", {})
        outcomes = repo_bundle.get("repoContext", {}).get("outcomes", {})
        readme = repo_bundle.get("readme", "")
        skills_index = repo_bundle.get("skills_index", "")
        architecture = repo_bundle.get("architecture", "")

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