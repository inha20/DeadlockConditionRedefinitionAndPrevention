"""뱅커 입력 생성기(입력군 F-ex, F-rand, F-bound; prereg/RQ6.md §4)와 큰 입력용 빠른 분류기.

F-ex     소규모 전수. oracle.banker.all_states를 BState로 바꿔 쓴다.
F-rand   무작위. 후보를 만들고 안전 여부를 정확하게 분류해, 목표 안전 비율이 되도록 안전 쪽과 불안전 쪽에서
         각각 필요한 만큼만 받는 층화 거절 표집이다. 후보 생성 분포의 매개변수(phi, s)는 시도마다 사전 분포에서 뽑는다.
F-bound  경계와 적대적 입력. 교재식 최악 입력(스캔 순서의 역으로만 끝낼 수 있음)과 경계 상태.
이 생성기의 사전 분포와 매개변수는 파일럿으로 조정할 후보이며 동결 전에는 확정이 아니다.

safe_fast는 numpy 폐포로 안전 여부를 정확하게 구한다. 큰 입력의 분류에 쓰며, 소규모에서 oracle.banker의
세 판정과 일치하는지 bench/check_pipeline.py가 검사한다.
"""
from __future__ import annotations

import math

import numpy as np

from bench.seeds import rng
from bench.state import BState


def safe_fast_arrays(avail, alloc, need) -> bool:
    work = np.array(avail, dtype=np.int64)
    alloc = np.asarray(alloc, dtype=np.int64)
    need = np.asarray(need, dtype=np.int64)
    done = np.zeros(len(alloc), dtype=bool)
    while True:
        runnable = (~done) & (need <= work).all(axis=1)
        if not runnable.any():
            break
        work = work + alloc[runnable].sum(axis=0)
        done |= runnable
    return bool(done.all())


def closure_stats(avail, alloc, need):
    """(안전 여부, 폐포 반복 횟수, 끝낸 프로세스 수). 반복 한 번은 그 시점에 끝낼 수 있는 프로세스를 모두 끝낸다.
    파일럿에서 생성한 입력이 너무 쉬운지(반복 1–2번에 끝남)를 보는 서술용 값이다."""
    work = np.array(avail, dtype=np.int64)
    alloc = np.asarray(alloc, dtype=np.int64)
    need = np.asarray(need, dtype=np.int64)
    done = np.zeros(len(alloc), dtype=bool)
    passes = 0
    while True:
        runnable = (~done) & (need <= work).all(axis=1)
        if not runnable.any():
            break
        passes += 1
        work = work + alloc[runnable].sum(axis=0)
        done |= runnable
    return bool(done.all()), passes, int(done.sum())


def safe_fast(st: BState) -> bool:
    return safe_fast_arrays(st.avail, st.alloc, st.need)


def request_outcome_fast(st: BState, i: int, req) -> str:
    """교재식 요청 의미(ERROR, WAIT, GRANT, DENY)를 정확 분류기로 구한 것(큰 입력의 오라클 대용)."""
    m = st.m
    if any(req[r] > st.need[i][r] for r in range(m)):
        return "ERROR"
    if any(req[r] > st.avail[r] for r in range(m)):
        return "WAIT"
    avail = np.array(st.avail, dtype=np.int64) - np.array(req, dtype=np.int64)
    alloc = np.array(st.alloc, dtype=np.int64)
    need = np.array(st.need, dtype=np.int64)
    alloc[i] += np.array(req, dtype=np.int64)
    need[i] -= np.array(req, dtype=np.int64)
    return "GRANT" if safe_fast_arrays(avail, alloc, need) else "DENY"


# ---------------------------------------------------------------- F-ex

def f_ex(n: int, total):
    from oracle.banker import all_states  # noqa: PLC0415
    for b in all_states(n, tuple(total)):
        yield BState.from_oracle(b)


# ---------------------------------------------------------------- F-rand

def random_candidate(g, n: int, m: int, phi: float, s: float):
    """총량은 n에 비례하는 범위에서, 최대 청구는 총량의 s 이하로, 보유는 청구 이하이고 종류별 합이 총량의 phi 이하로."""
    tlo, thi = max(3, n // 2), max(6, 2 * n)
    total = g.integers(tlo, thi + 1, size=m).astype(np.int64)
    maxc = np.floor(total[None, :] * s * g.random((n, m))).astype(np.int64)
    alloc = np.floor(maxc * g.random((n, m))).astype(np.int64)
    cap_alloc = np.floor(phi * total).astype(np.int64)
    colsum = alloc.sum(axis=0)
    over = colsum > cap_alloc
    if over.any():
        scale = np.where(over, cap_alloc / np.maximum(colsum, 1), 1.0)
        alloc = np.floor(alloc * scale[None, :]).astype(np.int64)
    need = maxc - alloc
    assert (alloc.sum(axis=0) <= total).all() and (need >= 0).all() and (maxc <= total[None, :]).all()
    return total, alloc, need


PHI_RANGE = (0.2, 0.98)
S_RANGE = (0.02, 1.0)


def candidate_at(master, cell: str, n: int, m: int, attempt: int):
    """cell의 attempt번째 후보. 후보는 (master, cell, n, m, attempt)만으로 정해지므로 어느 인스턴스든
    표집 과정을 다시 돌리지 않고 개별로 다시 만들 수 있다(큰 입력을 메모리에 쌓아 두지 않으려는 설계).
    반환: (phi, s, total, alloc, need)."""
    g = rng(master, "f-rand", cell, n, m, attempt)
    phi = float(g.uniform(*PHI_RANGE))
    s = float(math.exp(g.uniform(math.log(S_RANGE[0]), math.log(S_RANGE[1]))))
    total, alloc, need = random_candidate(g, n, m, phi, s)
    return phi, s, total, alloc, need


def select_cell(master, cell: str, n: int, m: int, count: int, target_safe: float, max_attempts_factor: int = 400):
    """한 셀(n, m, 목표 안전 비율)에서 count개를 고른다. 반환: (조리법 목록, 요약).

    후보를 attempt = 1, 2, ...의 차례로 만들고 정확 분류기로 안전 여부를 가려, 안전 쪽 round(count * target_safe)개와
    불안전 쪽 나머지가 찬 뒤에 멈춘다. 각 쪽은 먼저 나온 후보부터 받는다. 시도가 max_attempts_factor * count를 넘으면
    멈추고 부족분을 요약에 적는다(부족분이 있으면 그 셀은 목표 비율을 채우지 못한 것이다).
    조리법: dict(idx, attempt, safe, phi, s). idx는 attempt 순서로 0부터 매긴다.
    """
    want = {True: int(round(count * target_safe))}
    want[False] = count - want[True]
    got = {True: [], False: []}
    attempts = 0
    max_attempts = max_attempts_factor * count
    while (len(got[True]) < want[True] or len(got[False]) < want[False]) and attempts < max_attempts:
        attempts += 1
        phi, s, total, alloc, need = candidate_at(master, cell, n, m, attempts)
        avail = total - alloc.sum(axis=0)
        is_safe = safe_fast_arrays(avail, alloc, need)
        if len(got[is_safe]) < want[is_safe]:
            got[is_safe].append({"attempt": attempts, "safe": is_safe, "phi": phi, "s": s})
    recipes = sorted(got[True] + got[False], key=lambda d: d["attempt"])
    for k, d in enumerate(recipes):
        d["idx"] = k
    summary = {"cell": cell, "n": n, "m": m, "count": count, "target_safe": target_safe,
               "attempts": attempts, "got_safe": len(got[True]), "got_unsafe": len(got[False]),
               "short_safe": want[True] - len(got[True]), "short_unsafe": want[False] - len(got[False])}
    return recipes, summary


def state_from_recipe(master, cell: str, n: int, m: int, recipe) -> BState:
    _, _, total, alloc, need = candidate_at(master, cell, n, m, recipe["attempt"])
    return BState.make(total, alloc, need)


def sample_cell(master, cell: str, n: int, m: int, count: int, target_safe: float, max_attempts_factor: int = 400):
    """select_cell과 state_from_recipe를 합친 편의 함수(작은 셀과 검사용). 반환: (인스턴스 목록, 요약)."""
    recipes, summary = select_cell(master, cell, n, m, count, target_safe, max_attempts_factor)
    out = [dict(r, state=state_from_recipe(master, cell, n, m, r)) for r in recipes]
    return out, summary


# ---------------------------------------------------------------- F-bound

WORST_KINDS = ("chain-first", "chain-last", "chain-unsafe-first", "chain-unsafe-last")


def worst_case(n: int, m: int, kind: str) -> BState:
    """교재식 최악 입력(prereg/RQ6.md §4 F-bound (i)). 안전 순서가 스캔 순서의 역이라 바깥 반복이 n번 필요하다.

    chain-*      프로세스 p는 종류마다 보유 1, 가용 1, 총량 n+1. 필요량은 마지막 종류에서만 또는 모든 종류에서 n-p.
                 안전하며 끝낼 수 있는 프로세스는 매번 하나뿐이다. 벡터 비교는 n(n+1)/2번.
    chain-unsafe-*  앞의 두 프로세스를 서로 기다리는 쌍(필요량 n)으로 바꾼 불안전 입력. 쌍이 맨 앞이라 훑을 때마다 실패 비교가 둘 더 든다.
    *-first      필요량이 모든 종류에 있어 첫 성분에서 비교가 실패한다(단락 평가가 비교 횟수를 줄이는 쪽).
    *-last       필요량이 마지막 종류에만 있어 실패하기 전까지 m개 성분을 모두 비교한다(스칼라 비교가 가장 많은 쪽).
    """
    if kind not in WORST_KINDS:
        raise ValueError(kind)
    if n < 2 or m < 1:
        raise ValueError("n >= 2, m >= 1")
    last = kind.endswith("last")
    unsafe = "unsafe" in kind
    total = [n + 1] * m
    alloc = [[1] * m for _ in range(n)]

    def vec(k: int):
        return [0] * (m - 1) + [k] if last else [k] * m

    if unsafe:
        c = n - 2
        need = [vec(n), vec(n)] + [vec(c - j) for j in range(c)]
    else:
        need = [vec(n - p) for p in range(n)]
    return BState.make(total, alloc, need)


def worst_case_chain(n: int, m: int) -> BState:
    return worst_case(n, m, "chain-first")


def sample_requests(master, cell: str, idx: int, st: BState, k: int):
    """한 인스턴스에서 요청 k개를 뽑는다. 네 판정(ERROR, WAIT, GRANT, DENY)이 모두 나오도록 세 방식을 섞는다.
    45%  [0, min(need_i, avail)] 범위: 가용량 안이라 GRANT 또는 DENY
    45%  [0, need_i] 범위: 가용량을 넘으면 WAIT
    10%  [0, need_i]에서 뽑은 뒤 한 종류를 need_i + 1로: ERROR
    영벡터 요청은 제외한다. 반환: [(i, [..]), ...]. 뽑을 수 없으면 k개보다 적을 수 있다."""
    g = rng(master, "requests", cell, st.n, st.m, idx)
    out = []
    tries = 0
    while len(out) < k and tries < 20 * k:
        tries += 1
        i = int(g.integers(0, st.n))
        u = g.random()
        if u < 0.45:
            hi = [min(st.need[i][r], st.avail[r]) for r in range(st.m)]
        else:
            hi = st.need[i]
        req = [int(g.integers(0, h + 1)) for h in hi]
        if u >= 0.9:
            r = int(g.integers(0, st.m))
            req[r] = st.need[i][r] + 1
        if any(req):
            out.append((i, req))
    return out


def boundary_states():
    """경계 상태 몇 개(이름, 상태, 안전 여부)."""
    out = []
    out.append(("n=1, m=1, 필요=가용", BState.make([2], [[1]], [[1]]), True))
    out.append(("n=2, m=1, 필요=가용=2", BState.make([4], [[1], [1]], [[2], [2]]), True))
    out.append(("모두 필요 0", BState.make([3, 3], [[1, 1], [1, 1]], [[0, 0], [0, 0]]), True))
    out.append(("종류 하나를 아무도 청구하지 않음", BState.make([3, 5], [[1, 0], [1, 0]], [[1, 0], [1, 0]]), True))
    out.append(("보유 없음", BState.make([2, 2], [[0, 0], [0, 0]], [[2, 1], [1, 2]]), True))
    out.append(("m=1 교착", BState.make([2], [[1], [1]], [[1], [1]]), False))
    out.append(("m=2 맞물림", BState.make([1, 1], [[1, 0], [0, 1]], [[0, 1], [1, 0]]), False))
    return out
