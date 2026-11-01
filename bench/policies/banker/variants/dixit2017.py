"""Dixit·Khuteta 2017의 '수정 뱅커' 알고리즘 재구현 (R6-04). 해석별 정책 여섯 개. AI 초안: 사람의 확인 전.

원문: IJRITCC 5(8): 45–49, 2017. 읽은 방법: SlideShare 사본(인벤토리 W03)의 본문을 도구가 읽어 낸 텍스트(2026-11-01). 저널 PDF와 대조하지 않았다.
해석과 근거, 예제 재현 결과는 docs/rq6/variants.md §5.2.

논문의 절차(의역. 의사코드 네 줄과 예제의 서술)
  i = 0..n−1을 한 번 훑는다.
    Need(i) ≤ Available이면: Available = Available − Need(i); 프로세스 i를 실행; Available = Available + Allocation(아래첨자 없음); 다음 프로세스로.
    아니면: 필요량을 스택에 넣는다. 예제는 넣을 때마다 '스택을 정리'해 필요량이 가장 작은 것이 위(top)에 오게 한다.
  끝. 스택에 남은 프로세스는 '위에서부터 실행된다'고 예제 설명에 쓰나, 다시 검사하는 단계도, 종료 조건도, 최종 안전 순서의 출력도 없다.

모호한 곳과 이 구현의 매개변수(근거는 variants.md §5.2의 DK-1…DK-8)
  release  Available에 되돌리는 것:
             "max"   = 보유량 + 방금 받은 Need(= Max). Allocation을 '받은 뒤의 보유량'으로 읽는다. 순효과는 Available += Allocation_i(교재식과 같다).
             "alloc" = 처음 보유량 Allocation_i만. 인쇄된 식을 글자 그대로 읽은 것이다. 받은 Need가 돌아오지 않아 Available이 줄어든다.
  tail     훑기를 마친 뒤 스택을 어떻게 처리하는가(논문에 의사코드가 없다):
             "once"   처리하지 않는다. 훑기에서 모두 끝내지 못했으면 안전 순서를 찾지 못한 것(불안전). 인쇄된 의사코드 그대로.
             "top"    스택의 위에서부터 차례로 Need ≤ Available을 확인해 실행하고, 위의 것이 실행되지 못하면 멈춘다(불안전).
             "repeat" 스택을 위에서부터 훑어 실행 가능한 것을 실행하고, 한 번 훑어 진전이 없을 때까지 되풀이한다.
  정렬 키  스택 정리의 키는 Need 성분의 합(작은 것이 위). 예제의 인쇄된 스택 순서 P2, P4, P1, P0과 같은 순서를 내는 키는 여럿이고
           이 합은 그중 가장 단순한 것이다. 같은 키는 먼저 넣은 것이 위에 온다(안정). 예제에는 같은 키가 없다.
  비교     Need ≤ Available(같아도 통과. 예제의 P3 단계가 같은 값에서 통과한다).
  정책 이름은 dixit-<release>-<tail>이고 여섯 개(2 × 3)를 모두 등록한다. 어느 것이 '대표'인지는 정하지 않았다(variants.md V-1).

판정: 모든 프로세스가 실행되었으면 안전, 스택에 남은 것이 있으면 불안전. 안전 순서는 실행한 순서다.
  - release="max"이고 tail="repeat"이면 닫힘 계산(교재식)과 판정이 같다(도출 D7. check_variants_dixit.py가 점검한다). 다른 다섯은 판정이 다를 수 있다.
  - release="alloc"에서는 Available이 줄어들 수 있어 실행 순서에 따라 판정이 달라질 수 있다(도출 D8).

계측(textbook과 같은 단위): vec_cmp·sca_cmp는 Need ≤ Available 확인(ops.leq, 단락 평가), vec_add는 벡터 덧셈·뺄셈(실행한 프로세스마다 2번),
  iters는 확인한 칸 수. 그 밖에 sort_cmp(스택 정리의 키 비교. 위에서부터 내려가며 비교하는 삽입으로 센다. 스칼라 비교라 sca_cmp에도 더한다),
  key_add(키 계산의 스칼라 덧셈: 스택에 넣는 프로세스마다 d−1), pushes, rounds(tail="repeat"의 훑기 수).
  Max = Allocation + Need를 만드는 일은 입력의 일부로 보고 세지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from bench.policies.banker.base import SafetyPolicy


@dataclass
class DixitResult:
    safe: list                 # 실행한 순서
    unsafe: bool               # 스택에 남은 프로세스가 있음
    stack: list                # 끝났을 때 스택(위에서 아래로)
    counts: dict
    trace: list = field(default_factory=list)


class _Dixit(SafetyPolicy):
    name = "dixit-base"
    release = "max"            # "max" | "alloc"
    tail = "once"              # "once" | "top" | "repeat"

    def run(self, st, ops, want_trace: bool = False) -> DixitResult:
        n, d = st.n, st.m
        need, alloc = st.need, st.alloc
        avail = list(st.avail)
        safe: list = []
        stack: list = []                    # 위(top)에서 아래로. 키 오름차순
        keys: dict = {}
        c_sort = c_key = c_push = rounds = 0
        trace: list = []
        give_max = self.release == "max"

        def execute(i: int) -> None:
            ops.vsub(avail, need[i])                                        # Available = Available − Need(i)
            if give_max:
                ops.vadd(avail, [alloc[i][r] + need[i][r] for r in range(d)])   # Available + (받은 뒤의 Allocation = Max)
            else:
                ops.vadd(avail, alloc[i])                                   # Available + (처음 Allocation)
            safe.append(i)

        # 훑기: i = 0..n−1을 한 번
        for i in range(n):
            ops.tick()
            before = list(avail) if want_trace else None
            if ops.leq(need[i], avail):
                execute(i)
                act = "execute"
            else:
                k = sum(need[i])
                c_key += d - 1
                keys[i] = k
                pos = 0
                while pos < len(stack):         # 위에서부터 내려가며 자기보다 큰 키를 만날 때까지
                    c_sort += 1
                    if keys[stack[pos]] <= k:
                        pos += 1
                    else:
                        break
                stack.insert(pos, i)
                c_push += 1
                act = "push"
            if want_trace:
                trace.append({"phase": "pass", "i": i, "act": act, "avail_before": before, "avail": list(avail), "stack": list(stack)})

        # 스택 처리
        if self.tail == "top":
            while stack:
                j = stack[0]
                ops.tick()
                before = list(avail) if want_trace else None
                if ops.leq(need[j], avail):
                    stack.pop(0)
                    execute(j)
                    if want_trace:
                        trace.append({"phase": "top", "i": j, "act": "execute", "avail_before": before, "avail": list(avail), "stack": list(stack)})
                else:
                    if want_trace:
                        trace.append({"phase": "top", "i": j, "act": "stop", "avail_before": before, "avail": list(avail), "stack": list(stack)})
                    break
        elif self.tail == "repeat":
            while stack:
                rounds += 1
                progress = False
                rest: list = []
                for j in stack:
                    ops.tick()
                    before = list(avail) if want_trace else None
                    if ops.leq(need[j], avail):
                        execute(j)
                        progress = True
                        act = "execute"
                    else:
                        rest.append(j)
                        act = "keep"
                    if want_trace:
                        trace.append({"phase": "repeat", "round": rounds, "i": j, "act": act, "avail_before": before, "avail": list(avail), "stack": list(rest)})
                stack = rest
                if not progress:
                    break

        ops.add_counts(sca_cmp=c_sort, sort_cmp=c_sort, key_add=c_key, pushes=c_push)
        if rounds:
            ops.tick("rounds", rounds)
        counts = {"sort_cmp": c_sort, "key_add": c_key, "pushes": c_push, "rounds": rounds, "executed": len(safe)}
        return DixitResult(safe, bool(stack), list(stack), counts, trace)

    def is_safe(self, st, ops) -> bool:
        return not self.run(st, ops).unsafe


class DixitMaxOnce(_Dixit):
    name, release, tail = "dixit-max-once", "max", "once"


class DixitMaxTop(_Dixit):
    name, release, tail = "dixit-max-top", "max", "top"


class DixitMaxRepeat(_Dixit):
    name, release, tail = "dixit-max-repeat", "max", "repeat"


class DixitAllocOnce(_Dixit):
    name, release, tail = "dixit-alloc-once", "alloc", "once"


class DixitAllocTop(_Dixit):
    name, release, tail = "dixit-alloc-top", "alloc", "top"


class DixitAllocRepeat(_Dixit):
    name, release, tail = "dixit-alloc-repeat", "alloc", "repeat"


DIXIT_POLICIES = (DixitMaxOnce, DixitMaxTop, DixitMaxRepeat, DixitAllocOnce, DixitAllocTop, DixitAllocRepeat)
