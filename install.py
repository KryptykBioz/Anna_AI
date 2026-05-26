"""
Anna AI - Setup & Installation Script
Run via INSTALL.bat or: python INSTALL.py
Requires Python 3.11 to be installed before running.
"""

import os
import sys
import json
import time
import shutil
import struct
import platform
import subprocess
import urllib.request
from pathlib import Path
from typing import Optional

# ── Terminal colours (Windows ANSI via colorama or raw) ──────────────────────
try:
    import colorama
    colorama.init(autoreset=True)
    HAVE_COLORAMA = True
except ImportError:
    HAVE_COLORAMA = False
    os.system("color")          # enable ANSI on Windows 10+

R  = "\033[91m"
G  = "\033[92m"
Y  = "\033[93m"
B  = "\033[94m"
M  = "\033[95m"
C  = "\033[96m"
W  = "\033[97m"
DIM= "\033[2m"
RST= "\033[0m"
BOLD="\033[1m"

def c(color, text): return f"{color}{text}{RST}"

# ── Layout helpers ────────────────────────────────────────────────────────────
WIDTH = 70

def hr(ch="="):            print(c(B, ch * WIDTH))
def section(title):
    hr()
    pad = (WIDTH - len(title) - 4) // 2
    print(c(B, "=" * pad) + c(BOLD + W, f"  {title}  ") + c(B, "=" * (WIDTH - pad - len(title) - 4)))
    hr()

def ok(msg):   print(c(G,  f"  [OK]  {msg}"))
def warn(msg): print(c(Y,  f"  [!!]  {msg}"))
def err(msg):  print(c(R,  f"  [ERR] {msg}"))
def info(msg): print(c(C,  f"  [>>]  {msg}"))
def tip(msg):  print(c(DIM,f"         {msg}"))
def blank():   print()

def ask(prompt, default="y") -> bool:
    opts = f"[Y/n]" if default == "y" else f"[y/N]"
    ans = input(f"{C}  {prompt} {opts}: {RST}").strip().lower()
    if ans == "":
        return default == "y"
    return ans in ("y", "yes")

def ask_str(prompt, default="") -> str:
    disp = f" (default: {default})" if default else ""
    ans = input(f"{C}  {prompt}{disp}: {RST}").strip()
    return ans if ans else default

def pause(msg="Press Enter to continue..."):
    input(f"\n{Y}  {msg}{RST}")

def run(cmd, check=True, capture=False, env=None, cwd=None):
    kwargs = dict(shell=True, env=env, cwd=cwd)
    if capture:
        kwargs.update(capture_output=True, text=True)
    result = subprocess.run(cmd, **kwargs)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result

def run_ok(cmd, env=None, cwd=None) -> bool:
    try:
        run(cmd, check=True, capture=True, env=env, cwd=cwd)
        return True
    except Exception:
        return False

# ── Path resolution ───────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).resolve().parent
VENV_DIR    = SCRIPT_DIR / "venv"
VENV_PY     = VENV_DIR / "Scripts" / "python.exe"
VENV_PIP    = VENV_DIR / "Scripts" / "pip.exe"
REQ_FILE    = SCRIPT_DIR / "requirements.txt"
ENV_TMPL    = SCRIPT_DIR / ".env.template"
ENV_FILE    = SCRIPT_DIR / ".env"

RESULTS: dict = {}          # collects pass/fail for final summary

# ═════════════════════════════════════════════════════════════════════════════
# STEP 0 – Banner
# ═════════════════════════════════════════════════════════════════════════════
def banner():
    hr("*")
    print(c(M + BOLD, """
       █████╗ ███╗   ██╗███╗   ██╗ █████╗      █████╗ ██╗
      ██╔══██╗████╗  ██║████╗  ██║██╔══██╗    ██╔══██╗██║
      ███████║██╔██╗ ██║██╔██╗ ██║███████║    ███████║██║
      ██╔══██║██║╚██╗██║██║╚██╗██║██╔══██║    ██╔══██║██║
      ██║  ██║██║ ╚████║██║ ╚████║██║  ██║    ██║  ██║██║
      ╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═══╝╚═╝  ╚═╝    ╚═╝  ╚═╝╚═╝
    """))
    print(c(W, "                  Setup & Installation Script"))
    print(c(DIM, "              https://github.com/KryptykBioz/Anna_AI"))
    hr("*")
    blank()


# ═════════════════════════════════════════════════════════════════════════════
# STEP 1 – Pre-flight checks
# ═════════════════════════════════════════════════════════════════════════════
def check_os():
    section("SYSTEM CHECK")
    if platform.system() != "Windows":
        err("Anna AI requires Windows 10/11 (64-bit).")
        sys.exit(1)
    ok("Windows detected")

    bits = struct.calcsize("P") * 8
    if bits != 64:
        err("64-bit Python required.")
        sys.exit(1)
    ok(f"64-bit OS confirmed")

def check_python():
    major, minor, micro = sys.version_info[:3]
    ver = f"{major}.{minor}.{micro}"
    if major != 3 or minor != 11:
        warn(f"Python {ver} detected — Anna AI requires Python 3.11.x")
        warn("TTS / transformers may fail on other versions.")
        if not ask("Continue anyway?", default="n"):
            info("Download Python 3.11.9 from:")
            tip("https://www.python.org/downloads/release/python-3119/")
            sys.exit(1)
    else:
        ok(f"Python {ver}")
    return ver

def check_git():
    if shutil.which("git"):
        ok("git found")
        return True
    warn("git not found in PATH")
    tip("https://git-scm.com/download/win")
    return False

def check_ollama():
    if shutil.which("ollama"):
        ok("Ollama found in PATH")
        return True
    warn("Ollama not found")
    tip("https://ollama.ai/download")
    return False

def check_nvidia() -> tuple[bool, bool]:
    """Returns (gpu_found, is_50_series). gpu_found=False means no NVIDIA GPU."""
    if not shutil.which("nvidia-smi"):
        warn("nvidia-smi not found — no NVIDIA GPU detected, CPU-only mode")
        return False, False

    res = run(
        "nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader",
        capture=True, check=False,
    )
    if res.returncode != 0:
        warn("nvidia-smi found but query failed — treating as no GPU")
        return False, False

    for line in res.stdout.strip().splitlines():
        ok(f"GPU: {line.strip()}")

    names = res.stdout.upper()
    is_50 = any(tag in names for tag in ("RTX 50", "5060", "5070", "5080", "5090"))
    return True, is_50


# ═════════════════════════════════════════════════════════════════════════════
# STEP 2 – Venv
# ═════════════════════════════════════════════════════════════════════════════
def setup_venv():
    section("VIRTUAL ENVIRONMENT")
    if VENV_DIR.exists():
        if VENV_PY.exists():
            ok(f"venv already exists at {VENV_DIR}")
            if not ask("Recreate virtual environment?", default="n"):
                return
        warn("venv directory exists but appears broken — recreating")
        shutil.rmtree(VENV_DIR)

    info("Creating Python 3.11 virtual environment...")
    # Try py launcher first (respects version), then fallback
    created = False
    for cmd in [f'py -3.11 -m venv "{VENV_DIR}"',
                f'python3.11 -m venv "{VENV_DIR}"',
                f'python -m venv "{VENV_DIR}"']:
        if run_ok(cmd):
            created = True
            break
    if not created:
        err("Failed to create virtual environment.")
        err("Ensure Python 3.11 is installed and accessible.")
        sys.exit(1)
    ok("Virtual environment created")


# ═════════════════════════════════════════════════════════════════════════════
# STEP 3 – Dependencies
# ═════════════════════════════════════════════════════════════════════════════

# Packages that pip may install as dependencies of TTS/faster-whisper/vosk
# which must be removed before the Blackwell custom wheels are installed.
_BLACKWELL_OWNED = [
    "torch", "torchaudio", "torchvision",
    "pyaudio", "PyAudio",
]


def _purge_conflicting_packages():
    """Uninstall any pip-managed torch/pyaudio packages before Blackwell wheel install."""
    info("Checking for conflicting torch/pyaudio packages...")
    to_remove = []
    for pkg in _BLACKWELL_OWNED:
        res = run(f'"{VENV_PIP}" show {pkg}', capture=True, check=False)
        if res.returncode == 0:
            location_line = next(
                (l for l in res.stdout.splitlines() if l.startswith("Location:")), ""
            )
            to_remove.append(pkg)
            tip(f"  Found: {pkg} at {location_line.replace('Location:', '').strip()}")

    if not to_remove:
        ok("No conflicting packages found")
        return

    warn(f"Removing {len(to_remove)} conflicting package(s) before Blackwell wheel install...")
    pkg_list = " ".join(to_remove)
    run(f'"{VENV_PIP}" uninstall -y {pkg_list}', check=False)

    still_present = []
    for pkg in to_remove:
        if run_ok(f'"{VENV_PIP}" show {pkg}'):
            still_present.append(pkg)

    if still_present:
        warn(f"Could not remove: {', '.join(still_present)} — wheel install may conflict")
    else:
        ok("Conflicting packages removed")


def install_deps(is_50_series: bool = False):
    section("PYTHON DEPENDENCIES")

    if not REQ_FILE.exists():
        err(f"requirements.txt not found at {REQ_FILE}")
        sys.exit(1)

    info("Upgrading pip...")
    run(f'"{VENV_PY}" -m pip install --upgrade pip --quiet', check=True)
    ok("pip upgraded")

    core_probe = "import numpy, sounddevice, faster_whisper, TTS, discord, websockets"
    already_ok = run_ok(f'"{VENV_PY}" -c "{core_probe}"')

    if already_ok and not is_50_series:
        ok("Core packages already installed — skipping requirements.txt")
    else:
        if is_50_series:
            info("Installing requirements.txt — torch/pyaudio will be replaced by Blackwell wheels after...")
            tip("TTS and faster-whisper will pull in CPU torch as a dep; it will be purged next step.")
        else:
            info("Installing requirements.txt (this may take 10-20 minutes)...")
            tip("Large downloads: TTS, faster-whisper, numpy, scipy, etc.")
        try:
            run(f'"{VENV_PIP}" install -r "{REQ_FILE}"', check=True)
            ok("requirements.txt installed")
        except subprocess.CalledProcessError:
            warn("Some packages may have failed — check output above")
            warn("Re-running with verbose output for diagnostics...")
            run(f'"{VENV_PIP}" install -r "{REQ_FILE}"', check=False)

    tfm_probe = 'import transformers; assert transformers.__version__ == "4.38.2", transformers.__version__'
    if run_ok(f'"{VENV_PY}" -c "{tfm_probe}"'):
        ok("transformers==4.38.2 already installed — skipping pin")
    else:
        info("Pinning transformers==4.38.2 (XTTS compatibility)...")
        try:
            run(f'"{VENV_PIP}" install transformers==4.38.2 --quiet', check=True)
            ok("transformers==4.38.2 installed")
        except subprocess.CalledProcessError:
            err("Failed to pin transformers — XTTS voice may not work")

    RESULTS["python_deps"] = True


# ═════════════════════════════════════════════════════════════════════════════
# STEP 4 – GPU packages (RTX 50-series / Blackwell sm_120 aware)
# ═════════════════════════════════════════════════════════════════════════════

BLACKWELL_WHEELS_DIR = SCRIPT_DIR / "blackwell_sm120_wheels"
BLACKWELL_PARTS_DIR  = BLACKWELL_WHEELS_DIR / "wheel_parts"
BLACKWELL_ASSEMBLED  = BLACKWELL_WHEELS_DIR / "assembled"

_WHEEL_INSTALL_ORDER = ["torch", "torchaudio", "torchvision", "PyAudio"]


def _assemble_blackwell_wheels() -> list[Path]:
    import hashlib, json as _json

    manifest_path = BLACKWELL_PARTS_DIR / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"manifest.json not found in {BLACKWELL_PARTS_DIR}")

    manifest = _json.loads(manifest_path.read_text())
    BLACKWELL_ASSEMBLED.mkdir(parents=True, exist_ok=True)

    assembled = []
    for entry in manifest["files"]:
        out_path = BLACKWELL_ASSEMBLED / entry["original_filename"]

        if out_path.exists() and out_path.stat().st_size == entry["original_size"]:
            h = hashlib.sha256()
            with open(out_path, "rb") as f:
                while buf := f.read(1 << 20):
                    h.update(buf)
            if h.hexdigest() == entry["original_sha256"]:
                ok(f"  Already assembled: {entry['original_filename']}")
                assembled.append(out_path)
                continue
            warn(f"  Hash mismatch on existing file — reassembling: {entry['original_filename']}")
            out_path.unlink()

        info(f"  Assembling: {entry['original_filename']} ({entry['part_count']} parts)")
        parts = sorted(entry["parts"], key=lambda p: p["index"])

        with open(out_path, "wb") as out_f:
            for part in parts:
                part_path = BLACKWELL_PARTS_DIR / part["filename"]
                if not part_path.exists():
                    raise RuntimeError(f"Missing part: {part['filename']}")
                data = part_path.read_bytes()
                actual = hashlib.sha256(data).hexdigest()
                if actual != part["sha256"]:
                    raise RuntimeError(
                        f"Part hash mismatch: {part['filename']}\n"
                        f"  expected {part['sha256']}\n  got      {actual}"
                    )
                out_f.write(data)

        h = hashlib.sha256()
        with open(out_path, "rb") as f:
            while buf := f.read(1 << 20):
                h.update(buf)
        final_hash = h.hexdigest()
        if final_hash != entry["original_sha256"]:
            raise RuntimeError(
                f"Final hash mismatch: {entry['original_filename']}\n"
                f"  expected {entry['original_sha256']}\n  got      {final_hash}"
            )
        ok(f"  [Confirmed] {entry['original_filename']} ({out_path.stat().st_size / 1e6:.1f} MB)")
        assembled.append(out_path)

    return assembled


def _install_blackwell_wheels(assembled: list[Path]):
    wheel_map = {p.name.split("-")[0].lower(): p for p in assembled}

    install_order = []
    seen = set()
    for key in _WHEEL_INSTALL_ORDER:
        match = wheel_map.get(key.lower())
        if match:
            install_order.append(match)
            seen.add(match)
    for p in assembled:
        if p not in seen:
            install_order.append(p)

    for whl in install_order:
        info(f"  Installing: {whl.name}")
        try:
            run(f'"{VENV_PIP}" install "{whl}" --no-deps --force-reinstall --quiet', check=True)
            ok(f"  Installed: {whl.name}")
        except subprocess.CalledProcessError:
            warn(f"  --no-deps install failed, retrying with deps: {whl.name}")
            run(f'"{VENV_PIP}" install "{whl}" --force-reinstall --quiet', check=False)


def setup_gpu(gpu_found: bool, is_50_series: bool) -> bool:
    section("GPU / PYTORCH SETUP")

    torch_probe = 'import torch; assert torch.cuda.is_available(), "no cuda"'
    if run_ok(f'"{VENV_PY}" -c "{torch_probe}"'):
        ok("PyTorch with CUDA already installed — skipping GPU package step")
        _verify_torch()
        return True

    if not gpu_found:
        warn("No NVIDIA GPU detected — installing CPU-only PyTorch.")
        tip("TTS, Whisper, and vision will run on CPU. Image generation unavailable.")
        try:
            run(f'"{VENV_PIP}" install torch torchvision torchaudio --quiet', check=True)
            ok("PyTorch (CPU-only) installed")
        except subprocess.CalledProcessError:
            warn("PyTorch CPU install failed — agent may still run without torch")
        _verify_torch(cpu_only=True)
        RESULTS["torch"] = False
        return False

    if is_50_series:
        warn("RTX 50-series GPU (sm_120 / Blackwell) detected.")
        blank()

        has_parts = (BLACKWELL_PARTS_DIR / "manifest.json").exists()

        if has_parts:
            info("Blackwell wheel parts found — preparing install...")
            blank()
            _purge_conflicting_packages()
            blank()
            try:
                info("Assembling wheels from parts...")
                assembled = _assemble_blackwell_wheels()
                blank()
                info(f"Installing {len(assembled)} Blackwell wheel(s) into venv...")
                _install_blackwell_wheels(assembled)
                ok("Blackwell sm_120 wheels installed successfully")
                _verify_torch()
                RESULTS["torch"] = True
                return True
            except RuntimeError as e:
                err(f"Wheel assembly failed: {e}")
                blank()
                warn("Falling back to manual options...")

        blank()
        print(c(W,  "  No compatible sm_120 wheel parts found in:"))
        print(c(DIM, f"  {BLACKWELL_PARTS_DIR}"))
        blank()
        print(c(W,  "  To use GPU acceleration with Anna AI on an RTX 50-series card,"))
        print(c(W,  "  download the blackwell_sm120_wheels repository and place it"))
        print(c(W,  "  in the project root, then re-run this installer."))
        blank()
        print(c(DIM, "  https://github.com/KryptykBioz/pytorch-blackwell-sm120-wheels"))
        blank()
        print(c(Y,  "  OR continue in CPU-only mode (GPU tools will run on CPU and may be slow)."))
        blank()

        if not ask("Continue in CPU-only mode?", default="n"):
            info("Exiting installer.")
            tip("Re-run INSTALL.bat after placing Blackwell wheel parts in the project root.")
            sys.exit(0)

        warn("Continuing in CPU-only mode.")
        warn("TTS, Whisper, and vision will run on CPU — expect slower performance.")
        warn("Image generation (Stable Diffusion) will be unavailable.")
        try:
            run(f'"{VENV_PIP}" install torch torchvision torchaudio --quiet', check=True)
            ok("PyTorch (CPU-only) installed")
        except subprocess.CalledProcessError:
            warn("PyTorch CPU install failed — agent may still run without torch")
        _verify_torch(cpu_only=True)
        RESULTS["torch"] = False
        return False

    info("Compatible NVIDIA GPU detected — installing PyTorch with CUDA 12.6...")
    try:
        run(f'"{VENV_PIP}" install torch torchvision torchaudio pyaudio '
            f'--index-url https://download.pytorch.org/whl/cu126 --quiet', check=True)
        ok("PyTorch (cu126) + PyAudio installed")
    except subprocess.CalledProcessError:
        warn("Standard PyTorch install failed — trying nightly build...")
        run(f'"{VENV_PIP}" install --pre torch torchvision torchaudio '
            f'--index-url https://download.pytorch.org/whl/nightly/cu126 --quiet', check=False)

    _verify_torch()
    return True

def _verify_torch(cpu_only: bool = False):
    import os as _os
    import tempfile

    if cpu_only:
        info("Verifying PyTorch (CPU-only)...")
        script = (
            "import torch\n"
            "print('Version:', torch.__version__)\n"
            "print('CUDA: False')\n"
        )
    else:
        info("Verifying PyTorch CUDA support...")
        script = (
            "import torch\n"
            "print('CUDA:', torch.cuda.is_available())\n"
            "print('Version:', torch.__version__)\n"
            "n = torch.cuda.device_count()\n"
            "print('Device count:', n)\n"
            "for i in range(n):\n"
            "    print('GPU', i, ':', torch.cuda.get_device_name(i))\n"
        )

    cuda_paths = [
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0\bin\x64",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0\bin",
        r"C:\Program Files\NVIDIA\CUDNN\v9.16\bin\13.0",
    ]
    env = _os.environ.copy()
    extra = ";".join(p for p in cuda_paths if _os.path.isdir(p))
    if extra:
        env["PATH"] = extra + ";" + env.get("PATH", "")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tf:
        tf.write(script)
        tf_path = tf.name

    try:
        res = run(f'"{VENV_PY}" "{tf_path}"', capture=True, check=False, env=env)
    finally:
        try:
            _os.unlink(tf_path)
        except OSError:
            pass

    if res.returncode == 0:
        for line in res.stdout.strip().splitlines():
            ok(f"  {line}")
        RESULTS["torch"] = not cpu_only and "CUDA: True" in res.stdout
    else:
        warn("PyTorch verification failed — check GPU drivers")
        if res.stderr:
            for line in res.stderr.strip().splitlines()[-10:]:
                tip(f"  {line}")
        if res.stdout:
            for line in res.stdout.strip().splitlines():
                tip(f"  {line}")
        RESULTS["torch"] = False


# ═════════════════════════════════════════════════════════════════════════════
# STEP 5 – Ollama
# ═════════════════════════════════════════════════════════════════════════════
def setup_ollama(ollama_found: bool):
    section("OLLAMA SETUP")

    if not ollama_found:
        warn("Ollama is not installed.")
        info("Download and install from: https://ollama.ai/download")
        tip("Run this installer again after installing Ollama.")
        if not ask("Skip Ollama setup and continue?", default="y"):
            sys.exit(0)
        RESULTS["ollama"] = False
        return

    info("Starting Ollama service...")
    subprocess.Popen(
        "ollama serve",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    time.sleep(3)

    _pull_models()
    RESULTS["ollama"] = True


def _installed_models() -> set:
    res = run("ollama list", capture=True, check=False)
    if res.returncode != 0:
        return set()
    installed = set()
    for line in res.stdout.strip().splitlines()[1:]:   # skip header
        parts = line.split()
        if parts:
            installed.add(parts[0])
    return installed


def _pull_models():
    CORE_MODELS = [
        ("gemma4:latest",          "~7GB"),
        ("nomic-embed-text:latest","~275MB"),
    ]
    OPTIONAL_MODELS = [
        ("qwen3-vl:8b-instruct-q4_K_M", "~5GB"),
        ("qwen3-vl:8b-thinking-q4_K_M", "~5GB"),
    ]

    installed = _installed_models()

    blank()
    info("Core models (required for basic operation):")
    for name, size in CORE_MODELS:
        status = c(G, "[installed]") if name in installed else c(Y, f"[not found] {size}")
        print(f"    {c(W, f'{name:<45}')} {status}")
    blank()

    need_core = [m for m, _ in CORE_MODELS if m not in installed]
    if not need_core:
        ok("All core models already installed — skipping pull")
    elif ask("Pull missing core Ollama models now?", default="y"):
        for name in need_core:
            info(f"Pulling {name}...")
            if not run_ok(f"ollama pull {name}"):
                warn(f"Failed to pull {name} — pull manually: ollama pull {name}")
            else:
                ok(f"{name} ready")

    blank()
    info("Optional vision models:")
    for name, size in OPTIONAL_MODELS:
        status = c(G, "[installed]") if name in installed else c(Y, f"[not found] {size}")
        print(f"    {c(W, f'{name:<45}')} {status}")
    blank()

    need_opt = [m for m, _ in OPTIONAL_MODELS if m not in installed]
    if not need_opt:
        ok("All optional models already installed — skipping")
    elif ask("Pull optional vision models?", default="n"):
        for name in need_opt:
            info(f"Pulling {name}...")
            run(f"ollama pull {name}", check=False)
            ok(f"{name} done")


# ═════════════════════════════════════════════════════════════════════════════
# STEP 6 – .env file
# ═════════════════════════════════════════════════════════════════════════════
def setup_env():
    section("ENVIRONMENT CONFIGURATION (.env)")

    if ENV_FILE.exists():
        content = ENV_FILE.read_text(encoding="utf-8")
        if "Configured by INSTALL.py" in content:
            ok(".env already configured by installer -- skipping")
            RESULTS["env"] = True
            return
        ok(f".env exists (not previously configured by installer)")
        if not ask("Overwrite existing .env?", default="n"):
            RESULTS["env"] = True
            return

    if not ENV_TMPL.exists():
        warn("_env.template not found — cannot create .env")
        return

    blank()
    print(c(W, "  Select your GPU VRAM tier for Ollama tuning:"))
    print(c(W, "    1) 8GB  VRAM  (single GPU, lower context)"))
    print(c(W, "    2) 12GB VRAM  (balanced)"))
    print(c(W, "    3) 16GB+ VRAM (high context, multiple models)"))
    blank()
    tier = ask_str("VRAM tier", default="2")

    ctx_map    = {"1": "4096",  "2": "8192",  "3": "16384"}
    oh_map     = {"1": "512",   "2": "1024",  "3": "2048"}
    models_map = {"1": "1",     "2": "2",     "3": "3"}

    ctx    = ctx_map.get(tier, "8192")
    oh     = oh_map.get(tier, "1024")
    models = models_map.get(tier, "2")

    # Keys to uncomment and optionally override with tier values
    # Maps uncommented key -> value to set (None = use template default)
    ollama_overrides = {
        "OLLAMA_NUM_PARALLEL":         "1",
        "OLLAMA_CONTEXT_LENGTH":       ctx,
        "OLLAMA_FLASH_ATTENTION":      "true",
        "CUDA_VISIBLE_DEVICES":        "0",
        "OLLAMA_GPU_OVERHEAD":         oh,
        "OLLAMA_KEEP_ALIVE":           "24h",
        "OLLAMA_LOAD_TIMEOUT":         "5m",
        "OLLAMA_MAX_QUEUE":            "128",
        "OLLAMA_NUM_THREADS":          "6",
        "OLLAMA_MAX_LOADED_MODELS":    models,
        "OLLAMA_CONCURRENT_REQUESTS":  "1",
        "OLLAMA_ORIGINS":              "*",
        "OLLAMA_DEBUG":                "false",
        # AGENT_* variants
        "AGENT_OLLAMA_KEEP_ALIVE":           "24h",
        "AGENT_OLLAMA_NUM_PARALLEL":         "1",
        "AGENT_OLLAMA_MAX_LOADED_MODELS":    models,
        "AGENT_OLLAMA_CONCURRENT_REQUESTS":  "1",
    }

    lines = ENV_TMPL.read_text(encoding="utf-8").splitlines()
    out   = ["# Configured by INSTALL.py"]

    for line in lines:
        stripped = line.lstrip("# ").strip()
        if "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in ollama_overrides:
                val = ollama_overrides[key]
                out.append(f"{key}={val}")
                continue
        out.append(line)

    ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")
    ok(f".env configured (VRAM tier {tier}: ctx={ctx}, max_models={models})")
    RESULTS["env"] = True

def setup_identity():
    section("AGENT IDENTITY")

    print(c(W, "  These values set the agent's name and how it addresses you."))
    print(c(W, "  They can be changed later in .env or personality/bot_info.py."))
    blank()

    agent_name = ask_str("Agent name", default="Anna")
    user_name  = ask_str("Your name (how the agent addresses you)", default="User")

    if not ENV_FILE.exists():
        warn(".env not found -- skipping identity configuration")
        RESULTS["identity"] = False
        return

    content = ENV_FILE.read_text(encoding="utf-8")

    for key, val in (("AGENT_BOT_NAME", agent_name), ("AGENT_BOT_USERNAME", user_name)):
        import re
        # Replace existing uncommented key
        pattern = re.compile(rf"^{key}=.*$", re.MULTILINE)
        if pattern.search(content):
            content = pattern.sub(f"{key}={val}", content)
        # Uncomment commented key
        elif re.search(rf"^#\s*{key}=", content, re.MULTILINE):
            content = re.sub(rf"^#\s*{key}=.*$", f"{key}={val}", content, flags=re.MULTILINE)
        # Append if not present at all
        else:
            content = content.rstrip("\n") + f"\n{key}={val}\n"

    ENV_FILE.write_text(content, encoding="utf-8")
    ok(f"Agent name: {agent_name}")
    ok(f"User name:  {user_name}")
    RESULTS["identity"] = True

# ═════════════════════════════════════════════════════════════════════════════
# STEP 7 – Optional: VB-Audio / Tala cables
# ═════════════════════════════════════════════════════════════════════════════
def setup_audio():
    section("VIRTUAL AUDIO CABLES (optional)")

    # Detect VB-Audio cable via sounddevice if available
    vb_detected = False
    probe = (
        'import sounddevice as sd; '
        'devs = [d["name"] for d in sd.query_devices()]; '
        'found = any("CABLE" in d for d in devs); '
        'print("found" if found else "missing")'
    )
    res = run(f'"{VENV_PY}" -c "{probe}"', capture=True, check=False)
    if res.returncode == 0 and "found" in res.stdout:
        vb_detected = True
        ok("VB-Audio CABLE device already detected in Windows audio devices")
        if not ask("Re-run VB-Audio setup anyway?", default="n"):
            _audio_routing_reminder()
            return

    print(c(W, """
  Virtual audio cables route TTS speech to the avatar for lip-sync animation.
  Required for avatar speech. Not needed for text-only operation.
"""))

    if not ask("Open VB-Audio Cable download page?", default="y"):
        info("Skipping VB-Audio setup")
        print(c(DIM, "  Install manually: https://vb-audio.com/Cable/"))
        return

    import webbrowser
    webbrowser.open("https://vb-audio.com/Cable/")
    blank()
    print(c(Y, "  Manual steps required:"))
    print(c(W, "  1. Download VBCABLE_Driver_Pack*.zip"))
    print(c(W, "  2. Extract and right-click VBCABLE_Setup_x64.exe"))
    print(c(W, "  3. Run as Administrator -> Install Driver"))
    print(c(W, "  4. Restart your PC after installation"))
    blank()

    if ask("Open Tala Virtual Audio Cables page (for multi-agent)?", default="n"):
        webbrowser.open("https://github.com/Essence-Platform/TalaVirtualAudioCables-Public")
        print(c(W, "  Download TalaVirtualAudioCables.zip and run installer as Admin"))

    _audio_routing_reminder()


def _audio_routing_reminder():
    blank()
    info("Audio routing settings go in personality/bot_info.py:")
    tip('  vb_cable_name = "CABLE Input"   # must match exact Windows device name')
    blank()
    print(c(Y, "  After installation, configure Windows audio:"))
    print(c(W, "  Settings -> Sound -> More Sound Settings -> Recording tab"))
    print(c(W, "  Double-click CABLE Output -> 'Listen to this device' -> Playback: Default"))


# ═════════════════════════════════════════════════════════════════════════════
# STEP 8 – Optional: AI Agent Tools
# ═════════════════════════════════════════════════════════════════════════════
TOOL_REPOS = [
    "duckduckgo_search",
    "minecraft",
    "unity_controller",
    "game_guide",
    "notes",
    "user_details",
    "bing_search",
    "game_vision",
    "opencv_vision",
    "warudo",
    "calculator",
    "group_chat",
    "reminders",
    "web_fetch",
    "calendar",
    "image_generator",
    "screenshot_vision",
    "wiki_search",
    "canvas",
    "internet_search",
    "sound_effects",
    "youtube_chat",
    "dice_roller",
    "league_of_legends",
    "system_info",
    "discord_bot",
    "mcp_bridge",
    "twitch_chat",
    "discord_chat",
    "memory_search",
]

def _tool_checkbox_prompt() -> list[str]:
    total = len(TOOL_REPOS)
    cols  = 2
    col_w = 38

    print(c(W, "\n  Enter numbers separated by commas, ranges (e.g. 1-5),"))
    print(c(W,  "  'all' to select everything, or leave blank to skip.\n"))

    for i, name in enumerate(TOOL_REPOS, 1):
        label = f"  [{i:>2}] {name}"
        if i % cols == 1 and i + 1 <= total:
            print(c(C, f"{label:<{col_w}}"), end="")
        else:
            print(c(C, label))
    if total % cols == 1:
        print()

    blank()
    raw = input(f"{Y}  Selection: {RST}").strip().lower()
    if not raw:
        return []
    if raw == "all":
        return list(TOOL_REPOS)

    selected: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if "-" in part:
            try:
                lo, hi = part.split("-", 1)
                selected.update(range(int(lo), int(hi) + 1))
            except ValueError:
                warn(f"Ignoring invalid range: {part}")
        else:
            try:
                selected.add(int(part))
            except ValueError:
                warn(f"Ignoring invalid entry: {part}")

    return [TOOL_REPOS[i - 1] for i in sorted(selected) if 1 <= i <= total]


def setup_tools(git_found: bool):
    section("AI AGENT TOOLS (optional)")

    print(c(W, """
  Select individual tool modules to install into BASE/tools/installed/.
  Each tool is cloned from its own GitHub repository.
  Tools can also be installed manually at any time.
"""))

    if not git_found:
        warn("git not found — cannot clone tool repositories")
        tip("Install git from https://git-scm.com/download/win then re-run")
        RESULTS["tools"] = False
        return

    selected = _tool_checkbox_prompt()

    if not selected:
        info("No tools selected — skipping")
        tip("Install manually: git clone https://github.com/KryptykBioz/ANNA-tool-<name> BASE/tools/installed/<name>")
        RESULTS["tools"] = True
        return

    tools_dest = SCRIPT_DIR / "BASE" / "tools" / "installed"
    tools_dest.mkdir(parents=True, exist_ok=True)

    base_url = "https://github.com/KryptykBioz/ANNA-tool-"
    ok_count = fail_count = skip_count = 0

    blank()
    info(f"Installing {len(selected)} tool(s) to {tools_dest} ...")
    blank()

    for name in selected:
        dest = tools_dest / name
        repo_url = f"{base_url}{name}.git"

        if dest.exists() and (dest / ".git").exists():
            ok(f"  {name:<28} already installed — skipping")
            skip_count += 1
            continue

        if dest.exists():
            warn(f"  {name:<28} directory exists (no .git) — removing and re-cloning")
            shutil.rmtree(dest)

        info(f"  Cloning {name} ...")
        res = run(f'git clone --depth 1 "{repo_url}" "{dest}"', capture=True, check=False)
        if res.returncode == 0:
            ok(f"  {name:<28} installed")
            ok_count += 1
        else:
            warn(f"  {name:<28} FAILED")
            tip(f"    {repo_url}")
            if res.stderr:
                tip(f"    {res.stderr.strip().splitlines()[-1]}")
            fail_count += 1

    blank()
    ok(f"Tools: {ok_count} installed, {skip_count} skipped, {fail_count} failed")
    RESULTS["tools"] = fail_count == 0


# ═════════════════════════════════════════════════════════════════════════════
# STEP 10 – Directory scaffold
# ═════════════════════════════════════════════════════════════════════════════
def scaffold_dirs():
    section("DIRECTORY STRUCTURE")
    dirs = [
        SCRIPT_DIR / "BASE" / "interface",
        SCRIPT_DIR / "BASE" / "tools" / "installed",
        SCRIPT_DIR / "personality" / "voice",
        SCRIPT_DIR / "personality" / "avatar",
        SCRIPT_DIR / "personality" / "memory",
    ]
    for d in dirs:
        existed = d.exists()
        d.mkdir(parents=True, exist_ok=True)
        label = d.relative_to(SCRIPT_DIR)
        if existed:
            ok(f"Already exists: {label}")
        else:
            ok(f"Created: {label}")
    RESULTS["dirs"] = True


# ═════════════════════════════════════════════════════════════════════════════
# STEP 11 – Verification
# ═════════════════════════════════════════════════════════════════════════════
def verify():
    section("VERIFICATION")

    checks = [
        ("Python venv",       VENV_PY.exists()),
        ("requirements.txt",  REQ_FILE.exists()),
        (".env file",         ENV_FILE.exists()),
        ("BASE/interface",   (SCRIPT_DIR / "BASE" / "interface").exists()),
        ("START.bat",        (SCRIPT_DIR / "START.bat").exists()),
    ]

    for label, passed in checks:
        if passed:
            ok(label)
        else:
            warn(f"{label} -- NOT FOUND")

    # Import checks inside venv
    import_checks = [
        ("numpy",         "import numpy; print(numpy.__version__)"),
        ("sounddevice",   "import sounddevice"),
        ("faster_whisper","from faster_whisper import WhisperModel; print('ok')"),
        ("TTS",           "import TTS; print(TTS.__version__)"),
        ("discord",       "import discord; print(discord.__version__)"),
        ("websockets",    "import websockets; print(websockets.__version__)"),
    ]

    blank()
    info("Python import checks:")
    for label, probe in import_checks:
        res = run(f'"{VENV_PY}" -c "{probe}"', capture=True, check=False)
        if res.returncode == 0:
            ver = res.stdout.strip().split("\n")[0]
            ok(f"  {label:<20} {ver}")
        else:
            warn(f"  {label:<20} IMPORT FAILED")

    # Ollama
    blank()
    info("Ollama check:")
    if shutil.which("ollama"):
        res = run("ollama list", capture=True, check=False)
        if res.returncode == 0:
            ok("Ollama responding")
            lines = [l for l in res.stdout.strip().splitlines() if l.strip()]
            if len(lines) > 1:
                ok(f"  {len(lines)-1} model(s) installed")
            else:
                warn("  No models found — run: ollama pull gemma4:latest")
        else:
            warn("Ollama not responding — start with: ollama start")
    else:
        warn("Ollama not in PATH")


# ═════════════════════════════════════════════════════════════════════════════
# STEP 12 – Summary
# ═════════════════════════════════════════════════════════════════════════════
def summary():
    section("SETUP COMPLETE")

    print(c(W, """
  Next steps:
"""))
    steps = [
        ("1", "Edit personality/bot_info.py",      "Set agentname, username, model names"),
        ("2", "Edit personality/config.json",       "Advanced Ollama/voice/memory settings"),
        ("3", "Install VB-Audio Cable",             "If using avatar speech (requires restart)"),
        ("4", "Launch the agent",                   "Run START.bat"),
    ]
    for num, action, detail in steps:
        print(c(C, f"  [{num}] ") + c(W, f"{action}"))
        print(c(DIM, f"       {detail}"))
        blank()

    print(c(G + BOLD, "  Launch command:"))
    print(c(W, "    START.bat"))
    blank()
    print(c(DIM, "  Documentation: SETUP.md  |  Repository: README.md"))
    hr()


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════
def main():
    banner()

    if platform.system() != "Windows":
        err("This script targets Windows only.")
        sys.exit(1)

    # ── Pre-flight ────────────────────────────────────────────────────────
    check_os()
    python_ver   = check_python()
    git_found    = check_git()
    ollama_found = check_ollama()
    gpu_found, is_50 = check_nvidia()
    blank()

    print(c(Y, "  Install steps that will run:"))
    print(c(W,  "    1. Create / verify virtual environment"))
    print(c(W,  "    2. Install Python dependencies"))
    print(c(W,  "    3. PyTorch / GPU packages"))
    print(c(W,  "    4. Ollama model download"))
    print(c(W,  "    5. Generate .env configuration"))
    print(c(W,  "    6. Scaffold directory structure"))
    print(c(W,  "    7. Optional: VB-Audio cables"))
    print(c(W,  "    8. Optional: AI Agent Tools"))
    print(c(W,  "    9. Verification"))
    blank()

    if not ask("Begin installation?", default="y"):
        info("Aborted.")
        sys.exit(0)

    # ── Core steps ────────────────────────────────────────────────────────
    setup_venv()
    install_deps()
    setup_gpu(gpu_found, is_50)
    setup_ollama(ollama_found)
    setup_env()
    scaffold_dirs()

    # ── Optional steps ────────────────────────────────────────────────────
    blank()
    hr("-")
    print(c(M + BOLD, "  OPTIONAL COMPONENTS"))
    hr("-")

    if ask("Set up virtual audio cables (VB-Audio)?", default="y"):
            setup_audio()

    setup_tools(git_found)

    setup_identity()

    # ── Final verification ────────────────────────────────────────────────
    verify()
    summary()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        blank()
        warn("Installation interrupted by user.")
        sys.exit(1)