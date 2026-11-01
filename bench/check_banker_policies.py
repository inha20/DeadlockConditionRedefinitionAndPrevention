"""교재식 기준 구현의 소규모 전수 차등 테스트와 속성 점검 (prereg/README.md SP-5의 ②③, WP6.2).
실행: python3 -I bench/check_banker_policies.py formal/rq6/policies-diff-results.md   (약 5분)

대조 대상은 정확 오라클 O1(`oracle/banker.py`)이다. 범위는 오라클 자체 검증(`oracle/check_banker.py`)과 같은 9개 소규모 범위다.
  1. 안전성 판정: 두 교재식 구현과 numpy 닫힘(`safe_fast`)이 O1과 모든 상태에서 같은가(FU, FS 개수)
  2. 요청 판정: 범위 안 요청 전부와 ERROR·WAIT 탐침이 O1의 `request_outcome`과 같은가, 호출 뒤 상태가 그대로인가
  3. 속성: 벡터 비교 횟수 <= n(n+1)/2, 벡터 덧셈 횟수 = 끝낸 프로세스 수 = n − |끝낼 수 없는 집합(O1)|, is_safe는 상태를 바꾸지 않음,
     GRANT이면 요청 전 상태가 안전
  4. 전 요청 공간: 작은 범위에서 0 <= req <= 총량인 모든 벡터(영벡터 포함)
  5. 변이체 검출: 같은 점검이 고의로 틀린 정책을 잡는가(비공허)
  6. O1 크기·시간 한계표: 중간·큰 크기에서 O1과 numpy 닫힘, 교재식 구현이 같은 판정을 내는가와 걸리는 시간
AI(Claude)가 쓴 초안이며 사람의 검토 전이다. 증명이 아니라 반례 탐색이다.
"""
from __future__ import annotations

import itertools
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "oracle"))

import oracle.banker as ob  # noqa: E402
from bench import gen_banker as G  # noqa: E402
from bench.ops import CountingOps, PlainOps  # noqa: E402
from bench.policies.banker import mutants as MU  # noqa: E402
from bench.policies.banker.base import DENY, ERROR, GRANT, WAIT  # noqa: E402
from bench.policies.banker.textbook import TextbookRestart, TextbookSweep  # noqa: E402
from bench.state import BState  # noqa: E402

# (프로세스 수, 총량, 요청 점검 간격). oracle/check_banker.py의 RANGES와 같게 둔다.
RANGES = [(3, (1, 1), 1), (3, (2, 2), 1), (3, (1, 1, 1), 1), (3, (3, 2), 1), (4, (1, 1), 1), (4, (2, 1), 1),
          (4, (1, 1, 1), 2), (2, (3, 3, 3), 10), (5, (1, 1), 1)]
# 전 요청 공간(영벡터 포함)을 보는 범위와 간격
FULL_SPACE = [(3, (1, 1), 1), (3, (1, 1, 1), 1), (4, (1, 1), 1), (5, (1, 1), 1), (3, (2, 2), 3)]


def snap(st: BState):
    return (tuple(map(tuple, st.alloc)), tuple(map(tuple, st.need)), tuple(st.avail))


def probes(b: "ob.Banker", i: int):
    """범위 안 요청 전부(영벡터 제외) + ERROR 탐침 + WAIT 탐침."""
    need, avail = b.need(), b.avail()
    yield from ob.request_vectors(b, i)
    yield tuple(need[i][r] + (1 if r == 0 else 0) for r in range(b.m))                 # ERROR
    for r in range(b.m):                                                                  # WAIT
        if avail[r] < need[i][r]:
            yield tuple(avail[r] + 1 if q == r else 0 for q in range(b.m))
            break


def new_stats() -> dict:
    return {"states": 0, "safe": 0, "unsafe": 0, "fu": 0, "fs": 0, "fast_bad": 0, "bound_bad": 0, "add_bad": 0,
            "mut_bad": 0, "max_vec": 0, "bound_hit": 0, "req": 0, "req_bad": 0, "restore_bad": 0, "grant_unsafe_bad": 0,
            "outcomes": {ERROR: 0, WAIT: 0, GRANT: 0, DENY: 0}, "req_mismatch": {}}


def check_state(P, st: BState, b: "ob.Banker", truth: bool, stuck: int, S: dict, bound: int) -> None:
    before = snap(st)
    ops = CountingOps()
    got = P.is_safe(st, ops)
    if got != truth:
        S["fu" if truth else "fs"] += 1
    if snap(st) != before:
        S["mut_bad"] += 1
    if ops.vec_cmp > bound:
        S["bound_bad"] += 1
    if ops.vec_cmp == bound:
        S["bound_hit"] += 1
    S["max_vec"] = max(S["max_vec"], ops.vec_cmp)
    if ops.vec_add != st.n - stuck:
        S["add_bad"] += 1


def check_requests(P, st: BState, b: "ob.Banker", truth_safe: bool, S: dict, vectors_for) -> None:
    for i in range(b.n):
        for req in vectors_for(b, i):
            want = ob.request_outcome(b, i, req)
            before = snap(st)
            got = P.request(st, i, list(req), PlainOps())
            S["req"] += 1
            S["outcomes"][want] += 1
            if got != want:
                S["req_bad"] += 1
                k = f"{want}→{got}"
                S["req_mismatch"][k] = S["req_mismatch"].get(k, 0) + 1
            if snap(st) != before:
                S["restore_bad"] += 1
            if got == GRANT and not truth_safe:
                S["grant_unsafe_bad"] += 1


def run_range(policies, n: int, total, stride: int, full_space: bool = False) -> dict:
    t0 = time.time()
    per = {P.name: new_stats() for P in policies}
    fast = {"bad": 0}
    bound = n * (n + 1) // 2
    cnt = 0
    for k, b in enumerate(ob.all_states(n, total)):
        st = BState.from_oracle(b)
        truth = ob.safe_oracle(b)
        stuck = len(ob.unfinishable(b))
        if (stuck == 0) != truth:
            raise RuntimeError("오라클 내부 불일치(unfinishable과 safe_oracle)")
        cnt += 1
        if G.safe_fast(st) != truth:
            fast["bad"] += 1
        for P in policies:
            S = per[P.name]
            S["states"] += 1
            S["safe" if truth else "unsafe"] += 1
            check_state(P, st, b, truth, stuck, S, bound)
            if k % stride == 0:
                if full_space:
                    def vectors_for(b_, i_, _t=total):
                        return itertools.product(*[range(t + 1) for t in _t])
                else:
                    vectors_for = probes
                check_requests(P, st, b, truth, S, vectors_for)
    return {"n": n, "total": total, "stride": stride, "states": cnt, "per": per, "fast": fast, "seconds": time.time() - t0}


def mutant_detection(n: int, total) -> list[tuple[str, int, int, int]]:
    """변이체마다 (이름, FU, FS, 요청 불일치+복원 실패)를 돌려준다."""
    out = []
    for name, cls in MU.MUTANTS.items():
        P = cls()
        S = new_stats()
        bound = n * (n + 1) // 2
        for k, b in enumerate(ob.all_states(n, total)):
            st = BState.from_oracle(b)
            truth = ob.safe_oracle(b)
            stuck = len(ob.unfinishable(b))
            check_state(P, st, b, truth, stuck, S, bound)
            if k % 5 == 0:
                check_requests(P, st, b, truth, S, probes)
        out.append((name, S["fu"], S["fs"], S["req_bad"] + S["restore_bad"] + S["mut_bad"]))
    return out


def limits_table(master: int = 91) -> list[dict]:
    """O1과 numpy 닫힘, 교재식 두 구현을 중간·큰 크기에서 대조하고 시간을 잰다. 한 크기에 최대 4개를 본다."""
    rows = []
    plan = [("F-rand", 64, 8), ("F-rand", 256, 8), ("F-rand", 1024, 32), ("F-rand", 4096, 64), ("F-rand", 4096, 256),
            ("chain-last", 64, 8), ("chain-last", 256, 8), ("chain-last", 1024, 8), ("chain-last", 4096, 8),
            ("chain-unsafe-last", 1024, 8)]
    pols = [TextbookRestart(), TextbookSweep()]
    for fam, n, m in plan:
        if fam == "F-rand":
            insts, summ = G.sample_cell(master, f"lim-{n}-{m}", n, m, 4, 0.5, max_attempts_factor=50)
            states = [d["state"] for d in insts]
        else:
            states = [G.worst_case(n, m, fam)]
        t_o1 = t_fast = 0.0
        t_pol = {P.name: 0.0 for P in pols}
        agree = True
        for st in states:
            b = st.to_oracle()
            t = time.perf_counter()
            v = ob.safe_oracle(b)
            t_o1 += time.perf_counter() - t
            t = time.perf_counter()
            f = G.safe_fast(st)
            t_fast += time.perf_counter() - t
            agree &= (v == f)
            if n <= 1024 or fam == "F-rand":
                for P in pols:
                    t = time.perf_counter()
                    r = P.is_safe(st, PlainOps())
                    t_pol[P.name] += time.perf_counter() - t
                    agree &= (r == v)
            else:
                t_pol = {k: float("nan") for k in t_pol}
        k = max(1, len(states))
        rows.append({"fam": fam, "n": n, "m": m, "k": len(states), "o1": t_o1 / k, "fast": t_fast / k,
                     "restart": t_pol["textbook-restart"] / k, "sweep": t_pol["textbook-sweep"] / k, "agree": agree})
    return rows


def main(out_path: str | None) -> int:
    t_all = time.time()
    policies = [TextbookRestart(), TextbookSweep()]
    lines = ["# 교재식 기준 구현의 소규모 전수 차등 테스트 결과\n",
             "`bench/check_banker_policies.py`가 쓴 결과다. AI(Claude)가 작성한 초안이며 사람의 검토 전이다. "
             "정확 오라클 O1과의 대조이고, 증명이 아니라 소규모 범위의 반례 탐색이다. 같은 정의를 다른 코드로 계산한 값끼리의 일치이며 "
             "문헌의 안전 상태 정의와 같다는 뜻이 아니다.\n"]
    fails = 0

    lines.append("## 1. 안전성 판정과 속성 (오라클: `safe_oracle`)\n")
    lines.append("FU = 오라클 안전인데 구현 불안전, FS = 오라클 불안전인데 구현 안전. 속성 위반은 벡터 비교 횟수가 n(n+1)/2를 넘음, "
                 "벡터 덧셈 횟수가 끝낸 프로세스 수(n − O1의 끝낼 수 없는 집합 크기)와 다름, is_safe가 상태를 바꿈의 합이다.\n")
    lines.append("| 프로세스 수 | 총량 | 상태 수 | 안전 | 불안전 | 구현 | FU | FS | numpy 닫힘 불일치 | 속성 위반 | 벡터 비교 최대 | 상한 n(n+1)/2 | 시간(초) |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    req_rows = []
    for n, total, stride in RANGES:
        res = run_range(policies, n, total, stride)
        for P in policies:
            S = res["per"][P.name]
            prop = S["bound_bad"] + S["add_bad"] + S["mut_bad"]
            fails += S["fu"] + S["fs"] + prop
            lines.append(f"| {n} | {list(total)} | {res['states']:,} | {S['safe']:,} | {S['unsafe']:,} | {P.name} | {S['fu']} | {S['fs']} | "
                         f"{res['fast']['bad']} | {prop} | {S['max_vec']} | {n * (n + 1) // 2} | {res['seconds']:.1f} |")
            req_rows.append((n, total, stride, P.name, S))
        fails += res["fast"]["bad"]
        print(f"[안전성] n={n} total={total} 상태 {res['states']:,} {res['seconds']:.1f}초", flush=True)
    lines.append("")

    lines.append("## 2. 요청 판정 (오라클: `request_outcome`)\n")
    lines.append("범위 안 요청 전부(영벡터 제외)와 ERROR·WAIT 탐침을 본다. '요청 전 상태 불안전인데 GRANT'는 오라클의 성질"
                 "(허가 뒤 안전이면 허가 전도 안전)이 구현에서도 지켜지는지 보는 것이다.\n")
    lines.append("| 프로세스 수 | 총량 | 간격 | 구현 | 요청 수 | ERROR | WAIT | GRANT | DENY | 불일치 | 상태 복원 실패 | 불안전 상태에서 GRANT |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for n, total, stride, name, S in req_rows:
        o = S["outcomes"]
        fails += S["req_bad"] + S["restore_bad"] + S["grant_unsafe_bad"]
        lines.append(f"| {n} | {list(total)} | {stride} | {name} | {S['req']:,} | {o[ERROR]:,} | {o[WAIT]:,} | {o[GRANT]:,} | {o[DENY]:,} | "
                     f"{S['req_bad']} | {S['restore_bad']} | {S['grant_unsafe_bad']} |")
    lines.append("")

    lines.append("## 3. 전 요청 공간 (영벡터 포함, 0 <= req <= 총량인 모든 벡터)\n")
    lines.append("| 프로세스 수 | 총량 | 간격 | 구현 | 요청 수 | ERROR | WAIT | GRANT | DENY | 불일치 | 상태 복원 실패 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for n, total, stride in FULL_SPACE:
        res = run_range(policies, n, total, stride, full_space=True)
        for P in policies:
            S = res["per"][P.name]
            o = S["outcomes"]
            fails += S["req_bad"] + S["restore_bad"] + S["grant_unsafe_bad"] + S["fu"] + S["fs"]
            lines.append(f"| {n} | {list(total)} | {stride} | {P.name} | {S['req']:,} | {o[ERROR]:,} | {o[WAIT]:,} | {o[GRANT]:,} | {o[DENY]:,} | "
                         f"{S['req_bad']} | {S['restore_bad']} |")
        print(f"[전 요청 공간] n={n} total={total} {res['seconds']:.1f}초", flush=True)
    lines.append("")

    lines.append("## 4. 변이체 검출 (점검의 비공허성)\n")
    lines.append("n = 3, 총량 [2, 2]의 모든 상태에서 같은 점검을 변이체에 적용한다. 0이 아니어야 잡힌 것이다(`mut-no-restore`는 요청 뒤 상태 복원 실패로 잡힌다).\n")
    lines.append("| 변이체 | FU | FS | 요청 불일치·복원 실패·상태 변경 | 검출 |")
    lines.append("|---|---|---|---|---|")
    for name, fu, fs, other in mutant_detection(3, (2, 2)):
        caught = (fu + fs + other) > 0
        fails += 0 if caught else 1
        lines.append(f"| {name} | {fu:,} | {fs:,} | {other:,} | {'검출' if caught else '**놓침**'} |")
    lines.append("")

    lines.append("## 5. O1 크기·시간 한계표 (SI-2)\n")
    lines.append("중간·큰 크기에서 O1(`safe_oracle`, SM 축소)과 numpy 닫힘, 교재식 두 구현의 판정이 같은가와 호출당 평균 시간. "
                 "F-rand는 층화 표집(목표 안전 비율 0.5)한 최대 4개, chain-*는 최악 입력 하나다. 시간은 공유 가상 환경(코어 2개)의 값이라 크기에 따른 증가만 본다. "
                 "'—'는 시간이 길어 재지 않은 칸이다.\n")
    lines.append("| 입력군 | n | m | 입력 수 | O1 (ms) | numpy 닫힘 (ms) | Restart (ms) | Sweep (ms) | 판정 일치 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in limits_table():
        fails += 0 if r["agree"] else 1

        def ms(x):
            return "—" if x != x else f"{x * 1000:.1f}"
        lines.append(f"| {r['fam']} | {r['n']} | {r['m']} | {r['k']} | {ms(r['o1'])} | {ms(r['fast'])} | {ms(r['restart'])} | {ms(r['sweep'])} | "
                     f"{'일치' if r['agree'] else '**불일치**'} |")
        print(f"[한계표] {r['fam']} n={r['n']} m={r['m']}", flush=True)
    lines.append("")

    lines.append(f"전체 위반·실패: {fails}건. 총 시간 {time.time() - t_all:.0f}초.\n")
    lines.append("## 범위와 한계\n")
    lines.append("- 오라클 자체 검증(`formal/rq6/o1-check-results.md`)과 같은 9개 범위의 모든 상태를 본다. 요청은 범위 안 전부와 탐침이고, 큰 범위는 간격을 둔다.")
    lines.append("- 소규모 범위의 일치는 큰 입력에서의 일치를 보장하지 않는다. 큰 입력은 5절의 표본 대조와 동결 뒤 본 실행의 오라클 대조가 맡는다.")
    lines.append("- 교재식 구현이 오라클과 같다는 것은 '같은 정의의 두 계산이 같다'는 뜻이다. 교재 쪽 번호와 문구는 확인하지 못했다(수준 X).")
    text = "\n".join(lines) + "\n"
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
    print(f"전체 위반·실패 {fails}건, {time.time() - t_all:.0f}초")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
