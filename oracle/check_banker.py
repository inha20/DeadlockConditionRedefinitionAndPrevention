#!/usr/bin/env python3
"""뱅커 오라클 O1의 소규모 전수 자체 검증.

사용법: python3 -I check_banker.py [결과를 쓸 마크다운 경로]

검사하는 것(통과해도 증명이 아니라 소규모 범위의 반례 탐색이다):
  1. 세 구현(safe_oracle, safe_perm, safe_dp)의 안전·불안전 판정이 모든 상태에서 같다.
  2. 안전이면 safe_perm이 준 순서가 실제 안전 순서다. 불안전이면 끝낼 수 없는 집합(s_max의 가장 큰 교착
     집합)이 비어 있지 않고, 반복 폐포(closure)로 따로 구한 끝낼 수 있는 집합의 여집합과 같다.
  3. 요청 판정: 가용량과 필요량 안의 모든 영이 아닌 요청 벡터에서 GRANT <=> 허가 뒤 상태가 safe_perm으로 안전,
     처음 상태가 불안전이면 GRANT는 없다(허가 뒤 안전하면 처음도 안전하다는 단조성).
  4. 일부러 틀리게 만든 판정(엄격 부등호, need 대신 max)을 같은 검사가 잡는지(검사가 비어 있지 않다는 확인).
  5. 널리 쓰이는 교재 예제 하나(출처 쪽수는 확인하지 못했다. 수준 X, 구현 점검용이며 근거로 쓰지 않는다).
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import banker as bk  # noqa: E402
import sm  # noqa: E402
from banker import Banker  # noqa: E402

# (프로세스 수, 총량, 요청 점검 간격). 판정 점검은 모든 상태에서 하고, 요청 점검은 간격번째 상태마다 한다
# (간격 1이면 모든 상태). 상태가 많은 범위에서 시간을 줄이려는 것이며 간격은 결과에 함께 적는다.
RANGES = [
    (3, (1, 1), 1),
    (3, (2, 2), 1),
    (3, (1, 1, 1), 1),
    (3, (3, 2), 1),
    (4, (1, 1), 1),
    (4, (2, 1), 1),
    (4, (1, 1, 1), 2),
    (2, (3, 3, 3), 10),
    (5, (1, 1), 1),
]


def closure_finishable(b: Banker) -> frozenset:
    """반복 폐포. 끝낼 수 있는 프로세스를 하나씩 끝내며 가용량을 늘리는 것을 더 못 할 때까지 한다."""
    need, alloc, m = b.need(), b.alloc, b.m
    work = list(b.avail())
    done: set[int] = set()
    changed = True
    while changed:
        changed = False
        for p in range(b.n):
            if p not in done and all(need[p][r] <= work[r] for r in range(m)):
                done.add(p)
                for r in range(m):
                    work[r] += alloc[p][r]
                changed = True
    return frozenset(done)


def check_state(b: Banker, stats: dict, violations: list, with_requests: bool = True) -> None:
    so = bk.safe_oracle(b)
    sp, order = bk.safe_perm(b)
    sd = bk.safe_dp(b)
    stats["states"] += 1
    stats["safe" if so else "unsafe"] += 1
    if not (so == sp == sd):
        violations.append(("판정 불일치", bk.show(b), so, sp, sd))
        return
    unf = bk.unfinishable(b)
    fin = closure_finishable(b)
    if so:
        if not bk.check_order(b, order):
            violations.append(("안전 순서가 아님", bk.show(b), order))
        if unf:
            violations.append(("안전인데 끝낼 수 없는 집합이 있음", bk.show(b), unf))
    else:
        if not unf:
            violations.append(("불안전인데 끝낼 수 없는 집합이 없음", bk.show(b)))
        if unf != frozenset(range(b.n)) - fin:
            violations.append(("끝낼 수 없는 집합과 폐포의 여집합이 다름", bk.show(b), unf, fin))
    if not with_requests:
        return
    for i in range(b.n):
        for req in bk.request_vectors(b, i):
            out = bk.request_outcome(b, i, req)
            stats["requests"] += 1
            post = bk.apply_request(b, i, req)
            post_safe = bk.safe_perm(post)[0]
            if out not in (bk.GRANT, bk.DENY):
                violations.append(("가용량·필요량 안의 요청이 GRANT/DENY가 아님", bk.show(b), i, req, out))
                continue
            stats["grant" if out == bk.GRANT else "deny"] += 1
            if (out == bk.GRANT) != post_safe:
                violations.append(("GRANT와 허가 뒤 안전이 다름", bk.show(b), i, req, out, post_safe))
            if out == bk.GRANT and not so:
                violations.append(("불안전 상태에서 GRANT", bk.show(b), i, req))
    # 경계: 필요량 초과는 ERROR, 가용량 초과는 WAIT (요청 벡터 하나씩만 점검)
    need, avail = b.need(), b.avail()
    for i in range(b.n):
        for r in range(b.m):
            if need[i][r] < b.total[r]:
                req = tuple((need[i][r] + 1) if q == r else 0 for q in range(b.m))
                if bk.request_outcome(b, i, req) != bk.ERROR:
                    violations.append(("필요량 초과가 ERROR가 아님", bk.show(b), i, req))
            elif avail[r] < need[i][r]:
                req = tuple((avail[r] + 1) if q == r else 0 for q in range(b.m))
                if bk.request_outcome(b, i, req) != bk.WAIT:
                    violations.append(("가용량 초과가 WAIT가 아님", bk.show(b), i, req))


def run_range(n: int, total: tuple, stride: int = 1) -> dict:
    stats = {"states": 0, "safe": 0, "unsafe": 0, "requests": 0, "grant": 0, "deny": 0}
    violations: list = []
    t0 = time.time()
    for idx, b in enumerate(bk.all_states(n, total)):
        check_state(b, stats, violations, with_requests=(idx % stride == 0))
    stats["violations"] = len(violations)
    stats["examples"] = violations[:3]
    stats["seconds"] = time.time() - t0
    return stats


# ---------------------------------------------------------------- 일부러 틀리게 한 판정(검사가 비어 있지 않은지)

def mutation_detected(name: str, n: int, total: tuple) -> bool:
    """name의 오류를 심고 같은 검사를 돌려 위반이 나오는지 본다. 끝나면 원래대로 되돌린다."""
    orig_sat, orig_to_sm = sm.sat, bk.to_sm
    try:
        if name == "strict":  # a <= F 대신 a < F
            def sat_strict(alts, F):
                if not alts:
                    return True
                return any(all(a[r] < F[r] for r in range(len(F))) for a in alts)
            sm.sat = sat_strict
        elif name == "max_not_need":  # need 대신 max를 요청으로 둔다
            def to_sm_max(b):
                alts = tuple(frozenset({b.maxc[p]}) if any(b.maxc[p]) else frozenset() for p in range(b.n))
                return sm.Inst(cap=b.total, alloc=b.alloc, alts=alts)
            bk.to_sm = to_sm_max
        elif name == "ignore_free":  # 가용량을 0으로 본다
            def to_sm_nofree(b):
                inst = orig_to_sm(b)
                return sm.Inst(cap=tuple(sum(a[r] for a in b.alloc) for r in range(b.m)), alloc=inst.alloc, alts=inst.alts)
            bk.to_sm = to_sm_nofree
        else:
            raise ValueError(name)
        stats = {"states": 0, "safe": 0, "unsafe": 0, "requests": 0, "grant": 0, "deny": 0}
        violations: list = []
        for b in bk.all_states(n, total):
            check_state(b, stats, violations, with_requests=False)
            if violations:
                return True
        return False
    finally:
        sm.sat, bk.to_sm = orig_sat, orig_to_sm


# ---------------------------------------------------------------- 교재 예제

def textbook_example() -> list[tuple[str, bool]]:
    """널리 쓰이는 5개 프로세스, 3개 종류 예제. 출처 쪽수는 확인하지 못했고 구현 점검용이다."""
    b = Banker(
        total=(10, 5, 7),
        alloc=((0, 1, 0), (2, 0, 0), (3, 0, 2), (2, 1, 1), (0, 0, 2)),
        maxc=((7, 5, 3), (3, 2, 2), (9, 0, 2), (2, 2, 2), (4, 3, 3)),
    )
    out = []
    out.append(("처음 상태의 가용량이 (3,3,2)", b.avail() == (3, 3, 2)))
    out.append(("처음 상태가 안전", bk.safe_oracle(b) and bk.safe_perm(b)[0] and bk.safe_dp(b)))
    out.append(("순서 <P1,P3,P4,P0,P2>가 안전 순서", bk.check_order(b, (1, 3, 4, 0, 2))))
    out.append(("P1의 요청 (1,0,2)는 GRANT", bk.request_outcome(b, 1, (1, 0, 2)) == bk.GRANT))
    b2 = bk.apply_request(b, 1, (1, 0, 2))
    out.append(("그 뒤 P4의 요청 (3,3,0)은 WAIT(가용량 부족)", bk.request_outcome(b2, 4, (3, 3, 0)) == bk.WAIT))
    out.append(("그 뒤 P0의 요청 (0,2,0)은 DENY(허가하면 불안전)", bk.request_outcome(b2, 0, (0, 2, 0)) == bk.DENY))
    return out


def main(out_path: str | None) -> int:
    t0 = time.time()
    lines = []
    lines.append("# 뱅커 오라클 O1 소규모 전수 검증 결과\n")
    lines.append("`oracle/check_banker.py`가 쓴 결과다. AI(Claude)가 작성한 초안이며 사람의 검토 전이다. 증명이 아니라 소규모 범위의 반례 탐색이다.\n")
    bad_total = 0

    lines.append("## 교재 예제(구현 점검용)\n")
    lines.append("| 점검 | 결과 |\n|---|---|")
    for name, ok in textbook_example():
        lines.append(f"| {name} | {'통과' if ok else '**실패**'} |")
        bad_total += 0 if ok else 1
    lines.append("")

    lines.append("## 전수 범위\n")
    lines.append("| 프로세스 수 | 총량 | 상태 수 | 안전 | 불안전 | 요청 점검 간격 | 요청 점검 | GRANT | DENY | 위반 | 시간(초) |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    examples = []
    for n, total, stride in RANGES:
        st = run_range(n, total, stride)
        bad_total += st["violations"]
        lines.append(
            f"| {n} | {list(total)} | {st['states']:,} | {st['safe']:,} | {st['unsafe']:,} | {stride} | {st['requests']:,} | "
            f"{st['grant']:,} | {st['deny']:,} | {st['violations']} | {st['seconds']:.1f} |"
        )
        examples += st["examples"]
        print(f"n={n} total={total} states={st['states']} violations={st['violations']} {st['seconds']:.1f}s", flush=True)
    lines.append("")
    if examples:
        lines.append("### 위반 예시\n")
        for ex in examples[:5]:
            lines.append("```\n" + repr(ex) + "\n```")

    lines.append("## 일부러 넣은 오류(검사가 잡는지)\n")
    lines.append("| 오류 | 범위 | 검출 |\n|---|---|---|")
    for name, (n, total) in [("strict", (3, (2, 2))), ("max_not_need", (3, (2, 2))), ("ignore_free", (3, (2, 2)))]:
        det = mutation_detected(name, n, total)
        label = {"strict": "만족 판정에 엄격 부등호", "max_not_need": "need 대신 max를 요청으로", "ignore_free": "가용량을 0으로 계산"}[name]
        lines.append(f"| {label} | n={n}, {list(total)} | {'검출' if det else '**놓침**'} |")
        bad_total += 0 if det else 1
    lines.append("")

    lines.append(f"전체 위반·실패: {bad_total}건. 총 시간 {time.time() - t0:.0f}초.\n")
    lines.append("## 범위와 한계\n")
    lines.append(
        "- 상태 수가 많은 범위는 프로세스 5개까지, 총량이 작은 값으로 한정했다. 이보다 큰 입력은 전수 검증하지 않았다.\n"
        "- 세 구현과 폐포가 같은 정의(모델 명세 A1–A4, 안전 = 모든 프로세스가 끝나는 순서의 존재)에서 나왔다. "
        "일치는 정의 내부의 일관성이다.\n"
        "- 단일 종류에서 F8의 동치(불안전 <=> 두 집단 분할 조건)와의 대조는 하지 않았다. F8 원문을 다시 확인한 뒤에 한다.\n"
        "- 교재 예제의 출처 쪽수는 확인하지 못했다(수준 X). 구현 점검에만 썼다.\n"
    )
    text = "\n".join(lines)
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
    print("TOTAL violations/failures:", bad_total)
    return 1 if bad_total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
