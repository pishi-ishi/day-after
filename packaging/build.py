"""Build the one-file Day After binary for this OS with PyInstaller (pinned in pyproject's `build` extra).

    python packaging/make_icon.py && python packaging/build.py

Writes dist/dayafter-<os>-<arch>[.exe] and dist/<name>.sha256. The binary carries the report assets, the app
page, the coastlines and the public fixtures (for `--selftest`); never the private data/ folder.
"""
import hashlib
import os
import platform
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def target_name() -> str:
    osname = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    arch = platform.machine().lower().replace("amd64", "x64").replace("x86_64", "x64").replace("aarch64", "arm64")
    return f"dayafter-{osname}-{arch}" + (".exe" if osname == "windows" else "")


def main() -> int:
    name = target_name()
    stem = name[:-4] if name.endswith(".exe") else name
    icon = os.path.join(ROOT, "packaging", "icon.ico" if sys.platform == "win32" else "icon.png")
    datas = [("dayafter/report/assets", "dayafter/report/assets"), ("dayafter/app/app.html", "dayafter/app"),
             ("assets", "assets"), ("fixtures", "fixtures")]
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--console", "--name", stem,
           "--collect-data", "tzdata", "--exclude-module", "tkinter", "--exclude-module", "pytest",
           "--specpath", os.path.join(ROOT, "build"), "--distpath", os.path.join(ROOT, "dist"),
           "--workpath", os.path.join(ROOT, "build", "work")]
    for src, dest in datas:
        cmd += ["--add-data", f"{os.path.join(ROOT, src)}{os.pathsep}{dest}"]
    if os.path.exists(icon):
        cmd += ["--icon", icon]
    cmd.append(os.path.join(ROOT, "packaging", "entry.py"))
    print(" ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)
    built = os.path.join(ROOT, "dist", stem + (".exe" if sys.platform == "win32" else ""))
    final = os.path.join(ROOT, "dist", name)
    if built != final:
        shutil.move(built, final)
    digest = hashlib.sha256(open(final, "rb").read()).hexdigest()
    with open(final + ".sha256", "w", encoding="utf-8") as f:
        f.write(f"{digest}  {name}\n")
    print(f"{name}  {os.path.getsize(final) / 1e6:.1f} MB  sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
