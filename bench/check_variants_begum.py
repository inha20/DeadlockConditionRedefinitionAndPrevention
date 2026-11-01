"""Begum 외 2020 재구현의 점검 (prereg/RQ6.md SP-5, WP6.3). AI(Claude)가 쓴 초안이며 사람의 검토 전이다.
실행: python3 -I bench/check_variants_begum.py formal/rq6/variants-check-begum.md

bench/check_variants.py(DBDAA)와 같은 방식이다. 변형은 오라클과 비교하지 않는다(불일치가 K1이 재는 대상이다).
  1. 옮긴 표의 정합성과 문헌 예제 재현(처리 순서, 표 IV의 모든 줄, 안전 순서, 비교 횟수 10).
  2. DBDAA 논문의 표 8이 이 논문의 알고리즘('Momotaz et al.')에 대해 적은 결과(10회, 불안전, 불안전)의 재현.
  3. 같은 해석의 두 번째 독립 구현(순서도 그림 1의 노드를 그대로 옮긴 기계. 정렬은 기수 정렬이 아니라 안정 정렬, 최솟값은 매번 처음부터 구한다)과의 차등.
     점검이 비공허한지 일부러 틀린 구현(변이체)으로 확인한다. 입력이 분기를 모두 지나가는지 적용 횟수로 보인다.
  4. 속성: 되짚기, 비변경, 계측·비계측 동일, 비교 횟수 식, 빠른 검사의 건전성, 판정이 '정렬 순서가 안전 순서인가'와 같음,
     '건너뛰고 계속' 읽기와 판정이 같음.
오라클(O1)과의 비교(K1)와 등록된 입력군 위의 비교 횟수·시간(K2, K3)은 동결 전에 하지 않는다(prereg/RQ6.md §5).
문헌 예제는 그 입력군이 아니다. 이 점검의 '관찰' 절은 재현 결과이며 주장 판정이 아니다.
"""
from __future__ import annotations

import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "oracle"))

import oracle.banker as ob  # noqa: E402
from bench import gen_banker as G  # noqa: E402
from bench.literature import begum2020 as B  # noqa: E402
from bench.literature import dbdaa2024 as D  # noqa: E402
from bench.ops import CountingOps, PlainOps  # noqa: E402
from bench.policies import banker as pb  # noqa: E402
from bench.policies.banker.textbook import TextbookRestart, TextbookSweep  # noqa: E402
from bench.policies.banker.variants.begum2020 import BegumReturn  # noqa: E402
from bench.state import BState  # noqa: E402

COUNT_KEYS = ("paper_cmp", "quick_cmp", "res_cmp", "admit_cmp", "maxneed_cmp", "min_cmp", "vec_add", "iters", "radix_passes", "sca_cmp")


class _Log:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.checks = 0

    def check(self, cond: bool, what: str) -> bool:
        self.checks += 1
        if not cond:
            self.fails.append(what)
        return bool(cond)


# ---------------------------------------------------------------- 두 번째 독립 구현(순서도 그림 1의 노드)

def literal_begum(total, alloc, need, avail, mutation: str | None = None) -> dict:
    """그림 1을 노드 그대로 옮긴 기계. primary(run)와 구조를 달리한다.
      - 정렬: 기수 정렬이 아니라 파이썬의 안정 정렬. 자릿수는 len(str(최댓값)).
      - Minimum_Available: 점진적으로 갱신하지 않고 통과할 때마다 처음부터 구한다.
      - 최대 Need와 입장 검사는 내장 함수로 구하고 비교 횟수는 식으로 센다.
    mutation: 점검의 비공허성을 보이려는 고의 오류.
      strict-quick  빠른 검사에서 < 를 쓴다
      wrong-quick   빠른 검사에서 최솟값 대신 최댓값 Available과 비교한다
      stale-min     Minimum_Available를 처음 한 번만 구한다
      no-sort       정렬하지 않는다
      desc-sort     내림차순으로 정렬한다
      no-admission  입장 검사(2단계)를 하지 않는다
      last-res-ok   마지막 자원에서의 실패를 통과로 본다(순서도의 'j == d' 판정을 문자 그대로 읽은 경우)
      skip-continue 실패한 프로세스를 건너뛰고 계속한다(판정은 같고 안전 순서와 비교 횟수가 다르다)
    반환: dict(safe, unsafe, fail_at, reason, counts)."""
    n, d = len(alloc), len(total)
    c = dict(paper_cmp=0, quick_cmp=0, res_cmp=0, admit_cmp=0, maxneed_cmp=0, min_cmp=0)
    completed = [0] * n                                    # Completed_process[1:n] := 0
    safe: list[int] = []
    work = list(avail)

    def result(unsafe, fail_at, reason, passes):
        counts = dict(c)
        counts["vec_add"] = len(safe)
        counts["iters"] = examined
        counts["radix_passes"] = passes
        counts["sca_cmp"] = c["paper_cmp"] + c["admit_cmp"] + c["maxneed_cmp"] + c["min_cmp"]
        return {"safe": list(safe), "unsafe": unsafe, "fail_at": fail_at, "reason": reason, "counts": counts}

    examined = 0
    # 노드 ADM: Maximum_need[] > Resource[] (어떤 프로세스, 어떤 자원이든)
    if mutation != "no-admission":
        for i in range(n):
            for j in range(d):
                c["admit_cmp"] += 1
                if alloc[i][j] + need[i][j] > total[j]:
                    return result(True, None, "admission", 0)
    # 노드 SORT
    keys = [max(row) for row in need]
    c["maxneed_cmp"] = n * (d - 1)
    if mutation == "no-sort":
        order = list(range(n))
    else:
        order = sorted(range(n), key=lambda i: keys[i], reverse=(mutation == "desc-sort"))
    passes = len(str(max(keys))) if keys else 1

    def min_available():
        c["min_cmp"] += d - 1
        return min(work)

    minav = min_available()
    first_min = minav
    node, pos = "LOOP_I", 0
    j = 0
    i = -1
    while True:
        if node == "LOOP_I":                                # i <= n
            if pos >= n:
                node = "FINAL"
                continue
            i = order[pos]
            node = "QUICK"
        elif node == "QUICK":
            examined += 1
            c["paper_cmp"] += 1
            c["quick_cmp"] += 1
            if mutation == "strict-quick":
                ok = keys[i] < minav
            elif mutation == "wrong-quick":
                ok = keys[i] <= max(work)
            else:
                ok = keys[i] <= minav
            node = "DONE" if (ok and completed[i] == 0) else "SET_J"
        elif node == "SET_J":
            j = 0
            node = "LOOP_J"
        elif node == "LOOP_J":                              # j <= d
            node = "CMP_J" if j < d else "DONE"
        elif node == "CMP_J":
            c["paper_cmp"] += 1
            c["res_cmp"] += 1
            if need[i][j] <= work[j]:
                j += 1
                node = "LOOP_J"
            else:
                node = "FAIL"
        elif node == "FAIL":
            if mutation == "last-res-ok" and j == d - 1:
                node = "DONE"
            elif mutation == "skip-continue":
                pos += 1
                node = "LOOP_I"
            else:
                return result(True, i, "process", passes)
        elif node == "DONE":
            completed[i] = 1
            safe.append(i)
            for r in range(d):
                work[r] += alloc[i][r]
            minav = first_min if mutation == "stale-min" else min_available()
            pos += 1
            node = "LOOP_I"
        elif node == "FINAL":
            if any(x == 0 for x in completed):
                return result(True, None, "incomplete", passes)      # 건너뛴 프로세스가 남았다(skip-continue에서만 닿는다)
            return result(False, None, None, passes)
        else:
            raise RuntimeError(f"알 수 없는 노드 {node}")


def lit_of(st: BState, mutation: str | None = None) -> dict:
    return literal_begum(st.total, st.alloc, st.need, st.avail, mutation)


def same(res, lit: dict) -> bool:
    if (res.safe != lit["safe"] or res.unsafe != lit["unsafe"] or res.fail_at != lit["fail_at"] or res.reason != lit["reason"]):
        return False
    return all(res.counts[k] == lit["counts"][k] for k in COUNT_KEYS)


def verdict_skip(st: BState) -> bool:
    """'건너뛰고 계속' 읽기의 판정(불안전이면 True): 한 번만 훑으며 실행할 수 없는 프로세스는 건너뛴다. 끝에 건너뛴 것이 있으면 불안전."""
    n, d = st.n, st.m
    if any(st.alloc[i][j] + st.need[i][j] > st.total[j] for i in range(n) for j in range(d)):
        return True
    order = sorted(range(n), key=lambda i: max(st.need[i]))
    work = list(st.avail)
    skipped = False
    for i in order:
        if all(st.need[i][j] <= work[j] for j in range(d)):
            work = [work[j] + st.alloc[i][j] for j in range(d)]
        else:
            skipped = True
    return skipped


def replay_sorted_order_ok(st: BState) -> bool:
    """정렬 순서(안정, 최대 Need 오름차순) 전체가 안전 순서인가(되짚기). 입장 검사는 따로."""
    order = sorted(range(st.n), key=lambda i: max(st.need[i]))
    work = list(st.avail)
    for i in order:
        if not all(st.need[i][j] <= work[j] for j in range(st.m)):
            return False
        work = [work[j] + st.alloc[i][j] for j in range(st.m)]
    return True


# ---------------------------------------------------------------- 입력 생성(점검용. 등록된 입력군이 아님)

def rand_wide(rng: random.Random, n: int, m: int, vmax: int) -> BState:
    """값이 큰(여러 자릿수) 무작위 상태. 입장 검사를 어기는 상태를 가끔 섞는다. 가용량은 항상 음수가 아니다."""
    total = [rng.randint(1, vmax) for _ in range(m)]
    alloc = [[0] * m for _ in range(n)]
    for j in range(m):
        held = rng.randint(0, total[j])
        for _ in range(held):
            alloc[rng.randrange(n)][j] += 1
    need = []
    cap_mode = rng.choice(("small", "mid", "full"))
    for i in range(n):
        row = []
        for j in range(m):
            room = total[j] - alloc[i][j]
            cap = {"small": max(0, room // 4), "mid": max(0, room // 2), "full": room}[cap_mode]
            row.append(rng.randint(0, cap))
        need.append(row)
    if rng.random() < 0.08:
        i, j = rng.randrange(n), rng.randrange(m)
        need[i][j] = total[j] - alloc[i][j] + rng.randint(1, 5)
    return BState.make(total, alloc, need)


def pool_states(seed: int, small_stride: int = 40, wide: int = 1500) -> list[BState]:
    out: list[BState] = [B.load()[0]]
    out += [D.load(c)[0] for c in ("best", "average", "worst")]
    for n, total in [(2, (1, 1, 1, 1)), (3, (1, 1, 1)), (3, (2, 2, 1)), (4, (1, 1)), (2, (2, 2, 2, 2))]:
        out += [BState.from_oracle(b) for k, b in enumerate(ob.all_states(n, total)) if k % small_stride == 0]
    for n, m in [(6, 3), (10, 5), (16, 7)]:
        inst, _ = G.sample_cell(seed, f"b{n}x{m}", n, m, 30, 0.5)
        out += [it["state"] for it in inst]
    out += [st for _, st, _ok in G.boundary_states()]
    rng = random.Random(seed)
    for _ in range(wide):
        n, m = rng.randint(2, 12), rng.randint(1, 6)
        out.append(rand_wide(rng, n, m, rng.choice((9, 40, 150))))
    return out


# ---------------------------------------------------------------- 점검 본문

def check_registry(L: _Log) -> None:
    L.check("begum-return" in pb.REGISTRY and pb.get("begum-return").name == "begum-return", "등록부에 begum-return이 없음")
    L.check(len(set(pb.REGISTRY)) == len(pb.REGISTRY), "등록부 이름 중복")


def check_fixture(L: _Log, info: dict) -> None:
    st, ids, rows = B.load()
    t2 = B.parse_table2()
    by2 = {r["id"]: r for r in t2}
    L.check(ids == [f"P{i}" for i in range(10)], "프로세스 이름이 P0..P9가 아님")
    bad_need = [r["id"] for r in rows if by2[r["id"]]["need"] != [r["max"][j] - r["alloc"][j] for j in range(5)]]
    L.check(not bad_need, f"표 II의 Needed allocation ≠ 표 I의 Maximum − Allocation: {bad_need}")
    bad_mx = [r["id"] for r in t2 if r["max_needed"] != max(r["need"])]
    L.check(not bad_mx, f"표 II의 Maximum Needed ≠ Needed allocation의 최댓값: {bad_mx}")
    L.check(st.avail == list(B.INITIAL_AVAILABLE), f"Resource − Σ Allocation = {st.avail} ≠ 본문 {list(B.INITIAL_AVAILABLE)}")
    L.check(all(r["max"][j] <= B.RESOURCE[j] for r in rows for j in range(5)), "Maximum이 Resource를 넘음")
    order = [ids[i] for i in sorted(range(10), key=lambda i: by2[ids[i]]["max_needed"])]
    L.check(order == B.SORTED_ORDER, f"안정 정렬 순서 {order} ≠ 표 III의 순서")
    # 표 IV 다시 만들기: 앞 줄의 Available + 앞 프로세스의 Allocation
    t4 = B.parse_table4()
    alloc_by = {r["id"]: r["alloc"] for r in rows}
    avail = list(B.INITIAL_AVAILABLE)
    ok = True
    for r in t4:
        ok &= (r["avail"] == avail and r["min_avail"] == min(avail) and r["ok"] == (by2[r["id"]]["max_needed"] <= min(avail)))
        avail = [avail[j] + alloc_by[r["id"]][j] for j in range(5)]
    L.check(ok, "표 IV의 Available·Minimum available·조건 열이 표 I·II로 다시 만든 값과 다름")
    L.check(tuple(avail) == B.FINAL_AVAILABLE == B.RESOURCE, f"모두 끝난 뒤 Available {avail} ≠ Resource")
    L.check([r["id"] for r in t4] == B.SORTED_ORDER == B.SAFE_SEQUENCE, "표 IV의 순서 ≠ 정렬 순서 ≠ 안전 순서")
    # 비공허성: 옮긴 값 하나를 일부러 틀리게 하면 위 점검이 잡는가
    bad_t1 = B.TABLE_1.replace("P5 | 8 7 6 2 5 | 5 6 3 2 4", "P5 | 8 7 6 2 5 | 5 6 3 2 5")
    L.check(bad_t1 != B.TABLE_1, "비공허성 점검용 치환이 적용되지 않음")
    rows_bad = []
    for line in bad_t1.strip().splitlines():
        pid, mx, al = [p.strip() for p in line.split("|")]
        rows_bad.append({"id": pid, "max": [int(x) for x in mx.split()], "alloc": [int(x) for x in al.split()]})
    avail_bad = [B.RESOURCE[j] - sum(r["alloc"][j] for r in rows_bad) for j in range(5)]
    mism = [r["id"] for r in rows_bad if by2[r["id"]]["need"] != [r["max"][j] - r["alloc"][j] for j in range(5)]]
    L.check(avail_bad != list(B.INITIAL_AVAILABLE) and mism == ["P5"], "비공허성: 옮긴 값을 틀리게 한 표를 정합성 점검이 잡지 못함")
    info["fixture"] = {"avail": st.avail, "order": order, "final": avail}


def check_example(L: _Log, info: dict) -> None:
    st, ids, rows = B.load()
    res = BegumReturn().run(st, CountingOps(), want_trace=True)
    L.check([ids[i] for i in res.safe] == B.SAFE_SEQUENCE, f"안전 순서가 본문과 다름 {[ids[i] for i in res.safe]}")
    L.check(not res.unsafe, "예제가 불안전으로 판정됨")
    L.check(res.counts["paper_cmp"] == B.CLAIMED_COMPARISONS, f"논문 단위 비교 수 {res.counts['paper_cmp']} ≠ {B.CLAIMED_COMPARISONS}")
    L.check(res.counts["res_cmp"] == 0 and res.counts["quick_cmp"] == 10, "예제는 빠른 검사만으로 끝나야 함(자원별 검사 0회)")
    t4 = B.parse_table4()
    L.check([ids[t["i"]] for t in res.trace] == B.SORTED_ORDER, "처리 순서가 표 III·IV와 다름")
    L.check(len(res.trace) == len(t4) == 10, f"추적 행 수 {len(res.trace)}")
    for rec, exp in zip(res.trace, t4):
        got = (ids[rec["i"]], rec["avail"], rec["min_avail"], rec["ok"], rec["quick"])
        want = (exp["id"], exp["avail"], exp["min_avail"], exp["ok"], True)
        L.check(got == want, f"표 IV 줄 불일치 got={got} want={want}")
    L.check(all(t["comparisons"] == 1 for t in res.trace), "프로세스마다 비교 1회여야 함(본문: 'one comparison')")
    # 관찰: 같은 입력에서 단위별 비용과 교재식 구현의 비용
    base = {}
    for P in (TextbookRestart(), TextbookSweep()):
        ops = CountingOps()
        P.is_safe(st, ops)
        base[P.name] = {"vec_cmp": ops.vec_cmp, "full": ops.vec_cmp * st.m, "executed": ops.sca_cmp, "vec_add": ops.vec_add}
    info["example"] = {"counts": res.counts, "baseline": base, "n": st.n, "d": st.m}
    # 입력을 읽는 방식의 민감도(관찰): 예제에서 표 III의 P7 E칸 5(인쇄 불일치)를 쓰면 처리가 달라지는가
    st_alt = BState.make(B.RESOURCE, st.alloc, [list(r) for r in st.need])
    st_alt.need[7][4] = 5
    r_alt = BegumReturn().run(st_alt, CountingOps(), want_trace=True)
    info["example"]["alt_p7_e"] = {"safe_same": r_alt.safe == res.safe, "cmp_same": r_alt.counts["paper_cmp"] == res.counts["paper_cmp"],
                                   "unsafe": r_alt.unsafe}
    L.check(info["example"]["alt_p7_e"]["safe_same"] or r_alt.unsafe, "표 III의 P7 E칸을 5로 읽은 관찰이 모순")


def check_dbdaa_examples(L: _Log, info: dict) -> None:
    """DBDAA 논문 표 8의 'Momotaz et al. 2020 [4]' 열(10, 불안전, 불안전)을 재현하는가. 그 논문의 입력(표 2–4)을 쓴다."""
    want = D.TABLE_8["Momotaz et al. 2020 [4]"]
    out = {}
    for k, case in enumerate(("best", "average", "worst")):
        st, ids, rows = D.load(case)
        res = BegumReturn().run(st, CountingOps(), want_trace=True)
        w = want[k]
        if w == "Unsafe":
            L.check(res.unsafe, f"{case}: 표 8은 불안전인데 재구현은 안전")
        else:
            L.check((not res.unsafe) and res.counts["paper_cmp"] == w, f"{case}: 표 8의 {w}회와 다름({res.counts['paper_cmp']})")
            L.check([ids[i] for i in res.safe] == D.DBDAA_RESULT[case]["safe"],
                    f"{case}: 안전 순서가 DBDAA 본문이 두 알고리즘에 적은 순서와 다름 {[ids[i] for i in res.safe]}")
        # 관찰: 실패한 프로세스와 그때의 상황, 그 상태에 안전 순서가 있는가(DBDAA 논문이 적은 교재식 순서를 되짚어 본다)
        fail = res.fail_at
        row = res.trace[-1] if res.unsafe else None
        base_seq = [ids.index(x) for x in D.BASELINE_RESULT[case]["safe"]]
        work, replay_ok = list(st.avail), True
        for p in base_seq:
            if not all(st.need[p][j] <= work[j] for j in range(st.m)):
                replay_ok = False
                break
            work = [work[j] + st.alloc[p][j] for j in range(st.m)]
        L.check(replay_ok and len(base_seq) == st.n, f"{case}: DBDAA 본문의 교재식 순서가 되짚어지지 않음(옮긴 입력과 순서 사이의 불일치)")
        out[case] = {"unsafe": res.unsafe, "paper_cmp": res.counts["paper_cmp"], "safe_len": len(res.safe),
                     "fail": ids[fail] if fail is not None else None, "fail_row": row,
                     "need_fail": st.need[fail] if fail is not None else None,
                     "order": [ids[i] for i in sorted(range(st.n), key=lambda i: max(st.need[i]))],
                     "baseline_replays": replay_ok}
        if case == "average":
            st_alt, _, _ = D.load(case, use_printed_need=False)
            ra = BegumReturn().run(st_alt, CountingOps())
            out[case]["alt_need_unsafe"] = ra.unsafe
            out[case]["alt_need_fail"] = ids[ra.fail_at] if ra.fail_at is not None else None
            L.check(ra.unsafe == res.unsafe, "표 3의 P4 Need R5를 5로 읽으면 판정이 달라짐(관찰이 달라짐)")
    info["dbdaa"] = out


def check_differential(L: _Log, info: dict) -> None:
    t0 = time.time()
    pool = pool_states(20261101)
    pol = BegumReturn()
    bad = 0
    cov = {"입장 검사에서 불안전": 0, "안전": 0, "처리 중 불안전": 0, "빠른 검사 통과가 있었음": 0, "자원별 검사로 통과가 있었음": 0,
           "자원별 검사에서 마지막 자원이 아닌 곳에서 실패": 0, "자원별 검사에서 마지막 자원에서 실패": 0,
           "최대 Need가 두 자리 이상": 0, "정렬 키에 같은 값이 있음": 0, "d = 1": 0}
    for st in pool:
        res = pol.run(st, CountingOps(), want_trace=True)
        if not same(res, lit_of(st)):
            bad += 1
        if res.reason == "admission":
            cov["입장 검사에서 불안전"] += 1
            continue
        cov["안전" if not res.unsafe else "처리 중 불안전"] += 1
        if any(t["quick"] and t["ok"] for t in res.trace):
            cov["빠른 검사 통과가 있었음"] += 1
        if any((not t["quick"]) and t["ok"] for t in res.trace):
            cov["자원별 검사로 통과가 있었음"] += 1
        if res.unsafe:
            fi = res.fail_at
            first_fail = next(j for j in range(st.m) if st.need[fi][j] > res.trace[-1]["avail"][j])
            cov["자원별 검사에서 마지막 자원에서 실패" if first_fail == st.m - 1 else "자원별 검사에서 마지막 자원이 아닌 곳에서 실패"] += 1
        keys = [max(r) for r in st.need]
        if max(keys, default=0) >= 10:
            cov["최대 Need가 두 자리 이상"] += 1
        if len(set(keys)) < len(keys):
            cov["정렬 키에 같은 값이 있음"] += 1
        if st.m == 1:
            cov["d = 1"] += 1
    L.check(bad == 0, f"차등 불일치 {bad}건 / {len(pool)}")
    for k, v in cov.items():
        L.check(v > 0, f"차등 입력이 분기 '{k}'를 지나가지 않음")
    info["diff"] = {"states": len(pool), "bad": bad, "cov": cov, "seconds": time.time() - t0}


def check_mutants(L: _Log, info: dict) -> None:
    pool = pool_states(777, small_stride=60, wide=600)
    pol = BegumReturn()
    out = []
    for mut in ("strict-quick", "wrong-quick", "stale-min", "no-sort", "desc-sort", "no-admission", "last-res-ok", "skip-continue"):
        caught = sum(0 if same(pol.run(st, CountingOps()), lit_of(st, mut)) else 1 for st in pool)
        L.check(caught > 0, f"변이체 {mut}를 차등 점검이 잡지 못함")
        out.append((mut, caught, len(pool)))
    info["mutants"] = out


def check_properties(L: _Log, info: dict) -> None:
    pool = pool_states(424242, small_stride=50, wide=800)
    props = {"replay": 0, "mutate": 0, "plain": 0, "fail_runnable": 0, "prefix": 0, "formula": 0, "quick_sound": 0,
             "verdict_replay": 0, "verdict_skip": 0, "fail_row": 0, "bound": 0}
    for st in pool:
        n, d = st.n, st.m
        snap = (list(map(list, st.alloc)), list(map(list, st.need)), list(st.avail), list(st.total))
        ops = CountingOps()
        r = BegumReturn().run(st, ops, want_trace=True)
        # 되짚기: 안전 순서의 각 단계에서 Need <= Work
        work = list(st.avail)
        for p in r.safe:
            if not all(st.need[p][j] <= work[j] for j in range(d)):
                props["replay"] += 1
                break
            work = [work[j] + st.alloc[p][j] for j in range(d)]
        if snap != (list(map(list, st.alloc)), list(map(list, st.need)), list(st.avail), list(st.total)):
            props["mutate"] += 1
        r2 = BegumReturn().run(st, PlainOps())
        if (r2.safe, r2.unsafe, r2.fail_at, r2.reason) != (r.safe, r.unsafe, r.fail_at, r.reason):
            props["plain"] += 1
        # 계측 객체에 알린 값이 결과의 카운터와 같은가
        if (ops.sca_cmp, ops.vec_add, ops.iters) != (r.counts["sca_cmp"], r.counts["vec_add"], r.counts["iters"]) or ops.vec_cmp != 0:
            props["formula"] += 1
        if r.reason == "admission":
            first = next((i * d + j for i in range(n) for j in range(d) if st.alloc[i][j] + st.need[i][j] > st.total[j]), None)
            c = r.counts
            if not (first is not None and c["admit_cmp"] == first + 1 and c["paper_cmp"] == 0 and c["maxneed_cmp"] == 0 and r.safe == []):
                props["formula"] += 1
            if not verdict_skip(st):
                props["verdict_skip"] += 1
            continue
        # 정렬 순서의 접두사
        order = sorted(range(n), key=lambda i: max(st.need[i]))
        if r.safe != order[:len(r.safe)]:
            props["prefix"] += 1
        # 실패한 프로세스는 그 시점에 실행할 수 없다(Need가 Work를 넘는 자원이 있다). 빠른 검사는 건전하다
        if r.unsafe:
            fi = r.fail_at
            if all(st.need[fi][j] <= work[j] for j in range(d)) or r.trace[-1]["quick"]:
                props["fail_runnable"] += 1
        if any(t["quick"] and not t["ok"] for t in r.trace):
            props["quick_sound"] += 1
        # 판정 = '정렬 순서 전체가 안전 순서인가' = 건너뛰기 읽기의 판정
        if r.unsafe == replay_sorted_order_ok(st):
            props["verdict_replay"] += 1
        if r.unsafe != verdict_skip(st):
            props["verdict_skip"] += 1
        # 비교 횟수 식
        c = r.counts
        examined = len(r.safe) + (1 if r.unsafe else 0)
        keys = [max(row) for row in st.need]
        exp_min = (d - 1) * (1 + len(r.safe))
        exp_res = sum(t["comparisons"] - 1 for t in r.trace)
        if not (c["admit_cmp"] == n * d and c["maxneed_cmp"] == n * (d - 1) and c["min_cmp"] == exp_min and c["quick_cmp"] == examined
                and c["iters"] == examined and c["vec_add"] == len(r.safe) and c["res_cmp"] == exp_res
                and c["paper_cmp"] == c["quick_cmp"] + c["res_cmp"] and c["radix_passes"] == len(str(max(keys, default=0)))
                and c["sca_cmp"] == c["paper_cmp"] + c["admit_cmp"] + c["maxneed_cmp"] + c["min_cmp"]):
            props["formula"] += 1
        if not all(1 <= t["comparisons"] <= 1 + d for t in r.trace) or not (examined <= c["paper_cmp"] <= examined * (1 + d)):
            props["bound"] += 1
        # 실패한 줄: 빠른 검사가 아니고 자원별 검사가 j+1번 만에 멈춘다
        if r.unsafe:
            t = r.trace[-1]
            j0 = next(j for j in range(d) if st.need[r.fail_at][j] > t["avail"][j])
            if t["comparisons"] != 1 + j0 + 1:
                props["fail_row"] += 1
    labels = {"replay": "안전 순서 되짚기 실패", "mutate": "입력 변경", "plain": "계측·비계측 결과 불일치",
              "fail_runnable": "실패한 프로세스가 실행 가능했거나 빠른 검사에서 실패로 기록됨",
              "prefix": "안전 순서가 정렬 순서의 접두사가 아님", "formula": "비교·덧셈·반복 횟수 식 위반",
              "quick_sound": "빠른 검사를 통과했는데 실행 불가(건전성 위반)", "verdict_replay": "판정 ≠ '정렬 순서 전체가 안전 순서인가'(입장 검사 통과 입력)",
              "verdict_skip": "'건너뛰고 계속' 읽기와 판정이 다름", "fail_row": "실패한 줄의 비교 수가 j+2가 아님",
              "bound": "프로세스당 비교 수가 1..1+d를 벗어남"}
    for key, cnt in props.items():
        L.check(cnt == 0, f"속성 위반 {labels[key]}: {cnt}건")
    info["props"] = props
    info["prop_labels"] = labels
    info["prop_states"] = len(pool)


def main(out_path: str | None) -> int:
    t0 = time.time()
    L = _Log()
    info: dict = {}
    check_registry(L)
    check_fixture(L, info)
    check_example(L, info)
    check_dbdaa_examples(L, info)
    check_properties(L, info)
    check_mutants(L, info)
    check_differential(L, info)
    ex = info["example"]
    dd = info["dbdaa"]

    lines = ["# 문헌 변형 재구현 점검 결과: Begum 외 2020 (R6-05)\n",
             "`bench/check_variants_begum.py`가 쓴 결과다. AI(Claude)가 작성한 초안이며 사람의 검토 전이다. 변형은 오라클과 비교하지 않는다"
             "(불일치가 K1이 재는 대상이다). 문헌 예제 재현, 같은 해석의 두 번째 독립 구현과의 차등, 속성을 본다. "
             "아래 '관찰'은 문헌 예제의 재현 결과이며 주장 판정이 아니다.\n"]
    lines.append("## 1. 옮긴 표의 정합성과 예제 재현\n")
    f = info["fixture"]
    lines.append(f"표 II = 표 I의 Maximum − Allocation, Available = Resource − Σ Allocation = {f['avail']}(본문과 같음), "
                 f"표 III의 순서 = Maximum Needed allocation의 안정 오름차순 = {', '.join(f['order'])}, "
                 f"표 IV를 '앞 줄의 Available + 앞 프로세스의 Allocation'으로 다시 만든 값과 Minimum available·조건 열이 같고, 모두 끝난 뒤 Available = {f['final']} = Resource.\n")
    lines.append("재구현으로 예제를 돌려 처리 순서, 표 IV의 모든 줄(그때의 Available, Minimum available, 조건 Maximum Needed ≤ Minimum available), "
                 "안전 순서, 비교 횟수가 논문과 같은지 본다.\n")
    c = ex["counts"]
    lines.append("| 항목 | 재구현 | 논문 |")
    lines.append("|---|---|---|")
    lines.append(f"| 안전 순서 | {', '.join(B.SAFE_SEQUENCE)} | {', '.join(B.SAFE_SEQUENCE)} |")
    lines.append(f"| 안전 검사의 비교 횟수(논문 단위: 빠른 검사 + 자원별 검사) | {c['paper_cmp']} (빠른 검사 {c['quick_cmp']}, 자원별 {c['res_cmp']}) | {B.CLAIMED_COMPARISONS} |")
    lines.append(f"| 프로세스마다 비교 | 1회 | 1회('one comparison') |")
    lines.append("")
    lines.append("### 1.1 관찰: 같은 입력에서 단위별 비용\n")
    lines.append("논문의 '10회'는 빠른 검사(Maximum Needed ≤ Minimum available) 비교만이다. 아래는 같은 입력에서 실행한 모든 스칼라 비교다. "
                 "입장 검사(2단계)·최대 Need 계산·Minimum available 계산은 논문이 세지 않는 비교다. 기수 정렬은 비교 연산을 쓰지 않아 넣지 않았다"
                 f"(자릿수 {c['radix_passes']}회 훑기). 이는 K2의 단위 선택(열린 항목)에 속한다. 한 입력의 값이며 K2 결과가 아니다.\n")
    lines.append("| 항목 | 스칼라 비교 |")
    lines.append("|---|---|")
    lines.append(f"| 논문 단위(빠른 검사 + 자원별) | {c['paper_cmp']} |")
    lines.append(f"| 입장 검사(2단계) | {c['admit_cmp']} |")
    lines.append(f"| 프로세스별 최대 Need 계산 | {c['maxneed_cmp']} |")
    lines.append(f"| Minimum available 계산(처음 1번 + 통과마다) | {c['min_cmp']} |")
    lines.append(f"| 실행한 모든 스칼라 비교 | {c['sca_cmp']} |")
    lines.append("")
    lines.append("논문은 '원래의 뱅커라면 같은 일에 적어도 50회'라고 쓴다. 같은 입력에서 이 저장소의 교재식 구현은 다음과 같다"
                 f"(n = {ex['n']}, d = {ex['d']}이므로 n·d = {ex['n'] * ex['d']}).\n")
    lines.append("| 교재식 구현 | 벡터 비교 | ×d | 실행한 스칼라(단락 평가) | 벡터 덧셈 |")
    lines.append("|---|---|---|---|---|")
    for nm in ("textbook-restart", "textbook-sweep"):
        b = ex["baseline"][nm]
        lines.append(f"| {nm} | {b['vec_cmp']} | {b['full']} | {b['executed']} | {b['vec_add']} |")
    lines.append("")
    a = ex["alt_p7_e"]
    lines.append(f"표 III의 P7 행은 Needed allocation의 E칸이 5로 인쇄됐다(표 II와 Maximum − Allocation은 0, 표 IV의 P7 행은 0). "
                 f"이 값을 5로 읽고 재구현에 넣으면 {'안전 순서가 같다' if a['safe_same'] else '불안전으로 판정된다' if a['unsafe'] else '안전 순서가 달라진다'}"
                 f"(비교 수 {'같음' if a['cmp_same'] else '다름'}). 재구현은 표 II의 값(0)을 썼다.\n")
    lines.append("## 2. DBDAA 논문의 표 8에서 이 논문의 알고리즘('Momotaz et al.' [4]) 열\n")
    lines.append("DBDAA 논문(Zohora 외 2024)은 이 논문을 'Momotaz et al. [4]'라고 부르고, 자기 입력(표 2–4)에 대해 10회, 불안전, 불안전이라고 적는다. "
                 "같은 입력(옮긴 표)을 재구현에 넣어 비교한다. 아래 '실패한 프로세스' 이하는 재현 결과에서 읽은 관찰이다.\n")
    lines.append("| DBDAA 예제 | 표 8의 열 | 재구현 판정 | 논문 단위 비교 | 안전 순서 길이 | 실패한 프로세스(정렬 순서에서 처음 실행 불가) | 그 프로세스의 Need | 그 시점 Available | DBDAA 본문의 교재식 순서가 되짚어지는가 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    want8 = D.TABLE_8["Momotaz et al. 2020 [4]"]
    for k, case in enumerate(("best", "average", "worst")):
        r = dd[case]
        row = r["fail_row"]
        lines.append(f"| {case} | {want8[k]} | {'불안전' if r['unsafe'] else '안전'} | {r['paper_cmp']} | {r['safe_len']} | {r['fail'] or '—'} | "
                     f"{r['need_fail'] if r['fail'] else '—'} | {row['avail'] if row else '—'} | {'예' if r['baseline_replays'] else '아니오'} |")
    lines.append("")
    lines.append(f"표 3(average)의 P4 행은 Need R5가 4로 인쇄됐다(Maximum − Allocation은 5). 5로 읽어도 이 알고리즘의 판정은 같다"
                 f"(불안전, 실패한 프로세스 {dd['average']['alt_need_fail']}).\n")
    lines.append("DBDAA 논문 표 8의 열이 이 알고리즘의 단일 훑기·즉시 반환 읽기와 같은 결과를 내는 것을 확인했다. "
                 "average와 worst 입력에서 'DBDAA 본문의 교재식 순서가 되짚어진다'는 것은 그 입력의 상태에 안전 순서가 있다는 뜻이다"
                 "(DBDAA 논문 표 8이 쓴 '불안전'은 이 알고리즘이 안전 순서를 찾지 못했다는 뜻이다). 이 재현은 문헌의 보고를 재현한 것이며 오라클과의 비교가 아니다.\n")
    d = info["diff"]
    lines.append("## 3. 두 번째 독립 구현과의 차등\n")
    lines.append("순서도 그림 1의 노드를 그대로 옮긴 기계(`literal_begum`)와 비교한다. 비교 항목은 안전 순서, 불안전 판정, 실패한 프로세스, 실패 사유, "
                 "계측한 모든 횟수(논문 단위, 빠른 검사, 자원별, 입장, 최대 Need, Minimum available, 덧셈, 반복, 기수 훑기 수, 전체 스칼라)다. "
                 f"입력은 문헌 예제 4개, 소규모 전수 일부, 층화 무작위(F-rand형) 일부, 경계 상태, 값이 큰 무작위 상태(여러 자릿수·입장 검사 위반 포함) {d['states']:,}개다. "
                 f"불일치 {d['bad']}건. 시간 {d['seconds']:.1f}초.\n")
    lines.append("차등 입력이 코드의 분기를 지나갔는지(비공허성)를 입력에 적용된 횟수로 본다.\n")
    lines.append("| 분기 | 입력 수 |")
    lines.append("|---|---|")
    for k, v in d["cov"].items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("## 4. 속성과 변이체\n")
    lines.append(f"속성은 {info['prop_states']}개 입력에서 본다.\n")
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
        lines += [f"- {x}" for x in L.fails[:60]]
        lines.append("")
    lines.append("## 범위와 한계\n")
    lines.append("- 이 점검은 '구현이 논문의 서술(의사코드, 순서도, 예제)을 옮긴 해석과 같다'는 것과 '논문 예제를 재현한다'는 것만 본다. 해석이 논문의 뜻과 같다는 보장은 없다(docs/rq6/variants.md의 해석 목록).")
    lines.append("- 두 번째 구현은 같은 사람이 같은 이해로 쓴 것이다. 구조가 달라 옮기다 생기는 실수는 잡지만 해석의 오류는 잡지 못한다.")
    lines.append("- 순서도의 'j == d' 판정은 문자 그대로 읽으면 모순이다(docs/rq6/variants.md §3). 변이체 'last-res-ok'는 그 한 가지 문자 그대로의 읽기를 나타내며, 점검이 그 읽기와 해석을 구별함을 보인다.")
    lines.append("- 논문의 예제는 자원별 검사(4단계의 else 가지)를 한 번도 쓰지 않는다. 그래서 예제 재현은 그 가지를 점검하지 못한다. 그 가지는 차등과 속성이 본다.")
    lines.append("- 오라클(O1)과의 비교와 등록된 입력군 위의 비용·시간은 동결 전에 하지 않았다. 판정의 건전성(안전이라 한 것은 안전 순서가 있다)은 되짚기로 보였고 오라클을 쓰지 않았다.")
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
