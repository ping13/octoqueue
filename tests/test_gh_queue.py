"""Tests for the queue_gh_issues.gh_queue module."""

import time
import unittest
from queue_gh_issues import GithubQueue

test_issue_data = {
    "title": "Test Issue",
    "body": "Test Description",
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
