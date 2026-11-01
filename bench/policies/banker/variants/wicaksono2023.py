"""Wicaksono·Baeti·Salma·Kardian 2023의 '동적' 뱅커 알고리즘 재구현 (R6-06). AI 초안: 사람의 확인 전.

원문: JEEMECS 6(1), 2023. 그림 2–4의 의사코드와 표 1–5. 읽은 방법: 도구가 PDF 본문을 읽어 낸 텍스트(2026-11-01). PDF 원문 대조는 아직 하지 않았다.
해석과 근거, 예제 재현 결과는 docs/rq6/variants.md §5.1.

논문의 절차(의역)
  countNeed(그림 2)   Need[i][j] = Max[i][j] − Allocation[i][j]를 모든 칸에서 다시 계산한다.
  bankerLoop(그림 3)  Finish를 모두 거짓으로, 안전 순서를 빈 목록으로 둔다. Finish에 거짓이 남아 있는 동안 바깥 반복을 한다.
    1. (바깥 반복의 맨 앞에서만) 새 요청이 도착했으면 Allocation에 0 행을, Max에 새 프로세스의 최대 청구 행을 붙이고
       Need를 전부 다시 계산하고 프로세스 수를 하나 늘리고 Finish에 거짓을 붙인다.
    2. i = 0..M−1을 차례로 훑는다. Finish[i]가 거짓이고 모든 j에서 Need[i][j] ≤ Available[j]이면
       i를 안전 순서에 넣고 Available에 Allocation[i]를 더하고 Finish[i]를 참으로 한다(훑는 도중 바뀐 Available을 뒤의 i가 본다).
    3. 훑기에서 한 프로세스도 끝내지 못했으면 'error'(안전 순서 없음)를 돌려준다.
    Finish가 모두 참이 되면 안전 순서를 돌려준다.
  main(그림 4)        Need를 계산하고 bankerLoop를 부른다. 결과가 'error'이면 '안전 순서를 만들 수 없다'고 쓴다.

이 구조는 교재식 Sweep(textbook-sweep)과 같다. 다른 점은 도착 확인뿐이다: 도착이 없으면 계측 계수(vec_cmp, sca_cmp, vec_add, iters, sweeps)가
textbook-sweep과 같다(check_variants_wicaksono.py가 점검한다. 판정을 직접 견준 것은 아니다. 같은 계수는 같은 경로를 시사한다).

이 구현이 정한 것(논문이 정하지 않았거나 모호한 부분. 근거는 docs/rq6/variants.md §5.1)
  - 도착은 `arrivals` 인자(바깥 반복 번호 → 새 프로세스의 최대 청구 행)로 준다. 도착 확인은 바깥 반복의 맨 앞에서 한 번이다(그림 3).
    루프가 이미 끝났거나(모두 끝남) 'error'로 끝난 뒤의 도착은 받아들여지지 않는다(`missed`에 기록).
  - 한 번의 도착 확인에서 받는 프로세스는 하나다. 같은 시점에 둘 이상 도착하는 경우는 논문이 정하지 않아 지원하지 않는다.
  - 새 프로세스를 받을 때 최대 청구가 자원 총량 이하인지, 받아도 안전한지 검사하지 않는다(그림 3에 없다). 그래서 최대 청구가 총량을 넘는 도착은
    언젠가 'error'로 이어진다. 'error'일 때 이미 받은 프로세스를 되돌리지도 않는다(`admitted`에 남는다).
  - 호출자의 상태를 바꾸지 않는다(논문의 그림 3은 인자 Allocation, Max, Available을 제자리에서 바꾼다. 이 구현은 사본으로 돌린다).
  - Available의 차원은 자원 종류 수 N이다(본문 서술의 'M개 원소'는 오기로 읽었다).
  - 비교는 '어떤 j에서 Need[i][j] > Available[j]'가 없으면 통과다. 즉 Need ≤ Available이고 같아도 통과다(예제의 p0 단계가 같은 값에서 통과한다).

계측(textbook-sweep과 같은 단위)
  vec_cmp / sca_cmp   Finish가 거짓인 프로세스마다 하는 Need ≤ Available 비교(ops.leq, 단락 평가)
  vec_add             끝낸 프로세스 수(Available += Allocation)
  iters               훑기에서 본 칸 수(끝난 프로세스 칸 포함), sweeps 바깥 반복 수
  need_ops            도착 때마다 Need 전체를 다시 계산하는 스칼라 뺄셈: (그때의 프로세스 수) × (자원 종류 수)
처음의 Need 계산(그림 4)은 입력 상태가 Need를 주므로 세지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from bench.policies.banker.base import SafetyPolicy


@dataclass
class WicaksonoResult:
    safe: list                 # 안전 순서(끝낸 순서). error이면 막히기 전까지. 도착한 프로세스의 번호는 처음 프로세스 수부터
    error: bool                # 논문의 'error'(안전 순서를 만들 수 없음)
    passes: int                # 바깥 반복 수
    admitted: list             # [(바깥 반복 번호, 새 프로세스 번호)]
    missed: list               # 받아들이지 못한 도착 [(요청한 바깥 반복 번호, 최대 청구)]
    counts: dict
    n_final: int = 0
    trace: list = field(default_factory=list)


class WicaksonoSweep(SafetyPolicy):
    name = "wicaksono-sweep"

    def run(self, st, ops, arrivals=None, want_trace: bool = False) -> WicaksonoResult:
        m = st.m
        alloc = [list(r) for r in st.alloc]
        maxc = [[a + x for a, x in zip(ar, nr)] for ar, nr in zip(st.alloc, st.need)]
        need = [list(r) for r in st.need]
        avail = list(st.avail)
        n = len(alloc)
        finish = [False] * n
        safe: list = []
        sched = dict(arrivals or {})
        admitted: list = []
        trace: list = []
        passes = 0
        need_ops = 0
        error = False
        while False in finish:
            passes += 1
            ops.tick("sweeps")
            if passes in sched:                      # 바깥 반복의 맨 앞에서만 도착을 확인한다
                row = [int(x) for x in sched.pop(passes)]
                alloc.append([0] * m)
                maxc.append(row)
                n += 1
                need = [[maxc[i][j] - alloc[i][j] for j in range(m)] for i in range(n)]   # countNeed: 전체를 다시 계산
                finish.append(False)
                need_ops += n * m
                ops.tick("need_ops", n * m)
                admitted.append((passes, n - 1))
            stuck = True
            for i in range(n):
                ops.tick()
                if not finish[i] and ops.leq(need[i], avail):
                    before = list(avail) if want_trace else None
                    safe.append(i)
                    ops.vadd(avail, alloc[i])
                    finish[i] = True
                    stuck = False
                    if want_trace:
                        trace.append({"pass": passes, "i": i, "work": before, "avail": list(avail)})
            if stuck:
                error = True
                break
        missed = sorted((k, tuple(r)) for k, r in sched.items())
        counts = {"passes": passes, "need_ops": need_ops, "vec_add": len(safe), "arrivals": len(admitted)}
        return WicaksonoResult(safe, error, passes, admitted, missed, counts, n, trace)

    def is_safe(self, st, ops) -> bool:
        return not self.run(st, ops).error
