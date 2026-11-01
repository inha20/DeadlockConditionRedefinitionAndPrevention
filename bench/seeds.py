"""시드 관리. 마스터 시드와 이름표(셀, 인스턴스 번호 등)에서 결정적으로 하위 시드를 만든다.

같은 (마스터 시드, 이름표)는 어느 실행, 어느 순서에서도 같은 값이다. 정책 사이 짝지은 비교(SP-1)는
같은 이름표를 모든 정책에 쓰는 것으로 한다.
"""
from __future__ import annotations

import hashlib

import numpy as np


def derive(master, *parts) -> int:
    key = ":".join([str(master)] + [str(p) for p in parts]).encode("utf-8")
    return int.from_bytes(hashlib.sha256(key).digest()[:8], "big")


def rng(master, *parts) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(derive(master, *parts)))
