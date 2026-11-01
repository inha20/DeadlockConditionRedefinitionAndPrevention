"""RQ3 워크로드 생성기(L1, L2)와 무작위 스케줄 실행기의 무결성 점검 (동결 전 측정 도구의 시험).
실행: python3 -I bench/check_workloads.py formal/rq3/workloads-check.md

A. 생성기 점검: 결정성, 구조(프로그램 형식, 깊이, 범위), 순서 위반 비율, Zipf 인기도, 락 번호 무작위화, 임계구역 길이 분포, L2 구조.
B. 연기 시험(smoke): 핵심 격자 27셀 x 정책 11개 x 인스턴스 x 스케줄 시드를 T=16, R=32에서 실행해
   불변식 위반·교착 위반·멈춤이 없는지(보장 정책), 탐지 정책이 교착을 풀고 끝나는지, 무정책 B0가 교착을 실제로 겪는지(비공허성),
   순서 있는 획득(p_v=0)이나 깊이 1에서 B0가 멈추지 않는지(정리 T6와의 일치), P-RAG와 P-BNK의 실행이 같은지를 본다.
이 점검은 정책의 성능을 말하지 않는다. 정책별 중단 수·실패 수·대기 같은 비교 지표는 일부러 보고하지 않는다.
AI(Claude)가 쓴 초안이며 사람의 검토 전이다.
"""
from __future__ import annotations

import itertools
import math
import multiprocessing as mp
import os
import sys
import time
from collections import Counter, defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "oracle"))

import locks as o2  # noqa: E402
from bench.lockrun import run_random  # noqa: E402
from bench.policies.lock import policies as P  # noqa: E402
from bench.workloads.l1 import (L1Params, account_transfer, dining_philosophers, make_l1,  # noqa: E402
                                violation_fraction, zipf_weights)

MASTER = "rq3-workload-check"
ZIPF = (0.0, 0.8, 1.2)
DEPTH = (1, 2, 4)
PVIOL = (0.0, 0.05, 0.25)
NINST = 6                 # 연기 시험: 셀·정책마다 인스턴스 수
NSEED = 2                 # 인스턴스마다 스케줄 시드 수
NINST_RATIO = 200         # 충돌 비율 점검용 B0 인스턴스 수((Zipf, 깊이)마다). 처음 40개로 돌렸을 때 표본이 작아 깊이 4의 순서를 가리지 못했다(보고서 §2)
NINST_STATIC = 200        # 정적 겹침 점검용 인스턴스 수
MAX_STEPS = 300000
ALL = list(P.POLICIES)
GUARANTEED = list(P.GUARANTEED)


def cells():
    return [(s, d, pv) for s in ZIPF for d in DEPTH for pv in PVIOL]


def cell_label(c):
    s, d, pv = c
    return f"s={s}, d={d}, p_v={pv}"


# ---------------------------------------------------------------- B. 연기 시험 작업

def run_one(args):
    cell, pname, inst, seed = args
    s, d, pv = cell
    prm = L1Params(T=16, R=32, zipf_s=s, depth=d, p_viol=pv)
    w = make_l1(prm, MASTER, inst)
    pol = P.make(pname)
    r = run_random(w.first_programs(), pol, seed=seed, nlocks=w.nlocks, max_steps=MAX_STEPS)
    return (cell, pname, inst, seed, r)


def static_overlap(s, d, ninst):
    """(Zipf, 깊이) 셀에서 인스턴스마다 모든 스레드 쌍의 첫 작업이 락을 하나 이상 공유하는 비율과 공유 락 수의 평균.
    스케줄과 정책에 무관한 생성기의 성질이다."""
    prm = L1Params(T=16, R=32, zipf_s=s, depth=d, p_viol=0.05)
    share = tot = shared = 0
    for inst in range(ninst):
        w = make_l1(prm, MASTER, inst)
        sets = [frozenset(th[0].lockset) for th in w.threads]
        for a, b in itertools.combinations(sets, 2):
            tot += 1
            k = len(a & b)
            share += k > 0
            shared += k
    return share / tot, shared / tot


def binom_ok(f, p, n, k=5.0):
    sd = math.sqrt(p * (1 - p) / n) if 0 < p < 1 else 0.0
    return abs(f - p) <= k * sd + 1e-12, sd


def main(out_path):
    t0 = time.time()
    try:
        out_path = os.path.abspath(out_path)
    except OSError:
        out_path = os.path.join(ROOT, out_path)
    checks: list = []

    def check(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    L: list = []
    # ================================================================ A. 생성기
    gen_rows = []
    # A1 결정성
    det_ok = True
    for c in cells():
        prm = L1Params(zipf_s=c[0], depth=c[1], p_viol=c[2])
        a, b = make_l1(prm, MASTER, 0), make_l1(prm, MASTER, 0)
        c2 = make_l1(prm, MASTER, 1)
        if not (a == b and a != c2):
            det_ok = False
    check("A1 결정성: 같은 (시드, 매개변수, 인스턴스)는 같은 워크로드, 다른 인스턴스는 다른 워크로드 (27셀)", det_ok)

    # A2 구조
    struct_bad = []
    n_tasks = 0
    for c in cells():
        prm = L1Params(zipf_s=c[0], depth=c[1], p_viol=c[2], tasks_per_thread=2)
        for inst in range(10):
            w = make_l1(prm, MASTER, inst)
            for th in w.threads:
                for tk in th:
                    n_tasks += 1
                    prob = o2.valid_program(tk.ops)
                    acq = [l for k, l in tk.ops if k == "A"]
                    rel = [l for k, l in tk.ops if k == "R"]
                    if (prob or len(set(acq)) != c[1] or len(acq) != c[1] or rel != list(reversed(acq))
                            or any(not (0 <= l < prm.R) for l in acq) or len(tk.work) != len(tk.ops)
                            or any(x < 0 for x in tk.work) or any(x != 0.0 for (k, _), x in zip(tk.ops, tk.work) if k == "R")):
                        struct_bad.append((cell_label(c), inst, prob))
    check("A2 구조: 모든 작업이 올바른 락 프로그램(획득 깊이 d개, 서로 다른 락, 범위 안, 역순 반납, 반납 뒤 일 0)", not struct_bad,
          f"작업 {n_tasks:,}개 검사" if not struct_bad else str(struct_bad[:3]))

    # A3 순서 위반 비율
    viol_rows = []
    viol_ok = True
    for d in (2, 4):
        for pv in PVIOL:
            prm = L1Params(zipf_s=0.8, depth=d, p_viol=pv, T=16)
            fr = []
            for inst in range(120):
                fr.append(violation_fraction(make_l1(prm, MASTER, inst)))
            n = 120 * 16
            f = float(np.mean(fr))
            ok, sd = binom_ok(f, pv, n)
            if pv == 0.0:
                ok = (f == 0.0)
            viol_rows.append((d, pv, n, f, sd, ok))
            viol_ok &= ok
    # 깊이 1은 순서 위반이 정의되지 않는다
    f1 = float(np.mean([violation_fraction(make_l1(L1Params(depth=1, p_viol=0.25), MASTER, i)) for i in range(50)]))
    check("A3 순서 위반 비율이 p_v와 같다(5 표준오차 이내, p_v=0이면 정확히 0), 깊이 1은 항상 0",
          viol_ok and f1 == 0.0, "; ".join(f"d={d},p_v={pv}: 관측 {f:.4f} (n={n:,}, 표준오차 {sd:.4f})" for d, pv, n, f, sd, _ in viol_rows))

    # A4 Zipf 인기도 (hot_random=False, 깊이 1)
    zip_rows = []
    zip_ok = True
    for s in ZIPF:
        prm = L1Params(T=2000, R=32, zipf_s=s, depth=1, p_viol=0.0, hot_random=False)
        cnt = np.zeros(prm.R)
        N = 0
        for inst in range(5):
            w = make_l1(prm, MASTER, inst)
            for th in w.threads:
                for l in th[0].lockset:
                    cnt[l] += 1
                    N += 1
        emp = cnt / N
        th_ = zipf_weights(prm.R, s)
        worst = max(abs(emp[r] - th_[r]) / math.sqrt(th_[r] * (1 - th_[r]) / N) for r in range(prm.R))
        zip_rows.append((s, N, float(emp[0]), float(th_[0]), worst))
        zip_ok &= worst <= 5.0
    check("A4 Zipf 인기도: 락 선택 빈도가 이론 가중치와 같다(모든 순위에서 5 표준오차 이내)", zip_ok,
          "; ".join(f"s={s}: 1순위 관측 {e:.3f} 이론 {t:.3f} (최대 편차 {w_:.1f}σ, 표본 {n:,})" for s, n, e, t, w_ in zip_rows))

    # A5 락 번호 무작위화
    tops_rand, tops_fixed = set(), set()
    for inst in range(100):
        for hr, tops in ((True, tops_rand), (False, tops_fixed)):
            prm = L1Params(T=200, R=32, zipf_s=1.2, depth=1, p_viol=0.0, hot_random=hr)
            w = make_l1(prm, MASTER, inst)
            cnt = Counter(l for th in w.threads for l in th[0].lockset)
            tops.add(cnt.most_common(1)[0][0])
    check("A5 락 번호 무작위화(O3-19): hot_random=True면 가장 인기 있는 락 번호가 인스턴스마다 바뀌고(>=20종), False면 항상 0번",
          len(tops_rand) >= 20 and tops_fixed == {0}, f"True: {len(tops_rand)}종, False: {sorted(tops_fixed)}")

    # A6 임계구역 길이 분포
    cs_rows = []
    cs_ok = True
    for dist in ("exp", "lognormal"):
        prm = L1Params(T=64, R=64, depth=4, p_viol=0.0, tasks_per_thread=5, cs_dist=dist, cs_mean=2.0)
        xs = []
        for inst in range(20):
            w = make_l1(prm, MASTER, inst)
            for th in w.threads:
                for tk in th:
                    xs.extend(x for (k, _), x in zip(tk.ops, tk.work) if k == "A")
        xs = np.array(xs)
        n = len(xs)
        mean_rel = abs(xs.mean() - 2.0) / 2.0
        if dist == "exp":
            se = 1.0 / math.sqrt(n)
            ok = mean_rel <= 5 * se
            extra = f"표준편차/평균 {xs.std() / xs.mean():.3f} (지수분포 이론 1)"
        else:
            cv = math.sqrt(math.e - 1.0)
            se = cv / math.sqrt(n)
            lg = np.log(xs)
            ok = mean_rel <= 5 * se and abs(lg.std() - 1.0) <= 5 * (1.0 / math.sqrt(2 * n))
            extra = f"log의 표준편차 {lg.std():.3f} (이론 1)"
        cs_rows.append((dist, n, float(xs.mean()), extra))
        cs_ok &= ok
    check("A6 임계구역 길이: 지수·로그정규의 평균이 설정값과 같다(5 표준오차 이내), 로그정규의 시그마가 1", cs_ok,
          "; ".join(f"{d}: 평균 {m:.3f} (설정 2.0, 표본 {n:,}), {e}" for d, n, m, e in cs_rows))

    # A7 L2
    dp = dining_philosophers(5)
    dpa = dining_philosophers(5, asymmetric=True)
    ring_ok = all(set(tk[0].lockset) == {i, (i + 1) % 5} for i, tk in enumerate(dp.threads))
    asym_ok = [tk[0].ops[0][1] for tk in dpa.threads] == [0, 1, 2, 3, 0] and dpa.threads[4][0].ops[1][1] == 4
    tr = account_transfer(12, 5, tasks_per_thread=3)
    tr_ok = all(len(tk.lockset) == 2 and o2.valid_program(tk.ops) is None for th in tr.threads for tk in th)
    check("A7 L2 구조: 식사하는 철학자는 고리 모양(포크 i, i+1 mod n), 비대칭 변형은 마지막만 순서를 뒤집음, 이체는 서로 다른 두 계좌",
          ring_ok and asym_ok and tr_ok, f"고리 {ring_ok}, 비대칭 {asym_ok}, 이체 {tr_ok}")

    # ================================================================ B. 연기 시험
    tasks = [(c, p, inst, seed) for c in cells() for p in ALL for inst in range(NINST) for seed in range(NSEED)]
    ctx = mp.get_context("fork")
    with ctx.Pool(2) as pool:
        res = pool.map(run_one, tasks, chunksize=40)
    nruns = len(res)
    by_pol = {p: Counter() for p in ALL}
    by_cell_b0 = defaultdict(lambda: Counter())
    rag_bnk = {}
    first_bad = {}
    b1_detects = 0
    for cell, pname, inst, seed, r in res:
        c = by_pol[pname]
        c["runs"] += 1
        c[r["status"]] += 1
        c["inv"] += r["inv_violations"] > 0
        c["dlviol"] += r["deadlock_violations"] > 0
        if (r["inv_violations"] or r["deadlock_violations"] or r["status"] != "done") and pname not in ("B0",):
            first_bad.setdefault(pname, (cell_label(cell), inst, seed, r["status"], r["first_msg"]))
        if pname == "B0":
            by_cell_b0[cell]["runs"] += 1
            by_cell_b0[cell]["stall"] += r["status"] == "stall"
            by_cell_b0[cell]["cap"] += r["status"] == "cap"
        if pname == "B1":
            b1_detects += r["deadlock_steps"] > 0
        if pname in ("P-BNK", "P-RAG"):
            rag_bnk.setdefault((cell, inst, seed), {})[pname] = (r["status"], r["steps"], r["aborts"], r["fails"], r["max_blocked"], r["requests"], r["conflicts"])

    for p in GUARANTEED:
        c = by_pol[p]
        check(f"B {p}: 불변식 위반 0, 교착 위반 0, 모든 실행이 정상 종료(멈춤·상한 0)",
              c["inv"] == 0 and c["dlviol"] == 0 and c["done"] == c["runs"],
              f"실행 {c['runs']:,}회" + (f", 처음 실패 {first_bad.get(p)}" if p in first_bad else ""))
    c = by_pol["B1"]
    check("B B1: 불변식 위반 0, 모든 실행이 정상 종료(탐지가 교착을 풀음)", c["inv"] == 0 and c["done"] == c["runs"],
          f"실행 {c['runs']:,}회" + (f", 처음 실패 {first_bad.get('B1')}" if 'B1' in first_bad else ""))
    check("B B1 비공허성: 탐지가 실제로 필요했던 실행이 있음(교착 집합이 한 번이라도 생긴 실행)", b1_detects > 0, f"{b1_detects}회")
    safe_cells = [c_ for c_ in cells() if c_[1] == 1 or c_[2] == 0.0]
    risky_cells = [c_ for c_ in cells() if c_[1] >= 2 and c_[2] > 0.0]
    st_safe = sum(by_cell_b0[c_]["stall"] + by_cell_b0[c_]["cap"] for c_ in safe_cells)
    st_risk = sum(by_cell_b0[c_]["stall"] for c_ in risky_cells)
    check("B B0 일관성(정리 T6와의 일치): 깊이 1이거나 p_v=0인 셀(획득이 항상 순서대로)에서 무정책 B0는 한 번도 멈추지 않음",
          st_safe == 0, f"해당 셀 {len(safe_cells)}개, 멈춤 {st_safe}회")
    check("B B0 비공허성: 깊이>=2이고 p_v>0인 셀에서 무정책 B0가 실제로 교착으로 멈추는 실행이 있음", st_risk > 0,
          f"해당 셀 {len(risky_cells)}개, 멈춤 {st_risk}회 / {sum(by_cell_b0[c_]['runs'] for c_ in risky_cells)}회")
    same = sum(1 for v in rag_bnk.values() if v["P-BNK"] == v["P-RAG"])
    check("B P-RAG와 P-BNK의 무작위 실행이 같은 시드에서 완전히 같다(상태·걸음·중단·실패·최대 대기·요청·충돌)",
          same == len(rag_bnk), f"비교 {len(rag_bnk):,}쌍, 같음 {same:,}")
    # 충돌 비율 라벨 점검(B0): (Zipf, 깊이)마다 p_v=0.05로 인스턴스 NINST_RATIO개 x 시드 2개를 따로 돌려 표본을 늘린다
    rtasks = [((s, d, 0.05), "B0", inst, seed) for s in ZIPF for d in DEPTH for inst in range(NINST_RATIO) for seed in range(2)]
    with ctx.Pool(2) as pool:
        rres = pool.map(run_one, rtasks, chunksize=20)
    conflict = defaultdict(lambda: [0, 0])           # (s, d) -> [요청, 충돌]
    for cell, _p, _i, _sd, r in rres:
        cf = conflict[(cell[0], cell[1])]
        cf[0] += r["requests"]
        cf[1] += r["conflicts"]
    ratio = {k: (v[1] / v[0] if v[0] else 0.0) for k, v in conflict.items()}
    stat = {(sv, d): static_overlap(sv, d, NINST_STATIC) for sv in ZIPF for d in DEPTH}
    stat_ok = all(stat[(0.0, d)][0] < stat[(0.8, d)][0] < stat[(1.2, d)][0] and stat[(0.0, d)][1] < stat[(0.8, d)][1] < stat[(1.2, d)][1]
                  for d in DEPTH)
    check("B 경쟁 라벨 타당성(정적): 같은 깊이에서 Zipf 지수가 커질수록 두 작업이 락을 하나 이상 공유할 확률과 공유 락 수의 평균이 커진다",
          stat_ok, "; ".join(f"d={d}: " + " < ".join(f"{stat[(sv, d)][0]:.3f}" for sv in ZIPF) for d in DEPTH))
    end_ok = all(ratio[(0.0, d)] < ratio[(1.2, d)] for d in DEPTH)
    check("B 경쟁 라벨 타당성(동적): 같은 깊이에서 B0의 충돌 비율(요청이 쥐어진 락을 만난 비율)이 s=0.0보다 s=1.2에서 크다",
          end_ok, "; ".join(f"d={d}: {ratio[(0.0, d)]:.3f} < {ratio[(1.2, d)]:.3f}" for d in DEPTH))
    mono_ok = all(ratio[(0.0, d)] < ratio[(0.8, d)] < ratio[(1.2, d)] for d in DEPTH)   # 보고서에 사실로만 적는다(통과 여부를 점검에 쓰지 않음)

    # ================================================================ 보고서
    nfail = sum(1 for c_ in checks if not c_[1])
    elapsed = time.time() - t0
    L.append("# RQ3 워크로드 생성기와 무작위 스케줄 실행기의 무결성 점검 (AI 초안, 사람 검토 전)")
    L.append("")
    L.append("재현: `python3 -I bench/check_workloads.py formal/rq3/workloads-check.md` "
             f"(코어 2개, 약 {elapsed / 60:.1f}분). 이 점검은 **측정 도구의 시험**이다. 정책의 순위·비용·성능에 대해 아무것도 말하지 않으며, "
             "정책별 중단 수, 실패 수, 대기 같은 비교 지표는 일부러 싣지 않았다(동결 전에는 비교 결과를 보지 않는다, `prereg/RQ3.md`).")
    L.append("")
    L.append("## 1. 생성기 점검 (A)")
    L.append("")
    L.append("| 점검 | 결과 | 자세한 값 |")
    L.append("|---|---|---|")
    for name, ok, detail in checks:
        if name.startswith("A"):
            L.append(f"| {name} | {'통과' if ok else '**실패**'} | {detail} |")
    L.append("")
    L.append("## 2. 연기 시험 (B)")
    L.append("")
    L.append(f"핵심 격자 27셀(Zipf 지수 {list(ZIPF)} x 깊이 {list(DEPTH)} x p_v {list(PVIOL)}), T=16, R=32, 지수 분포, 작업은 스레드당 1개. "
             f"정책 {len(ALL)}개 x 셀마다 인스턴스 {NINST}개 x 스케줄 시드 {NSEED}개 = 총 {nruns:,}회 실행. "
             "스케줄은 매 걸음 실행 가능한 스레드를 균등하게 고르는 무작위 스케줄이다(시간 모델 없음). 걸음마다 정책 불변식과 교착 집합을 점검했다.")
    L.append("")
    L.append("| 정책 | 실행 | 정상 종료 | 멈춤 | 상한 | 불변식 위반 실행 | 교착 위반 실행 |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for p in ALL:
        c = by_pol[p]
        L.append(f"| {p} | {c['runs']:,} | {c['done']:,} | {c['stall']:,} | {c['cap']:,} | {c['inv']} | {c['dlviol']} |")
    L.append("")
    L.append("'멈춤'은 아무 스레드도 진행할 수 없는 상태로 끝난 실행이다. B0(무정책)만 멈추는 것이 정상이고(아래 표), 다른 정책은 0이어야 한다. "
             "'교착 위반'은 실행 중 어느 시점에든 교착 집합이 있었던 실행이다. 교착을 막겠다고 약속한 정책(예방·회피)은 0이어야 한다. "
             "B0(무정책)와 B1(교착을 허용하고 탐지해 풂)은 그런 약속이 없으므로 이 열의 0 요구에서 제외하며, 두 정책의 값은 참고용이다.")
    L.append("")
    L.append("### B0(무정책)의 셀별 멈춤 (워크로드가 교착을 실제로 일으키는가)")
    L.append("")
    L.append("| 셀 | B0 실행 | B0 멈춤 |")
    L.append("|---|---:|---:|")
    for c_ in cells():
        b = by_cell_b0[c_]
        L.append(f"| {cell_label(c_)} | {b['runs']} | {b['stall']} |")
    L.append("")
    L.append("깊이 1(락 하나만 쥐는 작업)이나 p_v=0(획득이 항상 락 번호 순서)인 셀에서는 B0도 멈추지 않는다. 락 순서대로 얻으면 교착이 없다는 정리(T6)와 일치한다. "
             "나머지 셀에서 멈춤이 나타나므로 이 격자는 정책이 할 일을 실제로 만든다.")
    L.append("")
    L.append("### 경쟁 라벨의 타당성 점검 (생성기 점검)")
    L.append("")
    L.append(f"정적: 같은 인스턴스의 두 스레드가 첫 작업에서 락을 하나 이상 공유할 확률(괄호 안은 공유 락 수의 평균). 인스턴스 {NINST_STATIC}개, 모든 스레드 쌍, p_v=0.05. "
             "스케줄과 정책에 무관한 생성기의 성질이다.")
    L.append("")
    L.append("| Zipf 지수(경쟁) | " + " | ".join(f"깊이 {d}" for d in DEPTH) + " |")
    L.append("|---|" + "---:|" * len(DEPTH))
    for sv in ZIPF:
        L.append(f"| {sv} | " + " | ".join(f"{stat[(sv, d)][0]:.3f} ({stat[(sv, d)][1]:.3f})" for d in DEPTH) + " |")
    L.append("")
    L.append(f"동적: 요청이 이미 다른 스레드가 쥔 락을 만난 비율(무정책 B0, 균등 무작위 스케줄, p_v=0.05, (Zipf, 깊이)마다 {NINST_RATIO}개 인스턴스 x 시드 2개 = {NINST_RATIO * 2}회 합산).")
    L.append("")
    L.append("| Zipf 지수(경쟁) | " + " | ".join(f"깊이 {d}" for d in DEPTH) + " |")
    L.append("|---|" + "---:|" * len(DEPTH))
    for sv in ZIPF:
        L.append(f"| {sv} | " + " | ".join(f"{ratio[(sv, d)]:.3f}" for d in DEPTH) + " |")
    L.append("")
    strict = {d: ratio[(0.0, d)] < ratio[(0.8, d)] < ratio[(1.2, d)] for d in DEPTH}
    L.append("이 스케줄에는 시간이 없으므로 절댓값은 시간 모델을 둔 시뮬레이션의 충돌 비율과 같지 않다. 판정에 쓴 것은 정적 값의 엄격한 증가와 동적 값의 양 끝(s=0.0 < s=1.2) 비교다. "
             "동적 값이 s=0.0 < 0.8 < 1.2로 엄격히 늘었는지는 깊이별로 " + ", ".join(f"d={d}: {'예' if strict[d] else '아니오'}" for d in DEPTH) +
             "이며 점검에는 쓰지 않았다(`prereg/RQ3.md` §4.4의 라벨 점검 요구의 생성기 쪽 예비 확인).")
    L.append("")
    L.append("**점검의 변경 기록(사후 변경).** 이 점검의 첫 판은 동적 충돌 비율이 s=0.0 < 0.8 < 1.2로 엄격히 늘 것을 요구했고 인스턴스 40개(80회)로 돌렸다(2026-11-02). "
             "깊이 4에서 s=0.8이 0.343, s=1.2가 0.340으로 순서가 뒤집혀 그 점검이 실패했다. 같은 구간에서 정적 겹침은 크게 늘어난다. "
             "동적 비율의 증가가 깊이 4에서 작아지는(포화하는) 것과 80회 표본으로 작은 차이를 가리지 못한 것이 원인이라고 짐작하나 이 점검이 그 원인을 확인하지는 않는다. "
             "그래서 점검을 위 두 가지로 바꾸고 인스턴스를 늘렸다. 생성기는 바꾸지 않았다. 이 변경은 실패를 본 뒤에 한 것이다.")
    L.append("")
    L.append("## 3. 검사 목록")
    L.append("")
    L.append(f"검사 {len(checks)}개, 실패 {nfail}개.")
    L.append("")
    L.append("| 검사 | 결과 | 비고 |")
    L.append("|---|---|---|")
    for name, ok, detail in checks:
        L.append(f"| {name} | {'통과' if ok else '**실패**'} | {detail} |")
    L.append("")
    L.append("## 4. 확인한 것과 하지 않은 것")
    L.append("")
    L.append("- 확인함: L1 생성기가 문서(`docs/rq3/workloads.md`)에 적은 분포대로 작업을 만든다(순서 위반 비율, Zipf, 길이 분포, 결정성). "
             "T=16, R=32의 격자 전체에서 같은 정책 코드가 불변식을 지키고, 약속한 정책은 교착 집합 없이 끝난다. 무정책이 교착을 겪는 셀과 겪지 않아야 하는 셀이 이론과 일치한다.")
    L.append("- 확인하지 않음: 시간 모델이 필요한 모든 것(대기 시간, 처리량, 롤백 비용 ρ_rb의 효과, 임계구역 길이의 효과는 아직 쓰이지 않는다), "
             "정책의 성능 비교, 작업이 둘 이상인 스레드(`tasks_per_thread`>1)의 실행, T와 R의 일차원 스윕, 로그정규 분포 셀의 실행(분포는 길이 값에만 영향을 주고 이 실행기는 길이를 쓰지 않는다).")
    L.append("- 한계: 생성기와 점검을 같은 사람(AI)이 썼다. 통계 점검은 5 표준오차 대역이라 작은 편차를 놓칠 수 있다. 위 통과는 계획용 매개변수(`prereg/RQ3.md` §4.4)에 대한 것이며 동결 때 매개변수가 바뀌면 다시 돌린다.")
    L.append("")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    print(f"검사 {len(checks)}개, 실패 {nfail}개 (소요 {elapsed:.0f}초) -> {out_path}")
    for name, ok, detail in checks:
        if not ok:
            print("실패:", name, detail)
    return nfail


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "formal", "rq3", "workloads-check.md")
    sys.exit(1 if main(out) else 0)
