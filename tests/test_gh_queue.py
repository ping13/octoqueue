"""Tests for the queue_gh_issues.gh_queue module."""

import pytest
from queue_gh_issues.gh_queue import GithubQueue


def test_github_queue_initialization():
    """Test that GithubQueue initializes with empty queue."""
    queue = GithubQueue()
    assert len(queue.issues) == 0


def test_add_issue():
    """Test adding an issue to the queue."""
    queue = GithubQueue()
    issue_data = {
        "title": "Test Issue",
        "body": "Test Description",
        "labels": ["bug"]
    }
    queue.add_issue(issue_data)
    assert len(queue.issues) == 1
    assert queue.issues[0] == issue_data


def test_process_queue():
    """Test processing issues in the queue."""
    queue = GithubQueue()
    issue1 = {"title": "Issue 1", "body": "Description 1", "labels": ["bug"]}
    issue2 = {"title": "Issue 2", "body": "Description 2", "labels": ["feature"]}
    
    queue.add_issue(issue1)
    queue.add_issue(issue2)
    
    processed_issues = queue.process_queue()
    assert len(processed_issues) == 2
    assert len(queue.issues) == 0
