import logging
import os
import time
from typing import Any
import httpx
from dotenv import load_dotenv
from fastapi import Depends
from fastapi import FastAPI
from fastapi import Header
from fastapi import HTTPException
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jsonschema import ValidationError
from jsonschema import validate
from pydantic import BaseModel
from .queue import GithubQueue

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("octoqueue.api")

# Initialize FastAPI app
app = FastAPI(
    title="OctoQueue API",
    description="A simple queue API based on GitHub issues",
    version="0.1.0",
)

# Get configuration from environment variables
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "http://localhost:3000")
API_KEY = os.getenv("API_KEY")
GITHUB_REPO = os.getenv("GITHUB_REPO")
GITHUB_TOKEN = os.getenv("GH_TOKEN")  # Get GitHub token from environment
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "600"))  # 10 mins in seconds

# Schema for job validation
JOB_SCHEMA = None

# Validate required environment variables
if not API_KEY:
    logger.warning("API_KEY environment variable not set. API will be unsecured!")

if not GITHUB_REPO:
    logger.error("GITHUB_REPO environment variable not set. API will not function correctly!")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=True,
    allow_methods=["POST", "GET"],  # Allow GET for health check
    allow_headers=["*"],
)

# Simple in-memory rate limiting
request_counts = {}


# Request models
class JobRequest(BaseModel):
    data: dict[str, Any]
    title: str | None = None
    additional_labels: list[str] | None = None


class JobResponse(BaseModel):
    job_id: int
    status: str = "pending"
    processing_status: str = "unknown"


class SchemaRequest(BaseModel):
    job_schema: dict[str, Any]


# Dependency for API key validation
def verify_api_key(x_api_key: str = Header(None)):
    if not API_KEY:
        # If API_KEY is not set, skip validation but log a warning
        logger.warning("API request processed without API key validation")
        raise HTTPException(status_code=403, detail="No API key set server side")

    if x_api_key is None:
        logger.warning("API request processed without API key validation")
        raise HTTPException(status_code=403, detail="No API key given client side")

    if x_api_key != API_KEY:
        logger.warning(f"Invalid API key attempt: {x_api_key[:5]}...")
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key


# Dependency for rate limiting
def check_rate_limit(request: Request):
    if not RATE_LIMIT_REQUESTS:
        return

    client_ip = request.client.host
    current_time = time.time()

    # Clean up old entries
    for ip in list(request_counts.keys()):
        if current_time - request_counts[ip]["timestamp"] > RATE_LIMIT_WINDOW:
            del request_counts[ip]

    # Check if client has exceeded rate limit
    if client_ip in request_counts:
        if request_counts[client_ip]["count"] >= RATE_LIMIT_REQUESTS:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        request_counts[client_ip]["count"] += 1
    else:
        request_counts[client_ip] = {"count": 1, "timestamp": current_time}


# Dependency to get queue instance
def get_queue():
    if not GITHUB_REPO:
        raise HTTPException(status_code=500, detail="GITHUB_REPO environment variable not set")
    try:
        return GithubQueue(GITHUB_REPO, token=GITHUB_TOKEN)
    except ValueError as e:
        logger.error(f"Failed to initialize GitHub queue: {e!s}")
        raise HTTPException(status_code=500, detail=f"Queue initialization error: {e!s}")
    except Exception as e:
        logger.error(f"Unexpected error initializing queue: {e!s}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Error handler
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc!s}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred"},
    )


# Routes
@app.post("/create-job", response_model=JobResponse, status_code=201)
def create_job(
    job_request: JobRequest,
    rate_limit: None = Depends(check_rate_limit),
    queue: GithubQueue = Depends(get_queue),
):
    """Create a new job in the queue"""
    try:
        # Validate against schema if one is set
        if JOB_SCHEMA is not None:
            logger.info(f"validating job request against {JOB_SCHEMA}")
            validate(instance=job_request.data, schema=JOB_SCHEMA)

        job_id = queue.enqueue(
            data=job_request.data,
            title=job_request.title,
            additional_labels=job_request.additional_labels,
        )
        logger.info(f"Octoqueue Job created successfully: {job_id}")

        # now let's ping k8s
        topoprint_host = os.getenv("TOPOPRINT_HOST")
        processing_status = "unknown"
        if topoprint_host:
            try:
                # Use httpx to make the request
                run_the_queue_url = f"{topoprint_host}/run-the-queue"
                logger.info(f"Pinging topoprint endpoint: {run_the_queue_url}")
                response = httpx.get(run_the_queue_url, timeout=5.0)
                if response.status_code == 200:
                    logger.info("Successfully pinged topoprint endpoint")
                    processing_status = "scheduled"
                else:
                    logger.warning(f"Topoprint queue ping failed with status code: {response.status_code}")
                    processing_status = "unscheduled"
            except Exception as e:
                logger.error(f"Failed to ping topoprint endpoint: {e}")

        return {"job_id": job_id, "status": "pending", "processing_status": processing_status}
    except ValidationError as e:
        logger.warning(f"Job data validation failed: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Job data does not match required schema: {e!s}",
        )
    except Exception as e:
        logger.error(f"Failed to create job: {e!s}")
        raise HTTPException(status_code=500, detail=f"Failed to create job: {e!s}")


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}


@app.post("/admin/schema")
def set_job_schema(
    schema_request: SchemaRequest,
    api_key: str = Depends(verify_api_key),
):
    """Set a JSON schema for job validation"""
    global JOB_SCHEMA
    JOB_SCHEMA = schema_request.job_schema
    logger.info("Job schema updated successfully")
    return {"status": "success", "message": "Schema updated successfully"}


@app.get("/admin/schema")
def get_job_schema(
    api_key: str = Depends(verify_api_key),
):
    """Get the current JSON schema for job validation"""
    return {"job_schema": JOB_SCHEMA}
