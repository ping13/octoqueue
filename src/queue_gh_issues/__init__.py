"""Documentation about queue_gh_issues."""

import logging

logging.getLogger(__name__).addHandler(logging.NullHandler())

__author__ = "Stephan Heuel"
__email__ = "mail@ping13.net"
__version__ = "0.1.0"

from .gh_queue import *
