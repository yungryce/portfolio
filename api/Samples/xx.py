def ensure_model_ready(self, all_repos_bundle: List[Dict], train_if_missing: bool = True, training_params: Dict = None) -> bool:
    """
    Ensures a fine-tuned model is ready for use. Checks cache first, loads existing model,
    or trains a new one if necessary and if train_if_missing is True.
    
    Args:
        all_repos_bundle: List of repository bundles
        train_if_missing: If True, train a new model when none exists; if False, just load existing
        training_params: Dictionary of parameters to customize training behavior
        
    Returns:
        bool: True if a fine-tuned model is ready, False otherwise
    """
    # Filter documented repositories
    documented_repos = [repo for repo in all_repos_bundle if repo.get("has_documentation", False)]
    if not documented_repos:
        logger.warning("No documented repositories available for training. Using base model.")
        # Still ensure base model and fit whitener from whatever we have
        self._ensure_base_model()
        corpus = [self._flatten_repo_bundle_for_training(rb) for rb in all_repos_bundle if rb]
        self._fit_embedding_whitener([c for c in corpus if c])
        return False

    # Generate fingerprint of current repositories
    fingerprint = FingerprintManager.generate_content_fingerprint(documented_repos)
    logger.info(f"Generated repository fingerprint: {fingerprint[:8]}...")
    
    # Check local disk cache first
    local_cache_dir = os.path.join(tempfile.gettempdir(), "semantic_models")
    local_model_path = os.path.join(local_cache_dir, f"model_{fingerprint}")
    
    if os.path.exists(local_model_path):
        try:
            logger.info(f"Found matching model in local disk cache: {fingerprint[:8]}")
            self.model = SentenceTransformer(local_model_path)
            # Fit whitening on current documented contexts
            corpus = [self._flatten_repo_bundle_for_training(rb) for rb in documented_repos if rb]
            self._fit_embedding_whitener([c for c in corpus if c])
            return True
        except Exception as e:
            logger.warning(f"Failed to load model from disk cache: {str(e)}")

    # Check global cache for the model metadata
    cache_key = cache_manager.generate_cache_key(kind='model', fingerprint=None)
    cache_result = cache_manager.get(cache_key)

    if cache_result['status'] == 'valid' and cache_result['data']:
        model_metadata = cache_result['data']

        # Check if we have a model matching the current fingerprint
        if model_metadata.get("fingerprint") == fingerprint:
            logger.info("Found model with matching repository fingerprint")
            
            load_success = self.load_model_from_storage(model_metadata, local_cache_dir)
            if load_success:
                corpus = [self._flatten_repo_bundle_for_training(rb) for rb in documented_repos if rb]
                self._fit_embedding_whitener([c for c in corpus if c])
                return True
    
    # No matching model found
    if not train_if_missing:
        logger.info("No matching model found and train_if_missing=False. Using base model.")
        self._ensure_base_model()
        corpus = [self._flatten_repo_bundle_for_training(rb) for rb in all_repos_bundle if rb]
        self._fit_embedding_whitener([c for c in corpus if c])
        return False
        
    # Train new model
    logger.info(f"No model found with matching fingerprint. Training with {len(documented_repos)} repositories")

    # Train model using the documented repositories
    model_path = f"model_{fingerprint}"
    success = self.train_from_repositories(documented_repos, model_path, local_cache_dir, training_params)
    if success:
        # Fit whitening on documented contexts after training
        corpus = [self._flatten_repo_bundle_for_training(rb) for rb in documented_repos if rb]
        self._fit_embedding_whitener([c for c in corpus if c])
        
        # Save model metadata to cache if training was successful
        model_info = {
            "storage_type": "blob",
            "container": cache_manager.container_name,
            "blob_name": f"{model_path}.zip",
            "fingerprint": fingerprint,
            "training_timestamp": datetime.datetime.now().isoformat(),
            "training_repos_count": len(documented_repos),
            "repo_names": [repo.get("name", "Unknown") for repo in documented_repos]
        }
        
        cache_manager.save(
            cache_key, 
            model_info,
            ttl=None,  # No expiration - models valid until repos change
            fingerprint=fingerprint
        )
        logger.info("Fine-tuned model metadata saved to cache.")
        return True
    return False


def train_from_repositories(self, repos_bundle: List[Dict], output_path: str, 
                           local_cache_dir: Optional[str] = None,
                           training_params: Dict = None) -> bool:
    """
    Trains a semantic model using a list of repository contexts and persists it to Azure Blob Storage.
    Now includes fallback to embedding whitening if fine-tuning fails.
    
    Args:
        repos_bundle: List of repository bundles with context
        output_path: Path where the model should be saved
        local_cache_dir: Directory for local caching
        training_params: Dictionary of parameters to customize training behavior
        
    Returns:
        bool: True if training succeeded, False otherwise
    """
    logger.info(f"Training semantic model from {len(repos_bundle)} repositories")
    
    # Default training parameters
    params = {
        'batch_size': 8,
        'max_pairs': 150,
        'epochs': 2,
        'warmup_steps': 50,
        'use_mnrl': True
    }
    
    # Update with custom parameters if provided
    if training_params:
        params.update(training_params)
    
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
        training_success = self.fine_tune_model(
            training_pairs, 
            temp_model_path, 
            use_mnrl=params['use_mnrl'],
            batch_size=params['batch_size'],
            max_pairs=params['max_pairs'],
            epochs=params['epochs'],
            warmup_steps=params['warmup_steps']
        )
        
        if not training_success:
            logger.warning("Fine-tuning failed. Falling back to base model with whitening only.")
            # Ensure base model is loaded
            self._ensure_base_model()
            
            # Save base model to the temp location
            self.model.save(temp_model_path)
            
            # Load corpus for whitening
            corpus = []
            for repo_bundle in repos_bundle:
                context = self._flatten_repo_bundle_for_training(repo_bundle)
                if context:
                    corpus.append(context)
            
            # Apply whitening to improve base model embeddings
            self._fit_embedding_whitener(corpus)
        else:
            # Load the trained model into self.model for immediate use
            self.model = SentenceTransformer(temp_model_path)
            logger.info("Trained model loaded into memory for immediate use.")
            
        # After training (successful or fallback), save to local cache if requested
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
    
        # Upload zip to Azure Blob Storage using the same blob service client as cache_manager
        if not cache_manager.blob_service_client:
            logger.error("Blob service client not available")
            return False
            
        # Use the standard github-cache container
        container_name = cache_manager.container_name
        blob_name = f"{model_id}.zip"
        
        # Check if container exists and create if needed
        try:
            container_client = cache_manager.blob_service_client.get_container_client(container_name)
            if not container_client.exists():
                logger.info(f"Container {container_name} does not exist, creating it...")
                cache_manager.blob_service_client.create_container(container_name)
                logger.info(f"Container {container_name} created successfully")
        except Exception as e:
            logger.error(f"Error checking/creating container {container_name}: {e}")
            return False
            
        blob_client = cache_manager.blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_name
        )
        
        # Upload the model to blob storage
        with open(zip_path, "rb") as data:
            try:
                blob_client.upload_blob(
                    data, 
                    overwrite=True,
                    content_settings=ContentSettings(
                        content_type='application/zip',
                        content_encoding='utf-8'
                    )
                )
                logger.info(f"Model uploaded to Azure Blob Storage: container={container_name}, blob={blob_name}")
            except Exception as e:
                logger.error(f"Failed to upload model to blob storage: {e}", exc_info=True)
                return False
                    
        # Cleanup temporary files 
        shutil.rmtree(temp_dir)
        return True
    except Exception as e:
        logger.error(f"Error during model training and storage: {str(e)}", exc_info=True)
        return False
    
    
def fine_tune_model(self, training_pairs: List[Tuple[str, str, float]], output_path: str, 
                   use_mnrl: bool = True, batch_size: int = 8, max_pairs: int = 150,
                   epochs: int = 2, warmup_steps: int = 50):
    """
    Fine-tunes the Sentence Transformer model with memory-optimized settings.
    
    Args:
        training_pairs: List of (query, context, score) training examples
        output_path: Path to save the trained model
        use_mnrl: Whether to use MultipleNegativesRankingLoss (vs CosineSimilarityLoss)
        batch_size: Batch size for training
        max_pairs: Maximum number of training pairs to use (prevents OOM errors)
        epochs: Number of training epochs
        warmup_steps: Number of warmup steps
        
    Returns:
        bool: True if training succeeded, False otherwise
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
        # Memory optimizations
        show_progress_bar = False  # Disable progress bar to save memory
        
        if use_mnrl:
            # Keep only strong positives; in-batch acts as negatives
            pos_pairs = [(q, c) for (q, c, y) in training_pairs if y >= 0.8]
            if not pos_pairs:
                logger.warning("No positive pairs for MNRL; falling back to cosine loss.")
                return self.fine_tune_model(
                    training_pairs, output_path, use_mnrl=False,
                    batch_size=batch_size, max_pairs=max_pairs,
                    epochs=epochs, warmup_steps=warmup_steps
                )
                
            # Sample if too many pairs (optional)
            if len(pos_pairs) > max_pairs:
                import random
                random.seed(42)
                pos_pairs = random.sample(pos_pairs, max_pairs)
                logger.info(f"Sampled training pairs to {max_pairs} to reduce memory usage")
                
            train_examples = [InputExample(texts=[q, c]) for (q, c) in pos_pairs]
            train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=batch_size)
            train_loss = losses.MultipleNegativesRankingLoss(self.model)
        else:
            # Sample if too many pairs (optional)
            if len(training_pairs) > max_pairs:
                import random
                random.seed(42)
                training_pairs = random.sample(training_pairs, max_pairs)
                logger.info(f"Sampled training pairs to {max_pairs} to reduce memory usage")
                
            train_examples = [InputExample(texts=[q, c], label=y) for (q, c, y) in training_pairs]
            train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=batch_size)
            train_loss = losses.CosineSimilarityLoss(self.model)

        # Lower epochs and add garbage collection
        import gc
        self.model.fit(
            train_objectives=[(train_dataloader, train_loss)], 
            epochs=epochs,
            warmup_steps=warmup_steps,
            show_progress_bar=show_progress_bar
        )
        gc.collect()  # Force garbage collection
        
        self.model.save(output_path)
        return True
    except Exception as e:
        logger.error(f"Error during fine-tuning: {str(e)}", exc_info=True)
        return False