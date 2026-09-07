"""Put the test directory on the path so shared stand-ins are importable."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
