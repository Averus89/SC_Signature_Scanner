#!/usr/bin/env python
"""
Clean up utility for SC Signature Scanner.
Removes cache files, debug output, user config, API credentials, and deprecated files.

Author: Mallachi
"""

import json
import shutil
import sys
from pathlib import Path

# Import paths module for consistent user-data directory resolution
sys.path.insert(0, str(Path(__file__).parent))
import paths


def _kill_running_processes(root: Path) -> int:
    """Terminate any process whose executable lives under `root`.

    Returns the count of processes killed. Prints per-process status.

    Cross-platform via psutil. Used so subsequent rmtree calls don't fail with
    PermissionError on locked .pyd / .exe files that a running bundle has
    mmap'd (e.g. a stale dist/SC_Signature_Scanner.exe left over from manual
    testing). Skips the running Python interpreter itself.
    """
    try:
        import psutil  # type: ignore[import-not-found]
    except ImportError:
        print("  (psutil not installed; skipping process cleanup. "
              "Run 'pip install psutil' if cleanup fails on locked files.)")
        return 0

    root_resolved = root.resolve()
    me_pid = psutil.Process().pid
    killed = 0

    for proc in psutil.process_iter(["pid", "name"]):
        if proc.pid == me_pid:
            continue
        # exe() raises on processes we can't read — system processes, processes
        # owned by other users on Linux, etc. Skip them; if they're not ours we
        # don't care, and if they were we wouldn't have permission to kill them
        # anyway.
        try:
            exe = proc.exe()
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            continue
        if not exe:
            continue
        # Windows kernel pseudo-processes (Registry, MemCompression, System,
        # ...) report bare names from exe() rather than real paths. Skip them
        # — otherwise Path("Registry").resolve() becomes <cwd>/Registry and
        # falsely passes the is_relative_to check below.
        exe_raw = Path(exe)
        if not exe_raw.is_absolute():
            continue
        try:
            exe_path = exe_raw.resolve()
        except (OSError, ValueError):
            continue
        try:
            under_root = exe_path.is_relative_to(root_resolved)
        except ValueError:
            continue
        if not under_root:
            continue

        rel = exe_path.relative_to(root_resolved)
        name = proc.info.get("name") or "<unknown>"
        try:
            print(f"  Terminating: {name} (PID {proc.pid}) - {rel}")
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                print(f"    Graceful terminate timed out; force-killing.")
                proc.kill()
                proc.wait(timeout=2)
            killed += 1
        except psutil.NoSuchProcess:
            # Process exited between detection and terminate(); treat as killed.
            killed += 1
        except psutil.AccessDenied as e:
            print(f"    Access denied: {e}")

    return killed


def clean(include_ocr_models: bool = False):
    """Remove cache files, debug output, user config, API credentials, and deprecated files.

    Cleans (in order):
    - Running processes whose executable lives under the project root
      (prevents rmtree() from failing on mmap'd .pyd / .exe files)
    - __pycache__ directories and .pyc/.pyo files
    - Tool caches (.pytest_cache, .mypy_cache, .ruff_cache)
    - Debug output folders (SignatureScannerBugreport, debug_output)
    - User config files (config.json, scan_region.json, regolith_cache.json)
    - Data cache files (rock_types.json, uex_prices.json)
    - Windows shell artifacts (nul)
    - Build artifacts (build/, dist/)
    - Deprecated config files (hud_config.json, identifier_config.json)
    - Deprecated source files (hud_calibration.py, identifier_window.py, etc.)
    - EasyOCR model cache (optional, ~115MB)

    Args:
        include_ocr_models: If True, also remove EasyOCR model cache (~115MB)
    """
    root = Path(__file__).parent
    user_data = paths.get_user_data_path()
    removed = 0

    print("SC Signature Scanner - Cleanup Utility")
    print("=" * 50)
    print(f"Python: {sys.version.split()[0]}")
    print()

    # ===== Running Processes =====
    # Must happen BEFORE rmtree on build/dist/dist_debug — Windows refuses to
    # delete a .pyd while any process has it mmap'd. psutil-based so the same
    # logic works on Linux/macOS.
    print("[Running Processes]")
    killed = _kill_running_processes(root)
    if killed == 0:
        print("  (none under project root)")
    print()

    # ===== Python Cache =====
    print("[Python Cache]")

    for cache_dir in root.rglob("__pycache__"):
        shutil.rmtree(cache_dir)
        print(f"  Removed: {cache_dir.relative_to(root)}")
        removed += 1

    for pattern in ("*.pyc", "*.pyo"):
        for file in root.rglob(pattern):
            file.unlink()
            print(f"  Removed: {file.relative_to(root)}")
            removed += 1

    # ===== Tool Caches =====
    print("\n[Tool Caches]")

    tool_caches = [".pytest_cache", ".mypy_cache", ".ruff_cache"]
    found_tool_cache = False
    for name in tool_caches:
        cache_path = root / name
        if cache_path.exists():
            shutil.rmtree(cache_path)
            print(f"  Removed: {name}/")
            removed += 1
            found_tool_cache = True
    if not found_tool_cache:
        print("  (none found)")

    # ===== Debug Output =====
    print("\n[Debug Output]")

    # Read custom debug folder from user config if it exists
    config_file = user_data / "config.json"
    custom_debug_folder = None
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                cfg = json.load(f)
                custom_debug_folder = cfg.get("debug_folder", "")
        except (json.JSONDecodeError, IOError):
            pass

    default_debug_dir = user_data / "SignatureScannerBugreport"
    if default_debug_dir.exists():
        file_count = sum(1 for _ in default_debug_dir.iterdir())
        shutil.rmtree(default_debug_dir)
        print(f"  Removed: SignatureScannerBugreport/ ({file_count} files)")
        removed += 1

    old_debug_dir = root / "debug_output"
    if old_debug_dir.exists():
        file_count = sum(1 for _ in old_debug_dir.iterdir())
        shutil.rmtree(old_debug_dir)
        print(f"  Removed: debug_output/ ({file_count} files)")
        removed += 1

    if custom_debug_folder:
        custom_path = Path(custom_debug_folder)
        if custom_path.exists() and custom_path not in (default_debug_dir, old_debug_dir):
            file_count = sum(1 for _ in custom_path.iterdir())
            if file_count > 0:
                for item in custom_path.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                print(f"  Cleared: {custom_path} ({file_count} items)")
                removed += 1

    # ===== Build Artifacts =====
    print("\n[Build Artifacts]")

    found_build = False
    for dirname in ("build", "dist"):
        dir_path = root / dirname
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"  Removed: {dirname}/")
            removed += 1
            found_build = True
    if not found_build:
        print("  (none found)")

    # ===== User Config Files =====
    print("\n[User Config]")

    config_files = [
        ("config.json", "Settings + API key"),
        ("scan_region.json", "Scan region config"),
        ("regolith_cache.json", "Regolith.rocks cache"),
    ]

    found_config = False
    for filename, description in config_files:
        filepath = user_data / filename
        if filepath.exists():
            filepath.unlink()
            print(f"  Removed: {filename} ({description})")
            removed += 1
            found_config = True
    if not found_config:
        print("  (none found)")

    # ===== Data Cache Files =====
    print("\n[Data Cache]")

    data_dir = root / "data"
    cache_files = [
        ("rock_types.json", "Regolith rock composition cache"),
        ("uex_prices.json", "UEX pricing cache"),
    ]

    found_data_cache = False
    for filename, description in cache_files:
        filepath = data_dir / filename
        if filepath.exists():
            filepath.unlink()
            print(f"  Removed: data/{filename} ({description})")
            removed += 1
            found_data_cache = True
    if not found_data_cache:
        print("  (none found)")

    # ===== Windows Shell Artifacts =====
    print("\n[Shell Artifacts]")

    shell_artifacts = ["nul", "nul.txt"]
    found_artifact = False
    for name in shell_artifacts:
        artifact = root / name
        if artifact.exists() and artifact.is_file():
            artifact.unlink()
            print(f"  Removed: {name} (Windows shell artifact)")
            removed += 1
            found_artifact = True
    if not found_artifact:
        print("  (none found)")

    # ===== Deprecated Config Files =====
    print("\n[Deprecated Config]")

    deprecated_configs = [
        ("hud_config.json", "Old HUD calibration config"),
        ("identifier_config.json", "Old identifier window config"),
    ]

    found_deprecated_config = False
    for filename, description in deprecated_configs:
        filepath = root / filename
        if filepath.exists():
            filepath.unlink()
            print(f"  Removed: {filename} ({description})")
            removed += 1
            found_deprecated_config = True
    if not found_deprecated_config:
        print("  (none found)")

    # ===== Deprecated Source Files =====
    print("\n[Deprecated Source Files]")

    deprecated_files = [
        ("hud_calibration.py", "Old circle-based calibration"),
        ("identifier_window.py", "Old overlay calibration window"),
        ("jxr_converter.py", "JXR to PNG converter (unused)"),
        ("tobii_tracker.py", "Tobii integration (deferred)"),
    ]

    found_deprecated = False
    for filename, description in deprecated_files:
        filepath = root / filename
        if filepath.exists():
            filepath.unlink()
            print(f"  Removed: {filename} ({description})")
            removed += 1
            found_deprecated = True
    if not found_deprecated:
        print("  (none found)")

    # ===== EasyOCR Model Cache =====
    print("\n[OCR Model Cache]")

    easyocr_dir = Path.home() / ".EasyOCR"
    if easyocr_dir.exists():
        total_size = sum(f.stat().st_size for f in easyocr_dir.rglob("*") if f.is_file())
        size_mb = total_size / (1024 * 1024)

        if include_ocr_models:
            shutil.rmtree(easyocr_dir)
            print(f"  Removed: ~/.EasyOCR/ ({size_mb:.1f} MB)")
            removed += 1
        else:
            print(f"  Skipped: ~/.EasyOCR/ ({size_mb:.1f} MB)")
            print("           Use --ocr flag to remove OCR models")
    else:
        print("  (not installed)")

    # ===== Summary =====
    print()
    print("=" * 50)
    print(f"Cleaned {removed} items.")
    print()
    print("Note: Run this before building for distribution.")


def main():
    """Entry point with argument parsing."""
    include_ocr = "--ocr" in sys.argv or "-o" in sys.argv

    if "--help" in sys.argv or "-h" in sys.argv:
        print("SC Signature Scanner - Cleanup Utility")
        print()
        print("Usage: python clean.py [options]")
        print()
        print("Options:")
        print("  --ocr, -o    Also remove EasyOCR model cache (~115MB)")
        print("  --help, -h   Show this help message")
        print()
        print("Removes:")
        print("  - Processes running from under the project root (e.g. a stale")
        print("    dist/SC_Signature_Scanner.exe holding files mmap'd)")
        print("  - __pycache__ directories and .pyc/.pyo files")
        print("  - Tool caches (.pytest_cache, .mypy_cache, .ruff_cache)")
        print("  - Debug output folders")
        print("  - Build artifacts (build/ and dist/ folders)")
        print("  - User config files (config.json, scan_region.json, regolith_cache.json)")
        print("  - Data cache files (rock_types.json, uex_prices.json)")
        print("  - Windows shell artifacts (nul)")
        print("  - Deprecated source and config files")
        print("  - EasyOCR models (optional, with --ocr flag)")
        return

    clean(include_ocr_models=include_ocr)


if __name__ == "__main__":
    main()
