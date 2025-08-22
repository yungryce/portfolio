# ChatGpt
@app.route(route="orchestrators/repo_context_orchestrator", methods=["POST"])
@app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client) -> func.HttpResponse:
    """
    Endpoint for both user requests and GitHub webhook push events.
    Triggers repo_context_orchestrator Durable Function.
    """
    logger.info("Received request to start repo_context_orchestrator")
    try:
        request_body = req.get_json() or {}

        # Detect GitHub webhook vs user request
        if "repository" in request_body:
            # GitHub webhook payload
            username = request_body["repository"]["owner"]["login"]
            repo_name = request_body["repository"]["name"]
            logger.info(f"Webhook triggered by push to {username}/{repo_name}")
            force_refresh = True  # Always force refresh on push
        else:
            # Normal user request
            username = request_body.get("username", "yungryce")
            force_refresh = request_body.get("force_refresh", False)

        # (Keep the rest of your cache-check logic unchanged...)

        # Start orchestration
        instance_id = await client.start_new("repo_context_orchestrator", None, username)
        logger.info(f"Started repo_context_orchestrator for {username}, instance ID: {instance_id}")

        response = client.create_check_status_response(req, instance_id)
        return response

    except Exception as e:
        logger.error(f"Error starting repo_context_orchestrator: {str(e)}")
        return create_error_response(f"Failed to start orchestration: {str(e)}", 500)

# # GitHub Webhook Payload:
# {
#   "ref": "refs/heads/main",
#   "repository": {
#     "id": 123456,
#     "name": "my-repo",
#     "full_name": "yungryce/my-repo",
#     "owner": { "login": "yungryce" }
#   },
#   "pusher": { "name": "yungryce" },
#   "commits": [ ... ]
# }

# Copilot
@app.route(route="orchestrator_start", methods=["POST"])
@app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client) -> func.HttpResponse:
    """
    HTTP endpoint to trigger the repo_context_orchestrator Durable Function.
    Handles both user requests and GitHub webhook payloads.
    """
    logger.info("Received request to start repo_context_orchestrator")
    try:
        # Parse request body
        request_body = req.get_json() or {}

        # Check if the request is from a GitHub webhook
        if "repository" in request_body:
            logger.info("Processing GitHub webhook payload")
            repo_data = request_body.get("repository", {})
            username = repo_data.get("owner", {}).get("login")
            repo_name = repo_data.get("name")

            if not username or not repo_name:
                return create_error_response("Invalid GitHub webhook payload: missing username or repo name", 400)

            logger.info(f"Webhook triggered for repo '{repo_name}' by user '{username}'")
            force_refresh = True  # Always force refresh for webhooks
        else:
            # Process as a user request
            logger.info("Processing user request")
            username = request_body.get("username", "yungryce")
            force_refresh = request_body.get("force_refresh", False)
            repo_name = None  # Not applicable for user requests

        # Check model cache status
        model_cache_key = cache_manager.generate_cache_key(kind="model")
        model_cache_result = cache_manager.get(model_cache_key)
        model_cache_valid = model_cache_result["status"] == "valid"

        # If model cache is missing, force refresh regardless of repository bundle status
        if not model_cache_valid:
            logger.info(f"Model cache missing or invalid (key: {model_cache_key}), forcing orchestration")
            force_refresh = True

        if not force_refresh:
            # Check cache status
            bundle_cache_key = cache_manager.generate_cache_key(kind="bundle", username=username)
            logger.info(f"Checking cache for user '{username}' with key: {bundle_cache_key}")

            cache_entry = cache_manager.get(bundle_cache_key)
            if cache_entry["status"] == "valid" and cache_entry["data"]:
                logger.info(f"Cache exists for user '{username}', cache info: {len(cache_entry['data'])} repositories")

                # Get current repository list and calculate fingerprints
                repo_manager = _get_github_managers(username)
                current_repos = repo_manager.get_all_repos_metadata(username=username, include_languages=False)

                current_fingerprints = {
                    repo.get("name"): FingerprintManager.generate_metadata_fingerprint(repo)
                    for repo in current_repos if repo.get("name")
                }

                # Generate a current bundle fingerprint
                current_repo_fingerprints = list(current_fingerprints.values())
                current_bundle_fingerprint = FingerprintManager.generate_bundle_fingerprint(current_repo_fingerprints)

                # Compare with cached bundle fingerprint
                cached_bundle_fingerprint = cache_entry.get("fingerprint")

                if cached_bundle_fingerprint and cached_bundle_fingerprint == current_bundle_fingerprint:
                    logger.info("Combined bundle fingerprints match")
                    logger.debug(f"First repository in bundle: {json.dumps(cache_entry['data'][1], indent=2)}")

                    # Return cached response with bundle fingerprint
                    return create_success_response({
                        "status": "cached",
                        "message": "Using cached repository data (fingerprint match)",
                        "timestamp": datetime.now().isoformat(),
                        "cache_key": bundle_cache_key,
                        "repos_count": len(cache_entry["data"]) if isinstance(cache_entry["data"], list) else 0,
                        "bundle_fingerprint": cached_bundle_fingerprint,
                        "cache_info": {
                            "last_modified": cache_entry.get("last_modified"),
                            "size_bytes": cache_entry.get("size_bytes"),
                            "no_expiry": cache_entry.get("no_expiry", False),
                        },
                    })
            else:
                logger.info(f"No valid cache found for user '{username}', proceeding with orchestration")
        else:
            logger.info(f"Force refresh requested for user '{username}', ignoring cache")

        # Start the orchestrator asynchronously
        instance_input = {"username": username}
        if repo_name:
            instance_input["repo"] = repo_name

        instance_id = await client.start_new("repo_context_orchestrator", None, instance_input)
        logger.info(f"Started repo_context_orchestrator for user '{username}', instance ID: {instance_id}")

        # Return response
        if repo_name:
            # Webhook acknowledgment
            return create_success_response({
                "status": "started",
                "message": f"Orchestration started for repo '{repo_name}' by user '{username}'",
                "instance_id": instance_id,
            })
        else:
            # User request orchestration status
            response = client.create_check_status_response(req, instance_id)
            logger.info(f"Check status response: {response.get_body().decode()}")
            return response

    except Exception as e:
        logger.error(f"Error starting repo_context_orchestrator: {str(e)}")
        return create_error_response(f"Failed to start orchestration: {str(e)}", 500)

# # GitHub Webhook Payload:
# {
#   "repository": {
#     "name": "example-repo",
#     "owner": {
#       "login": "yungryce"
#     }
#   }
# }
# # User Request Payload:
# {
#   "username": "yungryce",
#   "force_refresh": true
# }

@cache_manager.cache_decorator(cache_key_func=lambda username, **kwargs: cache_manager.generate_cache_key(kind='bundle', username=username))
def get_all_repos_with_context(self, username: Optional[str], include_languages: bool = True):
    """
    Get all repositories with enhanced context including .repo-context.json and file paths.
    """
    if not username:
        raise ValueError("Username is required")
    username = str(username)  # Ensure username is a string
    repos = self.get_all_repos_metadata(username, include_languages=include_languages)
    repos_with_context = [trim_processed_repo(repo) for repo in repos if isinstance(repo, dict)]
    
    # Generate fingerprint for the bundle
    fingerprint = FingerprintManager.generate_bundle_fingerprint([
        FingerprintManager.generate_metadata_fingerprint(repo)
        for repo in repos_with_context if isinstance(repo, dict)
    ])
    
    # Add fingerprint to cache metadata when saving
    # Note: The cache_decorator will handle this automatically
    
    return repos_with_context