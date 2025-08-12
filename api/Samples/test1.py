

@app.activity_trigger(input_name="activityContext")
def get_stale_repos_activity(activityContext):
    """
    Activity function to identify repositories that need processing.
    Returns both stale repositories and existing cached bundle.
    """
    username = activityContext
    _, _, repo_manager = _get_github_managers(username)

    bundle_cache_key = f"repos_bundle_context_{username}"
    cached_bundle_entry = cache_manager.get(bundle_cache_key)
    logger.info(f"Bundle cache status for '{username}': {cached_bundle_entry.get('status')}")

    # Normalize cached bundle to a list of repo bundle dicts
    cached_bundle_list = []
    if cached_bundle_entry and cached_bundle_entry.get('status') == 'valid':
        data = cached_bundle_entry.get('data')
        if isinstance(data, list):
            cached_bundle_list = data

    # Map cached repos by name with their fingerprint for quick lookup/hydration
    cached_by_name = {}
    for item in cached_bundle_list:
        # Support both shapes while transitioning (legacy bundles may not have top-level name/fingerprint)
        name = item.get('name') or item.get('repo_metadata', {}).get('name')
        if name:
            cached_by_name[name] = {
                "fingerprint": item.get("fingerprint"),
                "bundle": item
            }

    all_repos_metadata = repo_manager.get_all_repos_metadata(include_languages=True)

    stale_repos = []
    valid_repos_full = []

    for repo_metadata in all_repos_metadata:
        repo_name = repo_metadata.get('name')
        if not repo_name:
            continue

        current_fp = compute_repo_fingerprint(repo_metadata)
        cached = cached_by_name.get(repo_name)

        if cached and cached.get("fingerprint") == current_fp:
            # No change; hydrate from cached bundle
            valid_repos_full.append(cached["bundle"])
        else:
            # New or changed; mark as stale
            stale_repos.append(repo_metadata)

    logger.info(
        f"Found {len(stale_repos)} stale and {len(valid_repos_full)} valid (fingerprint-matched) "
        f"repositories out of {len(all_repos_metadata)} for '{username}'"
    )

    return {
        'stale_repos': stale_repos,
        'cached_bundle': valid_repos_full
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
    _, file_manager, repo_manager = _get_github_managers(username)
    file_type_analyzer = FileTypeAnalyzer()

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

    # Compute fingerprint from metadata (fast)
    fingerprint = compute_repo_fingerprint(repo_metadata)

    # Combine results (include name + fingerprint for easier merging and checks)
    result = {
        'name': repo_name,
        'fingerprint': fingerprint,
        'repo_metadata': repo_metadata,
        'repo_context': repo_context,
        'readme_content': readme_content,
        'skills_index_content': skills_index_content,
        'architecture_content': architecture_content,
        'file_types': file_types
    }

    # Save to cache (per-repo can still use TTL; optional to switch to no-expiry)
    repo_cache_key = f"repo_context_{username}_{repo_name}"
    cache_manager.save(repo_cache_key, result, ttl=43200)  # 12 hours

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

    _, _, _ = _get_github_managers(username)

    # Create lookup for fresh results by repository name (support both shapes)
    def repo_name_of(item):
        return item.get('name') or item.get('repo_metadata', {}).get('name')

    fresh_repo_lookup = {repo_name_of(r): r for r in fresh_results if repo_name_of(r)}

    # Start with cached bundle and update with fresh results
    merged_results = []
    processed_repo_names = set()

    # Update cached repos with fresh data where available
    for cached_repo in cached_bundle:
        repo_name = repo_name_of(cached_repo)
        if not repo_name:
            continue
        if repo_name in fresh_repo_lookup:
            merged_results.append(fresh_repo_lookup[repo_name])
            processed_repo_names.add(repo_name)
            logger.debug(f"Updated repository '{repo_name}' with fresh data")
        else:
            merged_results.append(cached_repo)
            processed_repo_names.add(repo_name)

    # Add any repos that weren't in the cached bundle
    for fresh_repo in fresh_results:
        repo_name = repo_name_of(fresh_repo)
        if repo_name and repo_name not in processed_repo_names:
            merged_results.append(fresh_repo)
            logger.debug(f"Added new repository '{repo_name}' to bundle")

    # Cache individual repository results (keep existing TTL policy)
    for fresh_repo in fresh_results:
        repo_name = repo_name_of(fresh_repo)
        if repo_name:
            repo_cache_key = f"repo_context_{username}_{repo_name}"
            cache_manager.save(repo_cache_key, fresh_repo, ttl=43200)  # 12 hours

    # Cache the complete merged bundle as non-expiring; fingerprints drive refresh
    bundle_cache_key = f"repos_bundle_context_{username}"
    if merged_results:
        cache_manager.save(bundle_cache_key, merged_results, ttl=None)  # No expiry
        logger.info(f"Cached merged bundle (no-expiry) with {len(merged_results)} repositories under key: {bundle_cache_key}")

    return merged_results
# ...existing code...
# First run after deployment will refresh all repos once (older bundles lack fingerprint), then subsequent runs will only process repos whose metadata changes.
# If you want per-repo entries to never expire as well, switch those save() calls to ttl=None too.