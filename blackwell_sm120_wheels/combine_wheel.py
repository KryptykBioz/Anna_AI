"""
combine_wheels.py - Reassemble split .whl parts back into original files
Verifies SHA256 hashes for each part and the final assembled file.
Usage: python combine_wheels.py [--dir PATH] [--out PATH] [--no-verify]
"""

import os
import sys
import json
import hashlib
import argparse
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while buf := f.read(chunk_size):
            h.update(buf)
    return h.hexdigest()


def combine_file(entry: dict, parts_dir: Path, out_dir: Path, verify: bool) -> bool:
    original_name = entry["original_filename"]
    expected_size = entry["original_size"]
    expected_hash = entry["original_sha256"]
    parts = sorted(entry["parts"], key=lambda p: p["index"])

    out_path = out_dir / original_name
    print(f"Assembling: {original_name} ({len(parts)} parts)")

    with open(out_path, "wb") as out_f:
        for part in parts:
            part_path = parts_dir / part["filename"]
            if not part_path.exists():
                print(f"  [Warning] Missing part: {part['filename']}")
                return False

            data = part_path.read_bytes()

            if verify:
                actual = sha256_bytes(data)
                if actual != part["sha256"]:
                    print(f"  [Warning] Hash mismatch on part {part['index']}: {part['filename']}")
                    print(f"    Expected: {part['sha256']}")
                    print(f"    Got:      {actual}")
                    return False

            out_f.write(data)

    actual_size = out_path.stat().st_size
    if actual_size != expected_size:
        print(f"  [Warning] Size mismatch: expected {expected_size}, got {actual_size}")
        return False

    if verify:
        print(f"  Verifying final file hash...")
        actual_hash = sha256_file(out_path)
        if actual_hash != expected_hash:
            print(f"  [Warning] Final hash mismatch!")
            print(f"    Expected: {expected_hash}")
            print(f"    Got:      {actual_hash}")
            return False
        print(f"  [Confirmed] Hash verified: {actual_hash[:16]}...")

    print(f"  [Confirmed] {original_name} ({actual_size / 1e6:.1f} MB)")
    return True


def main():
    parser = argparse.ArgumentParser(description="Combine split .whl parts into original files")
    parser.add_argument("--dir", default="wheel_parts", help="Directory containing part files and manifest.json")
    parser.add_argument("--out", default=".", help="Output directory for reassembled .whl files")
    parser.add_argument("--no-verify", action="store_true", help="Skip SHA256 verification (faster)")
    args = parser.parse_args()

    parts_dir = Path(args.dir).resolve()
    out_dir = Path(args.out).resolve()
    verify = not args.no_verify

    manifest_path = parts_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"[Warning] manifest.json not found in {parts_dir}")
        sys.exit(1)

    manifest = json.loads(manifest_path.read_text())
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Parts directory: {parts_dir}")
    print(f"Output directory: {out_dir}")
    print(f"Verification: {'enabled' if verify else 'disabled'}\n")

    success_count = 0
    for entry in manifest["files"]:
        ok = combine_file(entry, parts_dir, out_dir, verify)
        if ok:
            success_count += 1
        else:
            print(f"  [Warning] Failed to assemble: {entry['original_filename']}")
        print()

    total = len(manifest["files"])
    print(f"[Confirmed] {success_count}/{total} file(s) assembled successfully.")
    if success_count < total:
        sys.exit(1)


if __name__ == "__main__":
    main()