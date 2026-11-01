"""RQ6 파일럿(B-6)의 실행기. 프로토콜은 docs/rq6/pilot.md (측정 전에 커밋한 판이 우선한다).

AI(Claude)가 쓴 초안이며 사람의 검토 전이다. 동결 전 도구이고 본 분석이 아니다. 파일럿 자료는 본 분석에 쓰지 않는다(prereg/README.md §2).
  - 파일럿의 마스터 시드는 rq6-pilot-v1이다. 본 실행의 마스터 시드는 동결 때 정하며 이 이름을 쓰지 않는다.
  - 변형 정책의 판정(result)은 'withheld'로 기록한다. 기준 구현(교재식 둘)의 판정만 기록해 입력의 표지(truth)와 O1에 대조한다.
  - 이 모듈과 pilot_summary_rq6.py는 K1(변형의 판정 대조), K4(지수), K5(비율의 평균), K6(해석 민감도)를 계산하지 않는다.

단계 (python3 -I bench/pilot_rq6.py <단계> [--out 폴더] [--smoke]):
  s        표집·난이도·동률 (입력만)
  c        비용 사다리와 O1 (정책 12개의 호출당 시간, 크기 상한, O1 시간)
  o        과제마다 드는 고정 비용(상태 재구성, 해시). 프로토콜에 없던 측정이며 비용 모델에 쓴다
  v        분산 성분 (인스턴스 사이·반복 사이, 카나리)        v2  조각 길이
  p        짝지은 비용의 분산 (비교 횟수만. 시간은 재지 않는다)
  r        재현성 (같은 시드 두 번, 다른 프로세스 한 번)       r-child  r의 하위 프로세스
  summary  experiments/pilot/pilot-summary.md 생성
각 단계는 이어서 실행할 수 있다(끝난 단위는 건너뛴다).
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import multiprocessing
import os
import signal
import subprocess
import sys
import tempfile
import time
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "oracle"))

import numpy as np  # noqa: E402

import oracle.banker as ob  # noqa: E402
from bench import gen_banker as G  # noqa: E402
from bench import results as R  # noqa: E402
from bench import runner as RU  # noqa: E402
from bench.ops import CountingOps, PlainOps  # noqa: E402
from bench.policies import banker as pb  # noqa: E402
from bench.runner import Cell, CellSpec  # noqa: E402

PILOT_MASTER = "rq6-pilot-v1"
BASELINES = ("textbook-restart", "textbook-sweep")
WITHHELD = "withheld"
DEFAULT_OUT = os.path.join(ROOT, "experiments", "pilot")


def policy_names() -> list[str]:
    return list(BASELINES) + sorted(n for n in pb.REGISTRY if n not in BASELINES)


# ---------------------------------------------------------------- 격자 점 (docs/rq6/pilot.md §3)

SWEEP_N = [(n, 8) for n in (16, 32, 64, 128, 256, 512, 1024, 2048, 4096)]
SWEEP_M = [(256, m) for m in (2, 4, 8, 16, 32, 64, 128, 256)]
DIAG = [(16 * 2 ** k, 2 * 2 ** k) for k in range(8)]
POINTS = sorted(set(SWEEP_N + SWEEP_M + DIAG), key=lambda p: (p[0] * p[1], p[0]))
P_POINTS = sorted(set(SWEEP_N + SWEEP_M), key=lambda p: (p[0] * p[1], p[0]))
TARGETS = (0.1, 0.5, 0.9)
V_RAND = [(64, 8), (256, 8), (1024, 8), (256, 64), (1024, 64)]
V_BOUND = [("chain-first", 256, 8), ("chain-last", 256, 8), ("chain-unsafe-last", 128, 8)]
V3_COUNT = 60        # 사후 추가(V3): V와 같은 F-rand 다섯 셀, 인스턴스 60개(안전 30 + 불안전 30). 안전/불안전을 나눈 분산 추정용
C_KINDS = ("chain-last", "chain-unsafe-last")


# ---------------------------------------------------------------- 시간 상한

class PilotTimeout(Exception):
    pass


@contextlib.contextmanager
def deadline(seconds: float):
    """seconds 안에 끝나지 않으면 PilotTimeout을 일으킨다(메인 스레드의 파이썬 코드에서만 듣는다)."""
    def handler(signum, frame):
        raise PilotTimeout(f"{seconds}s")
    old = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def dominated(dead: list, n: int, m: int):
    """지배 건너뛰기: dead(상한을 넘은 점들) 가운데 n과 m이 모두 이 점 이하인 점이 있으면 그 점을 돌려준다."""
    for (n0, m0) in dead:
        if n >= n0 and m >= m0:
            return (n0, m0)
    return None


def shown_result(policy_name: str, res):
    return bool(res) if policy_name in BASELINES else WITHHELD


# ---------------------------------------------------------------- 단계 기록 (이어서 실행)

class Stage:
    """한 단계의 JSONL 출력. 끝난 단위(unit_done)는 다시 하지 않는다. 읽는 쪽은 끝난 단위의 기록만 쓴다(load_units)."""

    def __init__(self, out_dir: str, name: str, master: str, params: dict) -> None:
        os.makedirs(out_dir, exist_ok=True)
        self.name = name
        self.path = os.path.join(out_dir, f"{name}.jsonl")
        self.done: set = set()
        self.old: list = []
        resumed = os.path.exists(self.path)
        if resumed:
            self.old = load_units(self.path)
            self.done = {r["unit"] for r in self.old if r.get("rec") == "unit_done"}
        self.w = R.JsonlWriter(self.path, append=True)
        self.w.write({"rec": "resume" if resumed else "header", "stage": name, "master": master, "params": params,
                      "env": R.env_info(ROOT), "loadavg": list(os.getloadavg()), "hash_probe": hash("rq6-hash-probe"),
                      "policies_registered": sorted(pb.REGISTRY)})
        self.w._f.flush()

    def write(self, rec: dict) -> None:
        self.w.write(rec)

    def finish_unit(self, unit: str) -> None:
        self.w.write({"rec": "unit_done", "unit": unit})
        self.w._f.flush()

    def close(self) -> None:
        self.w.close()


def load_units(path: str) -> list[dict]:
    """끝난 단위의 기록과 헤더·재개 기록만 읽는다(중간에 끊긴 단위의 기록은 버린다)."""
    recs = list(R.read_jsonl(path))
    done = {r["unit"] for r in recs if r.get("rec") == "unit_done"}
    return [r for r in recs if r.get("rec") in ("header", "resume") or r.get("unit") in done]


# ---------------------------------------------------------------- 단계 s: 표집·난이도·동률

def tie_stats(need) -> dict:
    """정렬 키가 겹치는 정도. maxneed: DBDAA·Begum의 키(성분 최댓값), sumneed: Dixit의 키(성분 합)."""
    a = np.asarray(need, dtype=np.int64)
    out = {}
    for name, key in (("maxneed", a.max(axis=1)), ("sumneed", a.sum(axis=1))):
        _, cnt = np.unique(key, return_counts=True)
        tied = cnt[cnt > 1]
        out[name] = {"any": bool(tied.size), "frac": float(tied.sum() / key.size), "distinct": int(cnt.size)}
    return out


def stage_s(out_dir: str, master: str = PILOT_MASTER, points=None, targets=TARGETS, counts=(30, 12), log=print) -> None:
    points = points or POINTS
    st = Stage(out_dir, "S", master, {"points": points, "targets": list(targets), "counts": list(counts)})
    for (n, m) in points:
        for t in targets:
            unit = f"S-{n}-{m}-{int(round(t * 100))}"
            if unit in st.done:
                continue
            count = counts[1] if n * m > 131072 else counts[0]
            factor = 150 if n * m > 262144 else 400
            t0 = time.perf_counter()
            recipes, summ = G.select_cell(master, unit, n, m, count, t, factor)
            sec = time.perf_counter() - t0
            st.write(dict(summ, rec="sample", unit=unit, seconds=round(sec, 4)))
            for r in recipes:
                s = G.state_from_recipe(master, unit, n, m, r)
                safe, passes, done_n = G.closure_stats(s.avail, s.alloc, s.need)
                if bool(safe) != bool(r["safe"]):
                    raise RuntimeError(f"입력의 표지가 닫힘 계산과 다름: {unit} 번호 {r['idx']}")
                st.write({"rec": "instance", "unit": unit, "n": n, "m": m, "target": t, "idx": r["idx"], "attempt": r["attempt"],
                          "phi": r["phi"], "s": r["s"], "truth": bool(safe), "cl_passes": passes, "cl_done": done_n,
                          "ties": tie_stats(s.need)})
            st.finish_unit(unit)
            log(f"[S] {unit} 시도 {summ['attempts']} 부족 {summ['short_safe']}/{summ['short_unsafe']} {sec:.2f}초")
    st.close()


# ---------------------------------------------------------------- 시간 측정 보조

def ladder_time(policy, st, target_ns: int = 2_000_000, repeats: int = 3, slow_ns: int = 250_000_000) -> dict:
    """사다리용 가벼운 시간 측정. 첫 호출이 slow_ns를 넘으면 두 번만 재고 끝낸다. 아니면 조각 target_ns × repeats."""
    ops = PlainOps()

    def fn():
        policy.is_safe(st, ops)

    t0 = time.perf_counter_ns()
    fn()
    cold = time.perf_counter_ns() - t0
    if cold > slow_ns:
        t0 = time.perf_counter_ns()
        fn()
        warm = time.perf_counter_ns() - t0
        return {"mode": "slow", "cold_ns": float(cold), "wall_ns_per_call": [float(cold), float(warm)], "cpu_ns_per_call": None,
                "inner": 1, "repeats": 2}
    inner = RU.calibrate_inner(fn, target_ns)
    wall, cpu = RU.time_calls(fn, inner, repeats)
    return {"mode": "std", "cold_ns": float(cold), "wall_ns_per_call": wall, "cpu_ns_per_call": cpu, "inner": inner, "repeats": repeats}


def run_cost_task(pol, st, cap_count: float, cap_time: float) -> dict:
    """계수 실행 한 번과 시간 실행 한 번. 상한을 넘으면 status로 남긴다."""
    rec: dict = {}
    ops = CountingOps()
    t0 = time.perf_counter()
    try:
        with deadline(cap_count):
            res = pol.is_safe(st, ops)
    except PilotTimeout:
        rec.update(status="timeout_count", count_s=round(time.perf_counter() - t0, 3))
        return rec
    rec.update(count_s=round(time.perf_counter() - t0, 5), counts=ops.snapshot(), result=shown_result(pol.name, res))
    try:
        with deadline(cap_time):
            rec.update(ladder_time(pol, st))
    except PilotTimeout:
        rec["status"] = "timeout_time"
        return rec
    rec["status"] = "ok"
    return rec


# ---------------------------------------------------------------- 단계 c: 비용 사다리와 O1

def stage_c(out_dir: str, master: str = PILOT_MASTER, points=None, policies=None, cap_count: float = 20.0,
            cap_time: float = 40.0, cap_o1: float = 30.0, kinds=C_KINDS, rand_count: int = 4, log=print) -> None:
    points = sorted(points or POINTS, key=lambda p: (p[0] * p[1], p[0]))
    policies = list(policies or policy_names())
    st = Stage(out_dir, "C", master, {"points": points, "policies": policies, "cap_count": cap_count, "cap_time": cap_time,
                                      "cap_o1": cap_o1, "kinds": list(kinds), "rand_count": rand_count})
    dead: dict = defaultdict(list)
    for r in st.old:
        if r.get("rec") in ("cost", "o1") and str(r.get("status", "")).startswith("timeout"):
            dead[(r.get("policy", "o1"), r["fkind"])].append((r["n"], r["m"]))
    for (n, m) in points:
        unit = f"C-{n}-{m}"
        if unit in st.done:
            continue
        t_unit = time.perf_counter()
        cells = [("rand", CellSpec(f"C-rand-{n}-{m}", "F-rand", n, m, count=rand_count, target_safe=0.5))]
        cells += [(k, CellSpec(f"C-{k}-{n}-{m}", "F-bound", n, m, kind=k)) for k in kinds]
        for fkind, spec in cells:
            cell = Cell(master, spec)
            for idx in range(cell.size):
                s = cell.state(idx)
                truth, passes, done_n = G.closure_stats(s.avail, s.alloc, s.need)
                label = {"unit": unit, "cell": spec.name, "family": spec.family, "fkind": fkind, "n": n, "m": m, "idx": idx,
                         "truth": bool(truth), "cl_passes": passes, "cl_done": done_n}
                base_res: dict = {}
                for pname in policies:
                    key = (pname, fkind)
                    by = dominated(dead[key], n, m)
                    if by:
                        st.write(dict(label, rec="cost", policy=pname, status="skipped_dominated", by=list(by)))
                        continue
                    rec = run_cost_task(pb.get(pname), s, cap_count, cap_time)
                    rec.update(label, rec="cost", policy=pname)
                    if rec["status"].startswith("timeout"):
                        dead[key].append((n, m))
                    if pname in BASELINES and isinstance(rec.get("result"), bool):
                        base_res[pname] = rec["result"]
                    st.write(rec)
                # O1: 입력마다 한 번(기준 구현의 판정과 대조하는 것은 도구 점검이다. 변형의 판정은 대조하지 않는다)
                okey = ("o1", fkind)
                by = dominated(dead[okey], n, m)
                if by:
                    st.write(dict(label, rec="o1", status="skipped_dominated", by=list(by)))
                else:
                    t0 = time.perf_counter()
                    try:
                        with deadline(cap_o1):
                            b = s.to_oracle()
                            t1 = time.perf_counter()
                            v = ob.safe_oracle(b)
                            t2 = time.perf_counter()
                        st.write(dict(label, rec="o1", status="ok", o1_verdict=bool(v), o1_convert_s=round(t1 - t0, 5), o1_s=round(t2 - t1, 5),
                                      restart=base_res.get("textbook-restart"), sweep=base_res.get("textbook-sweep")))
                    except PilotTimeout:
                        dead[okey].append((n, m))
                        st.write(dict(label, rec="o1", status="timeout", o1_s=round(time.perf_counter() - t0, 3)))
        st.finish_unit(unit)
        log(f"[C] {unit} {time.perf_counter() - t_unit:.1f}초")
    st.close()


# ---------------------------------------------------------------- 단계 v, v2: 분산 성분

def stage_v(out_dir: str, master: str = PILOT_MASTER, rand_points=None, bound=None, policies=None, count: int = 12,
            sessions: int = 6, repeats: int = 8, target_ns: int = 5_000_000, chunk: int = 60, cap: float = 120.0,
            tag: str = "V", log=print) -> None:
    """tag="V": 프로토콜대로(F-rand 12개 + F-bound 세션 6개). tag="V3": 사후에 덧붙인 층화 확인(F-rand만, 인스턴스 60개 = 안전 30 + 불안전 30).
    시간 기록에는 판정이 없고, 입력의 표지(truth, 닫힘 계산으로 정한 입력의 성질)만 F-rand 기록에 붙는다."""
    rand_points = V_RAND if rand_points is None else rand_points
    bound = V_BOUND if bound is None else bound
    policies = list(policies or policy_names())
    specs = [CellSpec(f"{tag}-rand-{n}-{m}", "F-rand", n, m, count=count, target_safe=0.5) for n, m in rand_points]
    specs += [CellSpec(f"{tag}-{k}-{n}-{m}", "F-bound", n, m, kind=k) for k, n, m in bound]
    cells = RU.build_cells(master, specs)
    canary = Cell(master, CellSpec("V-canary", "F-rand", 256, 8, count=1, target_safe=1.0))
    canary_pol = pb.get("textbook-restart")
    plan = []
    for c in cells.values():
        k_items = c.size if c.spec.family == "F-rand" else sessions
        plan += [(p, c.spec.name, i) for i in range(k_items) for p in policies]
    order = RU.shuffled(master, f"{tag}-time", plan)
    st = Stage(out_dir, tag, master, {"rand_points": rand_points, "bound": bound, "policies": policies, "count": count, "sessions": sessions,
                                       "repeats": repeats, "target_ns": target_ns, "chunk": chunk, "tasks": len(order)})
    for j in range(0, len(order), chunk):
        unit = f"{tag}-chunk-{j // chunk:04d}"
        if unit in st.done:
            continue
        with deadline(cap):
            rec = RU.time_one(canary_pol, canary, 0, tag, target_ns, 5)
        st.write(dict(rec, rec="canary", unit=unit, k=j))
        for k in range(j, min(j + chunk, len(order))):
            pname, cname, idx = order[k]
            cell = cells[cname]
            try:
                with deadline(cap):
                    rec = RU.time_one(pb.get(pname), cell, idx, tag, target_ns, repeats)
                rec.update(unit=unit, k=k, stage=tag, status="ok", session=idx if cell.spec.family == "F-bound" else None)
                if cell.spec.family == "F-rand":
                    rec["truth"] = bool(cell.recipes[idx]["safe"])
            except PilotTimeout:
                rec = {"rec": "time", "unit": unit, "k": k, "stage": tag, "cell": cname, "idx": idx, "policy": pname, "status": "timeout"}
            st.write(rec)
        st.finish_unit(unit)
        log(f"[{tag}] {unit} / {math.ceil(len(order) / chunk)}")
    st.close()


def stage_v2(out_dir: str, master: str = PILOT_MASTER, point=(256, 8), policies=("textbook-restart", "dbdaa-cycle1", "dixit-max-repeat"),
             targets_ns=(500_000, 5_000_000, 50_000_000), count: int = 12, repeats: int = 8, chunk: int = 36, cap: float = 120.0, log=print) -> None:
    n, m = point
    cell = Cell(master, CellSpec(f"V2-rand-{n}-{m}", "F-rand", n, m, count=count, target_safe=0.5))
    plan = [(p, tn, i) for p in policies for tn in targets_ns for i in range(cell.size)]
    order = RU.shuffled(master, "V2-time", plan)
    st = Stage(out_dir, "V2", master, {"point": point, "policies": list(policies), "targets_ns": list(targets_ns), "count": count,
                                        "repeats": repeats, "tasks": len(order)})
    for j in range(0, len(order), chunk):
        unit = f"V2-chunk-{j // chunk:04d}"
        if unit in st.done:
            continue
        for k in range(j, min(j + chunk, len(order))):
            pname, tn, idx = order[k]
            with deadline(cap):
                rec = RU.time_one(pb.get(pname), cell, idx, "V2", tn, repeats)
            rec.update(unit=unit, k=k, stage="V2", target_ns=tn, status="ok")
            st.write(rec)
        st.finish_unit(unit)
    st.close()


# ---------------------------------------------------------------- 단계 o: 과제마다 드는 고정 비용 (프로토콜에 없던 측정. 비용 모델에 필요)

def _median_time(fn, reps: int) -> float:
    xs = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        xs.append(time.perf_counter() - t0)
    return float(np.median(xs))


def stage_o(out_dir: str, master: str = PILOT_MASTER, points=None, reps: int = 5, log=print) -> None:
    """runner는 과제마다 상태를 번호로 다시 만들고, 해시를 세고, (계수 과제에서는) 닫힘 계산으로 표지를 단다.
    정책 시간과 별개로 드는 이 비용을 잰다. 점마다 reps번 재어 중앙값을 남긴다(한 번 재면 첫 호출의 지연이 섞인다)."""
    points = sorted(points or POINTS, key=lambda p: (p[0] * p[1], p[0]))
    st = Stage(out_dir, "O", master, {"points": points, "reps": reps})
    for (n, m) in points:
        unit = f"O-{n}-{m}"
        if unit in st.done:
            continue
        cell = Cell(master, CellSpec(f"O-rand-{n}-{m}", "F-rand", n, m, count=2, target_safe=0.5))
        s = cell.state(0)
        build_rand = _median_time(lambda: cell.state(0), reps)
        digest = _median_time(lambda: R.state_digest(s), reps)
        closure = _median_time(lambda: G.closure_stats(s.avail, s.alloc, s.need), reps)
        build_bound = _median_time(lambda: G.worst_case(n, m, "chain-last"), reps)
        st.write({"rec": "overhead", "unit": unit, "n": n, "m": m, "reps": reps, "build_rand_s": round(build_rand, 5),
                  "build_bound_s": round(build_bound, 5), "digest_s": round(digest, 5), "closure_s": round(closure, 5)})
        st.finish_unit(unit)
        log(f"[O] {unit}")
    st.close()


# ---------------------------------------------------------------- 단계 p: 짝지은 비용의 분산 (계수만)

def p_count(n: int, m: int) -> int:
    return 40 if n * m <= 8192 else (20 if n * m <= 65536 else 10)


def _p_unit(args):
    master, n, m, t, policies, cap = args
    unit = f"P-{n}-{m}-{int(round(t * 100))}"
    cell = Cell(master, CellSpec(unit, "F-rand", n, m, count=p_count(n, m), target_safe=t))
    recs = [dict(cell.summary, rec="cell", unit=unit)]
    for idx in range(cell.size):
        s = cell.state(idx)
        truth, passes, done_n = G.closure_stats(s.avail, s.alloc, s.need)
        for pname in policies:
            ops = CountingOps()
            res, counts, status = None, None, "ok"
            try:
                with deadline(cap):
                    res = pb.get(pname).is_safe(s, ops)
                counts = ops.snapshot()
            except PilotTimeout:
                status = "timeout"
            recs.append({"rec": "count", "unit": unit, "n": n, "m": m, "target": t, "idx": idx, "policy": pname, "truth": bool(truth),
                         "cl_passes": passes, "cl_done": done_n, "counts": counts, "status": status,
                         "result": shown_result(pname, res) if status == "ok" else None})
    return unit, recs


def stage_p(out_dir: str, master: str = PILOT_MASTER, points=None, targets=TARGETS, policies=None, cap: float = 120.0,
            workers: int = 2, log=print) -> None:
    points = points or P_POINTS
    policies = list(policies or policy_names())
    st = Stage(out_dir, "P", master, {"points": points, "targets": list(targets), "policies": policies, "cap": cap, "workers": workers})
    todo = [(master, n, m, t, policies, cap) for (n, m) in points for t in targets
            if f"P-{n}-{m}-{int(round(t * 100))}" not in st.done]
    if workers > 1 and todo:
        ctx = multiprocessing.get_context("fork")
        with ctx.Pool(workers) as pool:
            it = pool.imap_unordered(_p_unit, todo)
            for unit, recs in it:
                for r in recs:
                    st.write(r)
                st.finish_unit(unit)
                log(f"[P] {unit} ({len(recs) - 1}건)")
    else:
        for args in todo:
            unit, recs = _p_unit(args)
            for r in recs:
                st.write(r)
            st.finish_unit(unit)
            log(f"[P] {unit} ({len(recs) - 1}건)")
    st.close()


# ---------------------------------------------------------------- 단계 r: 재현성

R_SPECS = [CellSpec("R-rand-64-8", "F-rand", 64, 8, count=6, target_safe=0.5),
           CellSpec("R-rand-256-32", "F-rand", 256, 32, count=6, target_safe=0.5),
           CellSpec("R-chain-first-64-8", "F-bound", 64, 8, kind="chain-first"),
           CellSpec("R-chain-unsafe-last-64-8", "F-bound", 64, 8, kind="chain-unsafe-last")]
R_SMOKE_SPECS = [CellSpec("R-rand-16-2", "F-rand", 16, 2, count=3, target_safe=0.5),
                 CellSpec("R-chain-first-16-2", "F-bound", 16, 2, kind="chain-first")]
R_TOL = (0.85, 1.18)
R_MIN_MEDIAN_NS = 100_000.0       # 호출당 중앙값이 0.1 ms 이상인 (정책, 셀) 쌍만 허용 범위를 본다
R_PASS_FRACTION = 0.90


def count_records(master: str, specs, policies) -> list[dict]:
    """정책마다 계수 실행만 한 기록(시간 없음). 변형의 판정은 withheld."""
    cells = RU.build_cells(master, specs)
    out = []
    for c in cells.values():
        for idx in range(c.size):
            s = c.state(idx)
            digest = R.state_digest(s)
            truth, passes, _ = G.closure_stats(s.avail, s.alloc, s.need)
            for pname in policies:
                ops = CountingOps()
                res = pb.get(pname).is_safe(s, ops)
                out.append({"cell": c.spec.name, "idx": idx, "policy": pname, "digest": digest, "truth": bool(truth), "cl_passes": passes,
                            "counts": ops.snapshot(), "result": shown_result(pname, res)})
    return out


def stage_r_child(out_dir: str, master: str = PILOT_MASTER, smoke: bool = False) -> None:
    recs = count_records(master, R_SMOKE_SPECS if smoke else R_SPECS, policy_names())
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "R-child.json"), "w", encoding="utf-8") as f:
        json.dump({"hash_probe": hash("rq6-hash-probe"), "records": recs}, f, sort_keys=True)


def _strip_run(r: dict) -> dict:
    return {k: v for k, v in r.items() if k not in ("run",)}


def median_wall(recs: list[dict]) -> dict:
    by = defaultdict(list)
    for r in recs:
        if r.get("rec") == "time":
            by[(r["policy"], r["cell"])].append(float(np.median(r["wall_ns_per_call"])))
    return {k: float(np.median(v)) for k, v in by.items()}


def compare_runs(a_recs: list[dict], b_recs: list[dict]) -> dict:
    """기준 구현의 두 실행(runner.execute 출력) 비교. 계수 기록은 완전히 같아야 하고, 시간은 중앙값 비를 본다."""
    ca = {(r["policy"], r["cell"], r["idx"], r["op"]): _strip_run(r) for r in a_recs if r.get("rec") == "count"}
    cb = {(r["policy"], r["cell"], r["idx"], r["op"]): _strip_run(r) for r in b_recs if r.get("rec") == "count"}
    same_keys = set(ca) == set(cb)
    diff = [k for k in ca if k in cb and ca[k] != cb[k]]
    ma, mb = median_wall(a_recs), median_wall(b_recs)
    ratios = {k: mb[k] / ma[k] for k in ma if k in mb and ma[k] >= R_MIN_MEDIAN_NS}
    inside = [k for k, v in ratios.items() if R_TOL[0] <= v <= R_TOL[1]]
    return {"count_records": len(ca), "same_keys": same_keys, "count_diffs": len(diff), "time_pairs": len(ratios), "time_inside": len(inside),
            "time_fraction": (len(inside) / len(ratios)) if ratios else None, "ratio_min": min(ratios.values()) if ratios else None,
            "ratio_max": max(ratios.values()) if ratios else None,
            "outside": sorted([[k[0], k[1], round(v, 3)] for k, v in ratios.items() if k not in inside])[:40]}


def stage_r(out_dir: str, master: str = PILOT_MASTER, smoke: bool = False, log=print) -> dict:
    specs = R_SMOKE_SPECS if smoke else R_SPECS
    st = Stage(out_dir, "R", master, {"specs": [s.name for s in specs], "tolerance": list(R_TOL), "min_median_ns": R_MIN_MEDIAN_NS,
                                      "pass_fraction": R_PASS_FRACTION})
    tmp = tempfile.mkdtemp(prefix="rq6-pilot-r-")
    pa, pbp = os.path.join(tmp, "A.jsonl"), os.path.join(tmp, "B.jsonl")
    RU.execute(master, specs, list(BASELINES), pa, "R-A", time_target_ns=2_000_000, time_repeats=5, repo_root=ROOT)
    RU.execute(master, specs, list(BASELINES), pbp, "R-B", time_target_ns=2_000_000, time_repeats=5, repo_root=ROOT)
    cmp_base = compare_runs(list(R.read_jsonl(pa)), list(R.read_jsonl(pbp)))
    # 기준 구현의 판정과 입력의 표지(실행기가 쓴 truth)
    rec_a = [r for r in R.read_jsonl(pa) if r.get("rec") == "count"]
    base_vs_truth = sum(1 for r in rec_a if r["result"] != r["truth"])
    # 변형까지 열두 정책의 계수: 같은 프로세스에서 두 번, 다른 프로세스(해시 시드가 다름)에서 한 번
    pol = policy_names()
    v1 = count_records(master, specs, pol)
    v2 = count_records(master, specs, pol)
    child_dir = os.path.join(tmp, "child")
    cmd = [sys.executable, "-I", os.path.abspath(__file__), "r-child", "--out", child_dir, "--master", master] + (["--smoke"] if smoke else [])
    subprocess.run(cmd, check=True, cwd=ROOT)
    with open(os.path.join(child_dir, "R-child.json"), encoding="utf-8") as f:
        child = json.load(f)
    same_proc = v1 == v2
    other_proc = json.loads(json.dumps(v1, sort_keys=True)) == child["records"]
    out = {"rec": "repro", "unit": "R-all", "baseline_runs": cmp_base, "baseline_result_vs_truth_mismatch": base_vs_truth,
           "twelve_policy_counts": len(v1), "same_process_equal": same_proc, "other_process_equal": other_proc,
           "hash_probe_parent": hash("rq6-hash-probe"), "hash_probe_child": child["hash_probe"],
           "hash_seed_differs": hash("rq6-hash-probe") != child["hash_probe"]}
    st.write(out)
    st.finish_unit("R-all")
    st.close()
    log("[R] " + json.dumps(out, ensure_ascii=False)[:600])
    return out


# ---------------------------------------------------------------- 진입점

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="RQ6 파일럿 실행기(docs/rq6/pilot.md)")
    ap.add_argument("stage", choices=["s", "c", "o", "v", "v2", "v3", "p", "r", "r-child", "summary"])
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--master", default=PILOT_MASTER)
    ap.add_argument("--smoke", action="store_true", help="아주 작은 크기로 돌려 동작만 본다(기본 출력은 임시 폴더)")
    a = ap.parse_args(argv)
    out = a.out
    if a.smoke and a.out == DEFAULT_OUT:
        out = tempfile.mkdtemp(prefix="rq6-pilot-smoke-")
        print("smoke 출력:", out)
    smoke_points = [(16, 2), (32, 4), (64, 8)]
    if a.stage == "s":
        stage_s(out, a.master, points=smoke_points if a.smoke else None, counts=(6, 4) if a.smoke else (30, 12))
    elif a.stage == "c":
        stage_c(out, a.master, points=smoke_points if a.smoke else None, rand_count=2 if a.smoke else 4,
                cap_count=5.0 if a.smoke else 20.0, cap_time=10.0 if a.smoke else 40.0)
    elif a.stage == "o":
        stage_o(out, a.master, points=smoke_points if a.smoke else None)
    elif a.stage == "v":
        if a.smoke:
            stage_v(out, a.master, rand_points=[(16, 2), (32, 4)], bound=[("chain-first", 16, 2)], count=3, sessions=2, repeats=3,
                    target_ns=500_000, chunk=20)
        else:
            stage_v(out, a.master)
    elif a.stage == "v2":
        if a.smoke:
            stage_v2(out, a.master, point=(32, 4), count=3, repeats=3, targets_ns=(200_000, 500_000), chunk=10)
        else:
            stage_v2(out, a.master)
    elif a.stage == "v3":
        if a.smoke:
            stage_v(out, a.master, rand_points=[(16, 2), (32, 4)], bound=[], count=4, repeats=3, target_ns=500_000, chunk=20, tag="V3")
        else:
            stage_v(out, a.master, bound=[], count=V3_COUNT, tag="V3")
    elif a.stage == "p":
        stage_p(out, a.master, points=smoke_points if a.smoke else None, workers=1 if a.smoke else 2)
    elif a.stage == "r":
        stage_r(out, a.master, smoke=a.smoke)
    elif a.stage == "r-child":
        stage_r_child(out, a.master, smoke=a.smoke)
    elif a.stage == "summary":
        from bench import pilot_summary_rq6 as PS  # noqa: PLC0415
        PS.write_summary(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
