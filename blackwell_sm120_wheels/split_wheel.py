"""
split_wheels.py - Split .whl files into GitHub-safe chunks (<100MB each)
Generates a manifest.json with file metadata and SHA256 hashes for verification.
Usage: python split_wheels.py [--dir PATH] [--out PATH] [--size MB]
"""

import os
import sys
import json
import hashlib
import argparse
from pathlib import Path

GITHUB_LIMIT_MB = 95  # Leave headroom below 100MB hard limit


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while buf := f.read(chunk_size):
            h.update(buf)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def split_file(src: Path, out_dir: Path, part_size: int) -> dict:
    total_size = src.stat().st_size
    src_hash = sha256_file(src)

    parts = []
    part_index = 0

    with open(src, "rb") as f:
        while True:
            data = f.read(part_size)
            if not data:
                break
            part_name = f"{src.name}.part{part_index:03d}"
            part_path = out_dir / part_name
            part_path.write_bytes(data)
            parts.append({
                "filename": part_name,
                "index": part_index,
                "size": len(data),
                "sha256": sha256_bytes(data),
            })
            part_index += 1

    print(f"  [{src.name}] -> {part_index} parts | {total_size / 1e6:.1f} MB | sha256: {src_hash[:16]}...")
    return {
        "original_filename": src.name,
        "original_size": total_size,
        "original_sha256": src_hash,
        "part_count": part_index,
        "parts": parts,
    }


def main():
    parser = argparse.ArgumentParser(description="Split .whl files for GitHub upload")
    parser.add_argument("--dir", default=".", help="Directory containing .whl files")
    parser.add_argument("--out", default="wheel_parts", help="Output directory for parts")
    parser.add_argument("--size", type=int, default=GITHUB_LIMIT_MB, help="Max part size in MB")
    args = parser.parse_args()

    src_dir = Path(args.dir).resolve()
    out_dir = Path(args.out).resolve()
    part_size = args.size * 1024 * 1024

    whl_files = sorted(src_dir.glob("*.whl"))
    if not whl_files:
        print(f"[Warning] No .whl files found in {src_dir}")
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {out_dir}")
    print(f"Part size limit: {args.size} MB\n")

    manifest = {"part_size_mb": args.size, "files": []}

    for whl in whl_files:
        print(f"Splitting: {whl.name}")
        entry = split_file(whl, out_dir, part_size)
        manifest["files"].append(entry)

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\n[Confirmed] Manifest written: {manifest_path}")
    print(f"[Confirmed] {len(whl_files)} file(s) split into parts in: {out_dir}")


if __name__ == "__main__":
    main()