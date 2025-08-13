@app.route(route="orchestrators/repo_context_orchestrator", methods=["POST"])
@app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client) -> func.HttpResponse:
    """
    HTTP endpoint to trigger the repo_context_orchestrator Durable Function.
    Enhanced with smarter cache checking and force refresh option.
    """
    logger.info("Received request to start repo_context_orchestrator")
    try:
        # Parse request body
        request_body = req.get_json() or {}
        username = request_body.get('username', 'yungryce')
        force_refresh = request_body.get('force_refresh', False)

        # Check cache status
        bundle_cache_key = f"repos_bundle_context_{username}"
        logger.info(f"Checking cache for user '{username}' with key: {bundle_cache_key}")

        if not force_refresh:
            cache_entry = cache_manager.get(bundle_cache_key)
            if cache_entry:
                logger.info(f"Cache exists for user '{username}', cache info: {len(cache_entry['data'])} repositories")

                # Get current repository list and calculate fingerprints
                _, _, repo_manager = _get_github_managers(username)
                current_repos = repo_manager.get_all_repos_metadata(include_languages=False)
                
                current_fingerprints = {
                    repo.get('name'): FingerprintManager.generate_metadata_fingerprint(repo)
                    for repo in current_repos if repo.get('name')
                }

                # Compare fingerprints with cached bundle
                cached_fingerprints = {
                    repo.get('repo_metadata', {}).get('name'): repo.get('fingerprint')
                    for repo in cache_entry['data'] if repo.get('repo_metadata', {}).get('name')
                }

                # Detect changes in existing repositories
                changed_repos = [
                    repo_name for repo_name, fingerprint in current_fingerprints.items()
                    if cached_fingerprints.get(repo_name) != fingerprint
                ]

                if not changed_repos:
                    # Return cached response with additional metadata
                    bundle_fingerprint = cache_entry.get('metadata', {}).get('fingerprint', 'unknown')
                    return create_success_response({
                        "status": "cached",
                        "message": "Using cached repository data",
                        "timestamp": datetime.now().isoformat(),
                        "cache_key": bundle_cache_key,
                        "repos_count": len(cache_entry['data']) if isinstance(cache_entry['data'], list) else 0,
                        "bundle_fingerprint": bundle_fingerprint,
                        "cache_info": {
                            "last_modified": cache_entry.get('last_modified'),
                            "size_bytes": cache_entry.get('size_bytes'),
                            "no_expiry": cache_entry.get('no_expiry', False)
                        }
                    })
            else:
                logger.info(f"No valid cache found for user '{username}', proceeding with orchestration")
        else:
            logger.info(f"Force refresh requested for user '{username}', ignoring cache")

        # Start the orchestrator asynchronously
        instance_id = await client.start_new('repo_context_orchestrator', None, username)
        logger.info(f"Started repo_context_orchestrator for user '{username}', instance ID: {instance_id}")

        # Return a status-check response for the orchestration
        response = create_success_response(req, instance_id)
        logger.info(f"Check status response: {response.get_body().decode()}")
        return response

    except Exception as e:
        logger.error(f"Error starting repo_context_orchestrator: {str(e)}")
        return create_error_response(f"Failed to start orchestration: {str(e)}", 500)
