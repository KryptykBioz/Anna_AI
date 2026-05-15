# PyAudio 0.2.8 — Python 3.11 Windows Build Guide

## Verified Build Configuration

| Parameter | Value |
|---|---|
| PyAudio Version | 0.2.8 |
| Wheel | `pyaudio-0.2.8-cp311-cp311-win_amd64.whl` |
| Python | 3.11.9 (cp311) — **must be 3.11.x** |
| Platform | Windows x64 |
| PortAudio Version | 19.7.0 |
| CMake Generator | Visual Studio 17 2022 |
| MSVC Toolset | 14.44.35207 (VS 2022 BuildTools) |
| CRT Runtime | VCRUNTIME140.dll (v140 compat) |
| Build Date | 2025-11-26 |
| Host | AMD Ryzen 9 7900X / Windows 11 26200.8328 |

---

## Critical Notes

- **VS 2022 BuildTools** were used for PortAudio (CMake build). The PyTorch build used VS 2019 — both are installed on this system. PyAudio's `setup.py` wheel build picks up whichever MSVC is initialized via `vcvars64.bat` first.
- **PyAudio 0.2.8** requires a `PY_SSIZE_T_CLEAN` patch to the C source for Python 3.11+. Without it, `stream.write()` raises a `SystemError` at runtime even though the build succeeds.
- `vswhere.exe` returns empty on this system — VS is installed but not registered with the VS installer database. All VS detection must use direct path lookups.
- PortAudio is built as a **static library** (`portaudio.lib`). No `portaudio.dll` is produced or needed.

---

## Prerequisites

### 1. Python 3.11.9

```powershell
py -3.11 --version  # Must return 3.11.x
```

Download: https://www.python.org/downloads/release/python-3119/

### 2. Visual Studio 2022 BuildTools

Install path: `C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools`

Required components:
- MSVC v143 — VS 2022 C++ x64/x86 build tools
- Windows 10/11 SDK
- C++ CMake tools for Windows

Verify:
```powershell
Test-Path "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
# True
```

Download: https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022

### 3. CMake 3.27+

CMake 3.27.9 was used. Install via pip into the venv or system-wide.

```powershell
pip install cmake
cmake --version  # cmake version 3.27.9
```

### 4. Git

```powershell
git --version  # git version 2.49.0.windows.1
```

### 5. Ninja (optional but present)

```powershell
pip install ninja
```

---

## Build Steps

### Step 1: Activate venv with Python 3.11

```powershell
cd C:\Users\KryptykBioz\Desktop\Anna_AI
.\venv\Scripts\Activate.ps1
python --version  # Must be 3.11.x
```

### Step 2: Initialize VS 2022 x64 environment

Must be done in the same shell before any build commands. This is required for both the PortAudio CMake build and the PyAudio wheel build.

```powershell
$vcvars = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
$tmp = [System.IO.Path]::GetTempFileName()
cmd /c "`"$vcvars`" && set" > $tmp
Get-Content $tmp | ForEach-Object {
    if ($_ -match "^([^=]+)=(.*)$") {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
    }
}
Remove-Item $tmp

# Verify
cl.exe 2>&1 | Select-String "Version"
# Microsoft (R) C/C++ Optimizing Compiler Version 19.44.xxxxx for x64
```

### Step 3: Build PortAudio from source

```powershell
$BUILD_DIR   = "C:\pyaudio_build"
$INSTALL_DIR = "C:\pyaudio_build\install"

New-Item -ItemType Directory -Path $BUILD_DIR -Force | Out-Null

# Clone
cd $BUILD_DIR
git clone https://github.com/PortAudio/portaudio.git
cd portaudio
git checkout v19.7.0

# Configure — generator must match VS 2022
$installFwd = $INSTALL_DIR -replace '\\', '/'
New-Item -ItemType Directory -Path "build" -Force | Out-Null
cd build

cmake .. `
    -G "Visual Studio 17 2022" `
    -A x64 `
    -DCMAKE_INSTALL_PREFIX="$installFwd" `
    -DPA_USE_ASIO=OFF `
    -DPA_USE_DS=ON `
    -DPA_USE_WMME=ON `
    -DPA_USE_WASAPI=ON `
    -DPA_USE_WDMKS=ON `
    -DCMAKE_BUILD_TYPE=Release

cmake --build . --config Release --parallel 8
cmake --install . --config Release
```

Verify:
```powershell
Test-Path "C:\pyaudio_build\install\include\portaudio.h"  # True
Test-Path "C:\pyaudio_build\install\lib\portaudio.lib"    # True
# Note: portaudio.dll will NOT exist — static build only
```

### Step 4: Obtain PyAudio 0.2.8 source

```powershell
cd C:\pyaudio_build

pip download "pyaudio==0.2.8" --no-binary :all: --no-deps
# Downloads PyAudio-0.2.8.tar.gz

tar -xzf PyAudio-0.2.8.tar.gz
Rename-Item "PyAudio-0.2.8" "pyaudio"
Remove-Item "PyAudio-0.2.8.tar.gz"
```

### Step 5: Patch source for Python 3.11+

This patch is **mandatory**. Without it the build succeeds but `stream.write()` raises `SystemError` at runtime.

```powershell
$cSource = "C:\pyaudio_build\pyaudio\src\_portaudiomodule.c"

# Backup
Copy-Item $cSource "$cSource.original" -Force

# Check if already patched
$content = Get-Content $cSource -Raw
if ($content -notmatch "#define PY_SSIZE_T_CLEAN") {
    Set-Content -Path $cSource -Value ("#define PY_SSIZE_T_CLEAN`n" + $content)
    Write-Host "Patched"
} else {
    Write-Host "Already patched"
}
```

### Step 6: Configure PyAudio build

```powershell
$INSTALL_DIR = "C:\pyaudio_build\install"

cd C:\pyaudio_build\pyaudio

# setup.cfg tells the compiler where PortAudio headers and lib are
@"
[build_ext]
include_dirs=$INSTALL_DIR\include
library_dirs=$INSTALL_DIR\lib
"@ | Set-Content "setup.cfg"

# Required environment variables
$env:PORTAUDIO_PATH    = $INSTALL_DIR
$env:DISTUTILS_USE_SDK = "1"
$env:MSSdk             = "1"
```

### Step 7: Build the wheel

```powershell
cd C:\pyaudio_build\pyaudio

# Clean any previous attempts
@("build", "dist", "PyAudio.egg-info") | ForEach-Object {
    if (Test-Path $_) { Remove-Item $_ -Recurse -Force }
}

python setup.py bdist_wheel
```

Expected output in `C:\pyaudio_build\pyaudio\dist\`:
```
pyaudio-0.2.8-cp311-cp311-win_amd64.whl  (~90 KB)
```

Build time: under 5 minutes.

### Step 8: Install

```powershell
$wheel = (Get-ChildItem "C:\pyaudio_build\pyaudio\dist\*.whl" | Select-Object -First 1).FullName
pip install $wheel --force-reinstall
```

---

## Verification

```powershell
python -c "
import pyaudio
import numpy as np

p = pyaudio.PyAudio()
print('Version  :', pyaudio.__version__)
print('Devices  :', p.get_device_count())

# This is the critical test — fails without PY_SSIZE_T_CLEAN patch
stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, output=True)
stream.write(np.zeros(1024, dtype=np.int16).tobytes())
stream.close()
p.terminate()
print('Write test: PASSED')
"
```

Expected output:
```
Version  : 0.2.8
Devices  : 47
Write test: PASSED
```

---

## Known Failure Modes

| Symptom | Cause | Fix |
|---|---|---|
| `SystemError: PY_SSIZE_T_CLEAN macro must be defined` | Patch not applied or build used pre-patch source | Re-apply patch, clean build dir, rebuild |
| `portaudio.h: No such file or directory` | `setup.cfg` missing or `include_dirs` wrong | Recreate `setup.cfg` with correct `INSTALL_DIR` |
| `portaudio.lib: cannot open` | `library_dirs` wrong or PortAudio not built | Verify `Test-Path C:\pyaudio_build\install\lib\portaudio.lib` |
| 32-bit compiler selected | `vcvars64.bat` not initialized | Re-run Step 2 in the same shell before building |
| `cl.exe not found` | VS not on PATH | Re-run Step 2; verify `vcvars64.bat` path |
| Build succeeds but import fails | Wrong Python version used to build | Ensure venv Python is 3.11, not 3.12/3.13 |
| `vswhere.exe` returns empty | VS not registered with installer | Use direct path to `vcvars64.bat` as shown in Step 2 |

---

## Reinstallation (from saved wheel)

```powershell
# Back up wheel after successful build
Copy-Item "C:\pyaudio_build\pyaudio\dist\pyaudio-0.2.8-cp311-cp311-win_amd64.whl" `
          "C:\Users\KryptykBioz\Desktop\pyaudio_sm120_backup.whl"

# Reinstall instantly from backup (no rebuild needed)
pip install C:\Users\KryptykBioz\Desktop\pyaudio_sm120_backup.whl --force-reinstall
```

---

## Compatibility

| Package | Version | Status |
|---|---|---|
| PyTorch | 2.10.0a0+gitd4493c5 | Compatible |
| TorchAudio | 2.10.0a0+32ce8c0 | Compatible |
| TTS (Coqui) | 0.22.0 | Compatible |
| numpy | 1.26.4 | Compatible |
| sounddevice | 0.5.2 | Compatible |
| soundfile | 0.13.1 | Compatible |