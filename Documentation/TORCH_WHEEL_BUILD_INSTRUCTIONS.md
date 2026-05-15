# PyTorch 2.10.0a0 — sm_120 (RTX 5060 Ti) Windows Build Guide

## Verified Build Configuration

| Parameter | Value |
|---|---|
| PyTorch Version | 2.10.0a0 (nightly) |
| Commit | `d4493c550a67de3501dfd17724e0387d2e5c91a6` |
| Python | 3.11.9 (cp311) — **must be 3.11.x** |
| Platform | Windows x64 |
| CUDA Runtime | 13.0 (V13.0.88) |
| cuDNN | 9.16.0.29 |
| NVCC Target | `sm_120` only |
| Compiler | MSVC 14.29.30133 (Visual Studio 2019 Build Tools) |
| C++ Standard | C++17 |
| CPU ISA | AVX512 |
| MKL-DNN | v3.7.1 (oneDNN) |
| OpenMP | 2019 |
| TorchAudio | 2.10.0a0+32ce8c0 (built alongside torch) |
| Host | AMD Ryzen 9 7900X / 32GB RAM / RTX 5060 Ti 16GB |

---

## Hardware Notes

- RTX 5060 Ti is GPU 0 (sm_120). Intel Arc B580 is also present — **it caused build failures** due to Intel oneAPI/SYCL being detected by CMake. Must be explicitly disabled.
- Build was performed with C: drive as build target. Ensure at least **20GB free** on build drive.
- `MAX_JOBS=8` is safe on the 7900X (12c/24t). Drop to 4–6 if RAM pressure causes failures.

---

## Prerequisites

### 1. Python 3.11.9

The wheel is `cp311`. Python 3.12+ or 3.13 will not work.

```powershell
py -3.11 --version  # Must return 3.11.x
```

Download: https://www.python.org/downloads/release/python-3119/

### 2. CUDA Toolkit 13.0

Install path: `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0`

Verify:
```powershell
nvcc --version  # Must show release 13.0, V13.0.88
```

Download: https://developer.nvidia.com/cuda-downloads

### 3. cuDNN 9.16.0 for CUDA 13

Install into the CUDA 13.0 directory:

```powershell
$cudaPath = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0"
$cudnnArchive = "cudnn-windows-x86_64-9.16.0.29_cuda13-archive"  # adjust to actual folder

Copy-Item "$cudnnArchive\bin\*"     "$cudaPath\bin\"     -Force
Copy-Item "$cudnnArchive\include\*" "$cudaPath\include\" -Force
Copy-Item "$cudnnArchive\lib\x64\*" "$cudaPath\lib\x64\" -Force

# Verify
Test-Path "$cudaPath\bin\cudnn64_9.dll"          # True
Test-Path "$cudaPath\bin\cudnn_ops64_9.dll"       # True
Test-Path "$cudaPath\bin\cudnn_cnn64_9.dll"       # True
```

Download: https://developer.nvidia.com/cudnn (free account required)

### 4. Visual Studio 2019 Build Tools

**Must be VS 2019, not 2022.** The build used `MSVC 14.29.30133` which is the VS 2019 v142 toolchain.

Download: https://visualstudio.microsoft.com/vs/older-downloads/

Required components:
- MSVC v142 — VS 2019 C++ x64/x86 build tools (14.29 specifically)
- Windows 10/11 SDK

Verify:
```powershell
$vcvars = "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
Test-Path $vcvars  # True
```

### 5. Git

```powershell
git --version
```

---

## Build Steps

### Step 1: Clone at the exact commit

```powershell
git clone https://github.com/pytorch/pytorch.git C:\pytorch_build\pytorch
cd C:\pytorch_build\pytorch
git checkout d4493c550a67de3501dfd17724e0387d2e5c91a6
git submodule sync
git submodule update --init --recursive
```

### Step 2: Create venv with Python 3.11

```powershell
py -3.11 -m venv C:\pytorch_build\venv
C:\pytorch_build\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

### Step 3: Install build dependencies

```powershell
pip install cmake ninja pyyaml setuptools typing-extensions numpy
pip install mkl-static mkl-include
pip install filelock sympy networkx jinja2 fsspec
```

### Step 4: Initialize x64 build environment

**Critical:** Must use the x64 toolchain. The build failed when 32-bit compilers were selected. Run this before setting env vars:

```powershell
cmd /c '"C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat" && powershell'
```

Then re-activate the venv inside the new shell:

```powershell
C:\pytorch_build\venv\Scripts\Activate.ps1
cd C:\pytorch_build\pytorch
```

### Step 5: Set environment variables

```powershell
# CUDA
$env:CUDA_PATH  = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0"
$env:CUDA_HOME  = $env:CUDA_PATH
$env:PATH       = "$env:CUDA_PATH\bin\x64;$env:CUDA_PATH\bin;$env:PATH"

# Target architecture — sm_120 only
$env:TORCH_CUDA_ARCH_LIST = "12.0"

# Compiler — force x64, match actual MSVC version used
$env:DISTUTILS_USE_SDK        = "1"
$env:MSSdk                    = "1"
$env:PROCESSOR_ARCHITECTURE   = "AMD64"
$env:VSCMD_ARG_TGT_ARCH       = "x64"

# Enable
$env:USE_CUDA    = "1"
$env:USE_CUDNN   = "1"
$env:USE_MKLDNN  = "1"
$env:USE_OPENMP  = "1"
$env:USE_XNNPACK = "1"

# Disable — Intel XPU MUST be off or CMake will detect oneAPI and fail
$env:USE_XPU          = "0"
$env:USE_GLOO         = "0"
$env:USE_MPI          = "0"
$env:USE_NCCL         = "0"
$env:USE_NNPACK       = "0"
$env:USE_GFLAGS       = "0"
$env:USE_GLOG         = "0"
$env:USE_ROCM         = "0"
$env:USE_CUSPARSELT   = "0"
$env:USE_DISTRIBUTED  = "0"
$env:BUILD_CAFFE2     = "0"
$env:BUILD_TEST       = "0"

# Performance
$env:MAX_JOBS          = "8"
$env:CMAKE_BUILD_TYPE  = "Release"

# Verify
Write-Host "TORCH_CUDA_ARCH_LIST : $env:TORCH_CUDA_ARCH_LIST"
Write-Host "CUDA_PATH            : $env:CUDA_PATH"
Write-Host "USE_XPU              : $env:USE_XPU"
Write-Host "MAX_JOBS             : $env:MAX_JOBS"
```

### Step 6: Build the wheel

```powershell
cd C:\pytorch_build\pytorch
python setup.py bdist_wheel
```

Expected output in `C:\pytorch_build\pytorch\dist\`:
```
torch-2.10.0a0+gitd4493c5-cp311-cp311-win_amd64.whl
```

Build time: **2–4 hours** on 7900X with MAX_JOBS=8.

If the build directory becomes stale from a previous attempt:
```powershell
python setup.py clean
Remove-Item -Recurse -Force build
```

---

## Post-Build: DLL Setup

After installing the wheel, CUDA DLLs must be copied into the torch lib directory. Without this step, `torch.cuda.is_available()` will return False even though the build succeeded.

```powershell
$cudaDllPath = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0\bin\x64"
$torchLib    = ".\venv\Lib\site-packages\torch\lib"

Copy-Item "$cudaDllPath\*.dll" $torchLib -Force
Copy-Item "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0\bin\cudnn64_9.dll" $torchLib -Force
```

---

## Installation

```powershell
pip install C:\pytorch_build\pytorch\dist\torch-2.10.0a0+gitd4493c5-cp311-cp311-win_amd64.whl --force-reinstall --no-deps
```

---

## Verification

```powershell
python -c "
import torch
print('Version :', torch.__version__)
print('CUDA    :', torch.version.cuda)
print('cuDNN   :', torch.backends.cudnn.version())
print('Archs   :', torch.cuda.get_arch_list())
print('GPU     :', torch.cuda.get_device_name(0))
print('Cap     :', torch.cuda.get_device_capability(0))
x = torch.zeros(1).cuda()
print('Test    :', (x + 1).item())
"
```

Expected output:
```
Version : 2.10.0a0+gitd4493c5
CUDA    : 13.0
cuDNN   : 91600
Archs   : ['sm_120']
GPU     : NVIDIA GeForce RTX 5060 Ti
Cap     : (12, 0)
Test    : 1.0
```

---

## Integration Notes (TTS / Anna)

From `dup_requirements.txt` — additional steps required after wheel install:

```powershell
# 1. Install transformers at pinned version after torch
pip install transformers==4.36.2 --force-reinstall --no-deps

# 2. Remove torchaudio if not needed (prevents DLL conflicts)
pip uninstall torchaudio -y

# 3. Patch TTS vits.py to not hard-require torchaudio
$vitsFile = ".\venv\Lib\site-packages\TTS\tts\models\vits.py"
$content  = Get-Content $vitsFile -Raw
$patched  = $content -replace 'import torchaudio', @'
try:
    import torchaudio
except ImportError:
    torchaudio = None
'@
Set-Content $vitsFile $patched
```

---

## Known Failure Modes

| Symptom | Cause | Fix |
|---|---|---|
| `SYCL: feature test compile failed` | Intel oneAPI detected | Set `USE_XPU=0` |
| `HostX86\x86\cl.exe` in build output | 32-bit compiler selected | Run `vcvars64.bat` first |
| `compiler is out of heap space` | Too many parallel jobs | Reduce `MAX_JOBS` to 4 |
| `CUDA not found` during CMake | PATH missing | Set `CUDA_PATH` and add to `PATH` |
| `cuda.is_available()` returns False after install | DLLs not in torch\lib | Run DLL copy step |
| TTS import fails after torch install | torchaudio conflict | Uninstall torchaudio, patch vits.py |

---

## Limitations

- **sm_120 only** — will not run on any pre-Blackwell GPU
- **CUDA 13.0 required at runtime** — CUDA 12.x is incompatible
- No multi-node distributed training (`USE_GLOO=0`, `USE_NCCL=0`)
- Single-GPU and `DataParallel` work normally