#!/usr/bin/env python
"""
Build script for SC Signature Scanner.
Creates a standalone .exe distribution using PyInstaller.

Author: Mallachi
"""

import json
import os
import subprocess
import shutil
import sys
from pathlib import Path

# Force UTF-8 output so checkmark/warning characters render on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Require Python 3.13+
if sys.version_info < (3, 13):
    print(f"ERROR: Python 3.13+ required, got {sys.version.split()[0]}")
    sys.exit(1)


def print_header(text: str):
    """Print a formatted header."""
    print()
    print("=" * 60)
    print(f"  {text}")
    print("=" * 60)
    print()


def print_section(text: str):
    """Print a section header."""
    print(f"\n[{text}]")


def run_command(cmd: list, description: str) -> bool:
    """Run a command and return success status."""
    print(f"  {description}...")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                print(f"    {line}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ERROR: {e}")
        if e.stderr:
            print(e.stderr)
        return False
    except FileNotFoundError:
        print(f"  ERROR: Command not found: {cmd[0]}")
        return False


def main():
    print_header("SC Signature Scanner - Build Script")

    # Ensure we're in the right directory
    project_dir = Path(__file__).parent
    if not (project_dir / "main.py").exists():
        print("ERROR: main.py not found. Run this script from the project directory.")
        sys.exit(1)

    os.chdir(project_dir)
    print(f"Project:  {project_dir}")
    print(f"Python:   {sys.version.split()[0]}  ({sys.executable})")

    # Get app version
    try:
        sys.path.insert(0, str(project_dir))
        import version_checker
        version = version_checker.CURRENT_VERSION
        print(f"App:      v{version}")
    except ImportError:
        version = "unknown"
        print("Warning: Could not determine version (version_checker.py missing)")

    # ===== Pre-build Checks =====
    print_section("Pre-build Checks")

    required_files = [
        "main.py",
        "scanner.py",
        "overlay.py",
        "splash.py",
        "monitor.py",
        "config.py",
        "theme.py",
        "paths.py",
        "version_checker.py",
        "region_selector.py",
        "requirements.txt",
        "SC_Signature_Scanner.spec",
    ]

    missing = [f for f in required_files if not (project_dir / f).exists()]
    if missing:
        print("  ERROR: Missing required files:")
        for f in missing:
            print(f"    - {f}")
        sys.exit(1)
    print(f"  ✓ All {len(required_files)} required source files present")

    # Database
    data_dir = project_dir / "data"
    db_file = data_dir / "combat_analyst_db.json"
    if not db_file.exists():
        print(f"  ERROR: Database not found: {db_file}")
        sys.exit(1)

    sc_version = "unknown"
    try:
        with open(db_file, "r", encoding="utf-8") as f:
            sc_version = json.load(f).get("metadata", {}).get("sc_version", "unknown")
    except (json.JSONDecodeError, IOError):
        pass
    print(f"  ✓ Database present (SC {sc_version})")

    # Windows shell artifacts — abort if present (they'd get bundled)
    shell_artifacts = [project_dir / "nul", project_dir / "nul.txt"]
    found_artifacts = [p for p in shell_artifacts if p.exists()]
    if found_artifacts:
        print(f"  ⚠ Warning: Shell artifacts found — run clean.py first:")
        for p in found_artifacts:
            print(f"    - {p.name}")

    # Deprecated source files — warn only
    deprecated_files = [
        "hud_calibration.py",
        "identifier_window.py",
        "jxr_converter.py",
        "tobii_tracker.py",
    ]
    found_deprecated = [f for f in deprecated_files if (project_dir / f).exists()]
    if found_deprecated:
        print("  ⚠ Warning: Deprecated files found — run clean.py first:")
        for f in found_deprecated:
            print(f"    - {f}")

    # ===== Clean Previous Builds =====
    print_section("Cleaning Previous Builds")

    cleaned_any = False
    for folder in ("build", "dist"):
        path = project_dir / folder
        if path.exists():
            shutil.rmtree(path)
            print(f"  Removed: {folder}/")
            cleaned_any = True
    if not cleaned_any:
        print("  (nothing to clean)")

    # ===== Check PyInstaller =====
    print_section("PyInstaller")

    try:
        import PyInstaller
        print(f"  ✓ PyInstaller {PyInstaller.__version__} found")
    except ImportError:
        print("  PyInstaller not found, installing...")
        if not run_command([sys.executable, "-m", "pip", "install", "pyinstaller"], "Installing"):
            print("  ERROR: Failed to install PyInstaller")
            sys.exit(1)

    # ===== Build =====
    print_header("Building Executable")

    spec_file = project_dir / "SC_Signature_Scanner.spec"
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(spec_file), "--noconfirm"],
        cwd=project_dir,
    )

    if result.returncode != 0:
        print_header("BUILD FAILED")
        sys.exit(1)

    # ===== Verify Output =====
    print_section("Verifying Build")

    dist_dir = project_dir / "dist" / "SC_Signature_Scanner"
    exe_file = dist_dir / "SC_Signature_Scanner.exe"
    # PyInstaller >=6 places bundled data in _internal/
    internal_dir = dist_dir / "_internal"
    db_file_dist = internal_dir / "data" / "combat_analyst_db.json"

    errors = []

    if not exe_file.exists():
        errors.append("SC_Signature_Scanner.exe not found in dist/")
    else:
        size_mb = exe_file.stat().st_size / (1024 * 1024)
        print(f"  ✓ Executable: {exe_file.name} ({size_mb:.1f} MB)")

    if not internal_dir.exists():
        errors.append("_internal/ directory missing — PyInstaller layout changed?")
    else:
        print(f"  ✓ _internal/ directory present")

    if not db_file_dist.exists():
        errors.append("_internal/data/combat_analyst_db.json not bundled")
    else:
        print(f"  ✓ Database: _internal/data/combat_analyst_db.json")

    if errors:
        print("\n  Build errors:")
        for e in errors:
            print(f"    ✗ {e}")
        sys.exit(1)

    # ===== Summary =====
    print_header("BUILD COMPLETE")

    print(f"App version: v{version}")
    print(f"SC version:  {sc_version}")
    print(f"Python:      {sys.version.split()[0]}")
    print(f"Output:      {dist_dir}")
    print()
    print("Bundled (in _internal/):")
    print("  data/combat_analyst_db.json")
    print()
    print("Runtime files (created next to exe on first use):")
    print("  config.json              — user settings")
    print("  scan_region.json         — scan region config")
    print("  SignatureScannerBugreport/ — debug screenshots")
    print()
    print("Distribution:")
    print("  Zip the entire SC_Signature_Scanner/ folder.")
    print("  Users extract and run SC_Signature_Scanner.exe")
    print()

    # Open dist folder on Windows
    if sys.platform == "win32":
        os.startfile(dist_dir)


if __name__ == "__main__":
    main()
