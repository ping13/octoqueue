import asyncio
import logging
import os
import time
import uuid
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
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:5173")
# Convert comma-separated string to list of origins, handling wildcards for localhost
ALLOWED_ORIGINS_LIST = []
for origin in [o.strip() for o in ALLOWED_ORIGINS.split("|")]:
    ALLOWED_ORIGINS_LIST.append(origin)

API_KEY = os.getenv("API_KEY")
GITHUB_REPO = os.getenv("GITHUB_REPO")
GITHUB_TOKEN = os.getenv("GH_TOKEN")  # Get GitHub token from environment
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "5"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds
RATE_LIMIT_BYPASS_KEY = os.getenv("RATE_LIMIT_BYPASS_KEY", None)
TOPOPRINT_HOST = os.getenv("TOPOPRINT_HOST")


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
    allow_origins=ALLOWED_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],  # Added OPTIONS for preflight requests
    allow_headers=["*"],
)


# Add middleware to log CORS requests
@app.middleware("http")
async def log_cors_requests(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin:
        logger.info(f"Received request with Origin: {origin}")
        if origin in ALLOWED_ORIGINS_LIST:
            logger.info(f"Origin {origin} is in allowed list")
        else:
            logger.warning(f"Origin {origin} is NOT in allowed list: {ALLOWED_ORIGINS_LIST}")

    response = await call_next(request)
    return response


# Log allowed origins on startup
@app.on_event("startup")
async def startup_event():
    logger.info(f"API started with allowed origins: {ALLOWED_ORIGINS_LIST}")


# Simple in-memory rate limiting
request_counts = {}


# Request models
class JobRequest(BaseModel):
    data: dict[str, Any]
    title: str | None = None
    source: str | None = None
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

    if request.headers.get("x-bypass-ratelimit", "") == RATE_LIMIT_BYPASS_KEY:
        logger.info("Bypassing rate limiting because RATE_LIMIT_BYPASS_KEY was set")
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


async def ping_topoprint_async(topoprint_host, request_id=None):
    """Asynchronously ping the topoprint endpoint with enhanced exception logging

    Args:
        topoprint_host (str): The host URL for topoprint
        request_id (str, optional): Unique identifier to track this specific request

    Returns:
        str: Status of the ping ("scheduled", "unscheduled", or "error")
    """
    request_id = request_id or uuid.uuid4().hex[:8]
    logger.info(f"[{request_id}] Starting topoprint ping to host: {topoprint_host}")

    try:
        async with httpx.AsyncClient() as client:
            run_the_queue_url = f"{topoprint_host}/run-the-queue"

            logger.info(f"[{request_id}] Pinging topoprint endpoint: {run_the_queue_url}")

            response = await client.post(
                run_the_queue_url,
                timeout=60.0,
                headers={"X-Request-ID": request_id},
            )

            if response.status_code == 200:
                logger.info(f"[{request_id}] Successfully pinged topoprint endpoint")
                return "scheduled"

            logger.warning(
                f"[{request_id}] Topoprint queue ping failed with status code: {response.status_code}, "
                f"Response: {response.text[:200]}",
            )
            return "unscheduled"

    except httpx.TimeoutException as e:
        # Log with both string representation and exception info
        logger.error(
            f"[{request_id}] Timeout while pinging topoprint endpoint: {e!r}",
            exc_info=True,
        )
        return "error"
    except httpx.RequestError as e:
        logger.error(
            f"[{request_id}] Network error while pinging topoprint endpoint: {e!r}",
            exc_info=True,
        )
        return "error"
    except Exception as e:
        # Log multiple representations of the exception
        error_message = (
            f"[{request_id}] Unexpected error while pinging topoprint endpoint:\n"
            f"Type: {type(e).__name__}\n"
            f"Repr: {e!r}\n"
            f"Str: {e!s}"
        )
        logger.error(error_message, exc_info=True)
        return "error"


# Routes
@app.post("/create-job", response_model=JobResponse, status_code=201)
async def create_job(
    job_request: JobRequest,
    rate_limit: None = Depends(check_rate_limit),
    queue: GithubQueue = Depends(get_queue),
):
    """Create a new job in the queue"""
    # Check if TOPOPRINT_HOST is overloaded
    if TOPOPRINT_HOST:
        try:
            async with httpx.AsyncClient() as client:
                status_url = f"{TOPOPRINT_HOST}/cluster/status"
                logger.info(f"Checking cluster status at: {status_url}")
                response = await client.get(status_url, timeout=10.0)

                if response.status_code != 200:
                    logger.warning(f"Cluster status check failed with status code: {response.status_code}")
                    raise HTTPException(
                        status_code=503,
                        detail=f"Service is temporarily unavailable (cluster status code={response.status_code})",
                    )

                status_data = response.json()
                if not status_data.get("status") == "healthy":
                    logger.warning(f"Cluster reported unhealthy status: {status_data}")
                    raise HTTPException(status_code=503, detail="Service may be overloaded")

                logger.info("Cluster status check passed")
        except Exception as e:
            logger.error(f"Failed to check cluster status: {e!s}")
            raise HTTPException(status_code=503, detail=f"Service is temporarily unavailable (error={e!s})")
    else:
        raise HTTPException(status_code=503, detail="Service host is undefined")

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

        # Start async task to ping topoprint without waiting for result
        processing_status = "unknown"
        assert TOPOPRINT_HOST, "unknown TOPOPRINT_HOST"

        # Create a background task that won't block the response
        asyncio.create_task(ping_topoprint_async(TOPOPRINT_HOST))
        processing_status = "scheduled"
        logger.info(f"created task for {TOPOPRINT_HOST}")

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
