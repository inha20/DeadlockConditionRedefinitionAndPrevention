"""결과 기록. 한 줄에 JSON 하나(JSONL)로 쓰고 읽는다. 환경 정보(SP-1, P4)와 입력 해시를 함께 남긴다.

개인 식별 정보는 남기지 않는다: 호스트 이름과 사용자 이름은 기록하지 않는다.
"""
from __future__ import annotations

import datetime
import gc
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections.abc import Iterable, Iterator


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest_of(obj, length: int = 16) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()[:length]


def state_digest(st) -> str:
    """BState의 (total, alloc, need, avail) 해시. avail은 total과 alloc에서 정해지는 값이지만, 정책이 avail만 바꿔 놓고
    돌려주지 않는 결함도 상태 복원 점검에 걸리도록 넣는다."""
    return digest_of([list(st.total), [list(r) for r in st.alloc], [list(r) for r in st.need], list(st.avail)])


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _cpu_model() -> str | None:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def _hypervisor() -> bool | None:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.lower().startswith("flags"):
                    return " hypervisor" in line
    except OSError:
        pass
    return None


def _read(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def _git(args: list[str], cwd: str) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def env_info(repo_root: str | None = None) -> dict:
    """실행 환경 기록. 컴파일러와 옵션 자리에는 인터프리터 정보를 쓴다(이 하니스는 파이썬이다)."""
    import numpy as np  # noqa: PLC0415
    import scipy  # noqa: PLC0415
    root = repo_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        affinity = len(os.sched_getaffinity(0))
    except AttributeError:
        affinity = None
    status = _git(["status", "--porcelain"], root)
    return {
        "utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_model": _cpu_model(),
        "cpu_count": os.cpu_count(),
        "cpu_affinity": affinity,
        "hypervisor_flag": _hypervisor(),
        "scaling_governor": _read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"),
        "timer_resolution_s": time.get_clock_info("perf_counter").resolution,
        "gc_enabled_at_start": gc.isenabled(),
        "git_commit": _git(["rev-parse", "HEAD"], root),
        "git_dirty": None if status is None else bool(status),
    }


class JsonlWriter:
    def __init__(self, path: str, append: bool = False) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._f = open(path, "a" if append else "w", encoding="utf-8")
        self.path = path
        self.count = 0

    def write(self, rec: dict) -> None:
        self._f.write(canonical_json(rec) + "\n")
        self.count += 1

    def close(self) -> None:
        self._f.flush()
        self._f.close()

    def __enter__(self) -> "JsonlWriter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def read_jsonl(path: str) -> Iterator[dict]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def select(records: Iterable[dict], **where) -> list[dict]:
    return [r for r in records if all(r.get(k) == v for k, v in where.items())]
