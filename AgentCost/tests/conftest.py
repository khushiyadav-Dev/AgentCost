"""Point the app at a throwaway SQLite file before anything imports db."""

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="agentcost-test-"))
os.environ["AGENTCOST_DB"] = str(_TMP / "test.db")
os.environ["AGENTCOST_BUDGET"] = "5.00"

# make the project root importable
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
