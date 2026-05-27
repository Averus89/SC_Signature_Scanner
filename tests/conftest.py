"""Shared pytest fixtures."""
import sys
from pathlib import Path

# Make the project root importable so tests can `import scanner`, `import live_capture`, etc.
sys.path.insert(0, str(Path(__file__).parent.parent))
