"""연산 계측. 정책 구현은 벡터 비교와 벡터 덧셈을 이 객체의 메서드로만 수행한다.

CountingOps는 K2(비교 횟수)를 세는 실행에, PlainOps는 시간을 재는 실행에 쓴다(두 실행을 분리한다. 문서 prereg/RQ6.md §5).
  vec_cmp  벡터 비교(a <= b 성분별) 횟수
  sca_cmp  실제로 수행한 스칼라 비교 횟수(왼쪽부터 비교하다 처음 실패하면 멈춘다)
           모든 성분을 비교하는 구현의 스칼라 횟수는 vec_cmp * m이다
  vec_add  벡터 덧셈·뺄셈 횟수
  iters    정책이 정한 반복 횟수(안쪽 반복 한 번마다 tick으로 센다)
  extra    정책별로 따로 세는 이름 붙은 횟수
"""
from __future__ import annotations


class PlainOps:
    counting = False

    def leq(self, a, b) -> bool:
        for x, y in zip(a, b):
            if x > y:
                return False
        return True

    def vadd(self, w, a) -> None:
        for r, x in enumerate(a):
            w[r] += x

    def vsub(self, w, a) -> None:
        for r, x in enumerate(a):
            w[r] -= x

    def tick(self, name: str = "iters", k: int = 1) -> None:
        pass

    def add_counts(self, sca_cmp: int = 0, vec_add: int = 0, iters: int = 0, **extra: int) -> None:
        """안쪽 반복에서 스칼라 비교를 직접 세는 변형이 마지막에 한꺼번에 알린다. 시간을 재는 실행에서는 아무것도 하지 않는다."""


class CountingOps(PlainOps):
    counting = True

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.vec_cmp = 0
        self.sca_cmp = 0
        self.vec_add = 0
        self.iters = 0
        self.extra: dict[str, int] = {}

    def leq(self, a, b) -> bool:
        self.vec_cmp += 1
        for x, y in zip(a, b):
            self.sca_cmp += 1
            if x > y:
                return False
        return True

    def vadd(self, w, a) -> None:
        self.vec_add += 1
        for r, x in enumerate(a):
            w[r] += x

    def vsub(self, w, a) -> None:
        self.vec_add += 1
        for r, x in enumerate(a):
            w[r] -= x

    def tick(self, name: str = "iters", k: int = 1) -> None:
        if name == "iters":
            self.iters += k
        else:
            self.extra[name] = self.extra.get(name, 0) + k

    def add_counts(self, sca_cmp: int = 0, vec_add: int = 0, iters: int = 0, **extra: int) -> None:
        self.sca_cmp += sca_cmp
        self.vec_add += vec_add
        self.iters += iters
        for key, v in extra.items():
            self.extra[key] = self.extra.get(key, 0) + v

    def snapshot(self) -> dict:
        d = {"vec_cmp": self.vec_cmp, "sca_cmp": self.sca_cmp, "vec_add": self.vec_add, "iters": self.iters}
        d.update(self.extra)
        return d
