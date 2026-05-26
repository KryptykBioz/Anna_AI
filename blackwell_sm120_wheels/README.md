# Blackwell sm_120 Custom Wheels

Pre-built Python wheels for PyTorch and PyAudio with NVIDIA Blackwell (sm_120) architecture support — for RTX 50-series GPUs. These wheels are not officially distributed and must be either built from source or downloaded and reassembled from the parts provided here.

**Included wheels:**
- `PyAudio-0.2.14-cp311-cp311-win_amd64.whl`
- `torch-2.9.1-cp311-cp311-win_amd64.whl`
- `torchaudio-2.9.1-cp311-cp311-win_amd64.whl`
- `torchvision-0.24.1-cp311-cp311-win_amd64.whl`

> Requires **Python 3.11**, **Windows x64**, and an **RTX 50-series GPU**.

---

## Downloading and Reassembling

Because these files exceed GitHub's 100MB file size limit, each wheel has been split into parts. A `manifest.json` file is included with hash data used to verify the integrity of every part and the final assembled file.

### Requirements

- Python 3.x (any version, no dependencies)

### Steps

**1. Clone or download this repository.**

**2. Run the combine script:**

```
python combine_wheels.py --dir wheel_parts --out assembled_wheels
```

This will:
- Read `wheel_parts/manifest.json`
- Verify the SHA256 hash of each part
- Assemble the original `.whl` files into `assembled_wheels/`
- Verify the SHA256 hash of each final file

**3. Install the wheels:**

Install in this order to satisfy dependencies:

```
pip install assembled_wheels/torch-2.9.1-cp311-cp311-win_amd64.whl
pip install assembled_wheels/torchaudio-2.9.1-cp311-cp311-win_amd64.whl
pip install assembled_wheels/torchvision-0.24.1-cp311-cp311-win_amd64.whl
pip install assembled_wheels/PyAudio-0.2.14-cp311-cp311-win_amd64.whl
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--dir` | `wheel_parts` | Directory containing part files and `manifest.json` |
| `--out` | `.` | Output directory for reassembled `.whl` files |
| `--no-verify` | off | Skip SHA256 verification (faster, not recommended) |

---

## For Maintainers — Splitting New Wheels

If you have rebuilt the wheels and need to re-split them for upload, use `split_wheels.py`.

### Steps

**1. Place your `.whl` files in a folder.**

**2. Run the split script:**

```
python split_wheels.py --dir path/to/wheels --out wheel_parts
```

This will:
- Split each `.whl` into parts under 95 MB
- Write a `manifest.json` with per-part and per-file SHA256 hashes
- Output everything into the `wheel_parts/` directory

**3. Commit and push the contents of `wheel_parts/` to the repository.**

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--dir` | `.` | Directory containing `.whl` files to split |
| `--out` | `wheel_parts` | Output directory for parts and manifest |
| `--size` | `95` | Maximum part size in MB |

---

## Building from Source

If you need to build these wheels yourself (e.g., for a different Python version or architecture), refer to the build instructions in [`BUILD.md`](BUILD.md).