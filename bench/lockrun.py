"""락 정책의 무작위 스케줄 실행기 (RQ3, 동결 전 측정 도구).

소규모 전수 검사(bench/lockexplore.py)가 닿지 않는 큰 크기(스레드 16개, 락 32개 등)에서 같은 정책 코드의 구현 무결성을
점검하고, 합성 트레이스(traces/FORMAT.md)를 만든다. 시간 모델이 없다. 매 걸음 실행 가능한 스레드 중 하나를 균등하게
골라 진행한다(탐지 정책은 탐지 동작도 후보에 넣고, 다른 동작이 없으면 탐지를 한다).

점검(check=True): 걸음마다 정책 불변식, 교착 집합(탐지 정책 제외), 멈춤. 스텝 상한을 넘으면 'cap'으로 끝낸다.
이것은 성능 측정이 아니다. 정책의 순위나 비용에 대해 아무것도 말하지 않는다.
"""
from __future__ import annotations

import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "oracle"))

import sm  # noqa: E402
from bench.lockexplore import apply, enabled  # noqa: E402
from bench.policies.lock.system import BLOCKED, DONE, FAILED, RUN, START, LockTable  # noqa: E402


def run_random(progs, pol, seed, nlocks, max_steps=500000, check=True, log=None, detect_prob=0.2):
    """무작위 스케줄 한 번. 결과 dict를 돌려준다. log가 리스트이면 트레이스 이벤트를 덧붙인다."""
    tb = LockTable(progs, nlocks=nlocks)
    rng = random.Random(seed)
    res = {"status": "done", "steps": 0, "aborts": 0, "fails": 0, "deadlock_steps": 0, "inv_violations": 0,
           "deadlock_violations": 0, "first_msg": None, "max_blocked": 0, "requests": 0, "conflicts": 0}
    attempt = [0] * tb.T
    seq = [0]

    def emit(th, op, lock=None, **extra):
        if log is None:
            return
        rec = {"seq": seq[0], "ts": res["steps"], "th": th, "task": f"{th}.0", "attempt": attempt[th], "op": op}
        if lock is not None:
            rec["lock"] = lock
            rec["cls"] = lock
            rec["mode"] = "X"
        rec.update(extra)
        log.append(rec)
        seq[0] += 1

    while not tb.terminal():
        if res["steps"] >= max_steps:
            res["status"] = "cap"
            break
        acts = enabled(tb, pol)
        if not acts:
            res["status"] = "stall"
            break
        steps_ = [a for a in acts if a[0] == "step"]
        if any(a[0] == "detect" for a in acts) and (not steps_ or rng.random() < detect_prob):
            act = ("detect", None)
        else:
            act = rng.choice(steps_)
        pre_phase = list(tb.phase)
        pre_holder = list(tb.holder)
        t = act[1]
        op = tb.next_op(t) if act[0] == "step" and tb.phase[t] == RUN else None
        if op is not None and op[0] == "A" and not (pol.batch and tb.holder[op[1]] == t):
            res["requests"] += 1                       # 락 요청 수와, 요청 때 락이 다른 스레드에게 쥐어져 있던 수(충돌)
            if tb.holder[op[1]] is not None:
                res["conflicts"] += 1
        res["steps"] += 1
        aborted = apply(tb, pol, act)
        # ---- 이벤트 기록
        if log is not None:
            if act[0] == "detect":
                for v, why in aborted:
                    emit(v, "ABORT", why=why)
                    attempt[v] += 1
            else:
                if pre_phase[t] == START:
                    emit(t, "BEGIN")
                elif op is None and tb.phase[t] == DONE:
                    emit(t, "END")
                elif op is not None and op[0] == "R":
                    emit(t, "RELEASE", op[1])
                elif op is not None and op[0] == "A" and pre_holder[op[1]] != t:
                    emit(t, "REQUEST", op[1])
                for v, why in aborted:
                    emit(v, "ABORT" if why != "fail" else "FAIL", why=why)
                    if why != "fail":
                        attempt[v] += 1
                if tb.phase[t] == BLOCKED and pre_phase[t] != BLOCKED:
                    emit(t, "WAIT", sorted(tb.want[t])[0] if len(tb.want[t]) == 1 else None,
                         locks=sorted(tb.want[t]))
            for l in range(tb.L):
                if tb.holder[l] is not None and pre_holder[l] != tb.holder[l]:
                    emit(tb.holder[l], "ACQUIRE", l)
        res["aborts"] += sum(1 for _, why in aborted if why != "fail")
        res["fails"] += sum(1 for _, why in aborted if why == "fail")
        res["max_blocked"] = max(res["max_blocked"], len(tb.blocked))
        if check:
            msg = pol.invariant(tb)
            if msg:
                res["inv_violations"] += 1
                res["first_msg"] = res["first_msg"] or msg
            if tb.blocked and sm.has_deadlock(tb.to_sm()):
                res["deadlock_steps"] += 1
                if not pol.detects:
                    res["deadlock_violations"] += 1
                    res["first_msg"] = res["first_msg"] or ("교착 집합: " + tb.show())
    # 끝난 상태 기록
    if res["status"] == "done":
        res["done"] = sum(1 for p in tb.phase if p == DONE)
        res["failed"] = sum(1 for p in tb.phase if p == FAILED)
    return res
