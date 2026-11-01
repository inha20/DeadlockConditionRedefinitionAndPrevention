"""하네스용 뱅커 상태. 큰 입력을 다루기 쉽게 리스트로 둔다. 오라클의 불변 상태와 서로 바꿀 수 있다."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BState:
    total: list
    alloc: list   # n x m
    need: list    # n x m
    avail: list   # m (보유로부터 계산해 저장한다. 교재식 알고리즘의 Available)

    @property
    def n(self) -> int:
        return len(self.alloc)

    @property
    def m(self) -> int:
        return len(self.total)

    @staticmethod
    def make(total, alloc, need) -> "BState":
        total = [int(x) for x in total]
        alloc = [[int(x) for x in row] for row in alloc]
        need = [[int(x) for x in row] for row in need]
        m = len(total)
        avail = [total[r] - sum(row[r] for row in alloc) for r in range(m)]
        return BState(total, alloc, need, avail)

    def copy(self) -> "BState":
        return BState(list(self.total), [list(r) for r in self.alloc], [list(r) for r in self.need], list(self.avail))

    def maxc(self):
        return [[self.alloc[p][r] + self.need[p][r] for r in range(self.m)] for p in range(self.n)]

    def to_oracle(self):
        """오라클의 불변 상태로. 유효하지 않으면 ValueError."""
        from oracle.banker import Banker  # noqa: PLC0415
        return Banker(tuple(self.total), tuple(tuple(r) for r in self.alloc), tuple(tuple(r) for r in self.maxc()))

    @staticmethod
    def from_oracle(b) -> "BState":
        return BState.make(b.total, b.alloc, b.need())
