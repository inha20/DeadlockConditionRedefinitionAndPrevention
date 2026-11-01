"""RQ6 파일럿 코드(bench/pilot_rq6.py, pilot_summary_rq6.py)의 자체 점검. AI(Claude)가 쓴 초안이며 사람의 검토 전이다.
실행: python3 -I bench/check_pilot.py formal/rq6/pilot-check-results.md

점검하는 것(파일럿 자료를 만드는 도구가 프로토콜대로 일하는가. 파일럿의 결과를 점검하는 것이 아니다):
  1. 추정식: ANOVA 분산 성분이 알려진 값을 되찾는가, summarize.variance_components와 같은가, 필요 인스턴스 수의 닫힌 형태,
     식이 가정하는 정규 로그 시간에서 구간 반폭이 목표(5%)에 가까운가(시뮬레이션), 드리프트 기울기 구간.
  2. 시간 상한: 상한이 바쁜 반복을 끊는가, 신호 처리기와 타이머가 원래대로 돌아오는가, 끊긴 뒤에도 입력 상태가 그대로인가, 지배 건너뛰기.
  3. 눈가림: 변형 정책의 판정이 어느 기록에도 없고(withheld), 기준 구현만 판정을 남기는가. 요약 파일에 금지된 지표(FU, FS, ρ, 기하평균, 로그–로그 기울기)가 없는가.
  4. 단계: 작은 크기로 S, C, V, V', P, O, R이 도는가. 이어서 실행하면 새 기록이 없는가, 끊긴 단위의 기록은 버려지는가,
     같은 시드의 S는 같은 인스턴스를 만드는가, C의 O1 대조에서 기준 구현이 표지와 O1에 일치하는가, R의 비교기가 차이를 잡는가.
  5. 시드 이름: 파일럿의 마스터 시드가 다른 모듈에서 쓰이지 않는가.
점검은 정확성의 증명이 아니라 알려진 답, 시뮬레이션, 변이체에 대한 반례 탐색이다.
"""
from __future__ import annotations

import glob
import json
import os
import signal
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "oracle"))

import numpy as np  # noqa: E402

from bench import gen_banker as G  # noqa: E402
from bench import pilot_rq6 as PR  # noqa: E402
from bench import pilot_summary_rq6 as PS  # noqa: E402
from bench import results as R  # noqa: E402
from bench import stats as S  # noqa: E402
from bench import summarize as SM  # noqa: E402
from bench.policies import banker as pb  # noqa: E402
from bench.seeds import rng  # noqa: E402

TEST_MASTER = "pilot-selftest"
SECTIONS: list[tuple[str, list[tuple[bool, str]]]] = []
FAILS: list[str] = []
NUMBERS: list[tuple[str, str]] = []


def check(section: str, name: str, ok: bool, detail: str = "") -> None:
    if not SECTIONS or SECTIONS[-1][0] != section:
        SECTIONS.append((section, []))
    SECTIONS[-1][1].append((bool(ok), name + (f" — {detail}" if detail else "")))
    if not ok:
        FAILS.append(f"[{section}] {name} {detail}")


def number(name: str, value: str) -> None:
    NUMBERS.append((name, value))


# ---------------------------------------------------------------- 1. 추정식

def sec_estimators() -> None:
    sec = "추정식"
    g = rng(TEST_MASTER, "est")
    I, R_, sb, sw = 3000, 8, 0.30, 0.10
    mat = g.normal(0, sb, size=(I, 1)) + g.normal(0, sw, size=(I, R_))
    b2, w2 = PS.anova_components(mat)
    check(sec, "ANOVA가 알려진 σ_b, σ_w를 되찾음(3000×8, 오차 5% 이내)",
          abs(b2 ** 0.5 - sb) / sb < 0.05 and abs(w2 ** 0.5 - sw) / sw < 0.05, f"σ_b={b2 ** 0.5:.4f} σ_w={w2 ** 0.5:.4f}")
    recs = [{"rec": "time", "policy": "p", "cell": "c", "wall_ns_per_call": list(np.exp(row))} for row in mat[:200]]
    vc = SM.variance_components(recs, "p", "c")
    b2s, w2s = PS.anova_components(mat[:200])
    check(sec, "pilot_summary.anova_components가 summarize.variance_components와 같음",
          abs(vc["sigma2_between"] - b2s) < 1e-9 and abs(vc["sigma2_within"] - w2s) < 1e-9)
    b0, w0 = PS.anova_components(g.normal(0, 0.1, size=(20, 5)) * 0 + g.normal(0, 0.1, size=(20, 5)))
    check(sec, "인스턴스 효과가 없으면 σ²_b는 0 아래로 내려가지 않음", b0 >= 0.0)
    check(sec, "N(중앙값): σ_b²=0.04, σ_w²=0, R=1에서 97 (손으로 계산한 ⌈(1.96·1.2533·0.2/0.05)²⌉)", PS.n_needed_median(0.04, 0.0, 1) == 97,
          str(PS.n_needed_median(0.04, 0.0, 1)))
    check(sec, "N(중앙값)은 R이 늘면 줄거나 같음", PS.n_needed_median(0.04, 0.09, 3) >= PS.n_needed_median(0.04, 0.09, 8))
    check(sec, "N(비율): sd=0.2에서 65 (⌈(1.96·0.2/ln1.05)²⌉)", PS.n_needed_ratio(0.2) == 65, str(PS.n_needed_ratio(0.2)))
    check(sec, "R 규칙: σ_b=0이면 상한, σ²_w가 σ²_b의 10% 이하면 1, 아니면 올림",
          PS.smallest_reps(0.0, 0.01) == 8 and PS.smallest_reps(1.0, 0.05) == 1 and PS.smallest_reps(0.01, 0.03) == 8
          and PS.smallest_reps(0.1, 0.03) == 3)
    # 식이 가정하는 정규 로그 시간에서 N(σ)=N개를 뽑았을 때 부트스트랩 반폭이 목표 5%에 가까운가
    sigma = 0.2
    N = PS.n_needed_median(sigma ** 2, 0.0, 1)
    gg = rng(TEST_MASTER, "cover")
    hw = []
    cover = 0
    trials = 200
    for _ in range(trials):
        x = np.exp(gg.normal(0.0, sigma, size=N))
        ci = S.percentile_ci(x, "median", 0.95, 400, gg)
        hw.append((ci["hi"] - ci["lo"]) / (2 * ci["estimate"]))
        cover += ci["lo"] <= 1.0 <= ci["hi"]
    check(sec, f"정규 로그 시간에서 N={N}개의 부트스트랩 상대 반폭 평균이 목표 5%의 ±20% 안", 0.04 <= float(np.mean(hw)) <= 0.06,
          f"평균 {float(np.mean(hw)):.4f}")
    check(sec, "같은 시뮬레이션에서 중앙값 구간이 참값을 덮는 비율이 0.90 이상", cover / trials >= 0.90, f"{cover / trials:.3f}")
    number("부트스트랩 반폭 평균(시뮬레이션)", f"{float(np.mean(hw)):.4f}")
    hf = PS.formula_rel_halfwidth(sigma ** 2, 0.0, 1, N)
    check(sec, "식의 상대 반폭이 목표 5% 이하(올림 때문에 약간 작음)", 0.045 <= hf <= 0.05, f"{hf:.4f}")
    # 드리프트 기울기
    y = 0.01 * np.arange(40) + gg.normal(0, 0.02, size=40)
    lo, hi = PS.slope_boot_ci(y, gg, 2000)
    check(sec, "기울기 0.01의 선형 추세를 구간이 덮고 0을 포함하지 않음", lo < 0.01 < hi and lo > 0, f"[{lo:.4f}, {hi:.4f}]")
    y0 = gg.normal(0, 0.02, size=40)
    lo0, hi0 = PS.slope_boot_ci(y0, gg, 2000)
    check(sec, "추세가 없는 값에서는 구간이 0을 포함(이 시드에서)", lo0 < 0 < hi0, f"[{lo0:.5f}, {hi0:.5f}]")
    check(sec, "OLS 기울기: 정확한 직선에서 기울기를 되찾음", abs(PS.ols_slope(3.0 + 0.5 * np.arange(10)) - 0.5) < 1e-12)


# ---------------------------------------------------------------- 2. 시간 상한

def sec_deadline() -> None:
    sec = "시간 상한"
    old = signal.getsignal(signal.SIGALRM)
    t0 = time.perf_counter()
    raised = False
    try:
        with PR.deadline(0.2):
            while True:
                pass
    except PR.PilotTimeout:
        raised = True
    dt = time.perf_counter() - t0
    check(sec, "상한(0.2초)이 바쁜 반복을 끊음", raised and 0.15 <= dt <= 0.6, f"{dt:.3f}초")
    check(sec, "끊은 뒤 SIGALRM 처리기가 원래대로", signal.getsignal(signal.SIGALRM) == old)
    check(sec, "끊은 뒤 타이머가 꺼져 있음", signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0))
    with PR.deadline(5.0):
        pass
    check(sec, "상한 안에 끝나면 타이머가 꺼짐", signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0))
    st = G.worst_case(768, 48, "chain-last")
    d0 = R.state_digest(st)
    rec = PR.run_cost_task(pb.get("textbook-restart"), st, 0.05, 0.05)
    check(sec, "정책 호출이 상한으로 끊겨도 입력 상태가 그대로", R.state_digest(st) == d0 and rec["status"].startswith("timeout"), rec["status"])
    check(sec, "지배 건너뛰기: 작은 점이 이미 상한을 넘었으면 n, m이 모두 크거나 같은 점은 건너뜀",
          PR.dominated([(64, 8)], 64, 8) == (64, 8) and PR.dominated([(64, 8)], 128, 16) == (64, 8)
          and PR.dominated([(64, 8)], 32, 64) is None and PR.dominated([(64, 8)], 256, 4) is None and PR.dominated([], 9, 9) is None)
    check(sec, "격자 점이 22개이고 n·m 오름차순", len(PR.POINTS) == 22 and PR.POINTS == sorted(PR.POINTS, key=lambda p: (p[0] * p[1], p[0])))
    check(sec, "격자 점이 프로토콜의 세 열을 모두 덮음",
          set(PR.SWEEP_N) <= set(PR.POINTS) and set(PR.SWEEP_M) <= set(PR.POINTS) and set(PR.DIAG) <= set(PR.POINTS)
          and len(PR.P_POINTS) == 16 and PR.DIAG[-1] == (2048, 256))


# ---------------------------------------------------------------- 3·4. 단계와 눈가림

def jl(path: str) -> list[dict]:
    return list(R.read_jsonl(path))


def sec_stages(tmp: str) -> None:
    sec = "단계"
    pts = [(16, 2), (32, 4), (64, 8)]
    # S
    d1, d2 = os.path.join(tmp, "s1"), os.path.join(tmp, "s2")
    PR.stage_s(d1, TEST_MASTER, points=pts, counts=(6, 4), log=lambda *_: None)
    PR.stage_s(d2, TEST_MASTER, points=pts, counts=(6, 4), log=lambda *_: None)
    a = [r for r in jl(os.path.join(d1, "S.jsonl")) if r["rec"] == "instance"]
    b = [r for r in jl(os.path.join(d2, "S.jsonl")) if r["rec"] == "instance"]
    check(sec, "S: 같은 마스터 시드는 같은 인스턴스(시도 번호, φ, s, 닫힘 횟수, 동률)를 만든다", a == b and len(a) == 9 * 6)
    n_before = len(jl(os.path.join(d1, "S.jsonl")))
    PR.stage_s(d1, TEST_MASTER, points=pts, counts=(6, 4), log=lambda *_: None)
    recs = jl(os.path.join(d1, "S.jsonl"))
    check(sec, "S: 이어서 실행하면 새 기록은 재개 표지 하나뿐", len(recs) == n_before + 1 and recs[-1]["rec"] == "resume")
    check(sec, "S: 모든 인스턴스의 표지(truth)가 닫힘 계산(cl_done == n)과 같다", all(r["truth"] == (r["cl_done"] == r["n"]) for r in a))
    # 끊긴 단위의 기록은 버린다
    p = os.path.join(d1, "S.jsonl")
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps({"rec": "instance", "unit": "S-99-99-50", "n": 99}) + "\n")
    kept = PR.load_units(p)
    check(sec, "load_units: unit_done이 없는 단위의 기록은 읽지 않는다", not any(r.get("unit") == "S-99-99-50" for r in kept))
    # C
    dc = os.path.join(tmp, "c")
    PR.stage_c(dc, TEST_MASTER, points=pts, rand_count=2, cap_count=5.0, cap_time=10.0, cap_o1=5.0, log=lambda *_: None)
    c = jl(os.path.join(dc, "C.jsonl"))
    cost = [r for r in c if r["rec"] == "cost"]
    o1 = [r for r in c if r["rec"] == "o1"]
    pols = PR.policy_names()
    check(sec, "C: 모든 (정책, 입력) 과제가 기록됨", len(cost) == len(pols) * len([1 for r in o1]), f"{len(cost)}건, O1 {len(o1)}건")
    check(sec, "C: 변형 정책의 기록에는 판정이 없고(withheld) 기준 구현만 판정(bool)을 남김",
          all((r["result"] == "withheld") if r["policy"] not in PR.BASELINES else isinstance(r["result"], bool) for r in cost if r["status"] == "ok"))
    check(sec, "C: 기준 구현의 판정이 입력의 표지와 같음", all(r["result"] == r["truth"] for r in cost if r["policy"] in PR.BASELINES and r["status"] == "ok"))
    check(sec, "C: O1의 판정이 입력의 표지와 같고 기준 구현 둘이 O1과 같음",
          all(r["o1_verdict"] == r["truth"] and r["restart"] == r["o1_verdict"] and r["sweep"] == r["o1_verdict"] for r in o1 if r["status"] == "ok"))
    check(sec, "C: 시간 기록에 반복 값이 있고 양수", all(all(x > 0 for x in r["wall_ns_per_call"]) for r in cost if r["status"] == "ok"))
    # 작은 상한으로 상한 초과가 기록되고 이후 지배된 점이 건너뛰어짐
    # (실측: chain-last에서 교재식 Restart의 계수 실행은 (16,2) 0.05 ms, (256,32) 41 ms. O1은 0.1 ms와 39 ms. 상한 10 ms와 5 ms가 둘을 가른다)
    dc2 = os.path.join(tmp, "c2")
    PR.stage_c(dc2, TEST_MASTER, points=[(16, 2), (256, 32), (512, 64)], policies=["textbook-restart"], rand_count=1, cap_count=0.01,
               cap_time=10.0, cap_o1=0.005, kinds=("chain-last",), log=lambda *_: None)
    c2 = jl(os.path.join(dc2, "C.jsonl"))
    cst = {(r["n"], r["m"]): r["status"] for r in c2 if r["rec"] == "cost" and r["fkind"] == "chain-last"}
    ost = {(r["n"], r["m"]): r["status"] for r in c2 if r["rec"] == "o1" and r["fkind"] == "chain-last"}
    check(sec, "C: 작은 점은 ok, 상한을 넘은 점은 timeout_count, 그 점 이상의 큰 점은 skipped_dominated로 기록됨(조용히 빠지지 않음)",
          cst == {(16, 2): "ok", (256, 32): "timeout_count", (512, 64): "skipped_dominated"}, str(cst))
    check(sec, "C: O1도 같은 규칙(ok, timeout, skipped_dominated)",
          ost == {(16, 2): "ok", (256, 32): "timeout", (512, 64): "skipped_dominated"}, str(ost))
    n_c2 = len(c2)
    PR.stage_c(dc2, TEST_MASTER, points=[(16, 2), (256, 32), (512, 64)], policies=["textbook-restart"], rand_count=1, cap_count=0.01,
               cap_time=10.0, cap_o1=0.005, kinds=("chain-last",), log=lambda *_: None)
    c2b = jl(os.path.join(dc2, "C.jsonl"))
    check(sec, "C: 이어서 실행하면 새 기록은 재개 표지 하나뿐", len(c2b) == n_c2 + 1 and c2b[-1]["rec"] == "resume")
    # V, V'
    dv = os.path.join(tmp, "v")
    PR.stage_v(dv, TEST_MASTER, rand_points=[(16, 2), (32, 4)], bound=[("chain-first", 16, 2)], policies=["textbook-restart", "dbdaa-cycle1"],
               count=3, sessions=2, repeats=3, target_ns=300_000, chunk=7, log=lambda *_: None)
    v = jl(os.path.join(dv, "V.jsonl"))
    tv = [r for r in v if r["rec"] == "time"]
    cv = [r for r in v if r["rec"] == "canary"]
    check(sec, "V: 과제 수 = (F-rand 인스턴스 + F-bound 세션) × 정책", len(tv) == (2 * 3 + 1 * 2) * 2, f"{len(tv)}건")
    check(sec, "V: 카나리가 청크마다 하나", len(cv) == len({r["unit"] for r in v if r["rec"] == "unit_done"}) and len(cv) >= 2)
    k_sorted = sorted(tv, key=lambda r: r["k"])
    k_order = [r["k"] for r in k_sorted]
    seq = [(r["policy"], r["cell"], r["idx"]) for r in k_sorted]
    check(sec, "V: 실행 순서는 계획 전체의 순열이지만 정렬된 순서가 아님(마스터 시드로 섞음)",
          len(set(seq)) == len(seq) and seq != sorted(seq), str(seq[:3]))
    check(sec, "V: k가 0부터 연속", k_order == list(range(len(tv))))
    check(sec, "V: 시간 기록에 판정 필드가 없음", all("result" not in r for r in tv))
    dv2 = os.path.join(tmp, "v2")
    PR.stage_v2(dv2, TEST_MASTER, point=(16, 2), policies=("textbook-restart",), targets_ns=(200_000, 400_000), count=3, repeats=3, chunk=4,
                log=lambda *_: None)
    t2 = [r for r in jl(os.path.join(dv2, "V2.jsonl")) if r["rec"] == "time"]
    check(sec, "V': 과제 수 = 정책 × 조각 목표 × 인스턴스", len(t2) == 1 * 2 * 3 and {r["target_ns"] for r in t2} == {200_000, 400_000})
    # P
    dp = os.path.join(tmp, "p")
    PR.stage_p(dp, TEST_MASTER, points=[(16, 2), (32, 4)], targets=(0.5,), workers=2, log=lambda *_: None)
    pc = [r for r in jl(os.path.join(dp, "P.jsonl")) if r["rec"] == "count"]
    check(sec, "P: 과제 수 = 셀 × 인스턴스 × 정책(워커 2개)", len(pc) == (PR.p_count(16, 2) + PR.p_count(32, 4)) * len(pols), f"{len(pc)}건")
    check(sec, "P: 변형의 판정이 기록에 없음", all(r["result"] in ("withheld", True, False) for r in pc)
          and all(r["result"] == "withheld" for r in pc if r["policy"] not in PR.BASELINES))
    dp1 = os.path.join(tmp, "p1")
    PR.stage_p(dp1, TEST_MASTER, points=[(16, 2), (32, 4)], targets=(0.5,), workers=1, log=lambda *_: None)
    pc1 = [r for r in jl(os.path.join(dp1, "P.jsonl")) if r["rec"] == "count"]
    key = lambda r: (r["unit"], r["idx"], r["policy"])  # noqa: E731
    check(sec, "P: 워커 1개와 2개의 계수 기록이 같음(병렬이 결과를 바꾸지 않음)",
          sorted(pc, key=key) == sorted(pc1, key=key))
    # O
    do = os.path.join(tmp, "o")
    PR.stage_o(do, TEST_MASTER, points=pts, log=lambda *_: None)
    ov = [r for r in jl(os.path.join(do, "O.jsonl")) if r["rec"] == "overhead"]
    check(sec, "O: 점마다 고정 비용이 기록됨", len(ov) == 3 and all(r["digest_s"] > 0 and r["build_rand_s"] > 0 for r in ov))
    # R
    dr = os.path.join(tmp, "r")
    out = PR.stage_r(dr, TEST_MASTER, smoke=True, log=lambda *_: None)
    check(sec, "R: 같은 프로세스 두 번과 다른 프로세스(해시 시드가 다름)의 계수 기록이 같음",
          out["same_process_equal"] and out["other_process_equal"] and out["hash_seed_differs"])
    check(sec, "R: 기준 구현 두 실행의 계수 기록이 모두 같음", out["baseline_runs"]["count_diffs"] == 0 and out["baseline_runs"]["same_keys"])
    check(sec, "R: 기준 구현의 판정이 입력의 표지와 모두 같음", out["baseline_result_vs_truth_mismatch"] == 0)
    # 비교기가 차이를 잡는가
    base = [{"rec": "count", "run": "A", "policy": "p", "cell": "c", "idx": 0, "op": "is_safe", "vec_cmp": 5},
            {"rec": "time", "run": "A", "policy": "p", "cell": "c", "idx": 0, "wall_ns_per_call": [200_000.0, 200_000.0]}]
    same = [dict(base[0], run="B"), dict(base[1], run="B", wall_ns_per_call=[210_000.0, 210_000.0])]
    cmp_ok = PR.compare_runs(base, same)
    bad_cnt = PR.compare_runs(base, [dict(base[0], run="B", vec_cmp=6), same[1]])
    bad_time = PR.compare_runs(base, [same[0], dict(base[1], run="B", wall_ns_per_call=[400_000.0, 400_000.0])])
    check(sec, "R 비교기: 같은 기록은 차이 0, 시간 비 1.05는 허용 범위 안", cmp_ok["count_diffs"] == 0 and cmp_ok["time_inside"] == 1)
    check(sec, "R 비교기: 비교 횟수가 하나 달라지면 잡음", bad_cnt["count_diffs"] == 1)
    check(sec, "R 비교기: 시간 비 2.0은 허용 범위 밖", bad_time["time_inside"] == 0 and bad_time["time_pairs"] == 1)
    # 요약
    mix = os.path.join(tmp, "mix")
    os.makedirs(mix, exist_ok=True)
    for fn, src in (("S.jsonl", d1), ("C.jsonl", dc), ("V.jsonl", dv), ("V2.jsonl", dv2), ("P.jsonl", dp), ("O.jsonl", do), ("R.jsonl", dr)):
        with open(os.path.join(src, fn), encoding="utf-8") as fi, open(os.path.join(mix, fn), "w", encoding="utf-8") as fo:
            fo.write(fi.read())
    text = PS.build_summary(mix)
    check(sec, "요약: 모든 절이 만들어짐", all(h in text for h in ("## S.", "## C.", "## V.", "## P.", "## R.")), f"{len(text.splitlines())}줄")
    body = text.split("\n", 6)[-1]
    forbidden = ["FU", "FS", "ρ", "기하평균", "로그–로그", "α_n", "α_m", "해석 민감도"]
    hits = [w for w in forbidden if w in body]
    check(sec, "요약: 금지된 지표(FU, FS, ρ, 기하평균, 로그–로그, 해석 민감도)가 본문에 없음", not hits, str(hits))


# ---------------------------------------------------------------- 5. 시드 이름

def sec_seeds() -> None:
    sec = "시드 이름"
    users = []
    for p in glob.glob(os.path.join(ROOT, "bench", "**", "*.py"), recursive=True):
        base = os.path.basename(p)
        if base.startswith("pilot_") or base == "check_pilot.py":
            continue
        with open(p, encoding="utf-8") as f:
            if "rq6-pilot" in f.read():
                users.append(os.path.relpath(p, ROOT))
    check(sec, "파일럿 마스터 시드 이름이 파일럿 모듈 밖에서 쓰이지 않음", not users, str(users))
    check(sec, "파일럿 마스터 시드와 점검용 마스터 시드가 다름", PR.PILOT_MASTER != TEST_MASTER)
    a = [rng(PR.PILOT_MASTER, "x").integers(0, 1 << 30), rng("rq6-main-placeholder", "x").integers(0, 1 << 30)]
    check(sec, "다른 마스터 시드는 같은 이름표에서 다른 수열을 만듦", a[0] != a[1])
    check(sec, "정책 열두 개가 등록되어 있고 기준 구현이 앞에 옴", len(PR.policy_names()) == 12 and PR.policy_names()[:2] == list(PR.BASELINES))


def main(out_path: str | None) -> int:
    t0 = time.time()
    sec_estimators()
    sec_deadline()
    with tempfile.TemporaryDirectory(prefix="rq6-pilot-check-") as tmp:
        sec_stages(tmp)
    sec_seeds()
    total = sum(len(v) for _, v in SECTIONS)
    lines = ["# RQ6 파일럿 코드의 자체 점검 결과\n",
             "`bench/check_pilot.py`가 쓴 결과다. AI(Claude)가 작성한 초안이며 사람의 검토 전이다. 파일럿 자료를 만드는 도구가 프로토콜(`docs/rq6/pilot.md`)대로 일하는지 "
             "알려진 답, 시뮬레이션, 작은 크기의 실행으로 본다. 정확성의 증명이 아니며 파일럿의 결과가 아니다. "
             f"점검 {total}개, 실패 {len(FAILS)}개, {time.time() - t0:.0f}초.\n"]
    for sec, items in SECTIONS:
        lines.append(f"## {sec}\n")
        for ok, text in items:
            lines.append(f"- {'통과' if ok else '**실패**'}: {text}")
        lines.append("")
    if NUMBERS:
        lines.append("## 관찰한 수\n")
        for k, v in NUMBERS:
            lines.append(f"- {k}: {v}")
        lines.append("")
    text = "\n".join(lines)
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
    print(f"점검 {total}개, 실패 {len(FAILS)}건, {time.time() - t0:.0f}초")
    for f_ in FAILS:
        print("실패:", f_)
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))
