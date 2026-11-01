"""뱅커 모델의 정확 오라클 O1 (문서 02 SI-2, 모델 명세 §3.5).

뱅커 모델의 상태는 (total, alloc, maxc)이고 need = maxc - alloc이다.
  total[r]    자원 종류 r의 총 단위 수
  alloc[p][r] 프로세스 p가 쥔 r의 단위 수
  maxc[p][r]  프로세스 p가 선언한 r의 최대 청구량
유효한 상태: 0 <= alloc <= maxc <= total, 종류마다 sum_p alloc[p][r] <= total[r].

안전 상태: need를 차례로 만족시키며 모든 프로세스를 끝낼 수 있는 순서가 있는 상태(F8).
세 가지 독립 구현을 둔다. 서로 다른 코드 경로이며 소규모 전수 범위에서 일치해야 한다.
  safe_oracle  모델 명세 §3.5. need가 0이 아닌 프로세스의 요청을 {need}로 둔 SM 상태 s_max에
               교착 집합이 없으면 안전. sm.py의 축소(reduction)를 쓴다.
  safe_perm    프로세스 완료 순서 n!개를 하나씩 시뮬레이션한다(정의를 그대로 읽은 전수 탐색).
  safe_dp      완료한 프로세스의 부분집합 위의 도달 가능성 DP. 가용량은 완료한 집합에만 의존한다.
요청 판정 request_outcome은 교재식 자원 요청 알고리즘의 의미를 오라클로 옮긴 것이다.
  ERROR  요청이 남은 필요량(need)을 넘는다(최대 청구 초과)
  WAIT   요청이 현재 가용량을 넘는다(안전성 판정 이전의 대기)
  GRANT  요청을 허가한 뒤의 상태가 안전하다
  DENY   요청을 허가한 뒤의 상태가 불안전하다(요청자는 대기)

한계: 이 오라클은 모델 명세의 정의(A1–A4)를 그대로 따른다. 단일 종류에서 F8의 동치(불안전 <=>
두 집단 분할 조건)와의 대조는 F8 원문을 다시 확인한 뒤에 한다(문서 02 SI-2 O1). 일치는 정의
내부의 일관성이며 문헌의 안전 상태 정의와 같다는 뜻이 아니다.
"""
from __future__ import annotations

import itertools
import os
import sys
from dataclasses import dataclass

# -I(격리 모드)로 실행해도 같은 폴더의 sm.py를 찾도록 이 파일의 폴더를 경로에 넣는다.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sm  # noqa: E402
from sm import Inst  # noqa: E402

Vec = tuple[int, ...]


@dataclass(frozen=True)
class Banker:
    total: Vec
    alloc: tuple[Vec, ...]
    maxc: tuple[Vec, ...]

    def __post_init__(self) -> None:
        problem = validity_problem(self)
        if problem:
            raise ValueError(problem)

    @property
    def n(self) -> int:
        return len(self.alloc)

    @property
    def m(self) -> int:
        return len(self.total)

    def need(self) -> tuple[Vec, ...]:
        return tuple(tuple(self.maxc[p][r] - self.alloc[p][r] for r in range(self.m)) for p in range(self.n))

    def avail(self) -> Vec:
        return tuple(self.total[r] - sum(self.alloc[p][r] for p in range(self.n)) for r in range(self.m))


def validity_problem(b: Banker) -> str | None:
    """유효하지 않으면 이유를, 유효하면 None을 돌려준다(생성자와 열거기가 같은 규칙을 쓴다)."""
    m = len(b.total)
    if m == 0 or any(t < 1 for t in b.total):
        return "total은 양수여야 한다"
    if len(b.alloc) != len(b.maxc):
        return "alloc과 maxc의 프로세스 수가 다르다"
    for p in range(len(b.alloc)):
        if len(b.alloc[p]) != m or len(b.maxc[p]) != m:
            return f"프로세스 {p}의 벡터 길이가 종류 수와 다르다"
        for r in range(m):
            if not (0 <= b.alloc[p][r] <= b.maxc[p][r] <= b.total[r]):
                return f"프로세스 {p}, 종류 {r}: 0 <= alloc <= maxc <= total이 아니다"
    for r in range(m):
        if sum(b.alloc[p][r] for p in range(len(b.alloc))) > b.total[r]:
            return f"종류 {r}의 보유 합이 total을 넘는다"
    return None


# ---------------------------------------------------------------- 안전성 판정(세 가지 독립 구현)

def to_sm(b: Banker) -> Inst:
    """모델 명세 §3.5의 s_max. need가 0이 아닌 프로세스의 요청은 {need}, need가 0이면 요청 없음."""
    need = b.need()
    alts = tuple(frozenset({need[p]}) if any(need[p]) else frozenset() for p in range(b.n))
    return Inst(cap=b.total, alloc=b.alloc, alts=alts)


def safe_oracle(b: Banker) -> bool:
    return not sm.has_deadlock(to_sm(b))


def unfinishable(b: Banker) -> frozenset:
    """끝낼 수 없는 프로세스의 집합(= s_max의 가장 큰 교착 집합). 안전이면 공집합."""
    return sm.greatest_deadlock_set(to_sm(b))


def safe_perm(b: Banker) -> tuple[bool, tuple[int, ...] | None]:
    """완료 순서 n!개를 모두 시뮬레이션한다. 안전이면 (True, 안전 순서), 아니면 (False, None)."""
    need, avail, alloc, m = b.need(), b.avail(), b.alloc, b.m
    for order in itertools.permutations(range(b.n)):
        work = list(avail)
        ok = True
        for p in order:
            if any(need[p][r] > work[r] for r in range(m)):
                ok = False
                break
            for r in range(m):
                work[r] += alloc[p][r]
        if ok:
            return True, order
    return False, None


def safe_dp(b: Banker) -> bool:
    """완료한 집합 S의 가용량은 avail + A(S)로 S에만 의존한다. 전체 집합에 도달할 수 있는가."""
    n, m = b.n, b.m
    need, avail, alloc = b.need(), b.avail(), b.alloc
    full = (1 << n) - 1
    reach = bytearray(1 << n)
    reach[0] = 1
    for mask in range(1 << n):
        if not reach[mask]:
            continue
        work = [avail[r] + sum(alloc[p][r] for p in range(n) if mask >> p & 1) for r in range(m)]
        for p in range(n):
            if mask >> p & 1:
                continue
            if all(need[p][r] <= work[r] for r in range(m)):
                reach[mask | 1 << p] = 1
    return bool(reach[full])


def check_order(b: Banker, order: tuple[int, ...]) -> bool:
    """order가 b의 안전 순서인가(모든 프로세스를 한 번씩, 차례로 끝낼 수 있는가)."""
    if sorted(order) != list(range(b.n)):
        return False
    need, alloc = b.need(), b.alloc
    work = list(b.avail())
    for p in order:
        if any(need[p][r] > work[r] for r in range(b.m)):
            return False
        for r in range(b.m):
            work[r] += alloc[p][r]
    return True


# ---------------------------------------------------------------- 요청 판정

ERROR, WAIT, GRANT, DENY = "ERROR", "WAIT", "GRANT", "DENY"


def apply_request(b: Banker, i: int, req: Vec) -> Banker:
    """프로세스 i가 req를 얻은 뒤의 상태(보유 증가). 최대 청구는 그대로다."""
    alloc = tuple(
        tuple(b.alloc[p][r] + (req[r] if p == i else 0) for r in range(b.m)) for p in range(b.n)
    )
    return Banker(b.total, alloc, b.maxc)


def request_outcome(b: Banker, i: int, req: Vec) -> str:
    need, avail = b.need(), b.avail()
    if any(req[r] > need[i][r] for r in range(b.m)):
        return ERROR
    if any(req[r] > avail[r] for r in range(b.m)):
        return WAIT
    return GRANT if safe_oracle(apply_request(b, i, req)) else DENY


def request_vectors(b: Banker, i: int, nonzero: bool = True):
    """허가 후보가 되는 요청 벡터: 0 <= req <= min(need_i, avail). 기본은 영벡터 제외."""
    need, avail = b.need(), b.avail()
    ranges = [range(min(need[i][r], avail[r]) + 1) for r in range(b.m)]
    for v in itertools.product(*ranges):
        if nonzero and not any(v):
            continue
        yield v


# ---------------------------------------------------------------- 소규모 전수 열거

def _per_type(n: int, total: int):
    """한 종류에서 (alloc 열, maxc 열)의 모든 유효한 조합. 0 <= a_p <= x_p <= total, sum a <= total."""
    pairs = [(a, x) for x in range(total + 1) for a in range(x + 1)]
    for combo in itertools.product(pairs, repeat=n):
        if sum(a for a, _ in combo) <= total:
            yield tuple(a for a, _ in combo), tuple(x for _, x in combo)


def all_states(n: int, total: Vec):
    """프로세스 n개, 총량 total인 모든 유효한 뱅커 상태."""
    per = [list(_per_type(n, t)) for t in total]
    m = len(total)
    for combo in itertools.product(*per):
        alloc = tuple(tuple(combo[r][0][p] for r in range(m)) for p in range(n))
        maxc = tuple(tuple(combo[r][1][p] for r in range(m)) for p in range(n))
        yield Banker(total, alloc, maxc)


def count_states(n: int, total: Vec) -> int:
    c = 1
    for t in total:
        c *= sum(1 for _ in _per_type(n, t))
    return c


# ---------------------------------------------------------------- 표기

def show(b: Banker) -> str:
    rows = []
    need = b.need()
    for p in range(b.n):
        rows.append(f"P{p}: alloc={list(b.alloc[p])} max={list(b.maxc[p])} need={list(need[p])}")
    return f"total={list(b.total)} avail={list(b.avail())}\n" + "\n".join(rows)
