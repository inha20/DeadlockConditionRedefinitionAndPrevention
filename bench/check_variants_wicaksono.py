"""Wicaksono 외 2023 재구현의 점검 (prereg/RQ6.md SP-5, WP6.3). AI(Claude)가 쓴 초안이며 사람의 검토 전이다.
실행: python3 -I bench/check_variants_wicaksono.py formal/rq6/variants-check-wicaksono.md

bench/check_variants_begum.py와 같은 방식이다. 변형은 오라클(O1)과 비교하지 않는다(불일치가 K1이 재는 대상이다).
  1. 옮긴 표의 정합성(Need = Max − Allocation, 총량, 표 2·5의 되짚기)과 문헌 예제 재현(안전 순서, 표 2·표 5의 Work 열).
  2. 도착 시점에 따른 결과(해석 W-1의 근거): 인쇄된 순서 p1→p3→p0→p2→p4는 도착이 바깥 반복의 둘째 맨 앞일 때만 나온다.
  3. 같은 해석의 두 번째 독립 구현(그림 2–4를 제자리 갱신 방식으로 그대로 옮긴 기계)과의 차등. 변이체로 점검이 비공허함을 보인다.
  4. 속성: 도착이 없으면 교재식 Sweep과 계측 계수가 같음, 안전 순서 되짚기, 같은 도착이 받아들여지기만 하면 도착 시점과 무관하게 error 여부가 같음,
     첫 반복의 도착 = 처음부터 있는 프로세스, 입력 불변, 도착한 프로세스는 받아들인 반복 이전에 나타나지 않음, 반복 수의 범위.
  5. 관찰: DBDAA 논문 표 8의 'Wicaksono et al.' 열(원래 뱅커와 같은 비교 횟수)과 이 구현의 결과를 같은 세 입력에서 견준다(문헌 예제의 재현이며 오라클 비교가 아님).
오라클(O1)과의 비교(K1)와 등록된 입력군 위의 비용·시간(K2, K3)은 동결 전에 하지 않는다(prereg/RQ6.md §5). 변형의 판정을 오라클이나 닫힘 계산(오라클의 정의)과
대조하지 않는다. 기준 구현(textbook-*)과의 비교는 계측 계수에 한한다. 문헌 예제는 등록된 입력군이 아니다.
"""
from __future__ import annotations

import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "oracle"))

from bench.check_variants_begum import pool_states  # noqa: E402  (층화 무작위·경계·값이 큰 무작위 입력 목록. 등록된 입력군이 아님)
from bench.literature import dbdaa2024 as D  # noqa: E402
from bench.literature import wicaksono2023 as W  # noqa: E402
from bench.ops import CountingOps, PlainOps  # noqa: E402
from bench.policies import banker as pb  # noqa: E402
from bench.policies.banker.textbook import TextbookSweep  # noqa: E402
from bench.policies.banker.variants.wicaksono2023 import WicaksonoSweep  # noqa: E402
from bench.state import BState  # noqa: E402

COUNT_KEYS = ("vec_cmp", "sca_cmp", "vec_add", "iters", "sweeps", "need_ops")


class _Log:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.checks = 0

    def check(self, cond: bool, what: str) -> bool:
        self.checks += 1
        if not cond:
            self.fails.append(what)
        return bool(cond)


# ---------------------------------------------------------------- 독립 함수

def extend(st: BState, rows: list) -> tuple[list, list]:
    """받아들인 프로세스(Allocation 0, Max = 행)를 붙인 alloc, need."""
    m = st.m
    alloc = [list(r) for r in st.alloc] + [[0] * m for _ in rows]
    need = [list(r) for r in st.need] + [list(r) for r in rows]
    return alloc, need


def replay_ok(alloc, need, avail, seq) -> bool:
    work = list(avail)
    for p in seq:
        if not all(need[p][j] <= work[j] for j in range(len(work))):
            return False
        work = [work[j] + alloc[p][j] for j in range(len(work))]
    return True


# ---------------------------------------------------------------- 두 번째 독립 구현(그림 2–4)

def literal_wicaksono(total, alloc, need, avail, arrivals, mutation: str | None = None) -> dict:
    """그림 2–4를 그대로 옮긴 기계. primary(run)와 달리 ops를 쓰지 않고 비교와 덧셈을 직접 세며,
    논문처럼 Allocation, Max, Available을 제자리에서 바꾼다(호출자 자료는 사본에서 시작).
    mutation: 점검의 비공허성을 보이려는 고의 오류.
      check-after-scan   도착 확인을 바깥 반복의 끝(훑기 뒤)에서 한다
      no-recompute       도착한 프로세스의 Need 행을 다시 계산하지 않고 0으로 둔다
      strict             Need ≥ Available이면 막는다(Need < Available만 통과)
      no-release         끝낸 프로세스의 Allocation을 Available에 더하지 않는다
      restart-on-arrival 도착하면 처음부터 다시 시작한다(Available을 처음 값으로, Finish를 모두 거짓으로, 순서를 비운다)
    반환: dict(safe, error, passes, admitted, missed, n_final, counts)"""
    N = len(total)
    Allocation = [list(r) for r in alloc]
    Max = [[alloc[i][j] + need[i][j] for j in range(N)] for i in range(len(alloc))]
    Available = list(avail)
    first_available = list(avail)
    Need = [list(r) for r in need]
    pending = dict(arrivals)
    c = dict(vec_cmp=0, sca_cmp=0, vec_add=0, iters=0, sweeps=0, need_ops=0)
    M = len(Allocation)
    Finish = [False] * M
    safeSequence: list = []
    admitted: list = []
    passno = 0
    error = False

    def countNeed():
        rows = len(Allocation)
        out = [[0] * N for _ in range(rows)]
        for i in range(rows):
            for j in range(N):
                out[i][j] = Max[i][j] - Allocation[i][j]
        c["need_ops"] += rows * N
        return out

    def intercept():
        nonlocal Need, M, Available, Finish, safeSequence
        row = pending.pop(passno)
        Allocation.append([0] * N)
        Max.append(list(row))
        if mutation == "no-recompute":
            Need.append([0] * N)
        else:
            Need = countNeed()
        M += 1
        Finish.append(False)
        admitted.append((passno, M - 1))
        if mutation == "restart-on-arrival":
            Available = list(first_available)
            Finish = [False] * M
            safeSequence = []

    while False in Finish:
        passno += 1
        c["sweeps"] += 1
        if mutation != "check-after-scan" and passno in pending:
            intercept()
        loopWillStuck = True
        for i in range(M):
            c["iters"] += 1
            if Finish[i] is False:
                c["vec_cmp"] += 1
                fits = True
                for j in range(N):
                    c["sca_cmp"] += 1
                    blocked = (Need[i][j] >= Available[j]) if mutation == "strict" else (Need[i][j] > Available[j])
                    if blocked:
                        fits = False
                        break
                if fits:
                    safeSequence.append(i)
                    if mutation != "no-release":
                        for j in range(N):
                            Available[j] += Allocation[i][j]
                    c["vec_add"] += 1
                    Finish[i] = True
                    loopWillStuck = False
        if mutation == "check-after-scan" and passno in pending:
            intercept()
            loopWillStuck = False
        if loopWillStuck:
            error = True
            break
    missed = sorted((k, tuple(r)) for k, r in pending.items())
    return {"safe": safeSequence, "error": error, "passes": passno, "admitted": admitted, "missed": missed, "n_final": M, "counts": c}


def same(res, lit: dict, ops_snapshot: dict) -> bool:
    if (res.safe != lit["safe"] or res.error != lit["error"] or res.passes != lit["passes"] or res.admitted != lit["admitted"]
            or res.missed != lit["missed"] or res.n_final != lit["n_final"]):
        return False
    return all(ops_snapshot.get(k, 0) == lit["counts"][k] for k in COUNT_KEYS)


def run_both(st: BState, arrivals: dict, mutation: str | None = None):
    ops = CountingOps()
    res = WicaksonoSweep().run(st, ops, arrivals)
    lit = literal_wicaksono(st.total, st.alloc, st.need, st.avail, arrivals, mutation)
    return res, lit, ops.snapshot()


# ---------------------------------------------------------------- 입력 생성(점검용. 등록된 입력군이 아님)

def gen_arrivals(rng: random.Random, st: BState) -> dict:
    r = rng.random()
    if r < 0.22:
        return {}
    count = 1 if r < 0.82 else 2
    arr: dict = {}
    for _ in range(count):
        k = rng.choice((1, 1, 2, 2, 3, 4, 6))
        row = [rng.randint(0, t) for t in st.total]
        if rng.random() < 0.15:                                   # 최대 청구가 총량을 넘는 도착(검사하지 않음)
            j = rng.randrange(st.m)
            row[j] = st.total[j] + rng.randint(1, 3)
        arr[k] = tuple(row)
    return arr


# ---------------------------------------------------------------- 점검 본문

def check_registry(L: _Log) -> None:
    L.check("wicaksono-sweep" in pb.REGISTRY and pb.get("wicaksono-sweep").name == "wicaksono-sweep", "등록부에 wicaksono-sweep이 없음")
    L.check(len(set(pb.REGISTRY)) == len(pb.REGISTRY), "등록부 이름 중복")


def tables_consistent(maxc, alloc, need_printed, total, avail_printed, table2, table5, new_max, avail_at_arrival, names) -> list[str]:
    """옮긴 표의 값 사이의 정합성. 어긋나는 항목의 목록(비어 있으면 정합)."""
    bad: list[str] = []
    m = len(total)
    for i in range(len(maxc)):
        if tuple(maxc[i][j] - alloc[i][j] for j in range(m)) != tuple(need_printed[i]):
            bad.append(f"Need ≠ Max − Allocation ({names[i]})")
        if any(maxc[i][j] > total[j] for j in range(m)):
            bad.append(f"Max > 총량 ({names[i]})")
    if any(new_max[j] > total[j] for j in range(m)):
        bad.append("새 프로세스의 Max > 총량")
    av = tuple(total[j] - sum(r[j] for r in alloc) for j in range(m))
    if av != tuple(avail_printed):
        bad.append(f"총량 − ΣAllocation = {av} ≠ 표 1의 Available {tuple(avail_printed)}")
    alloc_by = {names[i]: alloc[i] for i in range(len(alloc))}
    alloc_by["p4"] = (0,) * m
    for label, tab in (("표 2", table2), ("표 5", table5)):
        work = tuple(avail_printed)
        for nm, w, after in tab:
            if tuple(w) != work:
                bad.append(f"{label} {nm}: Work {tuple(w)} ≠ 앞 단계의 끝낸 뒤 Available {work}")
            work = tuple(work[j] + alloc_by[nm][j] for j in range(m))
            if tuple(after) != work:
                bad.append(f"{label} {nm}: 끝낸 뒤 Available {tuple(after)} ≠ Work + Allocation {work}")
        if work != tuple(total):
            bad.append(f"{label}: 모두 끝낸 뒤 Available {work} ≠ 총량")
    first_two = tuple(avail_printed[j] + alloc_by["p1"][j] + alloc_by["p3"][j] for j in range(m))
    if first_two != tuple(avail_at_arrival):
        bad.append(f"표 4: 처음 Available + p1 + p3의 Allocation = {first_two} ≠ 도착 시점 Available {tuple(avail_at_arrival)}")
    return bad


def check_fixture(L: _Log, info: dict) -> None:
    bad = tables_consistent(W.MAXC, W.ALLOC, W.NEED_PRINTED, W.TOTAL, W.AVAIL_PRINTED, W.TABLE_2, W.TABLE_5, W.NEW_MAX, W.AVAIL_AT_ARRIVAL, W.NAMES)
    L.check(not bad, f"옮긴 표의 정합성 위반: {bad}")
    st, names = W.load()
    L.check(st.avail == list(W.AVAIL_PRINTED), f"load()의 Available {st.avail} ≠ {list(W.AVAIL_PRINTED)}")
    L.check([r[0] for r in W.TABLE_2] == W.SEQ_STD and [r[0] for r in W.TABLE_5] == W.SEQ_DYN, "표의 행 순서 ≠ 인쇄된 안전 순서")
    # 비공허성: 옮긴 값을 일부러 틀리게 하면 정합성 점검이 잡는가
    alloc_bad = tuple(tuple(r) for r in W.ALLOC)
    alloc_bad = alloc_bad[:3] + ((2, 1, 2),)
    bad_a = tables_consistent(W.MAXC, alloc_bad, W.NEED_PRINTED, W.TOTAL, W.AVAIL_PRINTED, W.TABLE_2, W.TABLE_5, W.NEW_MAX, W.AVAIL_AT_ARRIVAL, W.NAMES)
    L.check(len(bad_a) > 0, "비공허성: p3의 Allocation을 틀리게 한 표를 정합성 점검이 잡지 못함")
    table_bad = (W.TABLE_2[0], W.TABLE_2[1], ("p0", (7, 4, 4), (7, 5, 4)), W.TABLE_2[3])
    bad_t = tables_consistent(W.MAXC, W.ALLOC, W.NEED_PRINTED, W.TOTAL, W.AVAIL_PRINTED, table_bad, W.TABLE_5, W.NEW_MAX, W.AVAIL_AT_ARRIVAL, W.NAMES)
    L.check(len(bad_t) > 0, "비공허성: 표 2의 한 줄을 틀리게 한 표를 정합성 점검이 잡지 못함")
    info["fixture"] = {"avail": st.avail}


def names_of(seq: list, names: list) -> list[str]:
    return [names[i] if i < len(names) else W.NEW_NAME for i in seq]


def check_example(L: _Log, info: dict) -> None:
    st, names = W.load()
    n0 = st.n
    out: dict = {}
    # (a) 도착 없음 = 표 2의 실행
    ops = CountingOps()
    r0 = WicaksonoSweep().run(st, ops, None, want_trace=True)
    L.check(names_of(r0.safe, names) == W.SEQ_STD and not r0.error, f"도착 없음의 안전 순서 {names_of(r0.safe, names)} ≠ 표 2")
    rows0 = [(names[t["i"]], tuple(t["work"]), tuple(t["avail"])) for t in r0.trace]
    L.check(rows0 == list(W.TABLE_2), f"도착 없음의 Work·Available 열이 표 2와 다름 {rows0}")
    L.check(r0.passes == 2 and r0.admitted == [] and r0.missed == [], "도착 없음의 반복 수·도착 기록")
    out["std"] = {"seq": names_of(r0.safe, names), "ops": ops.snapshot(), "passes": r0.passes}
    # (b) 도착을 둘째 반복 맨 앞에 두면 표 5의 실행
    ops = CountingOps()
    r2 = WicaksonoSweep().run(st, ops, {W.ARRIVAL_PASS: W.NEW_MAX}, want_trace=True)
    L.check(names_of(r2.safe, names) == W.SEQ_DYN and not r2.error, f"도착(2번째 반복)의 안전 순서 {names_of(r2.safe, names)} ≠ 표 5")
    rows2 = [(names_of([t["i"]], names)[0], tuple(t["work"]), tuple(t["avail"])) for t in r2.trace]
    L.check(rows2 == list(W.TABLE_5), f"도착(2번째 반복)의 Work·Available 열이 표 5와 다름 {rows2}")
    L.check(r2.admitted == [(W.ARRIVAL_PASS, n0)] and r2.missed == [] and r2.n_final == n0 + 1, "도착 기록")
    first_pass_exec = [t for t in r2.trace if t["pass"] == 1]
    L.check(tuple(first_pass_exec[-1]["avail"]) == W.AVAIL_AT_ARRIVAL and [names[t["i"]] for t in first_pass_exec] == ["p1", "p3"],
            "도착 직전(1번째 반복의 끝)의 Available·끝낸 프로세스가 표 4와 다름")
    out["dyn"] = {"seq": names_of(r2.safe, names), "ops": ops.snapshot(), "passes": r2.passes}
    # (c) 도착 시점 민감도: 인쇄된 순서는 어느 시점에서 나오는가
    sens = []
    for k in (1, 2, 3, 4):
        r = WicaksonoSweep().run(st, CountingOps(), {k: W.NEW_MAX})
        sens.append({"k": k, "seq": names_of(r.safe, names), "error": r.error, "admitted": r.admitted, "missed": r.missed, "passes": r.passes})
    printed_at = [s["k"] for s in sens if s["seq"] == W.SEQ_DYN and s["admitted"]]
    L.check(printed_at == [W.ARRIVAL_PASS], f"인쇄된 순서(p4가 마지막)가 나오는 도착 시점 {printed_at} ≠ [{W.ARRIVAL_PASS}]")
    L.check(sens[0]["seq"] != W.SEQ_DYN and sens[0]["admitted"], "1번째 반복에 도착한 경우 인쇄된 순서와 달라야 함(해석 W-1의 비공허성)")
    L.check(all((not s["admitted"]) and s["missed"] and s["seq"] == W.SEQ_STD for s in sens[2:]), "3번째 이후 반복의 도착은 받아들여지지 않아야 함(루프가 이미 끝남)")
    out["sens"] = sens
    # (d) 총량을 넘는 도착은 검사 없이 받아들이고 error로 끝나며 되돌리지 않는다
    over = (W.TOTAL[0] + 1, 0, 0)
    ro = WicaksonoSweep().run(st, CountingOps(), {W.ARRIVAL_PASS: over})
    L.check(ro.error and ro.admitted == [(W.ARRIVAL_PASS, n0)] and names_of(ro.safe, names) == W.SEQ_STD, "총량을 넘는 도착: error이고 받아들인 기록이 남고 기존 프로세스는 끝나야 함")
    out["over"] = {"seq": names_of(ro.safe, names), "error": ro.error, "admitted": ro.admitted, "passes": ro.passes}
    # (e) 같은 입력에서 교재식 구현의 비용(관찰)
    base = {}
    for P in (pb.get("textbook-restart"), pb.get("textbook-sweep")):
        o = CountingOps()
        P.is_safe(st, o)
        base[P.name] = o.snapshot()
    out["baseline"] = base
    # 입력 변경 없음
    L.check(st.alloc == [list(r) for r in W.ALLOC] and st.avail == list(W.AVAIL_PRINTED), "예제 실행이 입력 상태를 바꿈")
    info["example"] = out


def check_differential(L: _Log, info: dict) -> None:
    t0 = time.time()
    pool = pool_states(20261101, small_stride=40, wide=1500)
    rng = random.Random(20261101)
    bad = 0
    cov = {"도착 없음": 0, "도착이 받아들여짐(안전)": 0, "도착이 받아들여짐(error)": 0, "도착이 받아들여지지 않음(루프가 이미 끝남)": 0,
           "도착이 받아들여지지 않음(error로 끝난 뒤)": 0, "받아들여진 도착이 둘": 0, "1번째 반복의 도착": 0, "총량을 넘는 도착이 받아들여짐": 0,
           "바깥 반복이 3번 이상": 0}
    n_runs = 0
    for st in pool:
        for arrivals in ({}, gen_arrivals(rng, st), gen_arrivals(rng, st)):
            res, lit, snap = run_both(st, arrivals)
            n_runs += 1
            if not same(res, lit, snap):
                bad += 1
            if not arrivals:
                cov["도착 없음"] += 1
            if res.admitted:
                cov["도착이 받아들여짐(error)" if res.error else "도착이 받아들여짐(안전)"] += 1
                if len(res.admitted) == 2:
                    cov["받아들여진 도착이 둘"] += 1
                if res.admitted[0][0] == 1:
                    cov["1번째 반복의 도착"] += 1
                if any(any(arrivals[k][j] > st.total[j] for j in range(st.m)) for k, _ in res.admitted):
                    cov["총량을 넘는 도착이 받아들여짐"] += 1
            if res.missed:
                cov["도착이 받아들여지지 않음(error로 끝난 뒤)" if res.error else "도착이 받아들여지지 않음(루프가 이미 끝남)"] += 1
            if res.passes >= 3:
                cov["바깥 반복이 3번 이상"] += 1
    L.check(bad == 0, f"차등 불일치 {bad}건 / {n_runs}")
    for k, v in cov.items():
        L.check(v > 0, f"차등 입력이 분기 '{k}'를 지나가지 않음")
    info["diff"] = {"states": len(pool), "runs": n_runs, "bad": bad, "cov": cov, "seconds": time.time() - t0}


def check_mutants(L: _Log, info: dict) -> None:
    pool = pool_states(777, small_stride=60, wide=600)
    rng = random.Random(777)
    cases = []
    for st in pool:
        cases.append((st, {}))
        cases.append((st, gen_arrivals(rng, st)))
        cases.append((st, {1: tuple(rng.randint(0, t) for t in st.total)}))
    out = []
    for mut in ("check-after-scan", "no-recompute", "strict", "no-release", "restart-on-arrival"):
        caught = 0
        for st, arrivals in cases:
            res, lit, snap = run_both(st, arrivals, mut)
            if not same(res, lit, snap):
                caught += 1
        L.check(caught > 0, f"변이체 {mut}를 차등 점검이 잡지 못함")
        out.append((mut, caught, len(cases)))
    info["mutants"] = out


def check_properties(L: _Log, info: dict) -> None:
    pool = pool_states(424242, small_stride=50, wide=800)
    rng = random.Random(424242)
    keys = ("sweep_same", "replay", "time_invariant", "pass1_member", "mutate", "plain", "late", "passes", "admit_count", "missed_window", "formula")
    props = {k: 0 for k in keys}
    nrun = 0
    inv_pairs = 0
    p1_pairs = 0
    for st in pool:
        n0 = st.n
        snap = (list(map(list, st.alloc)), list(map(list, st.need)), list(st.avail), list(st.total))
        # 도착이 없을 때: 교재식 Sweep과 계측 계수가 같은가(판정은 비교하지 않는다. 계수가 같으면 같은 경로이다)
        o1, o2 = CountingOps(), CountingOps()
        WicaksonoSweep().run(st, o1, None)
        TextbookSweep().is_safe(st, o2)
        s1, s2 = o1.snapshot(), o2.snapshot()
        if any(s1.get(k, 0) != s2.get(k, 0) for k in ("vec_cmp", "sca_cmp", "vec_add", "iters", "sweeps")):
            props["sweep_same"] += 1
        for arrivals in ({}, gen_arrivals(rng, st), gen_arrivals(rng, st), gen_arrivals(rng, st)):
            nrun += 1
            ops = CountingOps()
            res = WicaksonoSweep().run(st, ops, arrivals, want_trace=True)
            rows = [list(arrivals[k]) for k, _ in res.admitted]
            alloc_e, need_e = extend(st, rows)
            # 안전 순서 되짚기(받아들인 프로세스를 붙인 상태에서)
            if not replay_ok(alloc_e, need_e, st.avail, res.safe):
                props["replay"] += 1
            # 같은 도착(하나)이 다른 반복에서도 받아들여지면 error 여부가 같다
            if len(arrivals) == 1 and res.admitted:
                (k0, row0), = arrivals.items()
                k1 = 1 if k0 != 1 else 2
                alt = WicaksonoSweep().run(st, PlainOps(), {k1: row0})
                if alt.admitted:
                    inv_pairs += 1
                    if alt.error != res.error:
                        props["time_invariant"] += 1
            # 첫 반복의 도착 = 처음부터 있는 프로세스(Allocation 0, 최대 청구 = 행)
            if len(arrivals) == 1 and 1 in arrivals:
                row1 = list(arrivals[1])
                st_e = BState.make(st.total, extend(st, [row1])[0], extend(st, [row1])[1])
                a = WicaksonoSweep().run(st, CountingOps(), {1: row1})
                o_e = CountingOps()
                b = WicaksonoSweep().run(st_e, o_e, None)
                p1_pairs += 1
                oa = CountingOps()
                WicaksonoSweep().run(st, oa, {1: row1})
                sa, sb = oa.snapshot(), o_e.snapshot()
                if (a.safe, a.error, a.passes) != (b.safe, b.error, b.passes) or any(sa.get(k, 0) != sb.get(k, 0) for k in ("vec_cmp", "sca_cmp", "vec_add", "iters", "sweeps")):
                    props["pass1_member"] += 1
            for k, _row in res.missed:
                # 요청한 반복 번호가 실제 반복 수보다 커야 한다(루프가 그 반복에 닿지 못했다)
                if k <= res.passes:
                    props["missed_window"] += 1
            # 도착한 프로세스는 받아들인 반복 이전에 나타나지 않는다
            adm = dict((idx, k) for k, idx in res.admitted)
            if any(t["i"] in adm and t["pass"] < adm[t["i"]] for t in res.trace):
                props["late"] += 1
            if len(res.admitted) + len(res.missed) != len(arrivals):
                props["admit_count"] += 1
            # 반복 수의 범위: 한 반복마다 하나 이상 끝내지 못하면 error
            if not (res.passes <= len(res.safe) + 1 and (res.error or res.passes <= len(res.safe))):
                props["passes"] += 1
            # 비용 식: need_ops = Σ (받아들인 시점의 프로세스 수 × m)
            exp_need = sum((n0 + a_ + 1) * st.m for a_ in range(len(res.admitted)))
            snapd = ops.snapshot()
            if snapd.get("need_ops", 0) != exp_need or snapd["vec_add"] != len(res.safe) or snapd["sweeps"] != res.passes:
                props["formula"] += 1
            # 계측·비계측 동일
            r2 = WicaksonoSweep().run(st, PlainOps(), arrivals)
            if (r2.safe, r2.error, r2.passes, r2.admitted, r2.missed) != (res.safe, res.error, res.passes, res.admitted, res.missed):
                props["plain"] += 1
        if snap != (list(map(list, st.alloc)), list(map(list, st.need)), list(st.avail), list(st.total)):
            props["mutate"] += 1
    labels = {"sweep_same": "도착이 없을 때 교재식 Sweep과 계측 계수(vec_cmp, sca_cmp, vec_add, iters, sweeps)가 다름",
              "replay": "안전 순서 되짚기 실패(받아들인 프로세스를 붙인 상태에서)",
              "time_invariant": "같은 도착이 다른 반복에서도 받아들여졌는데 error 여부가 다름",
              "pass1_member": "첫 반복의 도착 ≠ 처음부터 있는 프로세스(안전 순서·error·반복 수·계수)",
              "mutate": "입력 상태 변경", "plain": "계측·비계측 결과 불일치",
              "late": "도착한 프로세스가 받아들인 반복보다 앞에서 실행됨",
              "passes": "반복 수가 (끝낸 수 + 1) 또는 (안전이면 끝낸 수)를 넘음",
              "admit_count": "받아들인 도착 + 받아들이지 못한 도착 ≠ 요청한 도착",
              "missed_window": "받아들이지 못한 도착의 반복 번호가 실제 반복 수 이하(루프가 닿았는데 받지 않음)",
              "formula": "Need 재계산 횟수·덧셈·반복 수의 계측 식 위반"}
    for key, cnt in props.items():
        L.check(cnt == 0, f"속성 위반 {labels[key]}: {cnt}건")
    L.check(inv_pairs > 0 and p1_pairs > 0, f"속성 점검이 비공허하지 않음: 도착 시점 쌍 {inv_pairs}, 첫 반복 쌍 {p1_pairs}")
    info["props"] = props
    info["prop_labels"] = labels
    info["prop_runs"] = nrun
    info["prop_states"] = len(pool)
    info["prop_pairs"] = (inv_pairs, p1_pairs)


def check_dbdaa_table8(L: _Log, info: dict) -> None:
    """DBDAA 논문 표 8의 'Wicaksono et al.' 열(원래 뱅커와 같은 85, 100, 125)과 이 구현(그림 3의 Sweep 구조, 도착 없음)의 결과를
    같은 세 입력에서 견준다. 관찰이다. 오라클과의 비교가 아니라 제3자가 보고한 문헌 값의 재현이다. 비교 횟수는 DBDAA 논문의 단위(벡터 비교 수 × 자원 종류 수)로 쓴다."""
    rows = []
    for k, case in enumerate(("best", "average", "worst")):
        st, ids, _ = D.load(case)
        want = D.BASELINE_RESULT[case]
        table8 = D.TABLE_8["Wicaksono et al. 2023 [12]"][k]
        o = CountingOps()
        r = WicaksonoSweep().run(st, o, None)
        base = {}
        for P in (pb.get("textbook-restart"), pb.get("textbook-sweep")):
            ob = CountingOps()
            P.is_safe(st, ob)
            base[P.name] = ob.snapshot().get("vec_cmp", 0) * st.m
        seq = [ids[i] for i in r.safe]
        row = {"case": case, "table8": table8, "wick": o.snapshot().get("vec_cmp", 0) * st.m, "restart": base["textbook-restart"],
               "sweep": base["textbook-sweep"], "seq_same": seq == want["safe"], "seq": seq, "error": r.error, "passes": r.passes}
        rows.append(row)
        L.check(row["wick"] == row["sweep"], f"{case}: 도착 없는 wicaksono-sweep의 비교 횟수가 textbook-sweep과 다름")
        L.check(row["restart"] == table8 == want["count"], f"{case}: 표 8의 값과 교재식 Restart의 값이 다름(표 8 {table8}, Restart {row['restart']})")
    info["table8"] = rows


def collect_window_examples(info: dict) -> None:
    """도출 D6의 관찰: 도착 확인 창. 작은 예에서 (가) 모두 끝난 뒤의 도착은 받아들여지지 않는다, (나) 도착 시점이 순서를 바꾼다."""
    st, names = W.load()
    ex = {}
    r = WicaksonoSweep().run(st, CountingOps(), {3: W.NEW_MAX})
    ex["late_after_done"] = {"seq": names_of(r.safe, names), "missed": r.missed, "error": r.error}
    # 막힌 상태에서의 도착: Available이 (0, 0, 0)이고 모든 프로세스가 더 필요해 첫 반복에서 막히는 상태(점검용). 둘째 반복의 도착은 받아들여지지 않는다
    stuck = BState.make(W.TOTAL, ((4, 2, 1), (2, 1, 1), (3, 1, 2), (1, 1, 1)), ((3, 3, 2), (1, 1, 1), (6, 0, 0), (1, 1, 1)))
    r = WicaksonoSweep().run(stuck, CountingOps(), {2: W.NEW_MAX})
    ex["late_after_stuck"] = {"seq": names_of(r.safe, names), "missed": r.missed, "error": r.error, "passes": r.passes, "avail": stuck.avail}
    info["window"] = ex


def main(out_path: str | None) -> int:
    t0 = time.time()
    L = _Log()
    info: dict = {}
    check_registry(L)
    check_fixture(L, info)
    check_example(L, info)
    check_dbdaa_table8(L, info)
    check_properties(L, info)
    check_mutants(L, info)
    check_differential(L, info)
    collect_window_examples(info)
    ex = info["example"]
    d = info["diff"]
    w = info["window"]

    lines = ["# 문헌 변형 재구현 점검 결과: Wicaksono 외 2023 (R6-06)\n",
             "`bench/check_variants_wicaksono.py`가 쓴 결과다. AI(Claude)가 작성한 초안이며 사람의 검토 전이다. 변형은 오라클과 비교하지 않는다"
             "(불일치가 K1이 재는 대상이다). 문헌 예제 재현, 같은 해석의 두 번째 독립 구현과의 차등, 속성을 본다. "
             "이 점검은 오라클도, 오라클의 정의(닫힘 계산)를 따로 옮긴 함수도 쓰지 않는다. 아래 '관찰'은 문헌 예제의 재현 결과이며 주장 판정이 아니다. "
             "논문의 숫자는 도구가 PDF 본문을 읽어 낸 텍스트에서 옮겼고 PDF 원문과는 아직 대조하지 않았다.\n"]
    lines.append("## 1. 옮긴 표의 정합성과 예제 재현\n")
    lines.append(f"표 1의 Need = Max − Allocation, 총량 − ΣAllocation = {info['fixture']['avail']}(표 1의 Available과 같음), "
                 "표 2와 표 5를 '앞 단계의 끝낸 뒤 Available + 그 프로세스의 Allocation'으로 다시 만든 값과 Work·끝낸 뒤 Available 열이 같고, "
                 "모두 끝낸 뒤 Available = 총량이며, 표 4의 도착 시점 Available (7, 4, 3) = 처음 Available + p1 + p3의 Allocation이다. "
                 "옮긴 값을 일부러 틀리게 한 표 둘을 이 정합성 점검이 잡는다(비공허성).\n")
    lines.append("재구현으로 예제를 돌린 결과다(도착한 프로세스 p4는 바깥 반복의 둘째 맨 앞에서 받는다).\n")
    lines.append("| 실행 | 안전 순서 | 논문 | 표의 Work·Available 열 | 바깥 반복 |")
    lines.append("|---|---|---|---|---|")
    lines.append(f"| 도착 없음 | {' → '.join(ex['std']['seq'])} | {' → '.join(W.SEQ_STD)}(표 2) | 표 2와 같음 | {ex['std']['passes']} |")
    lines.append(f"| p4가 둘째 반복 맨 앞에 도착 | {' → '.join(ex['dyn']['seq'])} | {' → '.join(W.SEQ_DYN)}(표 5) | 표 5와 같음 | {ex['dyn']['passes']} |")
    lines.append("")
    lines.append("## 2. 도착 시점에 따른 결과 (해석 W-1의 근거)\n")
    lines.append("논문은 도착 시점을 시각 표지(T2)로만 쓰고 의사코드의 확인 위치(바깥 반복의 맨 앞)와 연결하지 않는다. "
                 "p4를 바깥 반복 k번째의 맨 앞에서 받게 했을 때의 결과다.\n")
    lines.append("| 도착 반복 k | 안전 순서 | 받아들임 | 받지 못함 | 바깥 반복 수 | 인쇄된 순서와 같은가 |")
    lines.append("|---|---|---|---|---|---|")
    for s in ex["sens"]:
        lines.append(f"| {s['k']} | {' → '.join(s['seq'])} | {s['admitted'] or '—'} | {s['missed'] or '—'} | {s['passes']} | "
                     f"{'예' if s['seq'] == W.SEQ_DYN else '아니오'} |")
    lines.append("")
    lines.append("인쇄된 순서(p4가 마지막)는 k = 2일 때만 나온다. 이 예에서는 p1·p3가 끝난 직후(표 4의 상황)가 둘째 바깥 반복의 맨 앞과 일치한다. "
                 "k = 1이면 p4가 처음부터 있어 p3 다음에 끝나고(p0, p2보다 앞), k ≥ 3이면 루프가 이미 끝나 p4는 받아들여지지 않는다. "
                 "이는 예제를 의사코드에 맞추기 위한 읽기이며, 논문이 '둘째 반복 맨 앞'이라고 쓴 것은 아니다.\n")
    o = ex["over"]
    lines.append(f"최대 청구가 총량을 넘는 프로세스(예: ({W.TOTAL[0] + 1}, 0, 0))가 도착해도 의사코드는 검사하지 않는다. 재구현에서 받아들여지고 "
                 f"기존 프로세스({', '.join(o['seq'])})는 끝난 뒤 새 프로세스가 영원히 실행되지 못해 error로 끝난다(받아들인 기록 {o['admitted']}, 되돌리지 않음).\n")
    lines.append("### 2.1 관찰: 같은 입력에서 비용\n")
    lines.append("논문은 비용이나 시간에 관한 주장을 하지 않는다. 아래는 이 예제에서 센 값이며 K2의 결과가 아니다. "
                 "`need_ops`는 도착 때마다 Need 전체를 다시 계산하는 스칼라 뺄셈이다(그림 2의 countNeed).\n")
    lines.append("| 실행 | vec_cmp | sca_cmp | vec_add | iters | sweeps | need_ops |")
    lines.append("|---|---|---|---|---|---|---|")
    for label, snap in (("wicaksono-sweep, 도착 없음", ex["std"]["ops"]), ("wicaksono-sweep, 도착(k = 2)", ex["dyn"]["ops"]),
                        ("textbook-restart, 도착 없음", ex["baseline"]["textbook-restart"]), ("textbook-sweep, 도착 없음", ex["baseline"]["textbook-sweep"])):
        lines.append(f"| {label} | {snap.get('vec_cmp', 0)} | {snap.get('sca_cmp', 0)} | {snap.get('vec_add', 0)} | {snap.get('iters', 0)} | "
                     f"{snap.get('sweeps', '—')} | {snap.get('need_ops', '—')} |")
    lines.append("")
    lines.append("도착이 없는 `wicaksono-sweep`은 `textbook-sweep`과 계측 계수(vec_cmp, sca_cmp, vec_add, iters, sweeps)가 같다(속성 점검. 판정을 직접 견준 것은 아니다).\n")
    lines.append("### 2.2 관찰: DBDAA 논문 표 8의 'Wicaksono et al.' 열과의 대조\n")
    lines.append("DBDAA 논문(S13)의 표 8은 Wicaksono 외 2023의 방법이 세 입력(best, average, worst)에서 원래 뱅커와 같은 비교 횟수(85, 100, 125)를 낸다고 적고, "
                 "본문은 [1], [5], [9], [12]가 같은 안전 순서를 낸다고 쓴다. 아래는 그림 3의 구조를 옮긴 이 구현(도착 없음)을 같은 세 입력(`bench/literature/dbdaa2024.py`)에 돌린 결과다. "
                 "비교 횟수는 DBDAA 논문의 단위(벡터 비교 수 × 자원 종류 수 5)로 쓴다. 문헌 값의 재현이며 K2의 결과가 아니고 오라클과의 비교도 아니다.\n")
    lines.append("| 입력 | 표 8의 Wicaksono 열 | `wicaksono-sweep` | `textbook-sweep` | `textbook-restart` | `wicaksono-sweep`의 안전 순서가 본문의 '원래 뱅커' 순서와 같은가 |")
    lines.append("|---|---|---|---|---|---|")
    for r8 in info["table8"]:
        lines.append(f"| {r8['case']} | {r8['table8']} | {r8['wick']} | {r8['sweep']} | {r8['restart']} | {'예' if r8['seq_same'] else '아니오'} |")
    lines.append("")
    lines.append("표 8의 Wicaksono 열은 찾을 때마다 처음부터 훑는 구현(`textbook-restart`)의 값과 같다. 훑는 도중 갱신된 Available을 뒤의 프로세스가 보는 Sweep 구조를 옮긴 이 구현은 "
                 "best에서는 비교 횟수만 같고 안전 순서가 다르며, average에서는 둘 다 다르고, worst에서는 안전 순서만 같고 비교 횟수가 다르다. DBDAA 논문이 Wicaksono의 알고리즘을 어떻게 돌렸는지는 읽은 범위에서 확인하지 못했다"
                 "(표 8의 열이 원래 뱅커의 값을 옮긴 것일 수도, 다른 읽기를 쓴 것일 수도 있다). 관찰이며 DBDAA 논문의 오류라고 단정하지 않는다. "
                 "그 값은 DBDAA 논문의 보고이고 Wicaksono 논문의 주장이 아니다.\n")
    lines.append("## 3. 두 번째 독립 구현과의 차등\n")
    lines.append("그림 2–4를 제자리 갱신 방식으로 그대로 옮긴 기계(`literal_wicaksono`: ops를 쓰지 않고 비교·덧셈을 직접 세며 Allocation, Max, Available을 제자리에서 바꾼다)와 비교한다. "
                 "비교 항목은 안전 순서, error 여부, 바깥 반복 수, 받아들인 도착과 받지 못한 도착, 최종 프로세스 수, 계측 계수(vec_cmp, sca_cmp, vec_add, iters, sweeps, need_ops)다. "
                 f"입력은 문헌 예제, 소규모 전수 일부, 층화 무작위(F-rand형) 일부, 경계 상태, 값이 큰 무작위 상태를 합한 {d['states']:,}개이고, 각 상태에 도착 없음과 무작위 도착 두 가지를 붙여 {d['runs']:,}회 실행했다"
                 f"(등록된 입력군이 아니다). 불일치 {d['bad']}건. 시간 {d['seconds']:.1f}초.\n")
    lines.append("| 분기 | 실행 수 |")
    lines.append("|---|---|")
    for k, v in d["cov"].items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("## 4. 속성과 변이체\n")
    lines.append(f"속성은 {info['prop_states']}개 상태에서 도착 없음과 무작위 도착 세 가지를 붙인 {info['prop_runs']}회 실행에서 본다.\n")
    lines.append("| 속성 | 위반 |")
    lines.append("|---|---|")
    for key, cnt in info["props"].items():
        lines.append(f"| {info['prop_labels'][key]} | {cnt} |")
    lines.append("")
    lines.append("| 변이체(두 번째 구현에 넣은 오류) | 차등 점검이 잡은 실행 수 | 실행 수 |")
    lines.append("|---|---|---|")
    for mut, caught, total in info["mutants"]:
        lines.append(f"| {mut} | {caught} | {total} |")
    lines.append("")
    lines.append("## 5. 관찰: 도착 확인 창 (도출 D6, AI, 사람 검토 대기)\n")
    lines.append("의사코드는 도착을 바깥 반복의 맨 앞에서 한 번만 확인한다. 따라서 (가) 모든 프로세스가 끝나 루프가 끝난 뒤에 도착한 프로세스와 "
                 "(나) error로 끝난 뒤에 도착한 프로세스는 받아들여지지 않고 호출자에게 알려지지도 않는다(재구현은 `missed`로 기록한다).\n")
    yn = lambda b: "예" if b else "아니오"  # noqa: E731
    lines.append(f"- (가) 예제에 k = 3으로 도착을 요청하면 안전 순서 {', '.join(w['late_after_done']['seq'])}, error {yn(w['late_after_done']['error'])}, 받지 못함 {w['late_after_done']['missed']}.")
    lines.append(f"- (나) Available이 {w['late_after_stuck']['avail']}이고 모든 프로세스가 더 필요해 첫 반복에서 막히는 점검용 상태에서 k = 2로 도착을 요청하면 "
                 f"안전 순서 {w['late_after_stuck']['seq'] or '(비어 있음)'}, error {yn(w['late_after_stuck']['error'])}, 바깥 반복 {w['late_after_stuck']['passes']}, 받지 못함 {w['late_after_stuck']['missed']}.")
    ip, pp = info["prop_pairs"]
    lines.append(f"- 같은 도착이 다른 반복에서도 받아들여지면 error 여부가 같다(점검 쌍 {ip:,}개, 위반 0). 첫 반복의 도착은 처음부터 있던 프로세스와 같다"
                 f"(안전 순서·error·반복 수·계수가 같음. 점검 쌍 {pp:,}개, 위반 0). 즉 이 읽기에서 도착 시점은 받아들여지기만 하면 안전 순서와 비교 횟수만 바꾸고 error 여부는 바꾸지 않는다. "
                 "이는 도출이며 증명이 아니다. 이 점검은 변형의 판정을 오라클이나 닫힘 계산과 대조하지 않았다.\n")
    status = "모두 통과" if not L.fails else f"실패 {len(L.fails)}건"
    lines.append(f"점검 {L.checks}개: {status}. 총 시간 {time.time() - t0:.0f}초.\n")
    if L.fails:
        lines.append("### 실패 목록\n")
        lines += [f"- {x}" for x in L.fails[:60]]
        lines.append("")
    lines.append("## 범위와 한계\n")
    lines.append("- 이 점검은 '구현이 논문의 서술(의사코드, 표)을 옮긴 해석과 같다'는 것과 '논문 예제를 재현한다'는 것만 본다. 해석이 논문의 뜻과 같다는 보장은 없다(docs/rq6/variants.md §5.1의 해석 목록).")
    lines.append("- 두 번째 구현은 같은 사람이 같은 이해로 쓴 것이다. 구조가 달라 옮기다 생기는 실수는 잡지만 해석의 오류는 잡지 못한다.")
    lines.append("- 논문의 값은 도구가 읽어 낸 PDF 본문에서 옮겼다. 값 사이의 중복(Need = Max − Allocation, 총량, 표 2·5의 되짚기)으로 정합성을 점검했으나 인쇄본과의 일치를 보장하지는 않는다.")
    lines.append("- 논문의 시각 표지(T0, T2, T4, T5)는 설명이 없어 해석하지 않았다. 도착 시점을 바깥 반복의 둘째 맨 앞으로 읽은 것은 예제의 인쇄된 순서와 표 4의 상황에 맞추기 위한 것이다.")
    lines.append("- DBDAA 표 8의 Wicaksono 열은 이 구현의 결과와 average·worst에서 다르다(§2.2). 어느 쪽이 DBDAA 저자들의 읽기인지는 모르며, 이 구현의 읽기가 저자들의 뜻과 같다는 보장도 없다.")
    lines.append("- 논문에는 정량 주장(복잡도, 성능, 비교 실험)이 없다. 그래서 재현할 비용·시간 주장이 없고 이 점검은 K2·K3를 재지 않는다.")
    lines.append("- 오라클(O1)과의 비교와 등록된 입력군 위의 비용·시간은 동결 전에 하지 않았다.")
    text = "\n".join(lines) + "\n"
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(f"점검 {L.checks}개, 실패 {len(L.fails)}건, {time.time() - t0:.0f}초")
    for x in L.fails[:20]:
        print("  실패:", x)
    return 1 if L.fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
