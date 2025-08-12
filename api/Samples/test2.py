# Update the http_start function

@app.route(route="orchestrators/repo_context_orchestrator", methods=["POST"])
@app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client) -> func.HttpResponse:
    """
    HTTP endpoint to trigger the repo_context_orchestrator Durable Function.
    Enhanced with fingerprint-based change detection and force refresh option.
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
            if cache_entry and cache_entry['status'] == 'valid':
                logger.info(f"Cache exists for user '{username}', cache info: {len(cache_entry['data'])} repositories")
                
                # Get current repository list to check for new repos
                _, _, repo_manager = _get_github_managers(username)
                current_repos = repo_manager.get_all_repos_metadata(include_languages=False)
                current_repo_names = {repo.get('name') for repo in current_repos if repo.get('name')}
                
                # Check if all current repos are in the bundle
                cached_repo_names = {repo.get('repo_metadata', {}).get('name') 
                                   for repo in cache_entry['data'] if repo.get('repo_metadata', {})}
                
                missing_repos = current_repo_names - cached_repo_names
                if missing_repos and not force_refresh:
                    logger.info(f"Found {len(missing_repos)} new repositories not in cache, triggering refresh")
                else:
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
    
# Update the get_stale_repos_activity function

@app.activity_trigger(input_name="activityContext")
def get_stale_repos_activity(activityContext):
    """
    Activity function to identify repositories that need processing.
    Uses fingerprinting to detect changes instead of relying solely on TTL.
    Returns both stale repositories and existing cached bundle.
    """
    username = activityContext
    _, _, repo_manager = _get_github_managers(username)

    bundle_cache_key = f"repos_bundle_context_{username}"
    cached_bundle = cache_manager.get(bundle_cache_key)
    logger.info(f"Bundle cache status for '{username}': {cached_bundle.get('status')}")

    # Initialize empty data array as default
    cached_data = []

    # Get all repos metadata first to calculate fingerprints
    all_repos_metadata = repo_manager.get_all_repos_metadata(include_languages=True)
    
    # If bundle cache is valid, use it but still check for changed repos
    if cached_bundle and cached_bundle['status'] == 'valid' and isinstance(cached_bundle.get('data'), list):
        logger.info(f"Valid bundle cache found for user '{username}', repositories: {len(cached_bundle['data'])}")
        
        # Calculate fingerprints for all current repos
        repo_fingerprints = {}
        for repo_metadata in all_repos_metadata:
            repo_name = repo_metadata.get('name')
            if repo_name:
                repo_fingerprints[repo_name] = cache_manager.generate_repo_fingerprint(repo_metadata)
        
        # Check for changed repos by comparing fingerprints
        stale_repos = []
        valid_repos_meta = []
        
        # Create lookup for cached repos by name
        cached_repos_lookup = {repo.get('repo_metadata', {}).get('name'): repo 
                              for repo in cached_bundle['data'] if repo.get('repo_metadata', {}).get('name')}
        
        for repo_metadata in all_repos_metadata:
            repo_name = repo_metadata.get('name')
            if not repo_name:
                continue
                
            # Calculate current fingerprint
            current_fingerprint = repo_fingerprints.get(repo_name)
            
            # Get cached repo
            cached_repo = cached_repos_lookup.get(repo_name)
            cached_fingerprint = None
            
            # Extract fingerprint from cached repo
            if cached_repo:
                cached_repo_metadata = cached_repo.get('repo_metadata', {})
                repo_cache_key = f"repo_context_{username}_{repo_name}"
                cached_repo_entry = cache_manager.get(repo_cache_key)
                if cached_repo_entry and cached_repo_entry['status'] == 'valid':
                    cached_fingerprint = cached_repo_entry.get('metadata', {}).get('fingerprint')
            
            # Compare fingerprints - if different or missing, repo is stale
            if not cached_fingerprint or current_fingerprint != cached_fingerprint:
                logger.debug(f"Repo '{repo_name}' marked as stale due to fingerprint change or missing fingerprint")
                stale_repos.append(repo_metadata)
            else:
                valid_repos_meta.append(repo_metadata)
                
        # If no repos have changed, return the cached bundle
        if not stale_repos:
            logger.info(f"No repository changes detected for user '{username}' based on fingerprints")
            return {
                'stale_repos': [],
                'cached_bundle': cached_bundle['data']
            }
            
        # Hydrate valid repos from per-repo cache
        valid_repos_full = []
        reclassified_stale = []
        for repo_metadata in valid_repos_meta:
            repo_name = repo_metadata.get('name')
            repo_cache_key = f"repo_context_{username}_{repo_name}"
            cached_repo = cache_manager.get(repo_cache_key)
            if cached_repo and cached_repo['status'] == 'valid' and isinstance(cached_repo.get('data'), dict):
                valid_repos_full.append(cached_repo['data'])
            else:
                # If hydration fails, reclassify as stale to refresh
                reclassified_stale.append(repo_metadata)
                
        if reclassified_stale:
            logger.warning(f"Reclassifying {len(reclassified_stale)} repos as stale due to missing per-repo cache")
            stale_repos.extend(reclassified_stale)
            
        logger.info(f"Found {len(stale_repos)} stale and {len(valid_repos_full)} valid (hydrated) repositories based on fingerprints")
        
        return {
            'stale_repos': stale_repos,
            'cached_bundle': valid_repos_full
        }
    
    # If bundle cache is not valid, check individual repo caches
    logger.info(f"Bundle cache not valid for user '{username}', checking individual repository caches")

    stale_repos = []
    valid_repos_meta = []
    for repo_metadata in all_repos_metadata:
        repo_name = repo_metadata.get('name')
        if not repo_name:
            continue

        # Calculate current fingerprint
        current_fingerprint = cache_manager.generate_repo_fingerprint(repo_metadata)
        
        repo_cache_key = f"repo_context_{username}_{repo_name}"
        cached_repo_data = cache_manager.get(repo_cache_key)

        # Check if cached data is valid and fingerprint matches
        if (cached_repo_data and cached_repo_data['status'] == 'valid' and
                cached_repo_data.get('metadata', {}).get('fingerprint') == current_fingerprint):
            valid_repos_meta.append(repo_metadata)
        else:
            stale_repos.append(repo_metadata)

    # Hydrate valid repos from per-repo cache
    valid_repos_full = []
    reclassified_stale = []
    for repo_metadata in valid_repos_meta:
        repo_name = repo_metadata.get('name')
        repo_cache_key = f"repo_context_{username}_{repo_name}"
        cached_repo = cache_manager.get(repo_cache_key)
        if cached_repo and cached_repo['status'] == 'valid' and isinstance(cached_repo.get('data'), dict):
            valid_repos_full.append(cached_repo['data'])
        else:
            # If hydration fails, reclassify as stale to refresh
            reclassified_stale.append(repo_metadata)

    if reclassified_stale:
        logger.warning(f"Reclassifying {len(reclassified_stale)} repos as stale due to missing per-repo cache")
        stale_repos.extend(reclassified_stale)

    logger.info(f"Found {len(stale_repos)} stale and {len(valid_repos_full)} valid (hydrated) repositories out of {len(all_repos_metadata)} for '{username}'")

    return {
        'stale_repos': stale_repos,
        'cached_bundle': valid_repos_full
    }
    
# Update the fetch_repo_context_bundle_activity function

@app.activity_trigger(input_name="activityContext")
def fetch_repo_context_bundle_activity(activityContext):
    """
    Activity function to fetch repository metadata, languages, .repo-context.json, and file types for a single repository.
    Includes fingerprinting for change detection.
    """
    input_data = activityContext
    username = input_data.get('username')
    repo_metadata = input_data.get('repo_metadata')
    repo_name = repo_metadata.get('name')

    # Initialize managers
    _, file_manager, repo_manager = _get_github_managers(username)
    file_type_analyzer = FileTypeAnalyzer()
    
    # Generate fingerprint for this repository
    fingerprint = cache_manager.generate_repo_fingerprint(repo_metadata)

    # Fetch .repo-context.json
    repo_context = repo_manager.get_file_content(repo=repo_name, path='.repo-context.json', username=username)
    if repo_context and isinstance(repo_context, str):
        import json
        try:
            repo_context = json.loads(repo_context)
        except Exception:
            repo_context = {}
    else:
        repo_context = {}

    # Fetch README.md
    readme_content = repo_manager.get_file_content(repo=repo_name, path='README.md', username=username) or ""

    # Fetch SKILLS-INDEX.md
    skills_index_content = repo_manager.get_file_content(repo=repo_name, path='SKILLS-INDEX.md', username=username) or ""

    # Fetch ARCHITECTURE.md
    architecture_content = repo_manager.get_file_content(repo=repo_name, path='ARCHITECTURE.md', username=username) or ""

    # Analyze file types
    file_extensions = repo_manager.get_all_file_types(repo_name, username)
    file_types = file_type_analyzer.analyze_repository_files(file_extensions)

    # Combine results
    result = {
        'repo_metadata': repo_metadata,
        'repo_context': repo_context,
        'readme_content': readme_content,
        'skills_index_content': skills_index_content,
        'architecture_content': architecture_content,
        'file_types': file_types,
        'fingerprint': fingerprint
    }

    # Save to cache with fingerprint
    repo_cache_key = f"repo_context_{username}_{repo_name}"
    cache_manager.save(repo_cache_key, result, ttl=None, fingerprint=fingerprint)  # Use None for TTL since we're using fingerprints
    logger.info(f"Saved repository '{repo_name}' with fingerprint: {fingerprint}")

    return result


# Update the merge_repo_results_activity function

@app.activity_trigger(input_name="activityContext")
def merge_repo_results_activity(activityContext):
    """
    Activity function to merge fresh repository results with cached bundle.
    Preserves fingerprints for change detection.
    """
    input_data = activityContext
    username = input_data.get('username')
    fresh_results = input_data.get('fresh_results', [])
    cached_bundle = input_data.get('cached_bundle', [])

    _, _, _ = _get_github_managers(username)

    # Create lookup for fresh results by repository name
    fresh_repo_lookup = {result.get('repo_metadata', {}).get('name'): result 
                         for result in fresh_results if result.get('repo_metadata', {}).get('name')}

    # Start with cached bundle and update with fresh results
    merged_results = []
    processed_repo_names = set()

    # Update cached repos with fresh data where available
    for cached_repo in cached_bundle:
        repo_name = cached_repo.get('repo_metadata', {}).get('name')
        if repo_name in fresh_repo_lookup:
            # Use fresh data
            merged_results.append(fresh_repo_lookup[repo_name])
            processed_repo_names.add(repo_name)
            logger.debug(f"Updated repository '{repo_name}' with fresh data")
        else:
            # Keep cached data
            merged_results.append(cached_repo)
            processed_repo_names.add(repo_name)

    # Add any new repositories that weren't in the cached bundle
    for fresh_repo in fresh_results:
        repo_name = fresh_repo.get('repo_metadata', {}).get('name')
        if repo_name and repo_name not in processed_repo_names:
            merged_results.append(fresh_repo)
            logger.debug(f"Added new repository '{repo_name}' to bundle")

    # Cache individual repository results with fingerprints
    for fresh_repo in fresh_results:
        repo_name = fresh_repo.get('repo_metadata', {}).get('name')
        if repo_name:
            repo_cache_key = f"repo_context_{username}_{repo_name}"
            fingerprint = fresh_repo.get('fingerprint')
            cache_manager.save(repo_cache_key, fresh_repo, ttl=None, fingerprint=fingerprint)  # Use None for TTL

    # Cache the complete merged bundle - this never expires as we use fingerprints
    bundle_cache_key = f"repos_bundle_context_{username}"
    if merged_results:
        # Generate bundle fingerprint as a hash of all repo fingerprints
        repo_fingerprints = [repo.get('fingerprint', '') for repo in merged_results]
        bundle_fingerprint = hashlib.md5(json.dumps(sorted(repo_fingerprints)).encode()).hexdigest()
        
        cache_manager.save(bundle_cache_key, merged_results, ttl=None, fingerprint=bundle_fingerprint)
        logger.info(f"Cached merged bundle with {len(merged_results)} repositories under key: {bundle_cache_key}")
        logger.info(f"Bundle fingerprint: {bundle_fingerprint}")

    return merged_results