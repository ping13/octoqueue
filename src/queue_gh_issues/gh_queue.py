from github import Github, Auth, GithubException
from datetime import datetime
import json
from typing import Optional, Dict, Any
import logging
from dotenv import load_dotenv
import os
import sys
import time

load_dotenv()

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
        required = {"pending": "0dbf66", "processing": "0052cc", "completed": "2cbe4e"}

        existing = {label.name: label for label in self.repo.get_labels()}

        for name, color in required.items():
            if name not in existing:
                self.repo.create_label(name=name, color=color)

    def enqueue(self, data: Dict[str, Any], title: str = None) -> int:
        """Add a job to the queue"""
        if title is None:
            title = f"Job {datetime.now().isoformat()}"

        try:
            issue = self.repo.create_issue(
                title=title, body=f"```json\n{json.dumps(data, indent=2)}\n```", labels=["pending"]
            )
            return issue.number
        except GithubException as e:
            self.logger.error(f"Failed to enqueue job: {e}")
            raise

    def count_open(self) -> int:
        """ count the pending and processing issues"""
        open_issues = self.repo.get_issues(state="open")
        cnt = 0
        for issue in open_issues:
            labels = list(issue.get_labels())
            for label in labels:
                if label.name == "processing" or label.name == "pending":
                    cnt+=1
        return cnt
        
    def dequeue(self) -> Optional[tuple[int, Dict[str, Any]]]:
        """Get and claim next pending job"""
        try:
            issues = self.repo.get_issues(labels=["pending"], state="open", sort="created")

            if not issues.totalCount:
                return None

            issue = issues[0]
            body = issue.body
            data = json.loads(body[body.find("```json\n") + 7 : body.rfind("\n```")])

            issue.remove_from_labels("pending")
            issue.add_to_labels("processing")

            return (issue.number, data)

        except GithubException as e:
            self.logger.error(f"Failed to dequeue job: {e}")
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


if __name__ == "__main__":

    def process_job(data):
        time.sleep(5)
        print(data)

    queue = GithubQueue("ping13/topoprint-ch")

    # Producer
    job_id = queue.enqueue({"task": "process_file", "path": "data.csv"})
    print(f"Enqueued job: {job_id}")

    # Consumer
    while True:
        job = queue.dequeue()
        if job:
            job_id, data = job
            try:
                # Process job
                process_job(data)
                queue.complete(job_id)
            except Exception as e:
                print(f"Error processing job {job_id}: {e}")
        else:
            print("I am done, thank you")
            sys.exit(0)
