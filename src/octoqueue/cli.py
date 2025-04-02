import logging
import os
import click
import uvicorn
from dotenv import load_dotenv


@click.group()
def cli():
    """OctoQueue CLI"""


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind the server to")
@click.option("--port", default=8080, type=int, help="Port to bind the server to")
@click.option("--repo", help="GitHub repository in the format 'owner/repo'")
@click.option("--allowed-origin", help="Allowed origin for CORS")
@click.option("--api-key", help="API key for authentication")
@click.option("--log-level", default="info", help="Logging level")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload for development")
def serve(host, port, repo, allowed_origin, api_key, log_level, reload):
    """Run the OctoQueue API server"""
    # Configure logging
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    logging.basicConfig(level=numeric_level)

    # Load environment variables from .env file
    load_dotenv()

    # Override with command line arguments if provided
    if repo:
        os.environ["GITHUB_REPO"] = repo
    if allowed_origin:
        os.environ["ALLOWED_ORIGIN"] = allowed_origin
    if api_key:
        os.environ["API_KEY"] = api_key

    # Check for required environment variables
    if "GITHUB_REPO" not in os.environ:
        click.echo("Error: GitHub repository not specified. Use --repo or set GITHUB_REPO environment variable.")
        return

    # Get port from environment variable if set (for cloud environments)
    env_port = os.environ.get("PORT")
    if env_port:
        click.echo(f"Using PORT from environment: {env_port}")
        port = int(env_port)

    click.echo(f"Using PORT: {port}")

    click.echo(f"Starting OctoQueue API server for repository: {os.environ['GITHUB_REPO']}")
    click.echo(f"Allowed origin: {os.environ.get('ALLOWED_ORIGIN', 'Not restricted')}")
    click.echo(f"API key authentication: {'Enabled' if os.environ.get('API_KEY') else 'Disabled'}")

    uvicorn.run("octoqueue.api:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    cli()
