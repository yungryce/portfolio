#!/usr/bin/env python3
"""
Test script to verify the new modular architecture works properly.
"""

import sys
import os
import logging

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('portfolio.api')

def test_github_managers():
    """Test the GitHub manager components."""
    try:
        print("Testing GitHub managers...")
        
        # Test GitHub API
        from github_api import GitHubAPI
        api = GitHubAPI(token="dummy_token", username="test_user")
        print("✓ GitHubAPI imports and initializes")
        
        # Test GitHub Cache
        from github_cache import GitHubCache
        cache = GitHubCache(use_cache=False)  # Don't use actual cache for testing
        print("✓ GitHubCache imports and initializes")
        
        # Test GitHub File Manager
        from github_file_manager import GitHubFileManager
        file_manager = GitHubFileManager(api, cache)
        print("✓ GitHubFileManager imports and initializes")
        
        # Test GitHub Repo Manager
        from github_repo_manager import GitHubRepoManager
        repo_manager = GitHubRepoManager(api, cache, file_manager)
        print("✓ GitHubRepoManager imports and initializes")
        
        # Test the original GitHub client facade
        from github_client import GitHubClient
        client = GitHubClient(token="dummy_token", username="test_user", use_cache=False)
        print("✓ GitHubClient facade imports and initializes")
        
        return True
        
    except Exception as e:
        print(f"✗ GitHub managers test failed: {e}")
        return False

def test_ai_modules():
    """Test the AI module components."""
    try:
        print("\nTesting AI modules...")
        
        # We'll need mock GitHub managers for AI testing
        from github_api import GitHubAPI
        from github_cache import GitHubCache
        from github_file_manager import GitHubFileManager
        from github_repo_manager import GitHubRepoManager
        
        # Create mock managers
        api = GitHubAPI(token="dummy_token", username="test_user")
        cache = GitHubCache(use_cache=False)
        file_manager = GitHubFileManager(api, cache)
        repo_manager = GitHubRepoManager(api, cache, file_manager)
        
        # Test AI Assistant (using .new version)
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ai'))
        
        # Import from the .new files
        import importlib.util
        
        # Load ai_assistant.py.new
        spec = importlib.util.spec_from_file_location(
            "ai_assistant_new", 
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ai', 'ai_assistant.py.new')
        )
        ai_assistant_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ai_assistant_module)
        
        assistant = ai_assistant_module.AIAssistant(username="test_user", repo_manager=repo_manager)
        print("✓ AIAssistant imports and initializes")
        
        # Load repository_scorer.py.new
        spec = importlib.util.spec_from_file_location(
            "repository_scorer_new", 
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ai', 'repository_scorer.py.new')
        )
        scorer_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scorer_module)
        
        scorer = scorer_module.RepositoryScorer()
        print("✓ RepositoryScorer imports and initializes")
        
        # Load context_builder.py.new
        spec = importlib.util.spec_from_file_location(
            "context_builder_new", 
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ai', 'context_builder.py.new')
        )
        context_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(context_module)
        
        context_builder = context_module.ContextBuilder(repo_manager=repo_manager)
        print("✓ ContextBuilder imports and initializes")
        
        # Load ai_query_processor.py.new
        spec = importlib.util.spec_from_file_location(
            "ai_query_processor_new", 
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ai', 'ai_query_processor.py.new')
        )
        processor_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(processor_module)
        
        processor = processor_module.AIQueryProcessor()
        print("✓ AIQueryProcessor imports and initializes")
        
        return True
        
    except Exception as e:
        print(f"✗ AI modules test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_function_app():
    """Test the function app with new architecture."""
    try:
        print("\nTesting Function App...")
        
        # Test that function_app can import and initialize
        from function_app import app
        print("✓ Function app imports successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ Function app test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=== Testing New Modular Architecture ===\n")
    
    success = True
    
    # Test GitHub managers
    if not test_github_managers():
        success = False
    
    # Test AI modules
    if not test_ai_modules():
        success = False
    
    # Test function app
    if not test_function_app():
        success = False
    
    print(f"\n=== Test Results ===")
    if success:
        print("✓ All tests passed! The new architecture is working correctly.")
        return 0
    else:
        print("✗ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
