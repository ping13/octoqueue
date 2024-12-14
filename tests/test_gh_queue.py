"""Tests for the queue_gh_issues.gh_queue module."""

import time
import unittest
from queue_gh_issues import GithubQueue

test_issue_data = {
    "title": "Test Issue 😃",
    "body": "Test Description, äöü, 世界 🌎",
    "labels": ["bug"],
}


class TestGitHubQueue(unittest.TestCase):
    def setUp(self):
        """Setup the queue"""
        self.queue = GithubQueue("ping13/queue_gh_issues_test")

    def test_01_add_issue(self):
        """Test adding an issue to the queue."""
        cnt = self.queue.count_open()
        print(f"cnt = {cnt}")
        self.assertTrue(cnt >= 0)
        TestGitHubQueue.job_id = self.queue.enqueue(test_issue_data)
        print(f"job_id = {self.job_id}, cnt = {cnt}")
        self.assertTrue(self.job_id > 0)
        time.sleep(5)
        self.assertEqual(self.queue.count_open(), cnt + 1)

    def test_02_process_issue(self):
        """Get the job from the queue"""
        job = self.queue.dequeue()
        self.assertTrue(isinstance(job, tuple))
        this_job_id, data = job
        self.assertEqual(this_job_id, TestGitHubQueue.job_id)
        self.assertTrue(isinstance(data, dict))

    def test_03_complete_issue(self):
        """Complete a job from the queue"""
        cnt = self.queue.count_open()
        self.queue.complete(TestGitHubQueue.job_id)
        self.assertEqual(self.queue.count_open(), cnt - 1)

    def test_04_requeue_issue(self):
        """Test requeuing a completed job"""
        cnt = self.queue.count_open()
        self.queue.requeue(TestGitHubQueue.job_id, "Requeuing for test")
        self.assertEqual(self.queue.count_open(), cnt + 1)

        # Verify it's back in pending state
        job = self.queue.dequeue()
        self.assertIsNotNone(job)
        job_id, data = job
        self.assertEqual(job_id, TestGitHubQueue.job_id)
        self.assertEqual(data, test_issue_data)

    def test_05_get_jobs(self):
        """Test getting list of jobs with different labels"""
        # First ensure we have a processing job and a job with custom label
        job1_id = self.queue.enqueue({"test": "processing_check"}, "Processing Job Test")
        job2_id = self.queue.enqueue({"test": "custom_label_check"}, "Custom Label Test", 
                                additional_labels=["mastodon"])
        
        # Dequeue first job to mark it as processing
        job = self.queue.dequeue()
        self.assertIsNotNone(job)
        
        # Test getting only processing jobs
        processing = self.queue.get_jobs()  # default label="processing"
        self.assertTrue(len(processing) >= 1)
        
        # Verify the structure of returned data for processing jobs
        found_processing = False
        for proc_id, start_time, data in processing:
            if proc_id == job1_id:
                found_processing = True
                self.assertIsNotNone(start_time)
                self.assertIsInstance(data, dict)
                self.assertEqual(data["test"], "processing_check")
        
        self.assertTrue(found_processing, "Recently created processing job not found")
        
        # Test getting jobs with custom label
        custom_labeled = self.queue.get_jobs(labels=["mastodon"])
        self.assertTrue(len(custom_labeled) >= 1)
        
        # Verify the structure of returned data for custom labeled jobs
        found_custom = False
        for proc_id, start_time, data in custom_labeled:
            if proc_id == job2_id:
                found_custom = True
                self.assertIsNotNone(start_time)
                self.assertIsInstance(data, dict)
                self.assertEqual(data["test"], "custom_label_check")
        
        self.assertTrue(found_custom, "Recently created custom labeled job not found")
        
        # Test getting jobs with multiple labels
        multi_labeled = self.queue.get_jobs(labels=["processing", "mastodon"])
        self.assertTrue(len(multi_labeled) >= 2)
        
        # Cleanup
        self.queue.complete(job1_id)
        self.queue.complete(job2_id)

    def test_05b_fail_issue(self):
        """Test marking a job as failed"""
        # Create a new job to test failure
        job_id = self.queue.enqueue({"test": "failure_test"}, "Failure Test Job")
        job = self.queue.dequeue()  # Mark it as processing
        self.assertIsNotNone(job)

        # Get initial count of open issues
        cnt = self.queue.count_open()

        # Mark the job as failed
        failure_message = "Test failure message"
        self.queue.fail(job_id, failure_message)

        # Verify open count decreased
        self.assertEqual(self.queue.count_open(), cnt - 1)

        # Could add more detailed verification here if needed, such as:
        # - Verify the failure label is present
        # - Verify the failure message was added as a comment
        # - Verify the issue is closed

    def test_06_complete_issue(self):
        """Complete a job from the queue"""
        cnt = self.queue.count_open()
        self.queue.complete(TestGitHubQueue.job_id)
        self.assertEqual(self.queue.count_open(), cnt - 1)

    def test_07_fifo_order(self):
        """Test that dequeue follows FIFO (First In, First Out) order"""
        # Create three test jobs in sequence

        # This test assumes that there are no other pending tests and no other process interferes, any suggestion to make this test more robust? AI!
        
        job1_data = {"test": "fifo1"}
        job2_data = {"test": "fifo2"}
        job3_data = {"test": "fifo3"}
        
        job1_id = self.queue.enqueue(job1_data, "FIFO Test 1")
        time.sleep(2)  # Ensure distinct creation times
        job2_id = self.queue.enqueue(job2_data, "FIFO Test 2")
        time.sleep(2)  # Ensure distinct creation times
        job3_id = self.queue.enqueue(job3_data, "FIFO Test 3")
        
        # Dequeue them in sequence and verify order
        job1 = self.queue.dequeue()
        self.assertEqual(job1[0], job1_id)
        self.assertEqual(job1[1], job1_data)
        
        job2 = self.queue.dequeue()
        self.assertEqual(job2[0], job2_id)
        self.assertEqual(job2[1], job2_data)
        
        job3 = self.queue.dequeue()
        self.assertEqual(job3[0], job3_id)
        self.assertEqual(job3[1], job3_data)
        
        # Clean up
        self.queue.complete(job1_id)
        self.queue.complete(job2_id)
        self.queue.complete(job3_id)


import pytest
from src.queue_gh_issues.gh_queue import GithubQueue


@pytest.fixture
def mock_repo(mocker):
    """Create a mock repository"""
    mock = mocker.Mock()
    mock.get_labels.return_value = []
    mock.create_label = mocker.Mock()
    mock.create_issue = mocker.Mock()

    # Mock Github client
    mocker.patch("github.Github.get_repo", return_value=mock)
    # Mock environment variable
    mocker.patch("os.getenv", return_value="fake-token")

    return mock


def test_enqueue_with_additional_labels(mock_repo):
    """Test enqueueing with additional labels"""
    queue = GithubQueue("test/repo")
    test_data = {"test": "data"}
    additional_labels = ["mastodon", "custom-label"]

    queue.enqueue(test_data, additional_labels=additional_labels)

    # Verify create_issue was called with all expected labels
    expected_labels = ["pending"] + additional_labels
    mock_repo.create_issue.assert_called_once()
    call_args = mock_repo.create_issue.call_args[1]
    assert set(call_args["labels"]) == set(expected_labels)


def test_enqueue_without_additional_labels(mock_repo):
    """Test enqueueing without additional labels"""
    queue = GithubQueue("test/repo")
    test_data = {"test": "data"}

    queue.enqueue(test_data)

    # Verify create_issue was called with only pending label
    mock_repo.create_issue.assert_called_once()
    call_args = mock_repo.create_issue.call_args[1]
    assert call_args["labels"] == ["pending"]
