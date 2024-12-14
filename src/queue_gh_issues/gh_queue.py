import json
import logging
import os
import re
from datetime import datetime
from typing import Any
from dotenv import load_dotenv
from github import Auth
from github import Github
from github import GithubException

load_dotenv()


def extract_json(text):
    # Look for content between ```json and ``` markers
    json_pattern = r"```json\s*(\{[^`]*\})\s*```"
    match = re.search(json_pattern, text, re.DOTALL)

    if not match:
        # Fallback: try to find any content between curly braces
        json_pattern = r"\{[^{]*\}"
        match = re.search(json_pattern, text, re.DOTALL)

    if match:
        try:
            # Parse the extracted string as JSON
            return json.loads(match.group(1))
        except (json.JSONDecodeError, IndexError):
            try:
                # If first attempt fails, try parsing the entire match
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None

    return None


class GithubQueue:
    def __init__(self, repo: str):
        token = os.getenv("GH_TOKEN")
        if not token:
            raise ValueError("GH_TOKEN not found in environment")

        auth = Auth.Token(token)
        self.gh = Github(auth=auth)

        self.repo = self.gh.get_repo(repo)
        self.logger = logging.getLogger(__name__)
        self._ensure_labels()

    def _ensure_labels(self) -> None:
        """Create required labels if they don't exist"""
        required = {
            "pending": "0dbf66",
            "processing": "0052cc",
            "completed": "2cbe4e",
            "failed": "d93f0b",  # Red color for failed
            "mastodon": "800080",
        }

        existing = {label.name: label for label in self.repo.get_labels()}

        for name, color in required.items():
            if name not in existing:
                self.repo.create_label(name=name, color=color)

    def enqueue(self, data: dict[str, Any], title: str = None, additional_labels=None) -> int:
        """Add a job to the queue"""
        if title is None:
            title = f"Job {datetime.now().isoformat()}"

        labels = ["pending"]
        if additional_labels:
            labels.extend(additional_labels)
        try:
            issue = self.repo.create_issue(
                title=title,
                body=f"```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```",
                labels=labels,
            )
            return issue.number
        except GithubException as e:
            self.logger.error(f"Failed to enqueue job: {e}")
            raise

    def count_open(self) -> int:
        """Count the pending and processing issues"""
        open_issues = self.repo.get_issues(state="open")
        cnt = 0
        for issue in open_issues:
            labels = list(issue.get_labels())
            for label in labels:
                if label.name == "processing" or label.name == "pending":
                    cnt += 1
        return cnt

    def dequeue(self) -> tuple[int, dict[str, Any]] | None:
        """Get and claim next pending job"""
        try:
            issues = self.repo.get_issues(labels=["pending"], state="open", sort="created")

            if not issues.totalCount:
                return None

            issue = issues[0]
            body = issue.body
            data = extract_json(body)

            issue.remove_from_labels("pending")
            issue.add_to_labels("processing")

            return (issue.number, data)

        except GithubException as e:
            self.logger.error(f"Failed to dequeue job: {e}")
            raise

    def fail(self, job_id: int, comment: str = None) -> None:
        """Mark job as failed"""
        if comment is None:
            comment = "This job has failed"
        try:
            issue = self.repo.get_issue(job_id)
            issue.remove_from_labels("processing")
            issue.add_to_labels("failed")
            issue.create_comment(comment)
            issue.edit(state="closed")
        except GithubException as e:
            self.logger.error(f"Failed to mark job {job_id} as failed: {e}")
            raise

    def complete(self, job_id: int, comment: str = None) -> None:
        """Mark job as complete"""
        if comment is None:
            comment = "This has been completed, thank you"
        try:
            issue = self.repo.get_issue(job_id)
            issue.remove_from_labels("processing")
            issue.add_to_labels("completed")
            issue.create_comment(comment)
            issue.edit(state="closed")
        except GithubException as e:
            self.logger.error(f"Failed to complete job {job_id}: {e}")
            raise

    def requeue(self, job_id: int, comment: str = None) -> None:
        """Put a job back in the queue for reprocessing"""
        if comment is None:
            comment = "Job has been requeued for processing"
        try:
            issue = self.repo.get_issue(job_id)

            # Remove existing status labels
            for label in ["processing", "completed"]:
                try:
                    issue.remove_from_labels(label)
                except GithubException:
                    pass  # Label might not exist

            # Add back to pending
            issue.add_to_labels("pending")

            # Reopen if closed
            if issue.state == "closed":
                issue.edit(state="open")

            if comment:
                issue.create_comment(comment)

        except GithubException as e:
            self.logger.error(f"Failed to requeue job {job_id}: {e}")
            raise

    def get_processing_jobs(self) -> list[tuple[int, datetime, dict[str, Any]]]:
        """Get all jobs currently being processed

        Returns:
            List of tuples containing (job_id, start_time, job_data)
            where start_time is when the processing label was added
        """
        try:
            processing = self.repo.get_issues(labels=["processing"], state="open")
            jobs = []

            for issue in processing:
                # Get the job data from the issue body
                body = issue.body
                data = json.loads(body[body.find("```json\n") + 7 : body.rfind("\n```")])

                # Find when the processing label was added by checking issue events
                start_time = None
                for event in issue.get_events():
                    if event.event == "labeled" and event.label.name == "processing":
                        start_time = event.created_at
                        break

                jobs.append((issue.number, start_time, data))

            return jobs

        except GithubException as e:
            self.logger.error(f"Failed to get processing jobs: {e}")
            raise
