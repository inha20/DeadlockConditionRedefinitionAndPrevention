"""문헌 변형 재구현의 점검 (prereg/README.md SP-5, WP6.3). AI(Claude)가 쓴 초안이며 사람의 검토 전이다.
실행: python3 -I bench/check_variants.py formal/rq6/variants-check-results.md

변형은 오라클과 같아야 하는 대상이 아니다(오라클과의 불일치가 K1이 재는 것이다). 그래서 이 점검은 오라클과 비교하지 않는다.
대신 세 가지를 본다.
  1. 문헌 예제 재현: 논문이 실은 입력에서 논문이 밝힌 결과(순서, 추적표의 값, 비교 횟수)가 나오는가.
  2. 두 번째 독립 구현과의 차등: 같은 해석을 줄 번호 그대로 옮긴 goto 기계(위치를 값으로 다시 찾는 등 구조가 다르다)와
     소규모 전수와 무작위 입력에서 같은 결과를 내는가. 점검이 비공허한지 일부러 틀린 구현(변이체)으로 확인한다.
  3. 속성: Safe_Sequence를 되짚으면 각 단계에서 Need <= Work인가, 입력을 바꾸지 않는가, 계측과 비계측 실행이 같은 결과인가,
     비교 횟수가 식과 맞는가.
오라클과의 비교(K1)와 등록된 입력군 위의 비교 횟수·시간(K2, K3)은 동결 전에 하지 않는다(prereg/RQ6.md §5).
문헌 예제(F-lit)는 그 입력군이 아니다. 이 점검의 '관찰' 절은 재현 결과이며 주장 판정이 아니다.
"""
from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "oracle"))

import oracle.banker as ob  # noqa: E402
from bench import gen_banker as G  # noqa: E402
from bench.literature import dbdaa2024 as D  # noqa: E402
from bench.ops import CountingOps, PlainOps  # noqa: E402
from bench.policies import banker as pb  # noqa: E402
from bench.policies.banker.textbook import TextbookRestart, TextbookSweep  # noqa: E402
from bench.policies.banker.variants.zohora2024 import DBDAACycle1, DBDAARepeat  # noqa: E402
from bench.state import BState  # noqa: E402


class _Log:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.checks = 0

    def check(self, cond: bool, what: str) -> bool:
        self.checks += 1
        if not cond:
            self.fails.append(what)
        return bool(cond)


# ---------------------------------------------------------------- 두 번째 독립 구현(DBDAA)

def literal_dbdaa(total, alloc, need, avail, requeue: bool, tie: str = "first", mutation: str | None = None):
    """Algorithm 1을 줄 번호 그대로 옮긴 goto 기계. 반환: (Safe_Sequence, 남은 Primary_Unsafe, Unsafe, 논문이 센 비교 수, 주기 수).
    run()과 구조를 달리한다: 위치(L1, L2)는 최댓값·최솟값을 먼저 구한 뒤 값으로 다시 찾는다.
    mutation: 점검의 비공허성을 보이려는 고의 오류('strict19': 19줄에서 <, 'no-l3': 35줄 검사 생략, 'desc-sort': 내림차순 정렬)."""
    n, d = len(alloc), len(total)
    half = d // 2
    Available = list(avail)
    Unsafe, RQ, Safe, Primary = [], [], [], []
    comps = 0
    for i in range(n):                                              # 3–11줄
        if any(alloc[i][j] + need[i][j] > total[j] for j in range(d)):
            Unsafe.append(i)
        else:
            RQ.append(i)
    mkey = {i: max(need[i]) for i in RQ}                            # 9줄
    SRQ = sorted(RQ, key=lambda i: mkey[i], reverse=(mutation == "desc-sort"))   # 10줄(안정 정렬)
    pc, cycles, progress = 12, 1, False
    i = k = L1 = L2 = L3 = MaxNeed = MinA = None
    mark: list = []
    unm: list = []
    guard = 0
    while True:
        guard += 1
        if guard > 5_000_000:
            raise RuntimeError("literal_dbdaa: 반복이 끝나지 않음")
        if pc == 12:
            if SRQ:
                pc = 13
            elif requeue and Primary and progress:
                SRQ, Primary, progress, cycles = list(Primary), [], False, cycles + 1
            else:
                break
        elif pc == 13:
            i = SRQ.pop(0)
            k = 1
            mark = [False] * d
            pc = 14
        elif pc == 14:
            pc = 15 if k <= half else 31
        elif pc == 15:
            unm = [j for j in range(d) if not mark[j]]
            MaxNeed = max(need[i][j] for j in unm)
            MinA = min(Available[j] for j in unm)
            pc = 19
        elif pc == 19:
            comps += 1
            ok19 = (MaxNeed < MinA) if mutation == "strict19" else (MaxNeed <= MinA)
            pc = 42 if ok19 else 22
        elif pc == 22:
            c1 = [j for j in unm if need[i][j] == MaxNeed]
            c2 = [j for j in unm if Available[j] == MinA]
            L1 = c1[0] if tie == "first" else c1[-1]
            L2 = c2[0] if tie == "first" else c2[-1]
            pc = 24
        elif pc == 24:
            comps += 1
            if need[i][L1] > Available[L1]:
                pc = 25
            else:
                comps += 1
                pc = 25 if need[i][L2] > Available[L2] else 27
        elif pc == 25:
            Primary.append(i)
            pc = 44
        elif pc == 27:
            mark[L1] = True
            mark[L2] = True
            k += 1
            pc = 14
        elif pc == 31:
            pc = 42 if all(mark) else 34
        elif pc == 34:
            L3 = [j for j in range(d) if not mark[j]][0]
            pc = 35
        elif pc == 35:
            comps += 1
            if mutation == "no-l3":
                pc = 38
            else:
                pc = 36 if need[i][L3] > Available[L3] else 38
        elif pc == 36:
            Primary.append(i)
            pc = 44
        elif pc == 38:
            pc = 42
        elif pc == 42:
            Safe.append(i)
            progress = True
            pc = 43
        elif pc == 43:
            for j in range(d):
                Available[j] += alloc[i][j]
            pc = 44
        elif pc == 44:
            pc = 12                                                   # 타이머는 만료되지 않는다고 본다
        else:
            raise RuntimeError(f"알 수 없는 줄 {pc}")
    return Safe, Primary, Unsafe, comps, cycles


def run_main(policy, st: BState, want_trace: bool = False):
    return policy.run(st, CountingOps(), want_trace)


def lit_of(st: BState, requeue: bool, tie: str = "first", mutation: str | None = None):
    return literal_dbdaa(st.total, st.alloc, st.need, st.avail, requeue, tie, mutation)


class _Tie(DBDAACycle1):
    name = "dbdaa-cycle1-lasttie"
    loc_tie = "last"


class _TieRepeat(DBDAARepeat):
    name = "dbdaa-repeat-lasttie"
    loc_tie = "last"


def same(res, lit) -> bool:
    safe, prim, uns, comps, cycles = lit
    return (res.safe == safe and res.primary_unsafe == prim and res.unsafe == uns
            and res.counts["paper_cmp"] == comps and res.cycles == cycles)


# ---------------------------------------------------------------- 점검 본문

def check_fixture(L: _Log, rows_out: list) -> None:
    """옮긴 표의 정합성."""
    stated_avail = {"best": [4, 5, 10, 4, 8], "average": [4, 5, 3, 8, 6], "worst": [2, 2, 7, 8, 5]}
    top_bottom = {"best": ("P10", "P8"), "average": ("P4", "P10"), "worst": ("P3", "P5")}
    for case in ("best", "average", "worst"):
        st, ids, rows = D.load(case)
        bad_rows = D.inconsistent_rows(rows)
        L.check(bad_rows == D.KNOWN_TABLE_INCONSISTENCIES[case],
                f"{case}: 인쇄된 Need가 Maximum − Allocation과 다른 행 {bad_rows} ≠ 알려진 {D.KNOWN_TABLE_INCONSISTENCIES[case]}")
        L.check(st.avail == stated_avail[case], f"{case}: Available {st.avail} ≠ 본문 {stated_avail[case]}")
        L.check(all(r["max"][j] <= D.RESOURCE[j] for r in rows for j in range(5)), f"{case}: Maximum이 Resource를 넘음")
        L.check(len(rows) == 10 and all(r["at"] == 0 for r in rows), f"{case}: 프로세스 수 10, AT 0")
        order = sorted(range(10), key=lambda i: max(st.need[i]))
        L.check((ids[order[0]], ids[order[-1]]) == top_bottom[case], f"{case}: SRQ의 맨 위·맨 아래가 본문과 다름")
        bt_total = sum(r["bt"] for r in rows)
        L.check(bt_total == D.CYCLE_M, f"{case}: BT 합 {bt_total} ≠ m")
        lost = sum(rows[ids.index(p)]["bt"] for p in D.DBDAA_RESULT[case]["primary_unsafe"])
        L.check(bt_total - lost == D.DBDAA_RESULT[case]["gantt_end"], f"{case}: 간트 끝 시각이 BT 합과 맞지 않음")
        rows_out.append((case, st.avail, bt_total, bt_total - lost))
    # 비공허성: 옮긴 값 하나를 일부러 틀리게 하면 위 점검이 잡는가
    bad = D.TABLE_3.replace("P2 0 4 | 10 13 12 14 14 | 1 3 3 3 4", "P2 0 4 | 10 13 12 14 14 | 2 3 3 3 4")
    L.check(bad != D.TABLE_3, "비공허성 점검용 치환이 적용되지 않음")
    rows = D.parse_table(bad)
    avail = [D.RESOURCE[j] - sum(r["alloc"][j] for r in rows) for j in range(5)]
    L.check(D.inconsistent_rows(rows) != D.KNOWN_TABLE_INCONSISTENCIES["average"] and avail != [4, 5, 3, 8, 6],
            "비공허성: 옮긴 값을 틀리게 한 표를 정합성 점검이 잡지 못함")


def check_examples(L: _Log, info: dict) -> None:
    """DBDAA 예제 재현: 추적표 5–7, 순서, 비교 횟수(표 8)."""
    for case in ("best", "average", "worst"):
        st, ids, rows = D.load(case)
        pol = DBDAACycle1()
        res = run_main(pol, st, want_trace=True)
        exp = D.DBDAA_RESULT[case]
        L.check([ids[i] for i in res.safe] == exp["safe"], f"{case}: Safe_Sequence가 본문과 다름 {[ids[i] for i in res.safe]}")
        L.check([ids[i] for i in res.primary_unsafe] == exp["primary_unsafe"], f"{case}: Primary_Unsafe가 본문과 다름")
        L.check(res.counts["paper_cmp"] == exp["comparisons"], f"{case}: 논문 단위 비교 수 {res.counts['paper_cmp']} ≠ {exp['comparisons']}")
        paper = D.parse_trace(D.TRACES[case])
        L.check(len(res.trace) == len(paper), f"{case}: 추적 행 수 {len(res.trace)} ≠ {len(paper)}")
        for rec, e in zip(res.trace, paper):
            got = (ids[rec["i"]], (rec["max_need"] + [None, None])[:2], rec["avail"], (rec["min_avail"] + [None, None])[:2],
                   rec["safe"], rec["comparisons"])
            want = (e["id"], e["max_need"], e["avail"], e["min_avail"], e["safe"], e["comparisons"])
            L.check(got == want, f"{case}: 추적표 행 불일치 got={got} want={want}")
        info[case] = {"counts": res.counts}
        if case == "average":
            # 표 3의 P4 행(Need R5가 4로 인쇄, Maximum − Allocation은 5)을 식 1대로 읽어도 순서·비교 수가 같은가(관찰)
            st_alt, _, _ = D.load(case, use_printed_need=False)
            ra = run_main(DBDAACycle1(), st_alt, want_trace=True)
            diffs = [(ids[a["i"]], key) for a, b in zip(ra.trace, res.trace)
                     for key in ("avail", "max_need", "min_avail", "safe", "comparisons") if a[key] != b[key]]
            info["alt_need"] = {"safe_same": ra.safe == res.safe, "cmp_same": ra.counts["paper_cmp"] == res.counts["paper_cmp"],
                                "diffs": diffs}
        # 해석 민감도(관찰): 위치가 여럿일 때 뒤쪽 자원을 고르면 예제가 그대로 재현되는가
        r2 = run_main(_Tie(), st, want_trace=True)
        tr_ok = (r2.safe == res.safe and r2.primary_unsafe == res.primary_unsafe
                 and [t["comparisons"] for t in r2.trace] == [t["comparisons"] for t in res.trace]
                 and all(a["avail"] == b["avail"] and a["max_need"] == b["max_need"] and a["min_avail"] == b["min_avail"]
                         for a, b in zip(r2.trace, res.trace)))
        info[case]["last_tie_same"] = tr_ok
        # 해석 민감도(관찰): 주기를 되풀이하면
        r3 = run_main(DBDAARepeat(), st)
        info[case]["repeat"] = {"safe": [ids[i] for i in r3.safe], "primary": [ids[i] for i in r3.primary_unsafe],
                                "cycles": r3.cycles, "paper_cmp": r3.counts["paper_cmp"], "counts": r3.counts}


def check_baseline_examples(L: _Log, info: dict) -> None:
    """표 8의 '원래의 뱅커' 열(85, 100, 125)과 본문이 적은 안전 순서가 어느 교재식 구현에서 나오는가(관찰 + Restart 재현 점검)."""
    def order(st, restart: bool):
        n, work, fin, out = st.n, list(st.avail), [False] * st.n, []
        if restart:
            while True:
                f = next((i for i in range(n) if not fin[i] and all(a <= b for a, b in zip(st.need[i], work))), -1)
                if f < 0:
                    break
                work = [w + a for w, a in zip(work, st.alloc[f])]
                fin[f] = True
                out.append(f)
        else:
            prog = True
            while prog and len(out) < n:
                prog = False
                for i in range(n):
                    if not fin[i] and all(a <= b for a, b in zip(st.need[i], work)):
                        work = [w + a for w, a in zip(work, st.alloc[i])]
                        fin[i] = True
                        out.append(i)
                        prog = True
        return out
    for case in ("best", "average", "worst"):
        st, ids, _ = D.load(case)
        want = D.BASELINE_RESULT[case]
        rec = {}
        for P, restart in ((TextbookRestart(), True), (TextbookSweep(), False)):
            ops = CountingOps()
            P.is_safe(st, ops)
            seq = [ids[i] for i in order(st, restart)]
            rec[P.name] = {"vec_cmp": ops.vec_cmp, "full": ops.vec_cmp * st.m, "executed": ops.sca_cmp,
                           "seq_ok": seq == want["safe"], "count_ok": ops.vec_cmp * st.m == want["count"]}
        info[case] = rec
        r = rec["textbook-restart"]
        L.check(r["seq_ok"] and r["count_ok"], f"{case}: 교재식 Restart가 표 8의 '원래의 뱅커'(순서·{want['count']}회)를 재현하지 못함")


def check_differential(L: _Log, info: dict) -> None:
    """DBDAA 두 정책(× 위치 규칙 두 가지)을 두 번째 독립 구현과 소규모 전수·무작위 입력에서 비교한다."""
    pols = [(DBDAACycle1(), False, "first"), (DBDAARepeat(), True, "first"), (_Tie(), False, "last"), (_TieRepeat(), True, "last")]
    ranges = [(2, (1, 1, 1, 1), 1), (2, (1, 1, 1, 1, 1), 2), (3, (1, 1, 1), 1), (3, (2, 2, 1), 3), (4, (1, 1), 1), (3, (1, 1, 1, 1), 7),
              (2, (2, 2, 2, 2), 15)]
    rows = []
    t_all = time.time()
    for n, total, stride in ranges:
        t0 = time.time()
        cnt = bad = 0
        for k, b in enumerate(ob.all_states(n, total)):
            if k % stride:
                continue
            st = BState.from_oracle(b)
            for P, rq, tie in pols:
                cnt += 1
                if not same(P.run(st, CountingOps()), lit_of(st, rq, tie)):
                    bad += 1
        L.check(bad == 0, f"차등 불일치 n={n} total={total}: {bad}건")
        rows.append((f"전수(간격 {stride})", n, list(total), cnt, bad, time.time() - t0))
        print(f"[차등-전수] n={n} total={total} 비교 {cnt:,} 불일치 {bad} {time.time() - t0:.1f}초", flush=True)
    cells = [(6, 3), (8, 4), (10, 5), (12, 6), (16, 7), (24, 8), (30, 9)]
    for n, m in cells:
        t0 = time.time()
        inst, _ = G.sample_cell(1234, f"v{n}x{m}", n, m, 40, 0.5)
        cnt = bad = 0
        for it in inst:
            st = it["state"]
            for P, rq, tie in pols:
                cnt += 1
                if not same(P.run(st, CountingOps()), lit_of(st, rq, tie)):
                    bad += 1
        L.check(bad == 0, f"차등 불일치 F-rand형 n={n} m={m}: {bad}건")
        rows.append(("무작위(층화, 안전 0.5)", n, m, cnt, bad, time.time() - t0))
        print(f"[차등-무작위] n={n} m={m} 비교 {cnt:,} 불일치 {bad} {time.time() - t0:.1f}초", flush=True)
    info["diff_rows"] = rows
    info["diff_seconds"] = time.time() - t_all


def check_mutants(L: _Log, info: dict) -> None:
    """변이체: 일부러 틀린 구현(두 번째 구현에 오류를 넣음)을 같은 차등 점검이 잡는가."""
    out = []
    pol = DBDAACycle1()
    pool = []
    for case in ("best", "average", "worst"):
        pool.append(D.load(case)[0])
    inst, _ = G.sample_cell(77, "mut", 12, 5, 60, 0.5)
    pool += [it["state"] for it in inst]
    # d가 홀수인 소규모 전수 일부(35줄의 마지막 자원 검사가 결과를 가르는 입력을 포함한다)
    pool += [BState.from_oracle(b) for k, b in enumerate(ob.all_states(3, (1, 1, 1))) if k % 100 == 0]
    for mut in ("strict19", "no-l3", "desc-sort"):
        caught = sum(0 if same(pol.run(st, CountingOps()), lit_of(st, False, "first", mut)) else 1 for st in pool)
        L.check(caught > 0, f"변이체 {mut}를 차등 점검이 잡지 못함")
        out.append((mut, caught, len(pool)))
    info["mutants"] = out


def check_properties(L: _Log, info: dict) -> None:
    """속성: 되짚기, 비변경, 계측·비계측 동일, 비교 횟수 식, 모노토닉."""
    states = [D.load(c)[0] for c in ("best", "average", "worst")]
    for n, m in [(6, 3), (8, 4), (12, 5), (16, 6), (20, 7), (10, 2), (10, 1), (7, 8)]:
        inst, _ = G.sample_cell(2468, f"p{n}x{m}", n, m, 30, 0.5)
        states += [it["state"] for it in inst]
    for _, st, _ok in G.boundary_states():
        states.append(st)
    props = {"replay": 0, "mutate": 0, "plain": 0, "bound": 0, "scan": 0, "formula": 0, "mono": 0}
    for st in states:
        n, d = st.n, st.m
        snap = (list(map(list, st.alloc)), list(map(list, st.need)), list(st.avail), list(st.total))
        res = {}
        for P in (DBDAACycle1(), DBDAARepeat()):
            ops = CountingOps()
            r = P.run(st, ops, want_trace=True)
            res[P.name] = r
            # 되짚기: Safe_Sequence의 각 단계에서 Need <= Work
            work = list(st.avail)
            for p in r.safe:
                if not all(st.need[p][j] <= work[j] for j in range(d)):
                    props["replay"] += 1
                    break
                work = [work[j] + st.alloc[p][j] for j in range(d)]
            if snap != (list(map(list, st.alloc)), list(map(list, st.need)), list(st.avail), list(st.total)):
                props["mutate"] += 1
            r2 = P.run(st, PlainOps())
            if (r2.safe, r2.primary_unsafe, r2.unsafe, r2.cycles) != (r.safe, r.primary_unsafe, r.unsafe, r.cycles):
                props["plain"] += 1
            hi = 3 * (d // 2) + (d % 2)
            if not all(1 <= t["comparisons"] <= hi for t in r.trace):
                props["bound"] += 1
            scan = sum(2 * (d - 2 * (t - 1) - 1) for rec in r.trace for t in range(1, len(rec["max_need"]) + 1))
            if scan != r.counts["scan_cmp"]:
                props["scan"] += 1
            c = r.counts
            sort_ok = c["sort_cmp"] >= max(0, n - 1 - len(r.unsafe))
            if not (c["admit_cmp"] == n * d and c["maxneed_cmp"] == n * (d - 1) and c["vec_add"] == len(r.safe)
                    and c["iters"] == len(r.trace) and sort_ok
                    and c["sca_cmp"] == c["paper_cmp"] + c["scan_cmp"] + c["admit_cmp"] + c["maxneed_cmp"] + c["sort_cmp"]):
                props["formula"] += 1
        a, b = res["dbdaa-cycle1"], res["dbdaa-repeat"]
        safe1 = not a.primary_unsafe and not a.unsafe
        safe2 = not b.primary_unsafe and not b.unsafe
        if not (b.safe[:len(a.safe)] == a.safe and (not safe1 or safe2)):
            props["mono"] += 1
    labels = {"replay": "Safe_Sequence 되짚기 실패", "mutate": "입력 변경", "plain": "계측·비계측 결과 불일치",
              "bound": "한 프로세스의 비교 수가 1..3⌊d/2⌋+(d mod 2)를 벗어남", "scan": "탐색 비교 수가 식과 다름",
              "formula": "비교·덧셈·반복 횟수 식 위반", "mono": "cycle1 ⊆ repeat 위반"}
    for key, cnt in props.items():
        L.check(cnt == 0, f"속성 위반 {labels[key]}: {cnt}건")
    info["prop_states"] = len(states)
    info["props"] = props
    info["prop_labels"] = labels


def check_registry(L: _Log) -> None:
    for name in ("dbdaa-cycle1", "dbdaa-repeat"):
        L.check(name in pb.REGISTRY and pb.get(name).name == name, f"등록부에 {name}이 없음")
    L.check(len(set(pb.REGISTRY)) == len(pb.REGISTRY), "등록부 이름 중복")


def main(out_path: str | None) -> int:
    t0 = time.time()
    L = _Log()
    info: dict = {}
    fx_rows: list = []
    check_registry(L)
    check_fixture(L, fx_rows)
    check_examples(L, info)
    ex = {k: info[k] for k in ("best", "average", "worst")}
    base_info: dict = {}
    check_baseline_examples(L, base_info)
    check_properties(L, info)
    check_mutants(L, info)
    check_differential(L, info)

    lines = ["# 문헌 변형 재구현 점검 결과\n",
             "`bench/check_variants.py`가 쓴 결과다. AI(Claude)가 작성한 초안이며 사람의 검토 전이다. 변형은 오라클과 비교하지 않는다"
             "(불일치가 K1이 재는 대상이다). 문헌 예제 재현, 같은 해석의 두 번째 독립 구현과의 차등, 속성을 본다. "
             "아래 '관찰'은 문헌 예제의 재현 결과이며 주장 판정이 아니다.\n"]
    lines.append("## 1. DBDAA (R6-07, Zohora·Farhin·Kaiser 2024)\n")
    lines.append("### 1.1 옮긴 표의 정합성\n")
    lines.append("| 예제 | Available(식 2) | BT 합 | 간트 끝 시각(BT 합 − Primary_Unsafe의 BT) |")
    lines.append("|---|---|---|---|")
    for case, av, bt, end in fx_rows:
        lines.append(f"| {case} | {av} | {bt} | {end} |")
    lines.append("")
    alt = info["alt_need"]
    lines.append(f"표 3의 P4 행은 논문 안에서 맞지 않는다. Maximum R5 = 5, Allocation R5 = 0이라 식 1의 Need R5는 5인데 표에는 4로 인쇄됐다"
                 f"(추적표 6의 최대 Need 4와 본문의 '4 > 3', '4 ≤ 6'은 4를 따른다. 5를 따르는 것은 식 1과 표 3의 Maximum·Allocation 열이다. "
                 f"본문의 'Max_Need (5)'는 값이 아니라 자원 위치 R5를 가리킨다). "
                 f"재구현은 인쇄된 Need를 썼다. 식 1대로 5로 읽으면 Safe_Sequence {'같음' if alt['safe_same'] else '다름'}, "
                 f"비교 수 {'같음' if alt['cmp_same'] else '다름'}, 추적표에서 달라지는 칸: {alt['diffs'] or '없음'}.\n")
    lines.append("### 1.2 예제 재현 (표 5–7, 표 8의 DBDAA 열)\n")
    lines.append("DBDAA를 첫 주기만(dbdaa-cycle1) 돌려, 추적표의 모든 행(처리 순서, 1회·2회의 최대 Need와 최소 Available, "
                 "그때의 Available, 안전 여부, 비교 횟수)과 Safe_Sequence·Primary_Unsafe·총 비교 횟수가 논문과 같은지 본다.\n")
    lines.append("| 예제 | 총 비교(논문 단위) | 논문 | Safe_Sequence 길이 | Primary_Unsafe | 위치 규칙 '뒤쪽 선택'에서도 같은 추적 |")
    lines.append("|---|---|---|---|---|---|")
    for case in ("best", "average", "worst"):
        c = ex[case]["counts"]
        lines.append(f"| {case} | {c['paper_cmp']} | {D.DBDAA_RESULT[case]['comparisons']} | {c['vec_add']} | "
                     f"{', '.join(D.DBDAA_RESULT[case]['primary_unsafe']) or '—'} | {'예' if ex[case]['last_tie_same'] else '아니오'} |")
    lines.append("")
    lines.append("### 1.3 관찰: 같은 입력에서 단위별 비용과 해석별 결과\n")
    lines.append("'논문 단위'는 논문이 센 명시적 비교(19, 24, 35줄)만이다. '전체 스칼라'는 입장 검사·Max_Need 계산·정렬(계측 실행)·"
                 "최대·최소 탐색까지 포함한 실행한 모든 스칼라 비교다. 두 단위의 차이는 K2의 단위 선택(열린 항목)에 속한다.\n")
    lines.append("| 예제 | DBDAA 논문 단위 | DBDAA 전체 스칼라 | (탐색 / 입장 / Max_Need / 정렬) | repeat: 주기 수 | repeat: 논문 단위 합 | repeat 결과 |")
    lines.append("|---|---|---|---|---|---|---|")
    for case in ("best", "average", "worst"):
        c = ex[case]["counts"]
        r = ex[case]["repeat"]
        res_txt = "모두 통과" if not r["primary"] else f"남음: {', '.join(r['primary'])}"
        lines.append(f"| {case} | {c['paper_cmp']} | {c['sca_cmp']} | {c['scan_cmp']} / {c['admit_cmp']} / {c['maxneed_cmp']} / {c['sort_cmp']} | "
                     f"{r['cycles']} | {r['paper_cmp']} | {res_txt} |")
    lines.append("")
    lines.append("### 1.4 관찰: 표 8의 '원래의 뱅커' 열(85, 100, 125)\n")
    lines.append("논문의 '원래의 뱅커' 열이 어느 교재식 구현의 어떤 단위에서 나오는지 본다. 벡터 비교 횟수에 d = 5를 곱한 값(단락 평가 없는 전체 스칼라)과 "
                 "본문이 적은 안전 순서를 비교한다. 'Restart'는 한 프로세스를 끝낼 때마다 처음부터 다시 훑는 구현, 'Sweep'은 훑기를 이어서 하는 구현이다.\n")
    lines.append("| 예제 | 논문 비교 수 | 구현 | 벡터 비교 | ×d | 실행한 스칼라(단락 평가) | 순서 일치 | ×d가 논문과 일치 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for case in ("best", "average", "worst"):
        for name in ("textbook-restart", "textbook-sweep"):
            r = base_info[case][name]
            lines.append(f"| {case} | {D.BASELINE_RESULT[case]['count']} | {name} | {r['vec_cmp']} | {r['full']} | {r['executed']} | "
                         f"{'예' if r['seq_ok'] else '아니오'} | {'예' if r['count_ok'] else '아니오'} |")
    lines.append("")
    lines.append("### 1.5 두 번째 독립 구현과의 차등\n")
    lines.append("줄 번호 그대로의 goto 기계(`literal_dbdaa`)와 비교한다. 비교 항목은 Safe_Sequence, 남은 Primary_Unsafe, Unsafe, "
                 "논문 단위 비교 수, 주기 수다. 두 정책(cycle1, repeat) × 위치 규칙 둘(앞, 뒤)을 각각 본다.\n")
    lines.append("| 입력 | n | 총량 또는 m | 비교 수 | 불일치 | 시간(초) |")
    lines.append("|---|---|---|---|---|---|")
    for kind, n, tm, cnt, bad, sec in info["diff_rows"]:
        lines.append(f"| {kind} | {n} | {tm} | {cnt:,} | {bad} | {sec:.1f} |")
    lines.append("")
    lines.append("### 1.6 속성과 변이체\n")
    lines.append(f"속성은 문헌 예제 3개, 무작위 입력, 경계 상태 {info['prop_states']}개 위에서 cycle1과 repeat에 대해 본다.\n")
    lines.append("| 속성 | 위반 |")
    lines.append("|---|---|")
    for key, cnt in info["props"].items():
        lines.append(f"| {info['prop_labels'][key]} | {cnt} |")
    lines.append("")
    lines.append("| 변이체(두 번째 구현에 넣은 오류) | 차등 점검이 잡은 입력 수 | 입력 수 |")
    lines.append("|---|---|---|")
    for mut, caught, total in info["mutants"]:
        lines.append(f"| {mut} | {caught} | {total} |")
    lines.append("")
    status = "모두 통과" if not L.fails else f"실패 {len(L.fails)}건"
    lines.append(f"점검 {L.checks}개: {status}. 총 시간 {time.time() - t0:.0f}초.\n")
    if L.fails:
        lines.append("### 실패 목록\n")
        lines += [f"- {f}" for f in L.fails[:60]]
        lines.append("")
    lines.append("## 범위와 한계\n")
    lines.append("- 이 점검은 '구현이 논문의 서술을 옮긴 해석과 같다'는 것과 '논문 예제를 재현한다'는 것만 본다. 해석이 논문의 뜻과 같다는 보장은 없다(docs/rq6/variants.md의 해석 목록).")
    lines.append("- 두 번째 구현은 같은 사람이 같은 이해로 쓴 것이다. 구조가 달라 옮기다 생기는 실수는 잡지만 해석의 오류는 잡지 못한다.")
    lines.append("- 오라클(O1)과의 비교와 등록된 입력군 위의 비용·시간은 동결 전에 하지 않았다.")
    lines.append("- 시계와 BT는 알고리즘에 쓰이지 않아 구현하지 않았다. 타이머는 만료되지 않는다고 보았다(해석).")
    text = "\n".join(lines) + "\n"
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
    print(f"점검 {L.checks}개, 실패 {len(L.fails)}건, {time.time() - t0:.0f}초")
    for f in L.fails[:20]:
        print("  실패:", f)
    return 1 if L.fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
