# decrypt_memory.py  (run from project root)
# Usage: python decrypt_memory.py

import json
import getpass
from pathlib import Path
from BASE.recall.memory_encryption import load_encrypted_with_fallback, _derive_key

MEMORY_DIR = Path("personality/memory")
FILES = ["short_memory.json", "medium_memory.json", "long_memory.json"]

salt = bytes.fromhex((MEMORY_DIR / ".salt").read_text().strip())
password = getpass.getpass("Memory password: ")
key = _derive_key(password, salt)

for filename in FILES:
    path = MEMORY_DIR / filename
    if not path.exists():
        print(f"{filename}: not found")
        continue
    try:
        plaintext = load_encrypted_with_fallback(path, key)
        if plaintext is None:
            print(f"{filename}: empty")
            continue
        data = json.loads(plaintext.decode("utf-8"))
        print(f"\n{'='*60}")
        print(f"  {filename}  ({len(data)} entries)")
        print(f"{'='*60}")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"{filename}: failed to decrypt — {e}")

