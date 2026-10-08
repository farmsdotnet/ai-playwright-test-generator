"""Self-tests for the pipeline itself (not the generated tests). Run from the project root:

    python -m pytest selftests -v

No Claude Code login, network or browser needed - Claude Code is replaced by a fake `claude`
executable in test_cli_dry_run.py, and everything else is plain Python.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
