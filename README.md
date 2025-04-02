
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

- A simple, persistent job queue with a nice GUI interface (you can GitHub's
  issue management on the web/app).
- Queue visibility and job history through GitHub's UI
- The ability to manually inspect, modify and restart queued jobs
- Integration with GitHub-based workflows
- No additional infrastructure beyond GitHub

## When not to use it

Octoqueue is not suitable when you need:

- Production-grade workflows
- High-performance job processing ([GitHub API has rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api))
- Real-time job processing (usually, it takes 1-3 seconds to create an issue)
- Complex queue operations like priorities or dependencies
- Processing of sensitive data (issues are visible in a GitHub repo, even if
  the repo is private, it could be exposed by making it public)

## Installation

To install `octoqueue` from GitHub repository:

```console
git clone git@github.com:ping13/octoqueue.git
cd octoqueue
python -m pip install .
```

or if you use [`uv`](https://docs.astral.sh/uv/) in your project:

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

## CLI Usage

OctoQueue provides a command-line interface for running the API server:

```console
# Basic usage
octoqueue serve

# With options
octoqueue serve --host 127.0.0.1 --port 5000 --repo owner/repo --reload
```

### CLI Options

- `--host`: Host to bind the server to (default: 0.0.0.0)
- `--port`: Port to bind the server to (default: 8080)
- `--repo`: GitHub repository in the format 'owner/repo'
- `--allowed-origin`: Allowed origin for CORS
- `--api-key`: API key for authentication
- `--log-level`: Logging level (default: info)
- `--reload`: Enable auto-reload for development

## API Usage

The OctoQueue API provides a simple interface to create jobs in the GitHub-based queue.

### Endpoints

#### POST /create-job

Creates a new job in the queue.

**Headers:**
- `Content-Type: application/json` (required)
- `X-API-Key: your_api_key` (required if API key is configured)

**Request Body:**
```json
{
  "data": {
    "your_key": "your_value",
    "another_key": 123
  },
  "title": "Optional job title",
  "additional_labels": ["optional", "labels"]
}
```

**Response:**
```json
{
  "job_id": 123,
  "status": "pending"
}
```

#### POST /admin/schema

Sets a JSON schema for validating job data. All subsequent job creation
requests will be validated against this schema, you need to have an API key to

**Headers:**
- `Content-Type: application/json` (required)
- `X-API-Key: your_api_key` (required)

**Request Body:**
```json
{
  "schema": {
    "type": "object",
    "properties": {
      "your_key": { "type": "string" },
      "another_key": { "type": "number" }
    },
    "required": ["your_key"]
  }
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Schema updated successfully"
}
```

#### GET /admin/schema

Retrieves the current JSON schema used for job validation.

**Headers:**
- `X-API-Key: your_api_key` (required)

**Response:**
```json
{
  "schema": {
    "type": "object",
    "properties": {
      "your_key": { "type": "string" },
      "another_key": { "type": "number" }
    },
    "required": ["your_key"]
  }
}
```

#### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": 1621234567.89
}
```

### Deployment

1. Set up environment variables (see `.env.example`)
2. Run the deployment script: `./deploy.sh`

### Local Development

1. Copy `.env.example` to `.env` and fill in the values
2. Run the server with auto-reload enabled:
   ```console
   octoqueue serve --reload
   ```
   
   Alternatively, you can use uvicorn directly:
   ```console
   uvicorn octoqueue.api:app --reload
   ```

## Documentation

Not ready yet.

