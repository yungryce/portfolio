import json
import logging
import os
import time
import azure.functions as func
import azure.durable_functions as df
from datetime import datetime
from fa_helpers import create_success_response, create_error_response, get_orchestration_status, trim_processed_repo

# Updated imports - use individual managers instead of GitHubClient
from config.github_api import GitHubAPI
from config.cache_manager import cache_manager
from config.github_repo_manager import GitHubRepoManager
from config.fingerprint_manager import FingerprintManager

# AI imports
from ai.type_analyzer import FileTypeAnalyzer

# Configure logging
logger = logging.getLogger('portfolio.api')
logger.setLevel(logging.DEBUG)
# Do NOT add FileHandler in production
if os.getenv("ENV_SETUP") == "Development":
    file_handler = logging.FileHandler("api_function_app.log", mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

app = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)
logger.info("Function app initialized")


# Fix initialization of GitHubFileManager and GitHubRepoManager
def _get_github_managers(username=None):
    """Get GitHub managers initialized with proper dependencies."""
    github_token = os.getenv('GITHUB_TOKEN')

    # Initialize components in dependency order
    api = GitHubAPI(token=github_token, username=username)
    repo_manager = GitHubRepoManager(api, username=username)

    return repo_manager


@app.route(route="orchestrator_start", methods=["POST"])
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
        model_cache_key = cache_manager.generate_cache_key(kind='model')
        model_cache_result = cache_manager.get(model_cache_key)
        model_cache_valid = model_cache_result['status'] == 'valid'

        # If model cache is missing, we should force refresh regardless of repository bundle status
        if not model_cache_valid:
            logger.info(f"Model cache missing or invalid (key: {model_cache_key}), forcing orchestration")
            force_refresh = True

        if not force_refresh:
            # Check cache status
            bundle_cache_key = cache_manager.generate_cache_key(kind='bundle', username=username)
            logger.info(f"Checking cache for user '{username}' with key: {bundle_cache_key}")

            cache_entry = cache_manager.get(bundle_cache_key)
            if cache_entry['status'] == 'valid' and cache_entry['data']:
                logger.info(f"Cache exists for user '{username}', cache info: {len(cache_entry['data'])} repositories")

                # Get current repository list and calculate fingerprints
                repo_manager = _get_github_managers(username)
                current_repos = repo_manager.get_all_repos_metadata(username=username, include_languages=False)

                current_fingerprints = {
                    repo.get('name'): FingerprintManager.generate_metadata_fingerprint(repo)
                    for repo in current_repos if repo.get('name')
                }

                # Generate a current bundle fingerprint
                current_repo_fingerprints = list(current_fingerprints.values())
                current_bundle_fingerprint = FingerprintManager.generate_bundle_fingerprint(current_repo_fingerprints)

                # Compare with cached bundle fingerprint
                cached_bundle_fingerprint = cache_entry.get('fingerprint')

                if cached_bundle_fingerprint and cached_bundle_fingerprint == current_bundle_fingerprint:
                    logger.info("Combined bundle fingerprints match")
                    # logger.debug(f"First repository in bundle: {json.dumps(cache_entry['data'][1], indent=2)}")

                    # Return cached response with bundle fingerprint
                    return create_success_response({
                        "status": "cached",
                        "message": "Using cached repository data (fingerprint match)",
                        "timestamp": datetime.now().isoformat(),
                        "cache_key": bundle_cache_key,
                        "repos_count": len(cache_entry['data']) if isinstance(cache_entry['data'], list) else 0,
                        "bundle_fingerprint": cached_bundle_fingerprint,
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
        response = client.create_check_status_response(req, instance_id)
        logger.info(f"Check status response: {response.get_body().decode()}")
        return response

    except Exception as e:
        logger.error(f"Error starting repo_context_orchestrator: {str(e)}")
        return create_error_response(f"Failed to start orchestration: {str(e)}", 500)

@app.orchestration_trigger(context_name="context")
def repo_context_orchestrator(context):
    """
    Durable Functions orchestrator for parallel repository context retrieval.
    Only processes repositories with stale or missing cache entries.
    """
    username = context.get_input()

    # Get repositories that need processing (stale or missing from cache)
    repos_data = yield context.call_activity('get_stale_repos_activity', username)

    if not repos_data['stale_repos'] and repos_data['cached_bundle']:
        logger.info(f"No stale repositories found for user '{username}', persisting/hydrating cached bundle via merge")
        # Route through merge to ensure bundle cache is saved/updated with a fingerprint
        merged_results = yield context.call_activity('merge_repo_results_activity', {
            'username': username,
            'fresh_results': [],  # nothing new to add
            'cached_bundle': repos_data['cached_bundle']
        })
        logger.info(f"Cached bundle contains {len(merged_results)} repositories")

        # Train semantic model as background activity even if using cached results
        yield context.call_activity('train_semantic_model_activity', {
            'username': username,
            'repos_bundle': merged_results,
            'training_params': {'batch_size': 8, 'max_pairs': 150, 'epochs': 2, 'warmup_steps': 50}
        })

        return merged_results

    logger.info(f"Processing {len(repos_data['stale_repos'])} stale repositories for user '{username}'")

    # Process only stale repositories
    tasks = []
    for repo_metadata in repos_data['stale_repos']:
        tasks.append(context.call_activity('fetch_repo_context_bundle_activity', {
            'username': username,
            'repo_metadata': trim_processed_repo(repo_metadata)
        }))

    # Get results for stale repositories
    stale_results = yield context.task_all(tasks)

    # Merge fresh and cached data
    merged_results = yield context.call_activity('merge_repo_results_activity', {
        'username': username,
        'fresh_results': stale_results,
        'cached_bundle': repos_data['cached_bundle']
    })

    # Train semantic model as a background activity after orchestration completes
    yield context.call_activity('train_semantic_model_activity', {
        'username': username,
        'repos_bundle': merged_results,
        'training_params': {'batch_size': 8, 'max_pairs': 150, 'epochs': 2, 'warmup_steps': 50}
    })

    logger.info(f"Completed repo context orchestration for user '{username}': "
                f"{len(stale_results)} processed, {len(merged_results)} total repositories")

    return merged_results

@app.activity_trigger(input_name="activityContext")
def get_stale_repos_activity(activityContext):
    """
    Activity function to identify repositories that need processing.
    Uses fingerprinting to detect changes instead of relying solely on TTL.
    Returns both stale repositories and existing cached bundle.
    """
    username = activityContext
    repo_manager = _get_github_managers(username)

    # Fetch cached bundle
    bundle_cache_key = cache_manager.generate_cache_key(kind='bundle', username=username)
    cached_bundle = cache_manager.get(bundle_cache_key)
    # logger.info(f"Bundle cache status for '{username}': {cached_bundle.get('status')}")

    # Fetch current repository metadata
    all_repos_metadata = repo_manager.get_all_repos_metadata(username=username, include_languages=True)

    # Calculate fingerprints for current repositories
    current_fingerprints = {
        repo.get('name'): FingerprintManager.generate_metadata_fingerprint(repo)
        for repo in all_repos_metadata if repo.get('name')
    }

    # Extract fingerprints from cached bundle (only if valid)
    bundle_ok = cached_bundle.get('status') == 'valid' and isinstance(cached_bundle.get('data'), list)
    cached_fingerprints = {
        repo.get('metadata', {}).get('name'): repo.get('fingerprint')
        for repo in (cached_bundle.get('data') or [])
        if bundle_ok and repo.get('metadata', {}).get('name')
    } if bundle_ok else {}

    # Identify stale and valid repositories
    stale_repos = []
    valid_repos = []
    for repo_metadata in all_repos_metadata:
        repo_name = repo_metadata.get('name')
        if not repo_name:
            continue

        current_fingerprint = current_fingerprints.get(repo_name)
        cached_fingerprint = cached_fingerprints.get(repo_name)

        # If bundle didn’t have it or mismatch, try per-repo cache before declaring stale
        if current_fingerprint != cached_fingerprint:
            repo_cache_key = cache_manager.generate_cache_key(kind='repo', username=username, repo=repo_name)
            per_repo_entry = cache_manager.get(repo_cache_key)
            per_repo_status = per_repo_entry.get('status')
            per_repo_fp = per_repo_entry.get('fingerprint')

            if per_repo_status == 'valid' and per_repo_fp == current_fingerprint:
                valid_repos.append(repo_metadata)
                continue

            # No usable per-repo cache; mark stale with clear diagnostics
            if cached_fingerprint is None and per_repo_status != 'valid':
                logger.info(f"Repo '{repo_name}' is stale: no bundle fingerprint and per-repo cache status={per_repo_status}.")
            else:
                logger.warning(
                    f"Fingerprint mismatch for repo '{repo_name}': "
                    f"current='{current_fingerprint}', bundle='{cached_fingerprint}', per_repo='{per_repo_fp}', "
                    f"per_repo_status='{per_repo_status}'"
                )
            stale_repos.append(repo_metadata)
        else:
            valid_repos.append(repo_metadata)

    # Hydrate valid repositories from per-repo cache
    hydrated_valid_repos = []
    for repo_metadata in valid_repos:
        repo_name = repo_metadata.get('name')
        repo_cache_key = cache_manager.generate_cache_key(kind='repo', username=username, repo=repo_name)
        cached_repo = cache_manager.get(repo_cache_key)
        if cached_repo and isinstance(cached_repo.get('data'), dict):
            hydrated_valid_repos.append(cached_repo['data'])
        else:
            logger.warning(f"Repo '{repo_name}' missing or invalid in per-repo cache, reclassifying as stale")
            stale_repos.append(repo_metadata)

    # Return results
    logger.info(f"Found {len(stale_repos)} stale and {len(hydrated_valid_repos)} valid repositories for user '{username}'")
    return {
        'stale_repos': stale_repos,
        'cached_bundle': hydrated_valid_repos
    }

@app.activity_trigger(input_name="activityContext")
def fetch_repo_context_bundle_activity(activityContext):
    """
    Activity function to fetch repository metadata, languages, .repo-context.json, and file types for a single repository.
    """
    input_data = activityContext
    username = input_data.get('username')
    repo_metadata = input_data.get('repo_metadata')
    repo_name = repo_metadata.get('name')

    # Initialize managers
    repo_manager = _get_github_managers(username)

    # Generate fingerprint for this repository
    fingerprint = FingerprintManager.generate_metadata_fingerprint(repo_metadata)

    # Fetch .repo-context.json
    repo_context = repo_manager.get_file_content(repo=repo_name, path='.repo-context.json', username=username)
    repo_context = json.loads(repo_context) if repo_context and isinstance(repo_context, str) else {}

    # Fetch README.md
    readme_content = repo_manager.get_file_content(repo=repo_name, path='README.md', username=username) or ""

    # Fetch SKILLS-INDEX.md
    skills_index_content = repo_manager.get_file_content(repo=repo_name, path='SKILLS-INDEX.md', username=username) or ""

    # Fetch ARCHITECTURE.md
    architecture_content = repo_manager.get_file_content(repo=repo_name, path='ARCHITECTURE.md', username=username) or ""

    # Analyze file types
    file_type_analyzer = FileTypeAnalyzer()
    file_types = repo_manager.get_all_file_types(repo_name, username)
    categorized_types = file_type_analyzer.analyze_repository_files(file_types)

    # Combine results
    result = {
        "name": repo_name,
        'metadata': repo_metadata,
        'repoContext': repo_context,
        'readme': readme_content,
        'skills_index': skills_index_content,
        'architecture': architecture_content,
        'file_types': file_types,
        "categorized_types": categorized_types,
        'fingerprint': fingerprint,
        "languages": repo_metadata.get("languages", {}) if repo_metadata else {},
        'has_documentation': bool(repo_context) and bool(readme_content)
    }

    # Save to cache
    repo_cache_key = cache_manager.generate_cache_key(kind='repo', username=username, repo=repo_name)
    cache_manager.save(repo_cache_key, result, ttl=None, fingerprint=fingerprint) # No TTL for repo context
    logger.info(f"Saved repository '{repo_name}' with fingerprint: {fingerprint}")

    return result

@app.activity_trigger(input_name="activityContext")
def merge_repo_results_activity(activityContext):
    """
    Activity function to merge fresh repository results with cached bundle.
    """
    input_data = activityContext
    username = input_data.get('username')
    fresh_results = input_data.get('fresh_results', [])
    cached_bundle = input_data.get('cached_bundle', [])

    # Create lookup for fresh results by repository name
    fresh_repo_lookup = {result.get('metadata', {}).get('name'): result
                         for result in fresh_results if result.get('metadata', {}).get('name')}

    # Start with cached bundle and update with fresh results
    merged_results = []
    processed_repo_names = set()

    # Update cached repos with fresh data where available
    for cached_repo in cached_bundle:
        repo_name = cached_repo.get('metadata', {}).get('name')
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
        repo_name = fresh_repo.get('metadata', {}).get('name')
        if repo_name and repo_name not in processed_repo_names:
            merged_results.append(fresh_repo)

    # Cache individual repository results
    for fresh_repo in fresh_results:
        repo_name = fresh_repo.get('metadata', {}).get('name')
        if repo_name:
            repo_cache_key = cache_manager.generate_cache_key(kind='repo', username=username, repo=repo_name)
            fingerprint = fresh_repo.get('fingerprint')
            cache_manager.save(repo_cache_key, fresh_repo, ttl=None, fingerprint=fingerprint)  # Use None for TTL

    # Cache the complete merged bundle which uses fingerprints
    bundle_cache_key = cache_manager.generate_cache_key(kind='bundle', username=username)
    if merged_results:
        repo_fingerprints = [repo.get('fingerprint', '') for repo in merged_results]
        bundle_fingerprint = FingerprintManager.generate_bundle_fingerprint(repo_fingerprints)

        cache_manager.save(bundle_cache_key, merged_results, ttl=None, fingerprint=bundle_fingerprint)
        logger.info(f"Cached merged bundle with {len(merged_results)} repositories under key: {bundle_cache_key}")
        logger.info(f"Bundle fingerprint: {bundle_fingerprint}")
    return merged_results

@app.activity_trigger(input_name="activityContext")
def train_semantic_model_activity(activityContext):
    """
    Activity function that ensures the semantic model is ready for use.
    This runs after orchestration completes to prepare models asynchronously.
    """
    logger.info("Starting semantic model training activity")
    try:
        # Extract parameters
        username = activityContext.get('username')
        repos_bundle = activityContext.get('repos_bundle', [])

        # Additional optimization: Only train if we have enough repositories
        documented_repos = [repo for repo in repos_bundle if repo.get("has_documentation", False)]
        if len(documented_repos) < 3:
            logger.info(f"Not enough documented repositories ({len(documented_repos)}) for meaningful training")
            return False

        # Initialize semantic model
        from config.fine_tuning import SemanticModel
        semantic_model = SemanticModel()

        # Consider passing training parameters through context
        training_params = activityContext.get('training_params', {})
        batch_size = training_params.get('batch_size', 8)
        max_pairs = training_params.get('max_pairs', 150)

        # Use parameters when training
        model_ready = semantic_model.ensure_model_ready(
            repos_bundle,
            train_if_missing=True,
            training_params={
                'batch_size': batch_size,
                'max_pairs': max_pairs
            }
        )

        logger.info(f"Semantic model training {'succeeded' if model_ready else 'failed'}")
        return model_ready
    except Exception as e:
        logger.error(f"Error training semantic model: {str(e)}", exc_info=True)
        return False

@app.route(route="bundles/{username}", methods=["GET"])
def get_repo_bundle(req: func.HttpRequest) -> func.HttpResponse:
    """
    Retrieve a single user's repository bundle from the cache (Azure Blob via cache_manager).
    """
    try:
        username = req.route_params.get('username')
        if not username:
            return create_error_response("Username required", 400)

        bundle_cache_key = cache_manager.generate_cache_key(kind='bundle', username=username)
        result = cache_manager.get(bundle_cache_key)

        status = result.get('status')
        if status != 'valid' or result.get('data') is None:
            return create_error_response(f"No valid bundle found for '{username}'", 404)

        payload = {
            "username": username,
            "fingerprint": result.get('fingerprint'),
            "last_modified": result.get('last_modified'),
            "size_bytes": result.get('size_bytes'),
            "data": result.get('data'),
        }
        return create_success_response(payload)
    except Exception as e:
        logger.error(f"Failed to retrieve bundle for '{username}': {str(e)}", exc_info=True)
        return create_error_response(f"Failed to retrieve bundle: {str(e)}", 500)

@app.route(route="bundles/{username}/{repo}", methods=["GET"])
def get_single_repo_bundle(req: func.HttpRequest) -> func.HttpResponse:
    """
    Retrieve a single repository bundle from the cache.

    Args:
        username: GitHub username
        repo: Repository name

    Returns:
        HTTP response with the repository bundle or error
    """
    try:
        username = req.route_params.get('username')
        repo = req.route_params.get('repo')

        if not username or not repo:
            return create_error_response("Username and repository name are required", 400)

        # Generate cache key for this specific repository
        repo_cache_key = cache_manager.generate_cache_key(kind='repo', username=username, repo=repo)
        result = cache_manager.get(repo_cache_key)

        status = result.get('status')
        if status != 'valid' or result.get('data') is None:
            return create_error_response(f"No valid repository data found for '{repo}' by user '{username}'", 404)

        payload = {
            "username": username,
            "repo": repo,
            "fingerprint": result.get('fingerprint'),
            "last_modified": result.get('last_modified'),
            "size_bytes": result.get('size_bytes'),
            "data": result.get('data')
        }
        return create_success_response(payload)
    except Exception as e:
        logger.error(f"Failed to retrieve repository bundle for '{repo}' by '{username}': {str(e)}", exc_info=True)
        return create_error_response(f"Failed to retrieve repository bundle: {str(e)}", 500)

@app.route(route="ai", methods=["POST"])
def portfolio_query(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("=-=-Received portfolio query request=-=-")
    try:
        # Parse request body
        request_body = req.get_json()
        if not request_body or 'query' not in request_body:
            return create_error_response("Request body must contain 'query' field", 400)

        query = request_body['query']
        username = request_body.get('username')
        instance_id = request_body.get('instance_id')
        status_query_url = request_body.get('status_query_url')

        # Try to get cached results first
        cache_key = cache_manager.generate_cache_key(kind='bundle', username=username)
        cached_results = cache_manager.get(cache_key)
        logger.debug(f"Cached results for user '{username}': {cached_results['status'] if cached_results else 'None'}")

        all_repos_bundle = None
        if cached_results and isinstance(cached_results.get('data'), list):
            all_repos_bundle = cached_results['data']
            logger.info(f"Using valid cached results for user '{username}'")

        if not all_repos_bundle and instance_id:
            orchestration_status = get_orchestration_status(instance_id, status_query_url)
            if orchestration_status and orchestration_status.get("runtimeStatus") == "Completed":
                all_repos_bundle = orchestration_status.get("output", [])
                cache_manager.save(cache_key, all_repos_bundle)
            else:
                return create_error_response("Orchestration not completed or results unavailable", 202)
        elif not all_repos_bundle:
            return create_error_response("No repo context results available. Provide instance_id or wait for orchestration.", 400)

        # Step 1: Score repositories with the optimized service
        from ai.repo_scoring_service import RepoScoringService
        scoring_service = RepoScoringService(username=username)
        scored_repos = scoring_service.score_repositories(query, all_repos_bundle)

        # Log top 3 repositories for debugging
        if scored_repos and len(scored_repos) > 0:
            logger.info("Top scoring repositories:")
            for i, repo in enumerate(sorted(scored_repos, key=lambda x: x.get("total_relevance_score", 0), reverse=True)[:3]):
                logger.info(f"{i+1}. {repo.get('name', 'Unknown')}: Context Score: {repo.get('context_score', 0):.4f}, Total: {repo.get('total_relevance_score', 0):.4f}")

        # Step 2: Process with optimized AI assistant using pre-scored repositories
        from ai.ai_assistant import AIAssistant
        ai_assistant = AIAssistant(username=username)
        response = ai_assistant.process_scored_repositories(query, scored_repos)

        return create_success_response(response)
    except Exception as e:
        logger.error(f"Error processing portfolio query: {str(e)}", exc_info=True)
        return create_error_response(f"Failed to process query: {str(e)}", 500)


@app.timer_trigger(schedule="0 0 * * * *", arg_name="myTimer", run_on_startup=False, use_monitor=True)
def cleanup_cache(myTimer: func.TimerRequest) -> None:
    """
    Timer trigger to clean up expired individual blobs generated by GitHubRepoManager
    and the cache_decorator in CacheManager.
    Runs daily at midnight.
    """
    try:
        # Call the cleanup method from CacheManager
        cleanup_results = cache_manager.cleanup_expired_cache(batch_size=100, dry_run=False)

        # Log summary
        if cleanup_results['status'] == 'completed':
            logger.info(f"Successfully cleaned up {cleanup_results['deleted_count']} expired cache entries")
        else:
            logger.warning(f"Cache cleanup failed or skipped: {cleanup_results}")

    except Exception as e:
        logger.error(f"Error during cleanup of individual blobs: {str(e)}")

@app.route(route="surveys", methods=["GET"])
def list_survey_images(req: func.HttpRequest) -> func.HttpResponse:
    """
    List survey rating screenshots from Azure Blob Storage container 'surveys'.
    Optional query: ?theme=light|dark
    Filenames: {slug}-{theme}.{ext} (e.g., csat-5-light.png).
    """
    try:
        theme = (req.params.get('theme') or '').strip().lower()
        if theme not in ('', 'light', 'dark'):
            return create_error_response("Invalid theme. Use 'light' or 'dark'.", 400)

        def infer_theme(name: str) -> str:
            n = name.lower()
            if any(t in n for t in ["-dark.", "_dark.", ".dark."]): return "dark"
            if any(t in n for t in ["-light.", "_light.", ".light."]): return "light"
            parts = n.replace("\\", "/").split("/")
            if "dark" in parts: return "dark"
            if "light" in parts: return "light"
            return "unknown"

        def infer_slug(name: str) -> str:
            import os
            base = os.path.basename(name)
            stem, _ = os.path.splitext(base)
            for suf in ("-dark", "_dark", ".dark", "-light", "_light", ".light"):
                if stem.endswith(suf): return stem[: -len(suf)]
            return stem

        container = "surveys"
        client = cache_manager.get_container_client(container)
        items = []
        for blob in client.list_blobs():
            bname = getattr(blob, "name", "")
            if not bname:
                continue
            t = infer_theme(bname)
            if theme and t != theme:
                continue
            items.append({
                # "name": infer_slug(bname),
                "theme": t,
                "path": bname,
                "url": cache_manager.make_blob_sas_url(container, bname)
            })

        items.sort(key=lambda x: x["theme"])
        return create_success_response({
            "count": len(items),
            "theme": theme or "all",
            "items": items
        }, cache_control="public, max-age=600")
    except Exception as e:
        logger.error(f"Failed to list survey images: {str(e)}", exc_info=True)
        return create_error_response(f"Failed to list survey images: {str(e)}", 500)
