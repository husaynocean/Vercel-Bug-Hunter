"""Contest definition + checkout. The scope list in the contest YAML is the
single source of truth for what the pipeline is allowed to analyse."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import yaml


class ScopeError(RuntimeError):
    pass


@dataclass
class Scope:
    files: list[str]                 # repo-relative POSIX paths, from the official scope
    project_dir: str = "."           # repo-relative dir of the Foundry/Hardhat project

    def __post_init__(self) -> None:
        self.files = [str(PurePosixPath(f)) for f in self.files]
        self._set = set(self.files)

    def project_relative(self) -> list[str]:
        """Scope paths relative to the build project (what tools report)."""
        base = PurePosixPath(self.project_dir)
        out = []
        for f in self.files:
            p = PurePosixPath(f)
            out.append(str(p.relative_to(base)) if base != PurePosixPath(".") else str(p))
        return out

    def contains(self, path: str, relative_to_project: bool = True) -> bool:
        p = PurePosixPath(path.replace("\\", "/"))
        if relative_to_project and self.project_dir not in (".", ""):
            p = PurePosixPath(self.project_dir) / p
        return str(p) in self._set


@dataclass
class Contest:
    id: str
    platform: str
    repo: str
    commit: str
    scope: Scope
    solc: str | None = None
    scope_file: str | None = None   # official scope.txt in the repo, cross-checked if present
    url: str | None = None
    notes: str = ""
    out_of_scope: list[str] = field(default_factory=list)
    known_issues: list[str] = field(default_factory=list)  # repo-relative automated reports
    sibling_files: list[str] = field(default_factory=list)  # other parts' scope (multi-project contests)
    group: str | None = None                                 # benchmark group for multi-part contests

    @classmethod
    def load(cls, path: str | Path) -> "Contest":
        raw = yaml.safe_load(Path(path).read_text())
        scope = Scope(files=raw["scope"]["files"], project_dir=raw["scope"].get("project_dir", "."))
        if not scope.files:
            raise ScopeError("contest has an empty scope; refusing to run")
        return cls(
            id=raw["id"], platform=raw["platform"], repo=raw["repo"], commit=raw["commit"],
            scope=scope, solc=raw.get("solc"), scope_file=raw["scope"].get("scope_file"),
            url=raw.get("url"), notes=raw.get("notes", ""),
            out_of_scope=raw.get("out_of_scope", []),
            known_issues=raw.get("known_issues", []),
            sibling_files=raw["scope"].get("sibling_files", []),
            group=raw.get("group"),
        )

    # ------------------------------------------------------------------ checkout
    def checkout(self, workdir: Path) -> Path:
        """Clone the official contest repo at the pinned commit. Returns repo root."""
        root = workdir / self.id / "repo"
        if not (root / ".git").exists():
            root.parent.mkdir(parents=True, exist_ok=True)
            _run(["git", "clone", "--quiet", self.repo, str(root)])
        head = _run(["git", "-C", str(root), "rev-parse", "HEAD"]).strip()
        if head != self.commit:
            _run(["git", "-C", str(root), "fetch", "--quiet", "origin", self.commit])
            _run(["git", "-C", str(root), "checkout", "--quiet", self.commit])
        _run(["git", "-C", str(root), "submodule", "update", "--init", "--recursive", "--depth", "1", "--quiet"])
        self.verify_scope(root)
        return root

    def verify_scope(self, root: Path) -> None:
        missing = [f for f in self.scope.files if not (root / f).is_file()]
        if missing:
            raise ScopeError(f"in-scope files missing at {self.commit[:10]}: {missing}")
        if self.scope_file and (root / self.scope_file).is_file():
            # Compared case-insensitively: official lists contain typos like `asd/` for `asD/`
            # (every yaml path was already checked to exist with its exact case above).
            official = {
                str(PurePosixPath(l.strip().removeprefix("./"))).lower()
                for l in (root / self.scope_file).read_text().splitlines()
                if l.strip() and not l.strip().startswith("#")
            }
            # Multi-project contests are split into one YAML per Foundry project ("parts");
            # each part lists the other parts' files so the union is still checked in full.
            ours = {f.lower() for f in self.scope.files} | {f.lower() for f in self.sibling_files}
            if official != ours:
                raise ScopeError(
                    "contest YAML scope disagrees with official scope file "
                    f"{self.scope_file}: only-in-yaml={sorted(ours - official)} "
                    f"only-in-official={sorted(official - ours)}"
                )

    def project_root(self, repo_root: Path) -> Path:
        return repo_root / self.scope.project_dir


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed:\n{r.stderr[-2000:]}")
    return r.stdout
