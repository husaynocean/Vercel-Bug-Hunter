"""Make sure forge / slither / semgrep / the pinned solc are usable."""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import urllib.request
from pathlib import Path

FOUNDRY_BIN = Path.home() / ".foundry" / "bin"
SVM_DIR = Path.home() / ".svm"
SOLC_RELEASE_URL = "https://github.com/ethereum/solidity/releases/download/v{v}/solc-static-linux"


def env() -> dict[str, str]:
    e = dict(os.environ)
    if FOUNDRY_BIN.is_dir() and str(FOUNDRY_BIN) not in e.get("PATH", ""):
        e["PATH"] = f"{FOUNDRY_BIN}:{e.get('PATH', '')}"
    e.setdefault("SEMGREP_ENABLE_VERSION_CHECK", "0")
    e.setdefault("SEMGREP_SEND_METRICS", "off")
    return e


def which(name: str) -> str | None:
    return shutil.which(name, path=env()["PATH"])


def ensure_solc(version: str) -> Path:
    """Install solc into forge's svm cache (fallback to GitHub releases when
    binaries.soliditylang.org is unreachable)."""
    target = SVM_DIR / version / f"solc-{version}"
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".part")
    urllib.request.urlretrieve(SOLC_RELEASE_URL.format(v=version), tmp)
    tmp.chmod(tmp.stat().st_mode | stat.S_IEXEC)
    out = subprocess.run([str(tmp), "--version"], capture_output=True, text=True).stdout
    if version not in out:
        tmp.unlink()
        raise RuntimeError(f"downloaded solc does not report version {version}: {out!r}")
    tmp.rename(target)
    return target


def check(solc: str | None = None) -> dict[str, str]:
    status = {}
    for tool in ("forge", "slither", "semgrep", "git"):
        status[tool] = which(tool) or "MISSING"
    if solc:
        status[f"solc {solc}"] = str(ensure_solc(solc))
    missing = [k for k, v in status.items() if v == "MISSING"]
    if missing:
        raise RuntimeError(f"missing tools: {missing}. See README#setup")
    return status
