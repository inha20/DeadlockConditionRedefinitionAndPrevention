"""Zohora·Farhin·Kaiser 2024의 DBDAA(Dynamic Banker's Deadlock Avoidance Algorithm) 재구현 (R6-07). AI 초안: 사람의 확인 전.

원문: PLoS ONE 19(9): e0310807, doi:10.1371/journal.pone.0310807. Algorithm 1(53줄)과 '제안 알고리즘' 절의 설명.
해석과 근거, 예제 재현 결과는 docs/rq6/variants.md.

논문의 절차(줄 번호는 Algorithm 1)
  4–11  모든 프로세스는 AT=0에 도착한다고 본다. Maximum[i,j] > Resource[j]인 프로세스는 Unsafe_Sequence로 보낸다.
        나머지는 Max_Need(= max_j Need[i,j])가 작은 순으로 정렬한 SRQ에 둔다.
  12–13 SRQ의 맨 앞 프로세스 i를 꺼낸다.
  14–41 자원 종류를 둘씩 짝지어 확인한다. 안 표시된 자원에서 Max_Need = max Need[i,j], Min_A = min Available[j]를 구하고
        Max_Need <= Min_A이면 통과(19–20). 아니면 두 값의 위치 L1, L2에서 Need > Available인지 본다. 하나라도 그러면
        i는 Primary_Unsafe_Sequence로(24–25), 아니면 두 자원을 표시하고 되풀이(27). floor(d/2)번 뒤에도 안 표시된 자원이
        남으면(d 홀수) 그 하나만 직접 확인한다(31–38).
  42–43 통과하면 Safe_Sequence에 넣고 Available에 Allocation을 더한다.
  44–50 타이머 확인. 본문: 시각이 타이머에 닿거나 SRQ가 비면 세 순서를 돌려주고, Primary_Unsafe의 프로세스는 SRQ로 되돌아간다.

이 구현이 정한 것(논문이 정하지 않았거나 모호한 부분. 근거는 docs/rq6/variants.md §2)
  - 시계와 BT는 정의되지 않았고 알고리즘에 쓰이지 않는다. 타이머는 만료되지 않는다고 본다. 한 주기는 SRQ가 빌 때까지다.
  - Primary_Unsafe를 되돌려 주기를 되풀이할지가 해석이다: dbdaa-cycle1(첫 주기만), dbdaa-repeat(진전이 없을 때까지 되풀이).
    상태가 안전하다는 판정은 '모든 프로세스가 Safe_Sequence에 들었다'로 정의한다(논문에는 상태 판정 규칙이 없다).
  - Max_Need·Min_A의 위치가 여럿이면 가장 앞 자원(loc_tie="first"). 논문 예제(표 7)의 서술이 이를 뒷받침한다.
    정렬에서 Max_Need가 같으면 프로세스 번호 순(안정 정렬). 논문 예제에는 같은 값이 없어 예제로는 구분되지 않는다.
  - Available은 상태가 주는 값(= Resource − Σ Allocation, 논문의 식 2)이다.

계측: 안쪽 반복에서 스칼라 비교를 지역 변수로 센 뒤 마지막에 ops.add_counts로 알린다(시간을 재는 실행에서도 같은 코드다).
  sca_cmp   실행한 모든 스칼라 비교(입장 검사, Max_Need 계산, 정렬, 최대·최소 탐색, 논문이 센 비교 모두)
  paper_cmp 논문이 센 비교만(19, 24, 35줄의 명시적 검사. 24줄은 ||의 단락 평가를 따른다). 표 5–7의 '비교 횟수'가 이것이다.
  scan_cmp  최대·최소 탐색(15–18줄), admit_cmp 입장 검사(4줄), maxneed_cmp Max_Need 계산(9줄), sort_cmp 정렬(계측 실행에서만)
  vec_cmp   0이다(벡터 비교 연산을 쓰지 않는다). vec_add는 통과한 프로세스 수(43줄).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import cmp_to_key

from bench.policies.banker.base import SafetyPolicy


@dataclass
class DBDAAResult:
    safe: list                 # Safe_Sequence (프로세스 번호, 통과한 순서)
    primary_unsafe: list       # 끝날 때 남은 Primary_Unsafe_Sequence
    unsafe: list               # Unsafe_Sequence (Maximum > Resource)
    cycles: int
    counts: dict
    trace: list = field(default_factory=list)


class _DBDAABase(SafetyPolicy):
    name = "dbdaa-base"
    requeue = False
    loc_tie = "first"          # "first": 위치가 여럿이면 가장 앞 자원, "last": 가장 뒤 자원

    def run(self, st, ops, want_trace: bool = False) -> DBDAAResult:
        n, d = st.n, st.m
        total, need, alloc = st.total, st.need, st.alloc
        work = list(st.avail)
        half = d // 2
        last = self.loc_tie == "last"
        c_paper = c_scan = c_admit = c_maxneed = c_sort = 0
        vadds = 0
        dispatches = 0

        # 4–11줄: 입장 검사와 Max_Need
        unsafe, ready = [], []
        mxneed = [0] * n
        for i in range(n):
            a_i, n_i = alloc[i], need[i]
            over = False
            for j in range(d):
                c_admit += 1
                if a_i[j] + n_i[j] > total[j]:
                    over = True
                    break
            if over:
                unsafe.append(i)
                continue
            ready.append(i)
            mx = n_i[0]
            for j in range(1, d):
                c_maxneed += 1
                if n_i[j] > mx:
                    mx = n_i[j]
            mxneed[i] = mx

        # 10줄: SRQ = Max_Need 오름차순(안정 정렬)
        if ops.counting:
            box = [0]

            def cmp(a, b):
                box[0] += 1
                x, y = mxneed[a], mxneed[b]
                return -1 if x < y else (1 if x > y else 0)

            srq = sorted(ready, key=cmp_to_key(cmp))
            c_sort = box[0]
        else:
            srq = sorted(ready, key=mxneed.__getitem__)

        safe: list = []
        primary: list = []
        cycles = 0
        queue = srq
        out_trace: list | None = [] if want_trace else None
        while True:
            cycles += 1
            primary = []
            progressed = False
            for i in queue:
                dispatches += 1
                n_i = need[i]
                mark = [False] * d
                k = 1
                before = c_paper
                ok = True
                if out_trace is not None:
                    t_avail, t_mx, t_mn = list(work), [], []
                while True:
                    if k <= half:
                        # 15–18줄: 안 표시된 자원에서 최대 Need와 최소 Available(위치 포함)
                        l1 = l2 = -1
                        for j in range(d):
                            if mark[j]:
                                continue
                            if l1 < 0:
                                l1 = l2 = j
                                continue
                            c_scan += 2
                            if last:
                                if n_i[j] >= n_i[l1]:
                                    l1 = j
                                if work[j] <= work[l2]:
                                    l2 = j
                            else:
                                if n_i[j] > n_i[l1]:
                                    l1 = j
                                if work[j] < work[l2]:
                                    l2 = j
                        mx, mn = n_i[l1], work[l2]
                        if out_trace is not None:
                            t_mx.append(mx)
                            t_mn.append(mn)
                        c_paper += 1                      # 19줄
                        if mx <= mn:
                            break                         # → 42줄
                        c_paper += 1                      # 24줄 앞 항
                        if n_i[l1] > work[l1]:
                            ok = False
                            break
                        c_paper += 1                      # 24줄 뒤 항(앞 항이 거짓일 때만 평가)
                        if n_i[l2] > work[l2]:
                            ok = False
                            break
                        mark[l1] = True                   # 27줄
                        mark[l2] = True
                        k += 1
                    else:
                        # 31–38줄
                        l3 = -1
                        for j in range(d):
                            if not mark[j]:
                                l3 = j
                                break
                        if l3 < 0:
                            break                         # 모두 표시됨 → 42줄
                        c_paper += 1                      # 35줄
                        if n_i[l3] > work[l3]:
                            ok = False
                        break
                if ok:                                    # 42–43줄
                    a_i = alloc[i]
                    for r in range(d):
                        work[r] += a_i[r]
                    vadds += 1
                    safe.append(i)
                    progressed = True
                else:
                    primary.append(i)
                if out_trace is not None:
                    out_trace.append({"i": i, "cycle": cycles, "avail": t_avail, "max_need": t_mx, "min_avail": t_mn,
                                      "safe": ok, "comparisons": c_paper - before})
            if not self.requeue or not primary or not progressed:
                break
            queue = primary                               # 46–47줄: Primary_Unsafe를 SRQ로 되돌린다

        counts = {"sca_cmp": c_paper + c_scan + c_admit + c_maxneed + c_sort, "paper_cmp": c_paper, "scan_cmp": c_scan,
                  "admit_cmp": c_admit, "maxneed_cmp": c_maxneed, "sort_cmp": c_sort, "vec_add": vadds,
                  "iters": dispatches, "cycles": cycles}
        ops.add_counts(sca_cmp=counts["sca_cmp"], vec_add=vadds, iters=dispatches, paper_cmp=c_paper, scan_cmp=c_scan,
                       admit_cmp=c_admit, maxneed_cmp=c_maxneed, sort_cmp=c_sort, cycles=cycles)
        return DBDAAResult(safe, primary, unsafe, cycles, counts, out_trace or [])

    def is_safe(self, st, ops) -> bool:
        res = self.run(st, ops)
        return not res.primary_unsafe and not res.unsafe


class DBDAACycle1(_DBDAABase):
    """첫 주기만 돌린다. 모든 프로세스가 한 번에 Safe_Sequence에 들어야 안전."""
    name = "dbdaa-cycle1"
    requeue = False


class DBDAARepeat(_DBDAABase):
    """Primary_Unsafe를 SRQ로 되돌려 주기를 되풀이한다. 한 주기에서 진전이 없으면 멈춘다."""
    name = "dbdaa-repeat"
    requeue = True
