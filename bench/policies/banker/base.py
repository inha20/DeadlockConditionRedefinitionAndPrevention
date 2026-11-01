"""뱅커 계열 정책의 인터페이스와 교재식 자원 요청 알고리즘.

is_safe(st, ops)         현재 상태가 안전한가(안전성 알고리즘)
request(st, i, req, ops) 프로세스 i의 요청 req를 어떻게 처리하는가. st는 호출 뒤에도 그대로다.

request의 기본 구현은 교재식 자원 요청 알고리즘이다.
  1. req <= need[i]가 아니면 ERROR(최대 청구 초과)
  2. req <= avail이 아니면 WAIT(가용량 부족)
  3. 허가한 것으로 가정하고 안전성 알고리즘을 돌려 안전이면 GRANT, 아니면 DENY
변형이 요청 처리 절차를 다르게 정의하면 그 변형이 request를 덮어쓴다.
"""
from __future__ import annotations

ERROR, WAIT, GRANT, DENY = "ERROR", "WAIT", "GRANT", "DENY"


class SafetyPolicy:
    name = "base"

    def is_safe(self, st, ops) -> bool:  # pragma: no cover - 인터페이스
        raise NotImplementedError

    def request(self, st, i: int, req, ops) -> str:
        if not ops.leq(req, st.need[i]):
            return ERROR
        if not ops.leq(req, st.avail):
            return WAIT
        # 허가한 것으로 가정한다(교재 3단계). 가정한 변경은 호출이 끝나면 계측 없이 되돌린다.
        ops.vsub(st.avail, req)
        ops.vadd(st.alloc[i], req)
        ops.vsub(st.need[i], req)
        try:
            safe = self.is_safe(st, ops)
        finally:
            for r, x in enumerate(req):
                st.avail[r] += x
                st.alloc[i][r] -= x
                st.need[i][r] += x
        return GRANT if safe else DENY
