"""실행기. 셀 × 정책 × 인스턴스 계획을 전체에서 무작위로 섞어 실행하고 JSONL로 기록한다 (prereg/README.md SP-1, SP-6).

세 가지를 지킨다.
  1. 같은 인스턴스를 모든 정책에 준다(짝지은 비교). 인스턴스는 (마스터 시드, 셀, 번호)에서 결정적으로 다시 만들어진다.
  2. 비교 횟수를 세는 실행(count 패스)과 시간을 재는 실행(time 패스)을 분리한다. 계측 코드가 시간에 영향을 주지 않게 하려는 것이다.
  3. 각 패스의 실행 순서를 (정책 × 셀 × 인스턴스) 전체에서 마스터 시드로 결정적으로 섞는다.

이 실행기는 도구다. 어떤 입력군·크기·시드 수로 돌릴지는 호출하는 쪽(파일럿 또는 동결 뒤의 본 실행)이 정한다.
동결 전에는 파일럿과 점검에만 쓰며, 파일럿 자료는 본 분석에 쓰지 않는다(prereg/README.md §2).
"""
from __future__ import annotations

import gc
import math
import time
from dataclasses import asdict, dataclass

from bench import gen_banker as G
from bench import results as R
from bench.ops import CountingOps, PlainOps
from bench.policies import banker as pb
from bench.seeds import rng
from bench.state import BState


@dataclass(frozen=True)
class CellSpec:
    name: str
    family: str                  # "F-rand" | "F-bound"
    n: int
    m: int
    count: int = 0               # F-rand: 인스턴스 수
    target_safe: float | None = None
    kind: str | None = None      # F-bound: gen_banker.WORST_KINDS 가운데 하나
    requests: int = 0            # 인스턴스마다 뽑는 요청 수(K1의 요청 판정)


class Cell:
    """한 셀의 인스턴스를 번호로 다시 만든다."""

    def __init__(self, master, spec: CellSpec) -> None:
        self.master = master
        self.spec = spec
        self.summary: dict = {}
        if spec.family == "F-rand":
            self.recipes, self.summary = G.select_cell(master, spec.name, spec.n, spec.m, spec.count, spec.target_safe)
            self.size = len(self.recipes)
        elif spec.family == "F-bound":
            self.recipes = None
            self.size = 1
            self.summary = {"cell": spec.name, "n": spec.n, "m": spec.m, "kind": spec.kind}
        else:
            raise ValueError(f"지원하지 않는 입력군: {spec.family}")

    def state(self, idx: int) -> BState:
        sp = self.spec
        if sp.family == "F-rand":
            return G.state_from_recipe(self.master, sp.name, sp.n, sp.m, self.recipes[idx])
        return G.worst_case(sp.n, sp.m, sp.kind)

    def meta(self, idx: int) -> dict:
        if self.spec.family == "F-rand":
            r = self.recipes[idx]
            return {"attempt": r["attempt"], "phi": r["phi"], "s": r["s"]}
        return {}

    def requests(self, idx: int, st: BState):
        if self.spec.requests <= 0:
            return []
        return G.sample_requests(self.master, self.spec.name, idx, st, self.spec.requests)


def build_cells(master, specs) -> dict[str, Cell]:
    cells = {}
    for sp in specs:
        if sp.name in cells:
            raise ValueError(f"셀 이름 중복: {sp.name}")
        cells[sp.name] = Cell(master, sp)
    return cells


def make_plan(cells: dict[str, Cell], policy_names) -> list[tuple[str, str, int]]:
    return [(p, c.spec.name, i) for c in cells.values() for i in range(c.size) for p in policy_names]


def shuffled(master, pass_name: str, plan):
    perm = rng(master, "order", pass_name).permutation(len(plan))
    return [plan[int(k)] for k in perm]


# ---------------------------------------------------------------- count 패스

def _base_rec(run_id, kind, cell: Cell, idx, digest, pname) -> dict:
    sp = cell.spec
    return {"rec": kind, "run": run_id, "family": sp.family, "cell": sp.name, "n": sp.n, "m": sp.m, "idx": idx,
            "digest": digest, "policy": pname}


def count_one(policy, cell: Cell, idx: int, run_id: str, w: R.JsonlWriter | None = None) -> list[dict]:
    st = cell.state(idx)
    digest = R.state_digest(st)
    truth, cl_passes, cl_done = G.closure_stats(st.avail, st.alloc, st.need)
    base = _base_rec(run_id, "count", cell, idx, digest, policy.name)
    base.update(cell.meta(idx))
    base.update(cl_passes=cl_passes, cl_done=cl_done)   # 입력의 어려움을 서술하는 값(닫힘 반복 횟수, 끝낸 프로세스 수)
    recs = []
    ops = CountingOps()
    res = policy.is_safe(st, ops)
    recs.append(dict(base, op="is_safe", result=bool(res), truth=bool(truth), **ops.snapshot()))
    for r_i, (i, req) in enumerate(cell.requests(idx, st)):
        ops = CountingOps()
        out = policy.request(st, i, req, ops)
        recs.append(dict(base, op="request", ridx=r_i, i=i, req_digest=R.digest_of(req), result=out,
                         truth=G.request_outcome_fast(st, i, req), **ops.snapshot()))
    if R.state_digest(st) != digest:
        raise RuntimeError(f"정책 {policy.name}의 request가 상태를 되돌리지 않았다 (셀 {cell.spec.name}, 번호 {idx})")
    if w is not None:
        for r in recs:
            w.write(r)
    return recs


# ---------------------------------------------------------------- time 패스

def calibrate_inner(fn, target_ns: int, max_inner: int = 1 << 20) -> int:
    t0 = time.perf_counter_ns()
    fn()
    one = max(1, time.perf_counter_ns() - t0)
    return int(min(max_inner, max(1, math.ceil(target_ns / one))))


def time_calls(fn, inner: int, repeats: int) -> tuple[list[float], list[float]]:
    """fn을 inner번 부르는 구간을 repeats번 재어, 호출당 벽시계 시간과 CPU 시간(ns)을 돌려준다. 재는 동안 GC를 끈다."""
    wall, cpu = [], []
    was = gc.isenabled()
    gc.disable()
    try:
        for _ in range(repeats):
            c0 = time.process_time_ns()
            t0 = time.perf_counter_ns()
            for _ in range(inner):
                fn()
            t1 = time.perf_counter_ns()
            c1 = time.process_time_ns()
            wall.append((t1 - t0) / inner)
            cpu.append((c1 - c0) / inner)
    finally:
        if was:
            gc.enable()
    return wall, cpu


def time_one(policy, cell: Cell, idx: int, run_id: str, target_ns: int, repeats: int, w: R.JsonlWriter | None = None) -> dict:
    st = cell.state(idx)
    digest = R.state_digest(st)
    ops = PlainOps()

    def fn():
        policy.is_safe(st, ops)

    fn()  # 데운다(첫 호출의 지연 효과를 재는 구간에 넣지 않는다)
    inner = calibrate_inner(fn, target_ns)
    wall, cpu = time_calls(fn, inner, repeats)
    rec = dict(_base_rec(run_id, "time", cell, idx, digest, policy.name), op="is_safe", inner=inner, repeats=repeats,
               wall_ns_per_call=wall, cpu_ns_per_call=cpu)
    if w is not None:
        w.write(rec)
    return rec


# ---------------------------------------------------------------- 전체 실행

def execute(master, specs, policy_names, out_path: str, run_id: str, count_pass: bool = True, time_pass: bool = True,
            time_target_ns: int = 2_000_000, time_repeats: int = 5, repo_root: str | None = None,
            extra_policies: dict | None = None) -> dict:
    """계획을 만들어 count 패스와 time 패스를 차례로 실행하고 out_path에 JSONL로 쓴다. 요약 dict를 돌려준다.
    extra_policies는 등록부에 없는 정책 객체(점검용 변이체 등)를 이름으로 넘기는 통로다."""
    t_start = time.time()
    cells = build_cells(master, specs)
    extra = extra_policies or {}
    policies = {name: (extra[name] if name in extra else pb.get(name)) for name in policy_names}
    plan = make_plan(cells, policy_names)
    with R.JsonlWriter(out_path) as w:
        w.write({"rec": "header", "schema": 1, "run": run_id, "master": master, "policies": list(policy_names),
                 "cells": [asdict(sp) for sp in specs], "cell_summaries": [c.summary for c in cells.values()],
                 "count_pass": count_pass, "time_pass": time_pass, "time_target_ns": time_target_ns,
                 "time_repeats": time_repeats, "tasks": len(plan), "env": R.env_info(repo_root)})
        if count_pass:
            for pname, cname, idx in shuffled(master, "count", plan):
                count_one(policies[pname], cells[cname], idx, run_id, w)
        if time_pass:
            for pname, cname, idx in shuffled(master, "time", plan):
                time_one(policies[pname], cells[cname], idx, run_id, time_target_ns, time_repeats, w)
        w.write({"rec": "footer", "run": run_id, "records": w.count, "seconds": round(time.time() - t_start, 3)})
    return {"tasks": len(plan), "cells": {k: v.summary for k, v in cells.items()}, "path": out_path}
