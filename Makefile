# Makefile for octoqueue project

.PHONY: help test test-api debug deploy run-container

all: help

test:		## run unittests
	@echo "**** ATTENTION: make sure that the tests are not run somewehere else (like in a CI/CD pipeline) due to side effects"
	uv run python -m pytest -x

debug:		## run the API server in debug mode
	uv run -m octoqueue.cli serve --port 8080 --reload

test-api:	## test the API with a simple curl command
	curl -X POST -H 'Content-Type: application/json' -d '{"data": {"test": true}}' localhost:8080/jobs

SERVICE_NAME=octoqueue
PROJECT_ID=topoprint
IMAGE_NAME="gcr.io/$(PROJECT_ID)/$(SERVICE_NAME)"

build: 
	docker build --platform linux/amd64 -t $(IMAGE_NAME) .

run: build ## run the container locally
	docker run -p 8080:8080 --name octoqueue --env-file .env $(IMAGE_NAME)

deploy: build	## deploy the application on Google Cloud Run
	uv run dotenv run ./deploy.sh $(SERVICE_NAME) $(PROJECT_ID) $(IMAGE_NAME)

help:		## output help for all targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
