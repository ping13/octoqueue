
# Octoqueue

A simple queue implementation using GitHub issues as the backend storage mechanism.

## What is it?

Octoqueue provides a queue interface backed by GitHub issues. It allows you to:

- Enqueue jobs as GitHub issues with data stored in JSON
- Dequeue and process jobs by managing issue labels
- Track job status (queued, processing, completed, failed)
- Add comments and metadata to jobs
- Requeue failed jobs

You get the web interface 

## When to use it

Octoqueue is appropriate when you need:

- A simple, persistent job queue with a web interface (GitHub)
- Queue visibility and job history through GitHub's UI
- The ability to manually inspect and modify queued jobs
- Integration with GitHub-based workflows
- No additional infrastructure beyond GitHub

## When not to use it

Octoqueue os not suitable when you need:

- Production-grade workflows
- High-performance job processing (GitHub API has rate limits)
- Real-time job processing
- Complex queue operations like priorities or dependencies
- Processing of sensitive data (issues are visible in GitHub)

## Installation

To install `octoqueue` from GitHub repository:

```console
git clone git@github.com:ping13/octoqueue.git
cd octoqueue
python -m pip install .
```

or of you use [`uv`](https://docs.astral.sh/uv/) in your project:

```console
uv add "octoqueue @ git+https://github.com/ping13/octoqueue"
```

## Quick Start

```python
from octoqueue import GithubQueue

# Initialize queue with your repo details
queue = GithubQueue(
    owner="username",
    repo="myrepo",
    token="github_pat_token"
)

# Enqueue a job
job_id = queue.enqueue({"data": "example"})

# Dequeue and process jobs
job = queue.dequeue()
if job:
    job_id, data = job
    try:
        # Process the job
        process_data(data)
        queue.complete(job_id)
    except Exception as e:
        queue.fail(job_id, str(e))
```

## Documentation

Not ready yet.

