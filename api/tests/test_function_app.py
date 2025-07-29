import pytest
from unittest.mock import MagicMock, patch

from function_app import fetch_repo_context_bundle_activity

class DummyActivityContext:
    def __init__(self, input_data):
        self._input = input_data
    def get_input(self):
        return self._input

@pytest.fixture
def dummy_repo_metadata():
    return {
        "name": "test-repo",
        "languages": {"Python": 1000, "JavaScript": 500}
    }

@pytest.fixture
def dummy_input(dummy_repo_metadata):
    return {
        "username": "testuser",
        "repo_metadata": dummy_repo_metadata
    }

@patch("function_app._get_github_managers")
@patch("ai.ai_assistant.AIAssistant")
def test_fetch_repo_context_bundle_activity_success(mock_ai_assistant, mock_get_managers, dummy_input, dummy_repo_metadata):
    # Setup mocks
    mock_repo_manager = MagicMock()
    mock_get_managers.return_value = (None, None, None, mock_repo_manager)
    mock_repo_manager.get_file_content.return_value = '{"tech_stack": ["Python", "Azure"]}'
    mock_ai_instance = MagicMock()
    mock_ai_instance.get_all_file_types.return_value = {".py": 10, ".js": 5}
    mock_ai_instance.file_type_analyzer.analyze_repository_files.return_value = {"code": 15}
    mock_ai_assistant.return_value = mock_ai_instance

    ctx = DummyActivityContext(dummy_input)
    result = fetch_repo_context_bundle_activity(ctx)

    assert result["metadata"] == dummy_repo_metadata
    assert result["repoContext"] == {"tech_stack": ["Python", "Azure"]}
    assert result["file_types"] == {".py": 10, ".js": 5}
    assert result["categorized_types"] == {"code": 15}
    assert result["languages"] == {"Python": 1000, "JavaScript": 500}

@patch("function_app._get_github_managers")
@patch("ai.ai_assistant.AIAssistant")
def test_fetch_repo_context_bundle_activity_invalid_json(mock_ai_assistant, mock_get_managers, dummy_input, dummy_repo_metadata):
    # Setup mocks
    mock_repo_manager = MagicMock()
    mock_get_managers.return_value = (None, None, None, mock_repo_manager)
    mock_repo_manager.get_file_content.return_value = "not a json"
    mock_ai_instance = MagicMock()
    mock_ai_instance.get_all_file_types.return_value = {".py": 10}
    mock_ai_instance.file_type_analyzer.analyze_repository_files.return_value = {"code": 10}
    mock_ai_assistant.return_value = mock_ai_instance

    ctx = DummyActivityContext(dummy_input)
    result = fetch_repo_context_bundle_activity(ctx)

    assert result["repoContext"] == {}

@patch("function_app._get_github_managers")
@patch("ai.ai_assistant.AIAssistant")
def test_fetch_repo_context_bundle_activity_missing_languages(mock_ai_assistant, mock_get_managers, dummy_input):
    # Setup mocks
    dummy_input["repo_metadata"].pop("languages", None)
    mock_repo_manager = MagicMock()
    mock_get_managers.return_value = (None, None, None, mock_repo_manager)
    mock_repo_manager.get_file_content.return_value = '{}'
    mock_ai_instance = MagicMock()
    mock_ai_instance.get_all_file_types.return_value = {}
    mock_ai_instance.file_type_analyzer.analyze_repository_files.return_value = {}
    mock_ai_assistant.return_value = mock_ai_instance

    ctx = DummyActivityContext(dummy_input)
    result = fetch_repo_context_bundle_activity(ctx)

    assert result["languages"]