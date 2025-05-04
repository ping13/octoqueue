from datetime import datetime
from unittest.mock import MagicMock
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from octoqueue.api import app
from octoqueue.api import get_queue
from octoqueue.api import verify_api_key
from octoqueue.queue import GithubQueue
from octoqueue.queue import extract_json


# Test client setup
@pytest.fixture
def client():
    return TestClient(app)


# Mock GitHub issue
@pytest.fixture
def mock_issue():
    issue = MagicMock()
    issue.number = 123
    issue.body = '```json\n{"test": "data"}\n```'
    issue.state = "open"

    # Mock labels
    label = MagicMock()
    label.name = "pending"
    issue.get_labels.return_value = [label]

    # Mock events
    event = MagicMock()
    event.event = "labeled"
    event.label.name = "pending"
    event.created_at = datetime.now()
    issue.get_events.return_value = [event]

    return issue


# Mock GitHub repo
@pytest.fixture
def mock_repo(mock_issue):
    repo = MagicMock()
    repo.get_issue.return_value = mock_issue
    repo.create_issue.return_value = mock_issue

    # Mock get_issues to return a list with our mock issue
    issues_mock = MagicMock()
    issues_mock.totalCount = 1
    issues_mock.__iter__ = lambda self: iter([mock_issue])
    issues_mock.__getitem__ = lambda self, idx: mock_issue
    repo.get_issues.return_value = issues_mock

    # Mock labels
    label = MagicMock()
    label.name = "pending"
    repo.get_labels.return_value = [label]

    return repo


# Mock queue fixture
@pytest.fixture
def mock_queue(mock_repo):
    with patch("octoqueue.queue.Github"), patch("octoqueue.queue.Auth"):
        queue = MagicMock(spec=GithubQueue)
        queue.repo = mock_repo
        queue.enqueue.return_value = 123

        # Override the dependency
        app.dependency_overrides[get_queue] = lambda: queue

        yield queue

        # Clean up
        app.dependency_overrides.clear()


# Mock API key for admin endpoints
@pytest.fixture
def mock_api_key():
    with patch("octoqueue.api.API_KEY", "test-api-key"):
        # Override API key validation
        app.dependency_overrides[verify_api_key] = lambda x_api_key=None: "test-api-key"

        yield "test-api-key"

        # Clean up
        app.dependency_overrides.clear()


# Tests for health endpoint
def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()
    assert response.json()["status"] == "healthy"
    assert "timestamp" in response.json()


# Tests for create job endpoint
def test_create_job(client, mock_queue):
    # Test data
    job_data = {
        "data": {"key": "value"},
        "title": "Test Job",
    }

    # Make request
    response = client.post("/create-job", json=job_data)

    # Assertions
    assert response.status_code == 201
    assert response.json() == {"job_id": 123, "processing_status": "scheduled", "status": "pending"}
    mock_queue.enqueue.assert_called_once_with(
        data=job_data["data"],
        title=job_data["title"],
        additional_labels=None,
    )


# Test with additional labels
def test_create_job_with_additional_labels(client, mock_queue):
    # Test data
    job_data = {
        "data": {"key": "value"},
        "title": "Test Job",
        "additional_labels": ["priority", "frontend"],
    }

    # Make request
    response = client.post("/create-job", json=job_data)

    # Assertions
    assert response.status_code == 201
    assert response.json() == {"job_id": 123, "processing_status": "scheduled", "status": "pending"}
    mock_queue.enqueue.assert_called_once_with(
        data=job_data["data"],
        title=job_data["title"],
        additional_labels=job_data["additional_labels"],
    )


# Test schema validation
def test_create_job_with_schema_validation(client, mock_queue):
    # Set a schema first
    with patch("octoqueue.api.JOB_SCHEMA", {"type": "object", "required": ["name"]}):
        # Valid job should pass
        valid_job = {"data": {"name": "test"}, "title": "Valid Job"}
        response = client.post("/create-job", json=valid_job)
        assert response.status_code == 201

        # Invalid job should fail
        invalid_job = {"data": {"not_name": "test"}, "title": "Invalid Job"}
        response = client.post("/create-job", json=invalid_job)
        assert response.status_code == 400
        assert "does not match required schema" in response.json()["detail"]


# Test API key validation for admin endpoints
def test_admin_schema_unauthorized(client):
    # No API key
    response = client.post(
        "/admin/schema",
        json={"job_schema": {"type": "object"}},
    )
    assert response.status_code == 403

    # Wrong API key
    with patch("octoqueue.api.API_KEY", "correct-key"):
        response = client.post(
            "/admin/schema",
            json={"job_schema": {"type": "object"}},
            headers={"X-API-Key": "wrong-key"},
        )
        assert response.status_code == 403


# Test schema endpoints
def test_set_job_schema(client, mock_api_key):
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}

    response = client.post(
        "/admin/schema",
        json={"job_schema": schema},
        headers={"X-API-Key": mock_api_key},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "Schema updated successfully"}


def test_get_job_schema(client, mock_api_key):
    # Set a schema for testing
    with patch("octoqueue.api.JOB_SCHEMA", {"type": "object"}):
        # Get the schema
        response = client.get(
            "/admin/schema",
            headers={"X-API-Key": mock_api_key},
        )

        assert response.status_code == 200
        assert response.json() == {"job_schema": {"type": "object"}}


# Test rate limiting
def test_rate_limiting(client, mock_queue):
    # Patch the rate limit settings to make testing easier
    with (
        patch("octoqueue.api.RATE_LIMIT_REQUESTS", 2),
        patch("octoqueue.api.RATE_LIMIT_WINDOW", 3600),
        patch("octoqueue.api.request_counts", {}),
    ):
        # First request should succeed
        response1 = client.post("/create-job", json={"data": {}, "title": "Job 1"})
        assert response1.status_code == 201

        # Second request should succeed
        response2 = client.post("/create-job", json={"data": {}, "title": "Job 2"})
        assert response2.status_code == 201

        # Third request should be rate limited
        response3 = client.post("/create-job", json={"data": {}, "title": "Job 3"})
        assert response3.status_code == 429


# Test queue methods through API
def test_queue_enqueue_error(client):
    queue = MagicMock(spec=GithubQueue)
    queue.enqueue.side_effect = Exception("Enqueue error")

    app.dependency_overrides[get_queue] = lambda: queue

    response = client.post("/create-job", json={"data": {}, "title": "Error Job"})
    assert response.status_code == 500
    assert "Failed to create job" in response.json()["detail"]

    app.dependency_overrides.clear()


# Test extract_json function from queue module
def test_extract_json():
    # Test with valid JSON in code block
    valid_text = 'Some text\n```json\n{"key": "value"}\n```\nMore text'
    result = extract_json(valid_text)
    assert result == {"key": "value"}

    # Test with valid JSON without code block markers
    valid_json = '{"key": "value"}'
    result = extract_json(valid_json)
    assert result == {"key": "value"}

    # Test with invalid JSON
    invalid_text = "Not JSON at all"
    result = extract_json(invalid_text)
    assert result is None
