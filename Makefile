
.PHONY: help test aider

all: help

test:		## run unittests
	uv run python -m pytest


aider:		## Start a chat with an LLM to change your code
	uvx -p 3.12 --from aider-chat aider --architect --watch-files

help:		## output help for all targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
