"""Begum·Faruque·Miah·Das 2020의 안전성 탐지 알고리즘 재구현 (R6-05). AI 초안: 사람의 확인 전.

원문: Begum 외, ISCAIE 2020, 쪽 73–78(IEEE Xplore 문서 9108818). §III.A의 단계 1–6과 기수 정렬 단계 1–9, 그림 1(순서도).
해석과 근거, 예제 재현 결과는 docs/rq6/variants.md.

논문의 절차(§III.A, 그림 1)
  1  Completed_process[i] := 0
  2  Maximum_need[i, j] > Resource[j]인 (i, j)가 하나라도 있으면 불안전을 돌려준다.
  3  프로세스를 Maximum_Needed_allocation(= max_j Need[i, j])의 오름차순으로 정렬한다(기수 정렬).
  4  정렬된 순서로 프로세스를 한 번만 훑는다.
       Maximum_Needed_allocation[i] <= Minimum_Available이면 통과(비교 1회).
       아니면 자원 j = 1..d를 차례로 Need[i, j] <= Available[j]인지 보고, 하나라도 아니면 불안전을 돌려준다(그림 1).
       통과하면 Safe_sequence에 넣고 Available += Allocation[i]를 하고 Minimum_Available를 다시 구한다.
  5  끝나지 않은 프로세스가 있으면 불안전, 6  없으면 안전과 Safe_sequence.
논문은 되풀이 훑기를 하지 않는다("순서를 한 번 이상 확인할 필요가 없다"). 그래서 정렬 순서에서 처음으로 실행할 수 없는 프로세스가 나오면
이 알고리즘은 즉시 불안전을 돌려준다(뒤 프로세스가 실행 가능해도). 5단계는 그 뒤에는 항상 참이라 중복이다.

이 구현이 정한 것(논문이 정하지 않았거나 모호한 부분. 근거는 docs/rq6/variants.md §3)
  - 처음 Minimum_Available는 4단계에 들어가기 전에 Available의 최솟값으로 구한다(논문 단계에는 없고 예제 표 IV가 그렇게 한다).
  - 정렬은 안정이다(기수 정렬은 안정이다. 표 III의 같은 값 프로세스 순서가 안정 정렬 결과다). 기수 정렬은 표준 LSD 계수 정렬(10진수)로 옮겼다.
    논문의 의사코드는 자릿수 추출 식이 정확하지 않다(나눗셈이 없다).
  - 실행할 수 없는 프로세스를 만나면 즉시 불안전을 돌려준다(그림 1과 의사코드). '건너뛰고 계속' 읽기는 판정이 같고 안전 순서와 비용이 다르다
    (뒤에 끝나지 않은 프로세스가 남아 5단계가 불안전을 내므로. 도출. 점검이 판정 동치를 확인한다) 구현하지 않았다.
  - 자원별 검사의 끝: 의사코드와 순서도의 'j == d' 판정은 문자 그대로 읽으면 모순이다(마지막 자원에서 실패해도 통과로 처리하거나, 모두 통과하면 j = d+1이라 불안전).
    '모든 자원을 통과하면 완료, 하나라도 실패하면 즉시 불안전'으로 읽었다. 자원은 j = 1..d(자원 번호 순, 모두)를 본다.
  - Available은 상태가 주는 값(= Resource − Σ Allocation)이다.

계측: 안쪽 반복에서 스칼라 비교를 지역 변수로 센 뒤 마지막에 ops.add_counts로 알린다.
  sca_cmp   실행한 모든 스칼라 비교(입장 검사, Max_Needed 계산, Minimum_Available 계산, 통과 검사, 자원별 검사)
  paper_cmp 논문이 센 비교(통과 검사 + 자원별 검사). 예제에서 논문이 센 '10회'는 통과 검사만이다(자원별 검사는 쓰이지 않았다).
  radix_passes 기수 정렬의 자리 수(비교 연산을 쓰지 않으므로 sca_cmp에 넣지 않는다).
  vec_cmp   0이다. vec_add는 통과한 프로세스 수.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from bench.policies.banker.base import SafetyPolicy


def radix_order(keys: list[int]) -> tuple[list[int], int]:
    """키의 안정 오름차순 정렬 순서(인덱스 목록)와 자리 수. 10진수 LSD 계수 정렬."""
    n = len(keys)
    order = list(range(n))
    mx = max(keys) if keys else 0
    passes = len(str(mx))
    div = 1
    for _ in range(passes):
        count = [0] * 10
        for idx in order:
            count[(keys[idx] // div) % 10] += 1
        for j in range(1, 10):
            count[j] += count[j - 1]
        out = [0] * n
        for idx in reversed(order):
            dg = (keys[idx] // div) % 10
            count[dg] -= 1
            out[count[dg]] = idx
        order = out
        div *= 10
    return order, passes


@dataclass
class BegumResult:
    safe: list                 # Safe_sequence (통과한 순서. 불안전이면 처음 실행할 수 없는 프로세스 앞까지)
    unsafe: bool               # 불안전 판정
    fail_at: int | None        # 처음 실행할 수 없었던 프로세스(없으면 None)
    reason: str | None         # None, "admission"(2단계), "process"(4단계)
    counts: dict
    trace: list = field(default_factory=list)


class BegumReturn(SafetyPolicy):
    """실행할 수 없는 프로세스를 처음 만나면 즉시 불안전(논문의 그림 1과 의사코드를 글자 그대로)."""
    name = "begum-return"

    def run(self, st, ops, want_trace: bool = False) -> BegumResult:
        n, d = st.n, st.m
        total, need, alloc = st.total, st.need, st.alloc
        work = list(st.avail)
        c_paper = c_quick = c_res = c_admit = c_maxneed = c_min = 0

        # 2단계: Maximum_need[i, j] > Resource[j]
        for i in range(n):
            for j in range(d):
                c_admit += 1
                if alloc[i][j] + need[i][j] > total[j]:
                    counts = self._counts(0, 0, 0, c_admit, 0, 0, 0, n, d, 0)
                    ops.add_counts(**counts["ops"])
                    return BegumResult([], True, None, "admission", counts["all"], [])

        # Maximum_Needed_allocation[i] = max_j Need[i][j]
        mxn = [0] * n
        for i in range(n):
            n_i = need[i]
            m_i = n_i[0]
            for j in range(1, d):
                c_maxneed += 1
                if n_i[j] > m_i:
                    m_i = n_i[j]
            mxn[i] = m_i

        # 3단계: 기수 정렬(안정)
        order, passes = radix_order(mxn)

        def min_of(w):
            nonlocal c_min
            m = w[0]
            for j in range(1, d):
                c_min += 1
                if w[j] < m:
                    m = w[j]
            return m

        minav = min_of(work)                     # 처음 Minimum_Available
        safe: list = []
        fail = None
        trace: list = []
        examined = 0
        for i in order:                          # 4단계: 한 번만 훑는다
            examined += 1
            before = c_paper
            t_avail = list(work) if want_trace else None
            t_min = minav
            c_paper += 1
            c_quick += 1
            quick = mxn[i] <= minav
            ok = True
            if not quick:
                n_i = need[i]
                for j in range(d):
                    c_paper += 1
                    c_res += 1
                    if n_i[j] > work[j]:
                        ok = False
                        break
            if want_trace:
                trace.append({"i": i, "avail": t_avail, "min_avail": t_min, "max_needed": mxn[i], "quick": quick, "ok": ok,
                              "comparisons": c_paper - before})
            if not ok:
                fail = i
                break                            # 불안전을 돌려준다
            a_i = alloc[i]
            for r in range(d):
                work[r] += a_i[r]
            safe.append(i)
            minav = min_of(work)

        counts = self._counts(c_paper, c_quick, c_res, c_admit, c_maxneed, c_min, len(safe), n, d, passes, examined)
        ops.add_counts(**counts["ops"])
        unsafe = fail is not None
        return BegumResult(safe, unsafe, fail, "process" if unsafe else None, counts["all"], trace)

    @staticmethod
    def _counts(c_paper, c_quick, c_res, c_admit, c_maxneed, c_min, completed, n, d, passes, examined=0) -> dict:
        sca = c_paper + c_admit + c_maxneed + c_min
        allc = {"sca_cmp": sca, "paper_cmp": c_paper, "quick_cmp": c_quick, "res_cmp": c_res, "admit_cmp": c_admit,
                "maxneed_cmp": c_maxneed, "min_cmp": c_min, "vec_add": completed, "iters": examined,
                "radix_passes": passes}
        ops = {"sca_cmp": sca, "vec_add": completed, "iters": examined, "paper_cmp": c_paper, "quick_cmp": c_quick,
               "res_cmp": c_res, "admit_cmp": c_admit, "maxneed_cmp": c_maxneed, "min_cmp": c_min, "radix_passes": passes}
        return {"all": allc, "ops": ops}

    def is_safe(self, st, ops) -> bool:
        return not self.run(st, ops).unsafe
