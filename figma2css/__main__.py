"""Allow ``python -m figma2css``."""

import sys

from .cli import main

sys.exit(main())
