"""하니스(bench/)의 자체 점검. 실행: python3 -I bench/check_pipeline.py formal/rq6/harness-check-results.md

점검하는 것: 시드, 연산 계측, 상태 변환, 교재식 기준 구현(오라클 대조의 맛보기), 입력 생성기, 통계 도구(독립 구현·시뮬레이션·닫힌 형태),
실행기의 끝에서 끝까지(JSONL, 재현성, 프로세스 사이 결정성), 판정 점검이 틀린 정책을 실제로 잡아내는지(변이체).
점검은 정확성의 증명이 아니라 알려진 답, 독립 구현, 변이체에 대한 반례 탐색이다. AI(Claude)가 쓴 초안이며 사람의 검토 전이다.
소규모 전수 차등 테스트(SP-5의 ②)는 bench/check_banker_policies.py가 맡는다(WP6.2).
"""
from __future__ import annotations

import itertools
import json
import math
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

import oracle.banker as ob  # noqa: E402
from bench import gen_banker as G  # noqa: E402
from bench import results as R  # noqa: E402
from bench import runner as RU  # noqa: E402
from bench import stats as S  # noqa: E402
from bench import summarize as SU  # noqa: E402
from bench.ops import CountingOps, PlainOps  # noqa: E402
from bench.policies import banker as pb  # noqa: E402
from bench.policies.banker import mutants as MU  # noqa: E402
from bench.policies.banker.base import DENY, ERROR, GRANT, WAIT  # noqa: E402
from bench.policies.banker.textbook import TextbookRestart, TextbookSweep  # noqa: E402
from bench.seeds import derive, rng  # noqa: E402
from bench.state import BState  # noqa: E402

CHECKS: list[tuple[str, str, bool, str]] = []
NUMBERS: list[tuple[str, str, str]] = []
SECTION_TIME: dict[str, float] = {}


def check(section: str, name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((section, name, bool(ok), detail))


def number(section: str, name: str, value: str) -> None:
    NUMBERS.append((section, name, value))


# ---------------------------------------------------------------- 시드

def sec_seeds() -> None:
    s = "시드"
    check(s, "같은 이름표는 같은 값", derive(1, "a", 2) == derive(1, "a", 2))
    check(s, "이름표가 다르면 값이 다름", len({derive(1, "a"), derive(1, "b"), derive(2, "a"), derive(1, "a", 0)}) == 4)
    a = rng(5, "x").integers(0, 10**9, 8).tolist()
    b = rng(5, "x").integers(0, 10**9, 8).tolist()
    c = rng(5, "y").integers(0, 10**9, 8).tolist()
    check(s, "같은 키의 난수열은 같고 다른 키의 난수열은 다름", a == b and a != c)
    here = os.path.abspath(__file__)
    outs = []
    for hs in ("1", "2"):
        code = ("import sys; sys.path.insert(0, %r); from bench.seeds import derive, rng; "
                "print(derive(9,'q',3), rng(9,'q',3).integers(0,10**9,3).tolist())" % ROOT)
        r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True,
                           env={"PYTHONHASHSEED": hs, "PATH": os.environ.get("PATH", "")})
        outs.append(r.stdout.strip())
    check(s, "프로세스와 해시 시드가 달라도 같은 값", outs[0] == outs[1] and outs[0] != "", outs[0])
    del here


# ---------------------------------------------------------------- 연산 계측

def sec_ops() -> None:
    s = "연산 계측"
    o = CountingOps()
    check(s, "leq([1,2],[1,1]) = False, 스칼라 2번", (not o.leq([1, 2], [1, 1])) and (o.vec_cmp, o.sca_cmp) == (1, 2))
    o = CountingOps()
    check(s, "leq([2,0],[1,1]) = False, 스칼라 1번(단락)", (not o.leq([2, 0], [1, 1])) and (o.vec_cmp, o.sca_cmp) == (1, 1))
    o = CountingOps()
    check(s, "leq([0,0],[1,1]) = True, 스칼라 2번", o.leq([0, 0], [1, 1]) and (o.vec_cmp, o.sca_cmp) == (1, 2))
    o = CountingOps()
    w = [1, 2, 3]
    o.vadd(w, [1, 1, 1])
    o.vsub(w, [0, 1, 2])
    check(s, "vadd/vsub의 값과 횟수", w == [2, 2, 2] and o.vec_add == 2)
    o.tick()
    o.tick("sweeps", 3)
    check(s, "tick의 이름별 횟수", o.iters == 1 and o.extra == {"sweeps": 3})
    o.reset()
    check(s, "reset", o.snapshot() == {"vec_cmp": 0, "sca_cmp": 0, "vec_add": 0, "iters": 0})
    g = rng(1, "ops")
    ok = True
    for _ in range(5000):
        m = int(g.integers(1, 6))
        a = g.integers(0, 4, m).tolist()
        b = g.integers(0, 4, m).tolist()
        if PlainOps().leq(a, b) != CountingOps().leq(a, b) or PlainOps().leq(a, b) != all(x <= y for x, y in zip(a, b)):
            ok = False
    check(s, "PlainOps와 CountingOps의 비교 결과가 같고 정의와 같음(5,000쌍)", ok)


# ---------------------------------------------------------------- 상태

def sec_state() -> None:
    s = "상태 변환"
    st = BState.make([3, 2], [[1, 0], [1, 1]], [[1, 1], [0, 1]])
    check(s, "avail은 total - 보유 합", st.avail == [1, 1])
    b = st.to_oracle()
    back = BState.from_oracle(b)
    check(s, "BState → 오라클 → BState 왕복", back == st and back is not st)
    cp = st.copy()
    cp.alloc[0][0] = 9
    check(s, "copy는 깊은 복사", st.alloc[0][0] == 1)
    bad = BState.make([1], [[1], [1]], [[0], [0]])
    try:
        bad.to_oracle()
        raised = False
    except ValueError:
        raised = True
    check(s, "유효하지 않은 상태(보유 합 > 총량)는 오라클 변환에서 거부", raised)


# ---------------------------------------------------------------- 정책(맛보기)

def _textbook_state() -> BState:
    b = ob.Banker(total=(10, 5, 7), alloc=((0, 1, 0), (2, 0, 0), (3, 0, 2), (2, 1, 1), (0, 0, 2)),
                  maxc=((7, 5, 3), (3, 2, 2), (9, 0, 2), (2, 2, 2), (4, 3, 3)))
    return BState.from_oracle(b)


def sec_policies() -> None:
    s = "교재식 기준 구현(맛보기)"
    R_, S_ = TextbookRestart(), TextbookSweep()
    st = _textbook_state()
    for P in (R_, S_):
        check(s, f"{P.name}: 교재 예제 5×3은 안전", P.is_safe(st, CountingOps()))
        d0 = R.state_digest(st)
        r1 = P.request(st, 1, [1, 0, 2], CountingOps())
        check(s, f"{P.name}: P1의 (1,0,2)는 GRANT", r1 == GRANT)
        st2 = st.copy()
        st2.avail = [a - x for a, x in zip(st2.avail, [1, 0, 2])]
        st2.alloc[1] = [a + x for a, x in zip(st2.alloc[1], [1, 0, 2])]
        st2.need[1] = [a - x for a, x in zip(st2.need[1], [1, 0, 2])]
        check(s, f"{P.name}: 요청 뒤 원래 상태 그대로(해시)", R.state_digest(st) == d0)
        check(s, f"{P.name}: 그 뒤 P4의 (3,3,0)은 WAIT", P.request(st2, 4, [3, 3, 0], CountingOps()) == WAIT)
        check(s, f"{P.name}: 그 뒤 P0의 (0,2,0)은 DENY", P.request(st2, 0, [0, 2, 0], CountingOps()) == DENY)
        check(s, f"{P.name}: P1이 필요량보다 많이 요청하면 ERROR", P.request(st, 1, [4, 0, 0], CountingOps()) == ERROR)

    # 소규모 전수에서 네 구현(오라클, 두 정책, numpy 닫힘)의 안전성 판정이 같은가
    ranges = [(3, (2, 2)), (3, (1, 1, 1)), (4, (2, 1))]
    states = bad = unsafe = 0
    req_checked = req_bad = 0
    outcome_seen: set[str] = set()
    t0 = time.time()
    for n, tot in ranges:
        for k, b in enumerate(ob.all_states(n, tot)):
            st = BState.from_oracle(b)
            truth = ob.safe_oracle(b)
            states += 1
            unsafe += (not truth)
            v = [R_.is_safe(st, PlainOps()), S_.is_safe(st, PlainOps()), G.safe_fast(st)]
            if any(x != truth for x in v):
                bad += 1
            if k % 7 == 0:
                need = b.need()
                avail = b.avail()
                for i in range(n):
                    reqs = list(itertools.islice(ob.request_vectors(b, i), 4))
                    full = tuple(min(need[i][r], avail[r]) for r in range(b.m))
                    if any(full):
                        reqs.append(full)
                    over = tuple(need[i][r] + (1 if r == 0 else 0) for r in range(b.m))
                    reqs.append(over)
                    wait = tuple(avail[r] + 1 if (r == 0 and avail[r] + 1 <= need[i][r]) else 0 for r in range(b.m))
                    if any(wait):
                        reqs.append(wait)
                    for req in reqs:
                        want = ob.request_outcome(b, i, req)
                        outcome_seen.add(want)
                        for P in (R_, S_):
                            got = P.request(st, i, list(req), PlainOps())
                            req_checked += 1
                            if got != want:
                                req_bad += 1
    check(s, f"안전성 판정: 오라클 = 교재식(두 구현) = numpy 닫힘, 상태 {states:,}개", bad == 0, f"불일치 {bad}")
    check(s, "위 범위에 안전·불안전이 모두 있음(비공허)", 0 < unsafe < states, f"불안전 {unsafe:,}")
    check(s, f"요청 판정: 오라클과 교재식 두 구현, 요청 {req_checked:,}건", req_bad == 0, f"불일치 {req_bad}")
    check(s, "위 요청에 네 판정이 모두 나옴(비공허)", outcome_seen == {ERROR, WAIT, GRANT, DENY}, str(sorted(outcome_seen)))
    number(s, "맛보기 범위 시간(초)", f"{time.time() - t0:.1f}")

    # 최악 입력의 비교 횟수 공식
    ok_all = True
    detail = []
    for n in (2, 3, 5, 8, 16, 33):
        for m in (1, 3):
            T = n * (n + 1) // 2
            for kind in G.WORST_KINDS:
                stw = G.worst_case(n, m, kind)
                unsafe_kind = "unsafe" in kind
                want_vec = T - 1 if unsafe_kind else T
                for P in (R_, S_):
                    o = CountingOps()
                    res = P.is_safe(stw, o)
                    if res == unsafe_kind or o.vec_cmp != want_vec:
                        ok_all = False
                        detail.append(f"{P.name} n={n} m={m} {kind}: res={res} vec={o.vec_cmp} want={want_vec}")
                # 정확 오라클과의 대조(n이 작을 때)
                if n <= 8:
                    if ob.safe_oracle(stw.to_oracle()) == unsafe_kind:
                        ok_all = False
                        detail.append(f"오라클 불일치 n={n} m={m} {kind}")
    check(s, "최악 입력: 벡터 비교 횟수 = n(n+1)/2 (안전) 또는 n(n+1)/2 − 1 (불안전), 판정은 오라클과 일치", ok_all, "; ".join(detail[:3]))
    n, m = 12, 4
    first, last = CountingOps(), CountingOps()
    TextbookRestart().is_safe(G.worst_case(n, m, "chain-first"), first)
    TextbookRestart().is_safe(G.worst_case(n, m, "chain-last"), last)
    T = n * (n + 1) // 2
    check(s, "스칼라 비교: chain-last는 m × 벡터 비교, chain-first는 단락으로 더 적음",
          last.sca_cmp == m * T and first.sca_cmp == (T - n) + m * n, f"last={last.sca_cmp} first={first.sca_cmp}")
    sw = CountingOps()
    TextbookSweep().is_safe(G.worst_case(10, 2, "chain-first"), sw)
    check(s, "훑기 이어서 하기: 최악 입력에서 훑기 횟수 = n", sw.extra.get("sweeps") == 10, str(sw.extra))


# ---------------------------------------------------------------- 생성기

def sec_generator() -> None:
    s = "입력 생성기"
    g = rng(3, "cand")
    valid = True
    for _ in range(300):
        n = int(g.integers(1, 9))
        m = int(g.integers(1, 5))
        phi = float(g.uniform(0.2, 0.98))
        sv = float(np.exp(g.uniform(np.log(0.02), np.log(1.0))))
        total, alloc, need = G.random_candidate(g, n, m, phi, sv)
        try:
            BState.make(total, alloc, need).to_oracle()
        except ValueError:
            valid = False
    check(s, "무작위 후보 300개가 모두 유효한 뱅커 상태(오라클 검증기 통과)", valid)

    ok = True
    info = []
    for (n, m) in ((8, 3), (16, 4)):
        for tgt in (0.1, 0.5, 0.9):
            recs, summ = G.select_cell(11, f"n{n}m{m}s{tgt}", n, m, 30, tgt)
            exp_safe = int(round(30 * tgt))
            if not (summ["got_safe"] == exp_safe and summ["got_unsafe"] == 30 - exp_safe and summ["short_safe"] == 0
                    and summ["short_unsafe"] == 0):
                ok = False
            info.append(f"n{n}m{m}s{tgt}: 시도 {summ['attempts']}")
    check(s, "층화 표집: 목표 안전 비율(0.1, 0.5, 0.9)대로 30개씩 채움", ok, "; ".join(info))

    a, _ = G.sample_cell(11, "n8m3s0.5", 8, 3, 20, 0.5)
    b, _ = G.sample_cell(11, "n8m3s0.5", 8, 3, 20, 0.5)
    c, _ = G.sample_cell(12, "n8m3s0.5", 8, 3, 20, 0.5)
    same = all(R.state_digest(x["state"]) == R.state_digest(y["state"]) for x, y in zip(a, b))
    diff = any(R.state_digest(x["state"]) != R.state_digest(y["state"]) for x, y in zip(a, c))
    check(s, "같은 마스터 시드는 같은 인스턴스, 다른 마스터 시드는 다른 인스턴스", same and diff)
    recipes, _ = G.select_cell(11, "n8m3s0.5", 8, 3, 20, 0.5)
    k = 13
    st_k = G.state_from_recipe(11, "n8m3s0.5", 8, 3, recipes[k])
    check(s, "번호 순서와 상관없이 인스턴스 하나를 다시 만들 수 있음(조리법)",
          R.state_digest(st_k) == R.state_digest(a[k]["state"]))
    check(s, "조리법이 적은 안전 여부와 numpy 정확 분류가 일치", all(G.safe_fast(x["state"]) == x["safe"] for x in a))

    # 생성기가 만드는 분포의 소규모 상태에서 오라클 판정과 numpy 닫힘의 일치(층화 표집이라 안전·불안전이 둘 다 충분하다)
    bad = n_safe = n_unsafe = total_states = 0
    yields = []
    for (n, m, tgt) in ((5, 3, 0.5), (6, 3, 0.1), (6, 3, 0.5), (6, 3, 0.9), (8, 3, 0.5), (10, 4, 0.5), (12, 4, 0.5)):
        cell = f"chk-n{n}m{m}s{tgt}"
        insts, summ = G.sample_cell(4, cell, n, m, 60, tgt)
        yields.append(f"n{n}m{m}s{tgt}: 시도 {summ['attempts']}")
        for d in insts:
            st = d["state"]
            b = st.to_oracle()
            verdicts = [ob.safe_oracle(b), ob.safe_dp(b), G.safe_fast(st)]
            if n <= 7:
                verdicts.append(ob.safe_perm(b)[0])
            total_states += 1
            if len(set(verdicts)) != 1 or verdicts[0] != d["safe"]:
                bad += 1
            n_safe += verdicts[0]
            n_unsafe += (not verdicts[0])
    check(s, f"numpy 닫힘(safe_fast)이 오라클 판정과 일치(n ≤ 7은 세 판정, 그 위는 둘), 생성기 분포의 소규모 층화 표본 {total_states}개",
          bad == 0, f"안전 {n_safe}, 불안전 {n_unsafe}")
    check(s, "위 표본에 안전·불안전이 모두 100개 이상(비공허)", n_safe >= 100 and n_unsafe >= 100)
    number(s, "소규모 층화 표집 수율", "; ".join(yields))

    # 요청 판정
    g = rng(5, "req")
    bad = 0
    seen: set[str] = set()
    total_req = 0
    for _ in range(1500):
        n = int(g.integers(1, 6))
        m = int(g.integers(1, 4))
        phi = float(g.uniform(0.2, 0.98))
        sv = float(np.exp(g.uniform(np.log(0.05), np.log(1.0))))
        total, alloc, need = G.random_candidate(g, n, m, phi, sv)
        st = BState.make(total, alloc, need)
        b = st.to_oracle()
        for i, req in G.sample_requests(5, "req", total_req, st, 4):
            total_req += 1
            want = ob.request_outcome(b, i, tuple(req))
            seen.add(want)
            if G.request_outcome_fast(st, i, req) != want:
                bad += 1
    check(s, f"request_outcome_fast가 오라클과 일치, 요청 {total_req:,}건", bad == 0)
    check(s, "표집한 요청에 네 판정이 모두 나옴(비공허)", seen == {ERROR, WAIT, GRANT, DENY}, str(sorted(seen)))

    # 경계 상태
    ok = True
    for name, st, expect in G.boundary_states():
        if ob.safe_oracle(st.to_oracle()) != expect or G.safe_fast(st) != expect:
            ok = False
    check(s, "경계 상태 7개의 판정이 기대와 오라클에 일치", ok)

    st = G.worst_case(9, 2, "chain-first")
    safe, passes, done = G.closure_stats(st.avail, st.alloc, st.need)
    check(s, "closure_stats: 최악 입력은 폐포 반복이 n번", safe and passes == 9 and done == 9, f"passes={passes}")


# ---------------------------------------------------------------- 통계

def sec_stats() -> None:
    s = "통계 도구"
    check(s, "required_resamples(0.95) = 10,000", S.required_resamples(0.95) == 10_000)
    lv = S.adjusted_level(20)
    check(s, "adjusted_level(20) = 0.9975, required_resamples는 80,000 이상(꼬리에 100개)",
          abs(lv - 0.9975) < 1e-12 and S.required_resamples(lv) >= 80_000, str(S.required_resamples(lv)))

    ok = True
    for n in (1, 7, 49, 200):
        lo0, hi0 = S.clopper_pearson(0, n)
        lo1, hi1 = S.clopper_pearson(n, n)
        ok &= lo0 == 0.0 and abs(hi0 - (1 - 0.025 ** (1 / n))) < 1e-12
        ok &= hi1 == 1.0 and abs(lo1 - 0.025 ** (1 / n)) < 1e-12
    check(s, "Clopper–Pearson: x = 0과 x = n의 닫힌 형태와 일치", ok)

    worst = 0.0
    for n in (1, 5, 20, 49, 120):
        for x in sorted({0, 1, n // 4, n // 2, n - 1, n} & set(range(n + 1))):
            a = S.clopper_pearson(x, n)
            b = S.clopper_pearson_bisect(x, n)
            worst = max(worst, abs(a[0] - b[0]), abs(a[1] - b[1]))
    check(s, "Clopper–Pearson: 베타 분위수 구현과 이분법 독립 구현이 1e-9 안에서 일치", worst < 1e-9, f"최대 차 {worst:.2e}")
    number(s, "CP 95% 구간 0/49", "(%.4f, %.4f)" % S.clopper_pearson(0, 49))
    number(s, "CP 95% 구간 1/49", "(%.4f, %.4f)" % S.clopper_pearson(1, 49))

    g = rng(21, "cov")
    ln = lambda g_, n: np.exp(g_.normal(0.0, 0.5, n))             # 중앙값 1인 로그정규
    cov = S.coverage_experiment(ln, 1.0, 30, trials=500, level=0.95, B=1000, g=g, stat="median")
    check(s, "중앙값의 백분위 부트스트랩 구간 덮임률이 0.88–0.99 (로그정규, n = 30, 500회)", 0.88 <= cov <= 0.99, f"{cov:.3f}")
    number(s, "중앙값 구간 덮임률", f"{cov:.3f}")

    hits = 0
    tr = 400
    for _ in range(tr):
        b_ = np.exp(g.normal(0.0, 0.7, 30))
        a_ = 0.9 * b_ * np.exp(g.normal(0.0, 0.2, 30))
        ci = S.paired_ratio_ci(a_, b_, 0.95, 1000, g)
        hits += ci["lo"] <= math.exp(np.log(0.9)) <= ci["hi"]
    cov2 = hits / tr
    check(s, "짝지은 비율 기하평균 구간 덮임률이 0.88–0.99 (참값 0.9, n = 30, 400회)", 0.88 <= cov2 <= 0.99, f"{cov2:.3f}")
    number(s, "짝지은 비율 구간 덮임률", f"{cov2:.3f}")

    ci1 = S.percentile_ci([1, 2, 3, 4, 5, 6, 7, 8], "median", 0.95, 2000, rng(1, "d"))
    ci2 = S.percentile_ci([1, 2, 3, 4, 5, 6, 7, 8], "median", 0.95, 2000, rng(1, "d"))
    check(s, "같은 Generator 키는 같은 구간", ci1 == ci2)
    ci = {"hi": 1.04}
    check(s, "not_worse/clearly_better 판정: 상한 1.04 → 나쁘지 않음(δ = 0.05), 유의하게 좋지는 않음",
          S.not_worse(ci, 0.05) and not S.clearly_better(ci))
    check(s, "상한 0.97 → 유의하게 좋음", S.clearly_better({"hi": 0.97}))

    ex = S.loglog_slope([16, 32, 64, 128], [3 * 16 ** 2, 3 * 32 ** 2, 3 * 64 ** 2, 3 * 128 ** 2])
    check(s, "loglog_slope: y = 3x²의 기울기 2", abs(ex["slope"] - 2.0) < 1e-12 and ex["r2"] > 1 - 1e-12)
    pts = [(x, [3.0 * x ** 2] * 5) for x in (16, 32, 64, 128)]
    sc = S.slope_ci(pts, 0.95, 500, rng(2, "s"))
    check(s, "slope_ci: 잡음 없는 자료의 구간 폭 0", abs(sc["hi"] - sc["lo"]) < 1e-12 and abs(sc["slope"] - 2) < 1e-12)
    g = rng(22, "slope")
    hits = 0
    tr = 200
    for _ in range(tr):
        pts = [(x, 3.0 * x ** 2 * np.exp(g.normal(0, 0.3, 30))) for x in (16, 32, 64, 128, 256, 512)]
        sc = S.slope_ci(pts, 0.95, 500, g)
        hits += sc["lo"] <= 2.0 <= sc["hi"]
    cov3 = hits / tr
    check(s, "기울기 부트스트랩 구간 덮임률이 0.85–0.99 (참값 2, 점 6개 × 30, 200회)", 0.85 <= cov3 <= 0.99, f"{cov3:.3f}")
    number(s, "기울기 구간 덮임률", f"{cov3:.3f}")


# ---------------------------------------------------------------- 실행기

TINY_SPECS = [
    RU.CellSpec("rand-n16m4s0.5", "F-rand", 16, 4, count=12, target_safe=0.5, requests=6),
    RU.CellSpec("rand-n32m4s0.1", "F-rand", 32, 4, count=12, target_safe=0.1, requests=6),
    RU.CellSpec("rand-n32m4s0.9", "F-rand", 32, 4, count=12, target_safe=0.9, requests=6),
    RU.CellSpec("bound-n16-chain-first", "F-bound", 16, 4, kind="chain-first"),
    RU.CellSpec("bound-n16-chain-last", "F-bound", 16, 4, kind="chain-last"),
    RU.CellSpec("bound-n16-unsafe-last", "F-bound", 16, 4, kind="chain-unsafe-last"),
]
TINY_POLICIES = ["textbook-restart", "textbook-sweep"]


def tiny_run(out_path: str, run_id: str = "tiny") -> dict:
    return RU.execute(master=2026, specs=TINY_SPECS, policy_names=TINY_POLICIES, out_path=out_path, run_id=run_id,
                      time_target_ns=100_000, time_repeats=3, repo_root=ROOT)


def _count_lines(path: str) -> list[str]:
    out = []
    for r in R.read_jsonl(path):
        if r["rec"] == "count":
            r = dict(r)
            r.pop("run", None)
            out.append(R.canonical_json(r))
    return out


def sec_runner(tmp: str) -> None:
    s = "실행기(끝에서 끝까지)"
    p1 = os.path.join(tmp, "a.jsonl")
    p2 = os.path.join(tmp, "b.jsonl")
    info = tiny_run(p1, "tiny-a")
    tiny_run(p2, "tiny-b")
    recs = list(R.read_jsonl(p1))
    head, foot = recs[0], recs[-1]
    check(s, "머리·꼬리 기록과 스키마", head["rec"] == "header" and foot["rec"] == "footer" and head["schema"] == 1
          and "env" in head and head["env"]["python"], f"기록 {len(recs)}건")
    check(s, "머리 기록에 환경 정보(CPU 모델, 코어 수, 파이썬·numpy 버전, git 커밋)가 있음",
          all(k in head["env"] for k in ("cpu_model", "cpu_count", "numpy", "python", "git_commit", "platform")))
    n_tasks = head["tasks"]
    sizes = {c["cell"]: (1 if c.get("kind") else None) for c in head["cell_summaries"]}
    exp_count = 0
    for sp in TINY_SPECS:
        size = 1 if sp.family == "F-bound" else sp.count
        exp_count += size * len(TINY_POLICIES) * (1 + sp.requests)
    cnt = [r for r in recs if r["rec"] == "count"]
    tim = [r for r in recs if r["rec"] == "time"]
    reqs_expected_max = exp_count
    check(s, "time 기록 수 = 과제 수, 모든 시간이 양수",
          len(tim) == n_tasks and all(min(r["wall_ns_per_call"]) > 0 and min(r["cpu_ns_per_call"]) >= 0 for r in tim),
          f"과제 {n_tasks}, time {len(tim)}")
    n_is_safe = sum(1 for r in cnt if r["op"] == "is_safe")
    check(s, "count 기록의 is_safe 수 = 과제 수", n_is_safe == n_tasks, f"{n_is_safe}")
    check(s, "count 기록의 요청 수가 기대 이하이고 0이 아님", 0 < len(cnt) - n_is_safe <= reqs_expected_max - n_tasks,
          f"요청 {len(cnt) - n_is_safe}")
    del sizes

    # 같은 마스터 시드의 두 번 실행은 count 기록이 모두 같다(실행 번호만 다름)
    l1, l2 = _count_lines(p1), _count_lines(p2)
    check(s, "같은 마스터 시드의 두 실행: count 기록이 줄 단위로 같음(순서 포함)", l1 == l2, f"{len(l1)}줄")

    # 다른 프로세스·해시 시드에서도 같은가
    outs = []
    for hs in ("1", "7"):
        pp = os.path.join(tmp, f"proc{hs}.jsonl")
        r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--tiny", pp], capture_output=True, text=True,
                           env={"PYTHONHASHSEED": hs, "PATH": os.environ.get("PATH", "")})
        outs.append(_count_lines(pp) if r.returncode == 0 and os.path.exists(pp) else [r.stderr[-300:]])
    check(s, "다른 프로세스·해시 시드(1, 7)의 실행도 count 기록이 같음", outs[0] == outs[1] == l1, f"{len(outs[0])}줄")

    # 실행 순서
    plan = RU.make_plan(RU.build_cells(2026, TINY_SPECS), TINY_POLICIES)
    o_count = RU.shuffled(2026, "count", plan)
    o_time = RU.shuffled(2026, "time", plan)
    check(s, "실행 순서는 계획의 순열이고 두 패스의 순서가 다르며 결정적임",
          sorted(o_count) == sorted(plan) and o_count != plan and o_count != o_time and o_count == RU.shuffled(2026, "count", plan))
    seq = [(r["policy"], r["cell"], r["idx"]) for r in cnt if r["op"] == "is_safe"]
    check(s, "파일에 기록된 count 순서가 계획한 무작위 순서와 같음", seq == o_count)

    # K1
    rows = SU.k1(recs)
    fu = sum(r["FU"] for r in rows)
    fs = sum(r["FS"] for r in rows)
    other = sum(r["other"] for r in rows)
    check(s, "K1: 교재식 두 구현은 FU = FS = 0, 요청 불일치 0", fu == 0 and fs == 0 and other == 0, f"FU={fu} FS={fs} other={other}")
    truths = {(r["cell"], r["truth"]) for r in cnt if r["op"] == "is_safe"}
    check(s, "점검 입력에 안전·불안전이 모두 있음(비공허)", {t for _, t in truths} == {True, False})
    out_seen = {r["truth"] for r in cnt if r["op"] == "request"}
    check(s, "점검 요청에 네 판정이 모두 있음(비공허)", out_seen == {ERROR, WAIT, GRANT, DENY}, str(sorted(out_seen)))
    fam = {r["cell"]: r["truth"] for r in cnt if r["family"] == "F-bound" and r["op"] == "is_safe"}
    check(s, "F-bound 셀의 진실값: 사슬은 안전, 불안전 사슬은 불안전",
          fam["bound-n16-chain-first"] is True and fam["bound-n16-chain-last"] is True and fam["bound-n16-unsafe-last"] is False)

    # K2, K5
    g = rng(31, "k5")
    va = SU.metric_by_instance(recs, "textbook-restart")
    vb = SU.metric_by_instance(recs, "textbook-sweep")
    pr = SU.paired_by_cell(va, vb, g, 0.95, 2000)
    bchk = pr["bound-n16-chain-first"]
    check(s, "K5: 최악 입력에서 두 구현의 벡터 비교 횟수가 같음(n(n+1)/2 = 136)",
          va[("bound-n16-chain-first", 0)] == 136 and vb[("bound-n16-chain-first", 0)] == 136)
    for c in ("rand-n16m4s0.5", "rand-n32m4s0.1", "rand-n32m4s0.9"):
        ci = pr[c]["ci"]
        number(s, f"K5 비율(restart/sweep) 벡터 비교, {c}", f"{ci['ratio']:.3f} [{ci['lo']:.3f}, {ci['hi']:.3f}]" if ci else "구간 없음")
    del bchk

    # K3과 분산 성분
    vc = SU.variance_components(recs, "textbook-restart", "rand-n32m4s0.9")
    check(s, "분산 성분 추정이 계산됨", vc is not None and vc["sigma2_within"] >= 0, str(vc and {k: round(v, 4) if isinstance(v, float) else v for k, v in vc.items()}))
    tw = SU.time_by_instance(recs, "textbook-restart")
    ts = SU.time_by_instance(recs, "textbook-sweep")
    prt = SU.paired_by_cell(tw, ts, g, 0.95, 2000)
    number(s, "K3 시간 비율(restart/sweep), rand-n32m4s0.9 (표본 12, 참고용)",
           "%.3f" % prt["rand-n32m4s0.9"]["ci"]["ratio"] if prt["rand-n32m4s0.9"]["ci"] else "-")

    # 시간 재현성(참고): 두 번 실행한 중앙값 사이의 비
    t1 = SU.time_by_instance(list(R.read_jsonl(p1)), "textbook-restart")
    t2 = SU.time_by_instance(list(R.read_jsonl(p2)), "textbook-restart")
    ratios = [t1[k] / t2[k] for k in t1 if k in t2]
    med = float(np.median(ratios))
    number(s, "같은 입력 두 번 실행한 시간 비의 중앙값(참고. 허용 오차 30% 안이면 정상)", f"{med:.3f}")
    check(s, "시간 재현성(참고): 두 실행의 시간 비 중앙값이 0.7–1.43", 0.7 <= med <= 1.43, f"{med:.3f}")

    # K4 (최악 입력의 로그–로그 기울기)
    xs = [16, 32, 64, 128, 256]
    cnts = []
    for n in xs:
        o = CountingOps()
        TextbookRestart().is_safe(G.worst_case(n, 4, "chain-last"), o)
        cnts.append(o.vec_cmp)
    sl = S.loglog_slope(xs, cnts)
    check(s, "K4: 최악 입력의 벡터 비교 횟수 기울기가 n에 대해 1.9–2.0", 1.9 <= sl["slope"] <= 2.0, f"{sl['slope']:.4f}")
    number(s, "최악 입력 벡터 비교 기울기(n = 16–256)", f"{sl['slope']:.4f}")
    del info


def sec_mutants(tmp: str) -> None:
    s = "변이체(점검이 틀린 구현을 잡는가)"
    names = [n for n in MU.MUTANTS if n != "mut-no-restore"]
    extra = {n: MU.MUTANTS[n]() for n in names}
    path = os.path.join(tmp, "mut.jsonl")
    specs = [sp for sp in TINY_SPECS if sp.family == "F-rand"]
    RU.execute(master=77, specs=specs, policy_names=names + ["textbook-restart"], out_path=path, run_id="mut",
               count_pass=True, time_pass=False, repo_root=ROOT, extra_policies=extra)
    rows = SU.k1(list(R.read_jsonl(path)))
    agg: dict[str, dict] = {}
    for r in rows:
        a = agg.setdefault(r["policy"], {"FU": 0, "FS": 0, "other": 0, "n": 0})
        for k in ("FU", "FS", "other", "n"):
            a[k] += r[k]
    check(s, "mut-always-safe는 FS > 0으로 잡힘", agg["mut-always-safe"]["FS"] > 0, str(agg["mut-always-safe"]))
    check(s, "mut-always-unsafe는 FU > 0으로 잡힘", agg["mut-always-unsafe"]["FU"] > 0, str(agg["mut-always-unsafe"]))
    check(s, "mut-strict(등호 제외)는 FU > 0으로 잡힘", agg["mut-strict"]["FU"] > 0, str(agg["mut-strict"]))
    check(s, "mut-skip-last(마지막 종류 생략)는 FS > 0으로 잡힘", agg["mut-skip-last"]["FS"] > 0, str(agg["mut-skip-last"]))
    check(s, "변이체와 같은 실행의 기준 구현은 FU = FS = 0", agg["textbook-restart"]["FU"] == 0 and agg["textbook-restart"]["FS"] == 0)
    try:
        RU.execute(master=77, specs=specs[:1], policy_names=["mut-no-restore"], out_path=os.path.join(tmp, "nr.jsonl"),
                   run_id="nr", count_pass=True, time_pass=False, repo_root=ROOT,
                   extra_policies={"mut-no-restore": MU.MutNoRestore()})
        caught = False
    except RuntimeError:
        caught = True
    check(s, "mut-no-restore(요청이 상태를 되돌리지 않음)는 실행기의 상태 복원 점검에 걸림", caught)


# ---------------------------------------------------------------- 진입점

def main(out_path: str | None) -> int:
    t_all = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        for name, fn in (("시드", sec_seeds), ("연산 계측", sec_ops), ("상태 변환", sec_state),
                         ("교재식 기준 구현(맛보기)", sec_policies), ("입력 생성기", sec_generator),
                         ("통계 도구", sec_stats), ("실행기(끝에서 끝까지)", lambda: sec_runner(tmp)),
                         ("변이체(점검이 틀린 구현을 잡는가)", lambda: sec_mutants(tmp))):
            t0 = time.time()
            fn()
            SECTION_TIME[name] = time.time() - t0
            bad = [c for c in CHECKS if c[0] == name and not c[2]]
            print(f"[{name}] {sum(1 for c in CHECKS if c[0] == name)}개 점검, 실패 {len(bad)}, {SECTION_TIME[name]:.1f}초", flush=True)
            for c in bad:
                print("  실패:", c[1], c[3], flush=True)
    total = len(CHECKS)
    failed = sum(1 for c in CHECKS if not c[2])
    lines = []
    lines.append("# 하니스 자체 점검 결과\n")
    lines.append("`bench/check_pipeline.py`가 쓴 결과다. AI(Claude)가 작성한 초안이며 사람의 검토 전이다. "
                 "알려진 답, 독립 구현, 시뮬레이션, 변이체에 대한 점검이고 정확성의 증명이 아니다. "
                 "파일럿이나 본 실행의 자료가 아니다.\n")
    lines.append(f"- 점검 {total}개, 실패 {failed}개, 총 {time.time() - t_all:.0f}초")
    env = R.env_info(ROOT)
    lines.append(f"- 환경: Python {env['python']}, numpy {env['numpy']}, scipy {env['scipy']}, {env['cpu_model']}, 코어 {env['cpu_count']}, "
                 f"{env['platform']}")
    lines.append("- 점검한 코드의 git 커밋은 이 파일을 커밋하기 직전의 작업 트리라 기록하지 않는다. 같은 파일을 만든 커밋의 해시는 진행 기록에 적는다.\n")
    lines.append("## 점검 목록\n")
    lines.append("| 구역 | 점검 | 결과 | 비고 |")
    lines.append("|---|---|---|---|")
    for sec, name, ok, detail in CHECKS:
        d = detail.replace("|", "/").replace("\n", " ")
        lines.append(f"| {sec} | {name} | {'통과' if ok else '**실패**'} | {d} |")
    lines.append("")
    lines.append("## 수치\n")
    lines.append("| 구역 | 항목 | 값 |")
    lines.append("|---|---|---|")
    for sec, name, val in NUMBERS:
        lines.append(f"| {sec} | {name} | {val.replace('|', '/')} |")
    lines.append("")
    lines.append("## 구역별 시간\n")
    lines.append("| 구역 | 초 |")
    lines.append("|---|---|")
    for k, v in SECTION_TIME.items():
        lines.append(f"| {k} | {v:.1f} |")
    lines.append("")
    lines.append("## 한계\n")
    lines.append("- 시간 재현성 점검은 참고용이다. 공유 가상 환경에서 절대 시간은 흔들리므로 비율과 기울기만 본다.")
    lines.append("- numpy 닫힘(`safe_fast`)은 큰 입력의 정답으로 쓰는 도구이고, 오라클 O1과의 일치는 위 소규모 범위에서만 확인했다. 큰 입력으로의 일반화는 표본 점검이며 증명이 아니다.")
    lines.append("- 소규모 전수 차등 테스트는 `bench/check_banker_policies.py`가 맡는다.")
    text = "\n".join(lines) + "\n"
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
    print(f"점검 {total}개, 실패 {failed}개")
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--tiny":
        tiny_run(sys.argv[2], "tiny-proc")
        sys.exit(0)
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
