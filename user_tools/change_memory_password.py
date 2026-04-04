# Filename: change_memory_password.py
"""
Memory Password Change Utility
Run from the project root while the agent is stopped.

Usage:
    python change_memory_password.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from BASE.recall.memory_encryption import change_password, recover_pending_writes

MEMORY_DIR = Path("personality") / "memory"

if __name__ == "__main__":
    print("=" * 60)
    print("  Anna AI — Memory Password Change")
    print("  Run this only while the agent is stopped.")
    print("=" * 60)

    recover_pending_writes(MEMORY_DIR)
    success = change_password(MEMORY_DIR)
    sys.exit(0 if success else 1)
