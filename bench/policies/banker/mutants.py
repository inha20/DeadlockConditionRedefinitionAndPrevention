"""고의로 틀린 정책(변이체). 점검 도구가 틀린 구현을 실제로 잡아내는지(비공허성) 보려고 만든다.
결과 분석에는 쓰지 않는다. 오라클 점검(oracle/check_banker.py의 변이체)과 같은 취지다.

  mut-always-safe     항상 안전이라고 답한다            비보수적(FS > 0이어야 한다)
  mut-always-unsafe   항상 불안전이라고 답한다          보수적(FU > 0이어야 한다)
  mut-strict          필요량 < 작업량(등호 제외)으로 비교 보수적
  mut-skip-last       마지막 자원 종류를 비교에서 뺀다   비보수적
  mut-no-restore      request가 가정한 변경을 되돌리지 않는다   러너의 상태 복원 점검에 걸려야 한다
"""
from __future__ import annotations

from bench.policies.banker.base import SafetyPolicy


class MutAlwaysSafe(SafetyPolicy):
    name = "mut-always-safe"

    def is_safe(self, st, ops) -> bool:
        return True


class MutAlwaysUnsafe(SafetyPolicy):
    name = "mut-always-unsafe"

    def is_safe(self, st, ops) -> bool:
        return False


class _Closure(SafetyPolicy):
    """교재식 훑기 이어서 하기에서 비교 한 줄만 바꾼 변이체의 바탕."""

    def runnable(self, need_i, work, ops) -> bool:  # pragma: no cover
        raise NotImplementedError

    def is_safe(self, st, ops) -> bool:
        n = st.n
        work = list(st.avail)
        finish = [False] * n
        remaining = n
        progress = True
        while progress and remaining:
            progress = False
            for i in range(n):
                if not finish[i] and self.runnable(st.need[i], work, ops):
                    ops.vadd(work, st.alloc[i])
                    finish[i] = True
                    remaining -= 1
                    progress = True
        return remaining == 0


class MutStrict(_Closure):
    name = "mut-strict"

    def runnable(self, need_i, work, ops) -> bool:
        return ops.leq([x + 1 for x in need_i], work)


class MutSkipLast(_Closure):
    name = "mut-skip-last"

    def runnable(self, need_i, work, ops) -> bool:
        if len(need_i) == 1:
            return True
        return ops.leq(need_i[:-1], work[:-1])


class MutNoRestore(SafetyPolicy):
    name = "mut-no-restore"

    def is_safe(self, st, ops) -> bool:
        from bench.policies.banker.textbook import TextbookSweep  # noqa: PLC0415
        return TextbookSweep().is_safe(st, ops)

    def request(self, st, i, req, ops) -> str:
        out = super().request(st, i, req, ops)
        st.avail[0] -= 1        # 되돌리지 않는 결함
        return out


MUTANTS = {cls.name: cls for cls in (MutAlwaysSafe, MutAlwaysUnsafe, MutStrict, MutSkipLast, MutNoRestore)}
