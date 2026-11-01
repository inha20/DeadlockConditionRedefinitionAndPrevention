"""교재식 안전성 알고리즘의 기준 구현(WP6.2). 정의는 docs/rq6/reference.md.

Work = Available, Finish[i] = false로 시작해, Finish[i]가 거짓이고 Need_i <= Work인 i를 찾아
Work += Allocation_i, Finish[i] = true로 하는 것을 더 찾을 수 없을 때까지 되풀이하고 모든 Finish가 참이면 안전이다.
'찾는 방법'에 따라 비용이 달라지는 두 구현을 둔다. 판정은 같다(닫힘 연산이므로 순서에 무관).
  TextbookRestart  한 프로세스를 끝낼 때마다 처음부터 다시 훑는다(교재의 2–3단계를 글자 그대로 옮김). 기준 구현의 기본값.
  TextbookSweep    훑기를 이어서 하며 한 번 훑어 진전이 없을 때까지 되풀이한다(강의 노트에 흔한 형태).
어느 쪽이 기준인가는 AI의 제안이며 사람이 확정한다(docs/rq6/reference.md의 열린 항목).
"""
from __future__ import annotations

from bench.policies.banker.base import SafetyPolicy


class TextbookRestart(SafetyPolicy):
    name = "textbook-restart"

    def is_safe(self, st, ops) -> bool:
        n = st.n
        need, alloc = st.need, st.alloc
        work = list(st.avail)
        finish = [False] * n
        remaining = n
        while True:
            found = -1
            for i in range(n):
                ops.tick()
                if not finish[i] and ops.leq(need[i], work):
                    found = i
                    break
            if found < 0:
                break
            ops.vadd(work, alloc[found])
            finish[found] = True
            remaining -= 1
        return remaining == 0


class TextbookSweep(SafetyPolicy):
    name = "textbook-sweep"

    def is_safe(self, st, ops) -> bool:
        n = st.n
        need, alloc = st.need, st.alloc
        work = list(st.avail)
        finish = [False] * n
        remaining = n
        progress = True
        while progress and remaining:
            progress = False
            ops.tick("sweeps")
            for i in range(n):
                ops.tick()
                if not finish[i] and ops.leq(need[i], work):
                    ops.vadd(work, alloc[i])
                    finish[i] = True
                    remaining -= 1
                    progress = True
        return remaining == 0
