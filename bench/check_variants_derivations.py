"""문헌 변형 해석 문서(docs/rq6/variants.md)가 싣는 '도출'의 기계 확인. AI(Claude)가 쓴 초안이며 사람의 검토 전이다.
실행: python3 -I bench/check_variants_derivations.py formal/rq6/variants-derivations.md

도출은 AI가 손으로 만든 입력에서 이끌어 낸 서술이고, 여기서 하는 일은 그 서술이 코드와 맞는지 확인하는 것뿐이다.
이 입력들은 등록된 입력군(F-ex, F-rand, F-bound, F-lit)이 아니고, 이 파일의 숫자는 K1·K2·K3의 결과가 아니다.
오라클(O1)과 비교하지 않는다. '안전 순서가 있다'는 것은 순서를 되짚어서(Need <= Work를 단계마다 확인) 보인다.

확인하는 서술
  D1  Begum 알고리즘은 안전 상태를 불안전으로 판정할 수 있다(2프로세스·2자원의 최소 예).
  D2  D1을 일반화한 '역사슬' 입력(n개 프로세스, 정렬 순서와 반대로만 끝낼 수 있음): Begum은 첫 프로세스에서 불안전,
      dbdaa-cycle1은 한 프로세스만 통과, dbdaa-repeat는 정확히 n주기가 걸린다. 안전 순서는 있다(되짚기).
  D3  판정 동치: begum-return의 판정 = dbdaa-cycle1의 판정(안전 ⟺ 정렬 순서 전체가 안전 순서). 안전 순서는 begum의 것이 dbdaa-cycle1의 접두사.
      dbdaa-repeat가 안전이라고 하는 상태는 dbdaa-cycle1이 안전이라고 하는 상태를 포함한다.
  D4  DBDAA의 위치 동률 규칙(앞 자원/뒤 자원)은 판정과 통과 순서를 바꾸지 않고 비교 횟수만 바꿀 수 있다.
  D5  같은 최대 Need를 가진 프로세스의 정렬 순서(동률 규칙)는 단일 훑기 판정을 바꿀 수 있다(프로세스 번호만 바꿔도 판정이 바뀌는 예).
"""
from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "oracle"))

from bench.check_variants_begum import pool_states  # noqa: E402
from bench.ops import CountingOps  # noqa: E402
from bench.policies.banker.textbook import TextbookRestart, TextbookSweep  # noqa: E402
from bench.policies.banker.variants.begum2020 import BegumReturn  # noqa: E402
from bench.policies.banker.variants.zohora2024 import DBDAACycle1, DBDAARepeat  # noqa: E402
from bench.state import BState  # noqa: E402


class _Cycle1Last(DBDAACycle1):
    name = "dbdaa-cycle1-lasttie"
    loc_tie = "last"


class _Log:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.checks = 0

    def check(self, cond: bool, what: str) -> bool:
        self.checks += 1
        if not cond:
            self.fails.append(what)
        return bool(cond)


def replay(st: BState, seq: list[int]) -> bool:
    """seq를 순서대로 끝낼 수 있는가(각 단계에서 Need <= Work)."""
    work = list(st.avail)
    for p in seq:
        if not all(st.need[p][j] <= work[j] for j in range(st.m)):
            return False
        work = [work[j] + st.alloc[p][j] for j in range(st.m)]
    return True


def reverse_chain(n: int) -> BState:
    """자원 n종(각 총량 1), 프로세스 P_k는 자원 k를 1단위 더 청구하고 자원 k-1을 1단위 쥔다(P_0은 아무것도 쥐지 않음).
    가용량은 자원 n-1만 1이다. 끝낼 수 있는 순서는 P_{n-1}, P_{n-2}, …, P_0 하나뿐이다.
    모든 프로세스의 최대 Need가 1이라 정렬 순서는 번호 순(P_0, …, P_{n-1})이고, 안전 순서의 정반대다."""
    total = [1] * n
    alloc = [[0] * n for _ in range(n)]
    need = [[0] * n for _ in range(n)]
    for k in range(n):
        need[k][k] = 1
        if k >= 1:
            alloc[k][k - 1] = 1
    return BState.make(total, alloc, need)


def two_by_two() -> BState:
    """D1의 최소 예. 자원 총량 (3, 5). P1은 (3, 0)을 쥐고 (0, 5)를 더 청구, P2는 아무것도 쥐지 않고 (3, 0)을 청구. Available (0, 5)."""
    return BState.make([3, 5], [[3, 0], [0, 0]], [[0, 5], [3, 0]])


def main(out_path: str | None) -> int:
    t0 = time.time()
    L = _Log()
    lines = ["# 해석 문서의 도출 확인 (Begum, DBDAA)\n",
             "`bench/check_variants_derivations.py`가 쓴 결과다. AI(Claude)가 작성한 초안이며 사람의 검토 전이다. "
             "도출은 AI가 손으로 만든 입력에서 이끌어 낸 서술이고 이 파일은 서술이 코드와 맞는지만 확인한다. "
             "입력은 등록된 입력군이 아니고, 아래 숫자는 K1·K2·K3의 결과가 아니다. 오라클과 비교하지 않았다.\n"]

    # ---- D1
    st = two_by_two()
    r = BegumReturn().run(st, CountingOps(), want_trace=True)
    seq = [0, 1]                                    # 인덱스 0 = P1, 1 = P2. 안전 순서는 P1, P2
    L.check(st.avail == [0, 5], f"D1: Available {st.avail}")
    L.check(max(st.need[0]) == 5 and max(st.need[1]) == 3, "D1: 최대 Need가 5와 3이 아님")
    L.check(replay(st, seq), "D1: 순서 P1, P2가 되짚어지지 않음")
    L.check(r.unsafe and r.fail_at == 1 and r.safe == [], f"D1: begum-return이 첫 프로세스(P2)에서 불안전이 아님: {r.unsafe} {r.fail_at} {r.safe}")
    lines.append("## D1. Begum 알고리즘은 안전 상태를 불안전으로 판정할 수 있다\n")
    lines.append("입력(프로세스 P1, P2 / 자원 두 종류): 총량 (3, 5). P1은 (3, 0)을 쥐고 (0, 5)를 더 청구한다(최대 청구 (3, 5)). "
                 "P2는 아무것도 쥐지 않고 (3, 0)을 더 청구한다(최대 청구 (3, 0)). Available = (0, 5).\n")
    lines.append(f"- 최대 Need는 P1이 5, P2가 3이라 정렬 순서는 P2, P1이다.")
    lines.append(f"- begum-return: P2를 먼저 본다. 빠른 검사 3 ≤ Minimum available 0이 거짓이고 자원별 검사의 첫 자원에서 3 > 0이라 불안전을 돌려준다"
                 f"(비교 {r.counts['paper_cmp']}회, 안전 순서 길이 {len(r.safe)}).")
    lines.append("- 순서 P1, P2를 되짚으면 P1의 Need (0, 5) ≤ Work (0, 5), 끝낸 뒤 Work (3, 5), P2의 Need (3, 0) ≤ Work. 즉 이 상태에는 안전 순서가 있다.")
    lines.append("- 그러므로 begum-return의 불안전 판정은 이 상태에서 틀린 불안전(안전 상태를 불안전이라 함)이다. 같은 판정은 정렬 순서가 안전 순서와 다른 모든 안전 상태에서 나온다. "
                 "이것은 이 저장소의 읽기(단일 훑기, 처음 실행 불가에서 즉시 반환)에서의 도출이다. 논문 본문도 순서를 한 번 이상 확인할 필요가 없다고 쓴다. "
                 "문헌 쪽 증거: DBDAA 논문이 표 8에서 같은 알고리즘을 자기 입력 두 개에서 불안전이라 보고하고 이를 오류라고 쓴다(같은 입력에서 재현은 variants-check-begum.md §2).\n")

    # ---- D2
    lines.append("## D2. 역사슬 입력\n")
    lines.append("자원 n종(총량 각 1), P_k는 자원 k를 1단위 더 청구하고 자원 k−1을 1단위 쥔다(P_0은 아무것도 쥐지 않음). Available은 자원 n−1만 1이다. "
                 "끝낼 수 있는 순서는 P_{n−1}, …, P_0 하나뿐이고 모든 최대 Need가 1이라 정렬 순서는 번호 순이다(안전 순서의 정반대). "
                 "손으로 만든 입력이며 등록된 입력군(F-bound 등)이 아니다.\n")
    lines.append("| n | 안전 순서가 있음(되짚기) | begum-return | dbdaa-cycle1: 통과 수 | dbdaa-repeat: 주기 수 | dbdaa-repeat: 모두 통과 | dbdaa-repeat 논문 단위 비교 | 교재식 Restart 벡터 비교 | 교재식 Sweep 벡터 비교 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for n in range(2, 9):
        st = reverse_chain(n)
        rev = list(range(n - 1, -1, -1))
        ok_replay = replay(st, rev)
        L.check(ok_replay, f"D2 n={n}: 역순이 되짚어지지 않음")
        L.check(all(not replay(st, [p] + [q for q in range(n) if q != p]) for p in range(n - 1)), f"D2 n={n}: P_{n - 1} 외에 먼저 끝낼 수 있는 프로세스가 있음")
        b = BegumReturn().run(st, CountingOps())
        L.check(b.unsafe and b.fail_at == 0 and b.safe == [], f"D2 n={n}: begum-return이 P_0에서 불안전이 아님")
        c1 = DBDAACycle1().run(st, CountingOps())
        L.check(c1.safe == [n - 1] and len(c1.primary_unsafe) == n - 1, f"D2 n={n}: dbdaa-cycle1의 통과가 P_{n - 1} 하나가 아님 {c1.safe}")
        rp = DBDAARepeat().run(st, CountingOps())
        L.check(rp.safe == rev and not rp.primary_unsafe and rp.cycles == n, f"D2 n={n}: dbdaa-repeat의 주기 수 {rp.cycles}, 통과 {rp.safe}")
        vc = {}
        for P in (TextbookRestart(), TextbookSweep()):
            ops = CountingOps()
            P.is_safe(st, ops)
            vc[P.name] = ops.vec_cmp
        L.check(vc["textbook-restart"] == n * (n + 1) // 2, f"D2 n={n}: Restart 벡터 비교 {vc['textbook-restart']} ≠ n(n+1)/2")
        lines.append(f"| {n} | {'예' if ok_replay else '아니오'} | 불안전(P_0, 비교 {b.counts['paper_cmp']}회) | {len(c1.safe)} | {rp.cycles} | "
                     f"{'예' if not rp.primary_unsafe else '아니오'} | {rp.counts['paper_cmp']} | {vc['textbook-restart']} | {vc['textbook-sweep']} |")
    lines.append("")
    lines.append("읽는 법: 이 입력에서 begum-return은 정렬 순서의 첫 프로세스에서 불안전을 돌려주므로 틀린 불안전이다. dbdaa-cycle1은 한 프로세스만 통과시키고 나머지를 "
                 "Primary_Unsafe_Sequence에 둔다(상태 판정을 '모두 통과'로 정의하면 불안전이므로 역시 틀린 불안전). dbdaa-repeat는 매 주기에 한 프로세스씩 통과시켜 n주기가 걸린다. "
                 "주기를 되풀이하는 읽기에서 DBDAA의 비용이 한 주기의 O(nd)에 머물지 않을 수 있다는 도출이다(상한은 이 파일이 증명하지 않는다. n = 2..8에서 맞는 것만 확인). "
                 "논문이 상태 판정을 어떻게 정하는지는 docs/rq6/variants.md의 해석 항목 Z-2에 있다.\n")

    # ---- D3
    pool = pool_states(31415, small_stride=30, wide=1500)
    bad_verdict = bad_prefix = bad_rep = 0
    safe_cnt = 0
    for st in pool:
        b = BegumReturn().run(st, CountingOps())
        c1 = DBDAACycle1().run(st, CountingOps())
        rp = DBDAARepeat().run(st, CountingOps())
        safe_b = not b.unsafe
        safe_c1 = (not c1.primary_unsafe) and (not c1.unsafe)
        safe_rp = (not rp.primary_unsafe) and (not rp.unsafe)
        safe_cnt += safe_b
        if safe_b != safe_c1:
            bad_verdict += 1
        if c1.safe[:len(b.safe)] != b.safe:
            bad_prefix += 1
        if safe_c1 and not safe_rp:
            bad_rep += 1
        if safe_b and b.safe != c1.safe:
            bad_prefix += 1
    L.check(bad_verdict == 0, f"D3: begum-return과 dbdaa-cycle1의 판정이 다른 입력 {bad_verdict}개")
    L.check(bad_prefix == 0, f"D3: begum-return의 안전 순서가 dbdaa-cycle1의 접두사가 아닌 입력 {bad_prefix}개")
    L.check(bad_rep == 0, f"D3: dbdaa-cycle1이 안전인데 dbdaa-repeat가 불안전인 입력 {bad_rep}개")
    lines.append("## D3. 단일 훑기 판정의 동치\n")
    lines.append("begum-return과 dbdaa-cycle1은 같은 키(최대 Need, 같은 값이면 번호 순)로 정렬하고 각 프로세스를 그 시점의 Available에 대해 '모든 자원에서 Need ≤ Available'인지 본다"
                 "(DBDAA의 짝 검사와 Max_Need ≤ Min_A 검사는 이 판정을 다른 순서로 하는 것이다. 근거는 D4의 도출). 두 정책이 '안전'이라고 하는 상태는 같고 "
                 "(안전 ⟺ 정렬 순서 전체가 안전 순서), begum의 안전 순서는 dbdaa-cycle1이 통과시킨 순서의 접두사이다(begum은 첫 실패에서 멈추고 dbdaa는 계속한다). "
                 "dbdaa-repeat는 dbdaa-cycle1이 안전이라 하는 상태를 모두 안전이라 한다(되풀이는 안전 판정을 늘릴 뿐 줄이지 않는다). 이것은 도출이다. 위 입력군에서 맞는지 기계로 확인했다.\n")
    lines.append(f"- 확인한 입력: {len(pool):,}개(문헌 예제 4개, 소규모 전수 일부, 층화 무작위, 경계 상태, 값이 큰 무작위 상태). 그중 begum-return이 안전이라 한 입력 {safe_cnt:,}개.")
    lines.append(f"- 판정이 다른 입력: {bad_verdict}개, 접두사 관계 위반: {bad_prefix}개, cycle1 안전·repeat 불안전: {bad_rep}개.")
    lines.append("- 함의(도출): 이 읽기들에서 두 알고리즘의 판정 함수가 같으므로 판정 정확도(K1)를 따로 측정하면 같은 값이 나온다. 비교 횟수와 시간(K2, K3)은 다르다. "
                 "그래서 인벤토리의 최소 건수(N_min)를 셀 때 이 두 항목은 판정에 관해서는 독립 증거가 아니고 비용 주장에 관해서만 독립이다. 결정은 사람 몫이다(Q8).\n")
    # ---- D4
    diff_cmp = same_cmp = 0
    bad_loc = 0
    for st in pool:
        a = DBDAACycle1().run(st, CountingOps())
        b = _Cycle1Last().run(st, CountingOps())
        if (a.safe, a.primary_unsafe, a.unsafe) != (b.safe, b.primary_unsafe, b.unsafe):
            bad_loc += 1
        if a.counts["paper_cmp"] != b.counts["paper_cmp"]:
            diff_cmp += 1
        else:
            same_cmp += 1
    L.check(bad_loc == 0, f"D4: 위치 동률 규칙에 따라 통과 순서나 판정이 달라진 입력 {bad_loc}개")
    lines.append("## D4. DBDAA의 위치 동률 규칙(앞 자원/뒤 자원)\n")
    lines.append("최대 Need나 최소 Available가 여러 자원에서 같을 때 어느 위치를 L1, L2로 잡는가(Algorithm 1의 22줄)는 논문에 없다. "
                 "도출: (a) 어떤 단계에서 Max_Need ≤ Min_A이면 안 표시된 모든 자원에서 Need ≤ Available이다(Need[j] ≤ Max_Need ≤ Min_A ≤ Available[j]). "
                 "(b) 그렇지 않을 때 L1이나 L2에서 Need > Available이면 그 자원은 실제로 어긋난 것이다. "
                 "(c) 둘 다 통과하면 L1 ≠ L2이다(L1 = L2이면 Need[L1] = Max_Need > Min_A = Available[L1]이라 (b)에서 이미 실패한다). "
                 "그래서 통과한 단계는 서로 다른 두 자원을 표시하고, 표시된 자원은 모두 Need ≤ Available를 만족한 것이다. ⌊d/2⌋단계 뒤 남는 자원은 0개 또는 1개이고 1개는 L3에서 직접 확인한다. "
                 "따라서 프로세스가 통과하는 것은 모든 자원에서 Need ≤ Available일 때, 그때만이다. 이 결론은 동률 규칙에 의존하지 않는다. "
                 "그러므로 동률 규칙은 판정과 통과 순서를 바꾸지 않고 비교 횟수와 확인 순서만 바꿀 수 있다.\n")
    lines.append(f"- 확인한 입력 {len(pool):,}개에서 통과 순서·판정이 다른 입력 {bad_loc}개. 논문 단위 비교 횟수가 다른 입력 {diff_cmp:,}개, 같은 입력 {same_cmp:,}개.\n")

    # ---- D5
    # 프로세스 A(알고리즘이 먼저 끝낼 수 있음)와 B. 최대 Need가 모두 2. 두 번호 붙이기를 비교한다.
    tot = [2, 2]
    st_ab = BState.make(tot, [[0, 2], [0, 0]], [[2, 0], [0, 2]])     # 번호 0 = A(Need (2,0), 쥔 것 (0,2)), 번호 1 = B(Need (0,2))
    st_ba = BState.make(tot, [[0, 0], [0, 2]], [[0, 2], [2, 0]])     # 같은 상태에서 번호만 바꿈: 번호 0 = B, 번호 1 = A
    r_ab, r_ba = BegumReturn().run(st_ab, CountingOps()), BegumReturn().run(st_ba, CountingOps())
    c_ab, c_ba = DBDAACycle1().run(st_ab, CountingOps()), DBDAACycle1().run(st_ba, CountingOps())
    p_ab, p_ba = DBDAARepeat().run(st_ab, CountingOps()), DBDAARepeat().run(st_ba, CountingOps())
    L.check(st_ab.avail == [2, 0] and st_ba.avail == [2, 0], "D5: Available가 (2, 0)이 아님")
    L.check(replay(st_ab, [0, 1]) and replay(st_ba, [1, 0]), "D5: 안전 순서 A, B가 되짚어지지 않음")
    L.check((not r_ab.unsafe) and r_ba.unsafe, f"D5: begum-return 판정이 번호 붙이기에 따라 다르지 않음 {r_ab.unsafe} {r_ba.unsafe}")
    L.check((not c_ab.primary_unsafe) and c_ba.primary_unsafe == [0], f"D5: dbdaa-cycle1 판정 {c_ab.primary_unsafe} {c_ba.primary_unsafe}")
    L.check((not p_ab.primary_unsafe) and (not p_ba.primary_unsafe) and p_ba.cycles == 2, f"D5: dbdaa-repeat {p_ab.primary_unsafe} {p_ba.primary_unsafe} {p_ba.cycles}")
    lines.append("## D5. 정렬의 동률 규칙\n")
    lines.append("단일 훑기 읽기(begum-return, dbdaa-cycle1)의 판정은 정렬 순서에 달려 있다. 최대 Need가 같은 프로세스의 순서는 두 논문 모두 정하지 않았다"
                 "(Begum의 기수 정렬은 안정이라 입력 순서를 따르고, DBDAA의 Sort(RQ)는 동률 규칙이 없다. 이 저장소는 둘 다 번호 순). "
                 "예: 자원 두 종류(총량 2, 2). 프로세스 A는 (0, 2)를 쥐고 (2, 0)을 더 청구하고, B는 아무것도 쥐지 않고 (0, 2)를 더 청구한다. Available = (2, 0). "
                 "최대 Need는 둘 다 2다. A, B 순이면 A가 끝나 (0, 2)를 내놓고 B도 끝난다. B, A 순이면 B가 처음부터 실행할 수 없다.\n")
    lines.append("| 번호 붙이기(동률이면 번호 순) | begum-return | dbdaa-cycle1 | dbdaa-repeat |")
    lines.append("|---|---|---|---|")
    lines.append(f"| A=0, B=1 | {'불안전' if r_ab.unsafe else '안전'} | {'불안전' if c_ab.primary_unsafe else '안전'} | {'불안전' if p_ab.primary_unsafe else '안전'}(주기 {p_ab.cycles}) |")
    lines.append(f"| B=0, A=1 | {'불안전' if r_ba.unsafe else '안전'} | {'불안전' if c_ba.primary_unsafe else '안전'} | {'불안전' if p_ba.primary_unsafe else '안전'}(주기 {p_ba.cycles}) |")
    lines.append("")
    lines.append("같은 상태인데 프로세스 번호만 바꾸면 단일 훑기 읽기의 판정이 바뀐다. 되풀이하는 읽기는 판정이 같고 주기 수만 다르다. 그래서 동률 규칙은 단일 훑기 읽기의 판정 정확도(K1)에 영향을 줄 수 있는 해석이다"
                 "(동률이 얼마나 자주 나오는가는 입력군에 달려 있고 여기서는 재지 않았다).\n")
    status = "모두 통과" if not L.fails else f"실패 {len(L.fails)}건"
    lines.append(f"점검 {L.checks}개: {status}. 총 시간 {time.time() - t0:.0f}초.\n")
    if L.fails:
        lines.append("### 실패 목록\n")
        lines += [f"- {x}" for x in L.fails[:40]]
        lines.append("")
    lines.append("## 범위와 한계\n")
    lines.append("- 도출은 증명이 아니다. 기계 확인은 위 입력(손으로 만든 입력, 소규모와 무작위 입력)에서 서술이 코드와 맞음을 보일 뿐이다. 일반적인 참은 사람이 증명을 검토해야 한다.")
    lines.append("- 이 입력들은 등록된 입력군이 아니다. 숫자는 K1·K2·K3의 결과가 아니다.")
    lines.append("- 도출은 이 저장소의 읽기(해석 목록의 선택)에 대한 것이다. 논문의 뜻이 다르면 도출도 달라진다.")
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
