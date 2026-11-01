"""락 프로그램 오라클 O2(oracle/locks.py)의 자체 검증.
실행: python3 -I oracle/check_locks.py formal/rq3/o2-check-results.md

  1. 손으로 답을 아는 예제(AB/BA, 같은 순서, 세 락 순환, 식사하는 철학자 3명, 손잡기)
  2. 독립 구현과의 일치: 메모를 쓰는 safe()와 완전 탐색 safe_bruteforce, 스냅샷 모델의 교착 집합과 정의대로 쓴
     possible_deadlock_bruteforce. 모든 상태(소규모 범위 전수 또는 고정 시드 표본)에서 비교한다.
  3. 관계: finished => safe, stuck => 교착 집합 있음, not safe => possible_deadlock, safe인 상태의 어떤 이동은 safe로 간다
  4. 변이체: O2를 일부러 틀리게 바꿔 이 검사가 잡는지
AI(Claude)가 쓴 초안이며 사람의 검토 전이다. 일치는 정의 내부의 일관성이다.
"""
from __future__ import annotations

import itertools
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "oracle"))
sys.path.insert(0, ROOT)

import locks as o2  # noqa: E402
from locks import LockProgSystem, program  # noqa: E402
from bench import seeds  # noqa: E402


def thread_programs(L, kmax, rels):
    s = set()
    for k in range(1, kmax + 1):
        for order in itertools.permutations(range(L), k):
            for r in rels:
                s.add(program(order, r))
    return sorted(s)


def known_answers(checks):
    ab = LockProgSystem([program((0, 1)), program((1, 0))])
    checks.append(("AB/BA: 시작 상태는 안전(교착 없는 스케줄이 있음)", ab.safe((0, 0)), ""))
    checks.append(("AB/BA: 시작 상태에서 교착이 가능", ab.possible_deadlock((0, 0)), ""))
    checks.append(("AB/BA: 각자 첫 락을 쥔 상태는 전체 교착(stuck)이고 불안전", ab.stuck((1, 1)) and not ab.safe((1, 1)), ""))
    checks.append(("AB/BA: T1이 첫 락을 얻는 요청은 T0이 A0를 쥔 상태에서 오라클 허용 불가",
                   not ab.request_permissible((1, 0), 1), ""))
    checks.append(("AB/BA: T0의 첫 요청은 시작 상태에서 허용 가능", ab.request_permissible((0, 0), 0), ""))
    same = LockProgSystem([program((0, 1)), program((0, 1))])
    checks.append(("같은 순서: 어떤 상태에서도 교착 불가", not same.possible_deadlock((0, 0)), ""))
    cyc = LockProgSystem([program((0, 1)), program((1, 2)), program((2, 0))])
    checks.append(("세 락 순환: 교착이 가능하고 시작은 안전", cyc.possible_deadlock((0, 0, 0)) and cyc.safe((0, 0, 0)), ""))
    checks.append(("세 락 순환: 각자 첫 락을 쥔 상태는 불안전", not cyc.safe((1, 1, 1)), ""))
    phil = LockProgSystem([program((i, (i + 1) % 3)) for i in range(3)])
    checks.append(("식사하는 철학자 3명: 모두 왼쪽 포크를 쥔 상태는 불안전, 시작은 교착 가능",
                   not phil.safe((1, 1, 1)) and phil.possible_deadlock((0, 0, 0)), ""))
    phil_ord = LockProgSystem([program(tuple(sorted((i, (i + 1) % 3)))) for i in range(3)])
    checks.append(("식사하는 철학자 3명(락 번호 순서로 획득): 교착 불가", not phil_ord.possible_deadlock((0, 0, 0)), ""))
    hoh = LockProgSystem([program((0, 1, 2), "hoh"), program((2, 1, 0), "hoh")])
    checks.append(("손잡기 반대 방향: 교착 가능", hoh.possible_deadlock((0, 0)), ""))
    bad = []
    for prog in ([("A", 0), ("A", 0), ("R", 0)], [("R", 0)], [("A", 0)], [("X", 0)]):
        try:
            LockProgSystem([tuple(prog)])
            bad.append(prog)
        except ValueError:
            pass
    checks.append(("잘못된 프로그램 4가지(중복 획득, 쥐지 않은 반납, 반납 누락, 모르는 연산)를 거부", len(bad) == 0, str(bad)))
    # 자기 자신이 쥔 락은 다른 스레드의 요청을 막는다
    one = LockProgSystem([program((0,)), program((0,))])
    checks.append(("같은 락 하나: T0이 쥐면 T1은 이동 불가(이동 목록에 T1 없음)",
                   [t for t, _ in one.moves((1, 0))] == [0], ""))


def cross_checks(checks, scopes):
    for (name, T, L, kmax, rels, sample, seed) in scopes:
        progs = thread_programs(L, kmax, rels)
        if sample:
            rng = random.Random(seeds.derive("rq3-o2check", name))
            wls = [tuple(rng.choice(progs) for _ in range(T)) for _ in range(sample)]
        else:
            wls = list(itertools.product(progs, repeat=T))
        nstates = mism_safe = mism_dead = mism_set = rel_fail = rel_fail_stuck = 0
        nsafe = nunsafe = ndead = 0
        for w in wls:
            S = LockProgSystem(w)
            for pcs in S.all_states():
                nstates += 1
                s1 = S.safe(pcs)
                s2 = o2.safe_bruteforce(w, pcs)
                if s1 != s2:
                    mism_safe += 1
                d1 = S.possible_deadlock(pcs)
                d2 = o2.possible_deadlock_bruteforce(w, pcs)
                if d1 != d2:
                    mism_dead += 1
                if S.has_deadlock_set(pcs) != o2.deadlock_set_bruteforce(w, pcs):
                    mism_set += 1
                if d1 != any(S.stuck(x) for x in S.reachable(pcs)):
                    rel_fail_stuck += 1
                nsafe += s1
                nunsafe += (not s1)
                ndead += d1
                ok = True
                if S.finished(pcs) and not s1:
                    ok = False
                if S.stuck(pcs) and not (S.has_deadlock_set(pcs) and not s1):
                    ok = False
                if (not s1) and not d1:
                    ok = False
                if s1 and not S.finished(pcs):
                    if not any(S.safe(n) for _, n in S.moves(pcs)):
                        ok = False
                if not ok:
                    rel_fail += 1
        checks.append((f"{name}: safe(메모) = safe(완전 탐색), 상태 {nstates:,}개 (안전 {nsafe:,}, 불안전 {nunsafe:,})", mism_safe == 0, f"불일치 {mism_safe}"))
        checks.append((f"{name}: possible_deadlock(SM 교착 집합) = 정의대로 쓴 완전 탐색 (가능 {ndead:,}개)", mism_dead == 0, f"불일치 {mism_dead}"))
        checks.append((f"{name}: 관계(끝남=>안전, 전체 교착=>교착 집합 있음이고 불안전, 불안전=>교착 가능, 안전이면 안전한 이동)", rel_fail == 0, f"위반 {rel_fail}"))
        checks.append((f"{name}: has_deadlock_set(SM 축소) = 정의대로 쓴 고정점 계산 (모든 상태)", mism_set == 0, f"불일치 {mism_set}"))
        checks.append((f"{name}: possible_deadlock <=> 도달 가능한 전체 교착(stuck) 상태가 있음", rel_fail_stuck == 0, f"위반 {rel_fail_stuck}"))
        checks.append((f"{name}: 비공허(안전, 불안전, 교착 가능 상태가 모두 있음)", nsafe > 0 and nunsafe > 0 and ndead > 0, ""))


def mutant_checks(checks):
    """O2를 틀리게 바꿔서 교차 검증이 잡는지 본다."""
    progs = thread_programs(3, 2, ("nested", "fifo"))
    rng = random.Random(seeds.derive("rq3-o2mut"))
    wls = [tuple(rng.choice(progs) for _ in range(3)) for _ in range(150)]

    def run(make):
        for w in wls:
            S = make(w)
            for pcs in S.all_states():
                if S.safe(pcs) != o2.safe_bruteforce(w, pcs):
                    return True
                if S.possible_deadlock(pcs) != o2.possible_deadlock_bruteforce(w, pcs):
                    return True
                if S.has_deadlock_set(pcs) != o2.deadlock_set_bruteforce(w, pcs):
                    return True
        return False

    class NoBlock(LockProgSystem):          # 획득이 막히지 않음(배타성 무시)
        def moves(self, pcs):
            out = []
            for t in range(self.T):
                if pcs[t] < self.end[t]:
                    out.append((t, pcs[:t] + (pcs[t] + 1,) + pcs[t + 1:]))
            return out

    class SelfBlock(LockProgSystem):        # 자기가 쥔 락도 다른 스레드를 막지 못함(반납을 무시)
        def held_masks(self, pcs):
            return [self.held_mask[t][pcs[t]] if t == 0 else 0 for t in range(self.T)]

    class DeadOnlyStuck(LockProgSystem):    # 교착 집합을 전체 교착(이동 없음)으로만 인정
        def has_deadlock_set(self, pcs):
            return self.stuck(tuple(pcs))

    class SafeIsReach(LockProgSystem):      # safe를 '교착이 불가능'으로 잘못 정의
        def safe(self, pcs):
            return not self.possible_deadlock(pcs)

    checks.append(("변이체 NoBlock(배타성 무시) 검출", run(NoBlock), ""))
    checks.append(("변이체 SelfBlock(스레드 0만 락을 쥔다고 계산) 검출", run(SelfBlock), ""))
    checks.append(("변이체 DeadOnlyStuck(부분 교착을 놓침) 검출", run(DeadOnlyStuck), ""))
    checks.append(("변이체 SafeIsReach(안전을 교착 불가로 정의) 검출", run(SafeIsReach), ""))


def main(out_path):
    checks: list = []
    known_answers(checks)
    scopes = [
        ("T=2, 락 3개, 획득 1–3, nested·fifo·hoh 전수", 2, 3, 3, ("nested", "fifo", "hoh"), 0, 0),
        ("T=3, 락 3개, 획득 1–2, nested·fifo 전수", 3, 3, 2, ("nested", "fifo"), 0, 0),
        ("T=3, 락 4개, 획득 1–3, nested·hoh 표본 300", 3, 4, 3, ("nested", "hoh"), 300, 0),
    ]
    cross_checks(checks, scopes)
    mutant_checks(checks)
    nfail = sum(1 for c in checks if not c[1])
    lines = ["# 락 프로그램 오라클 O2 자체 검증 결과 (AI 초안, 사람 검토 전)", "",
             "재현: `python3 -I oracle/check_locks.py formal/rq3/o2-check-results.md`", "",
             "정의와 한계는 `oracle/locks.py` 머리말에 있다. 일치는 정의 내부의 일관성이며 문헌의 안전 정의와 같다는 뜻이 아니다. "
             "완전 탐색은 상태 수가 큰 곳에서 지수 시간이라 소규모에서만 돌렸다.", "",
             f"검사 {len(checks)}개, 실패 {nfail}개.", "", "| 검사 | 결과 | 비고 |", "|---|---|---|"]
    for name, ok, detail in checks:
        lines.append(f"| {name} | {'통과' if ok else '**실패**'} | {detail} |")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"검사 {len(checks)}개, 실패 {nfail}개")
    for name, ok, detail in checks:
        if not ok:
            print("실패:", name, detail)
    return nfail


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "formal", "rq3", "o2-check-results.md")
    sys.exit(1 if main(out) else 0)
