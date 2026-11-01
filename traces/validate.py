"""락 트레이스 형식 검증기 (traces/FORMAT.md v0.1).
실행: python3 -I traces/validate.py <파일.jsonl> [...]
표준 라이브러리만 쓴다. 오류가 하나라도 있으면 종료 코드 1.
AI(Claude)가 쓴 초안이며 사람의 검토 전이다.
"""
from __future__ import annotations

import json
import sys

FORMAT = "rq3-trace-v0.1"
SOURCES = {"synthetic", "userspace", "kernel"}
CLOCKS = {"logical", "ns"}
OPS = {"BEGIN", "REQUEST", "WAIT", "ACQUIRE", "RELEASE", "ABORT", "FAIL", "END"}
LOCK_OPS = {"REQUEST", "ACQUIRE", "RELEASE"}      # lock, cls, mode가 필수인 연산(WAIT는 batch일 때 lock이 없을 수 있음)
MODES = {"X", "S"}


class Thread:
    __slots__ = ("state", "task", "attempt", "pending", "wait_set", "batch_ok", "held")

    def __init__(self):
        self.state = "IDLE"          # IDLE, RUN, REQ, WAIT, START
        self.task = None
        self.attempt = 0
        self.pending = None          # REQ 상태에서 요청한 락
        self.wait_set = set()        # WAIT 상태에서 기다리는 락(일괄이면 여럿)
        self.batch_ok = False
        self.held = set()


def validate_lines(lines):
    errors: list[str] = []
    warnings: list[str] = []
    stats = {"events": 0, "ops": {}, "threads": 0, "tasks_ended": 0, "tasks_failed": 0, "aborts": 0, "locks": 0, "classes": 0}

    def err(i, msg):
        errors.append(f"줄 {i}: {msg}")

    it = iter(enumerate(lines, 1))
    try:
        i, first = next(it)
    except StopIteration:
        return ["빈 파일"], warnings, stats
    try:
        head = json.loads(first)
    except json.JSONDecodeError as e:
        return [f"줄 1: 머리 레코드가 JSON이 아님({e})"], warnings, stats
    if head.get("trace_format") != FORMAT:
        err(1, f"trace_format이 {FORMAT!r}이 아님: {head.get('trace_format')!r}")
    if head.get("source") not in SOURCES:
        err(1, f"source가 {sorted(SOURCES)} 중 하나가 아님: {head.get('source')!r}")
    if head.get("clock") not in CLOCKS:
        err(1, f"clock이 {sorted(CLOCKS)} 중 하나가 아님: {head.get('clock')!r}")
    if not isinstance(head.get("generator"), str) or not head.get("generator"):
        err(1, "generator가 비어 있거나 문자열이 아님")
    nth = head.get("threads")
    if not isinstance(nth, int) or nth <= 0:
        err(1, "threads가 양의 정수가 아님")
        nth = 0
    stats["threads"] = nth

    threads = [Thread() for _ in range(nth)]
    holder: dict = {}                 # lock -> th
    lock_cls: dict = {}
    expect_seq = 0
    last_ts = None
    for i, line in it:
        if not line.strip():
            err(i, "빈 줄")
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError as e:
            err(i, f"JSON이 아님({e})")
            continue
        stats["events"] += 1
        # ---- 필드
        ok = True
        for f, typ in (("seq", int), ("ts", (int, float)), ("th", int), ("task", str), ("attempt", int), ("op", str)):
            if f not in r or isinstance(r[f], bool) or not isinstance(r[f], typ):
                err(i, f"필수 필드 {f}가 없거나 형이 틀림")
                ok = False
        if not ok:
            continue
        op, th = r["op"], r["th"]
        if op not in OPS:
            err(i, f"알 수 없는 op {op!r}")
            continue
        stats["ops"][op] = stats["ops"].get(op, 0) + 1
        if r["seq"] != expect_seq:
            err(i, f"seq가 {expect_seq}이어야 하는데 {r['seq']}")
        expect_seq = r["seq"] + 1
        if last_ts is not None and r["ts"] < last_ts:
            err(i, f"ts가 줄어듦({last_ts} -> {r['ts']})")
        last_ts = r["ts"]
        if not (0 <= th < nth):
            err(i, f"th={th}가 범위 밖")
            continue
        lock = r.get("lock")
        if op in LOCK_OPS or (op == "WAIT" and "locks" not in r):
            if not isinstance(lock, int) or isinstance(lock, bool):
                err(i, f"{op}에 lock이 없거나 정수가 아님")
                continue
            if not isinstance(r.get("cls"), int) or isinstance(r.get("cls"), bool):
                err(i, f"{op}에 cls가 없거나 정수가 아님")
                continue
            if r.get("mode") not in MODES:
                err(i, f"{op}에 mode가 없거나 {sorted(MODES)}가 아님")
                continue
            if lock_cls.setdefault(lock, r["cls"]) != r["cls"]:
                err(i, f"락 {lock}의 cls가 바뀜({lock_cls[lock]} -> {r['cls']})")
        if "locks" in r and not (isinstance(r["locks"], list) and all(isinstance(x, int) for x in r["locks"])):
            err(i, "locks가 정수 목록이 아님")
            continue
        T = threads[th]
        # ---- 상태 기계
        if op == "BEGIN":
            if T.state == "IDLE":
                if r["attempt"] != 0:
                    err(i, f"새 작업의 첫 시도인데 attempt={r['attempt']}")
            elif T.state == "START":
                if r["task"] != T.task or r["attempt"] != T.attempt + 1:
                    err(i, f"중단 뒤 재시작이 같은 작업의 attempt+1이 아님(task {T.task!r}→{r['task']!r}, attempt {T.attempt}→{r['attempt']})")
            else:
                err(i, f"{T.state} 상태에서 BEGIN")
            T.state, T.task, T.attempt, T.batch_ok = "RUN", r["task"], r["attempt"], True
            continue
        if T.state in ("IDLE", "START"):
            err(i, f"BEGIN 없이 {op}(상태 {T.state})")
            continue
        if r["task"] != T.task or r["attempt"] != T.attempt:
            err(i, f"task/attempt가 현재 시도와 다름({r['task']!r}/{r['attempt']} vs {T.task!r}/{T.attempt})")
        if op == "REQUEST":
            if T.state != "RUN":
                err(i, f"{T.state} 상태에서 REQUEST")
            if lock in T.held:
                err(i, f"이미 쥔 락 {lock}을 다시 요청(재진입은 형식에 없음)")
            T.state, T.pending, T.batch_ok = "REQ", lock, False
        elif op == "WAIT":
            if T.state == "REQ":
                if lock != T.pending:
                    err(i, f"요청한 락 {T.pending}이 아닌 {lock}에서 WAIT")
                T.wait_set = {T.pending}
            elif T.state == "RUN" and "locks" in r and T.batch_ok:
                T.wait_set = set(r["locks"])
            else:
                err(i, f"{T.state} 상태에서 WAIT")
            T.state = "WAIT"
        elif op == "ACQUIRE":
            if holder.get(lock) is not None:
                err(i, f"락 {lock}이 스레드 {holder[lock]}에게 쥐어져 있는데 스레드 {th}가 ACQUIRE")
            if T.state == "REQ":
                if lock != T.pending:
                    err(i, f"요청한 락 {T.pending}이 아닌 {lock}을 ACQUIRE")
                T.state = "RUN"
            elif T.state == "WAIT":
                if lock not in T.wait_set:
                    err(i, f"기다리지 않은 락 {lock}을 ACQUIRE")
                T.wait_set.discard(lock)
                if not T.wait_set:
                    T.state = "RUN"
            elif T.state == "RUN" and T.batch_ok:
                pass                                   # 일괄 요청의 즉시 허가
            else:
                err(i, f"{T.state} 상태에서 ACQUIRE")
            holder[lock] = th
            T.held.add(lock)
        elif op == "RELEASE":
            if T.state != "RUN":
                err(i, f"{T.state} 상태에서 RELEASE")
            if holder.get(lock) != th:
                err(i, f"스레드 {th}가 쥐지 않은 락 {lock}을 RELEASE")
            else:
                del holder[lock]
                T.held.discard(lock)
            T.batch_ok = False
        elif op in ("ABORT", "FAIL"):
            if op == "FAIL" and T.state not in ("REQ", "RUN"):
                err(i, f"{T.state} 상태에서 FAIL")
            for l in list(T.held):
                if holder.get(l) == th:
                    del holder[l]
            T.held.clear()
            T.wait_set = set()
            if op == "ABORT":
                stats["aborts"] += 1
                T.state = "START"
            else:
                stats["tasks_failed"] += 1
                T.state = "IDLE"
        elif op == "END":
            if T.state != "RUN":
                err(i, f"{T.state} 상태에서 END")
            if T.held:
                err(i, f"락 {sorted(T.held)}를 쥔 채 END")
            stats["tasks_ended"] += 1
            T.state = "IDLE"
    unfinished = [t for t, T in enumerate(threads) if T.state not in ("IDLE",)]
    if unfinished:
        warnings.append(f"트레이스 끝에서 끝나지 않은 스레드: {unfinished}(수집이 끊겼거나 교착일 수 있음)")
    stats["locks"] = len(lock_cls)
    stats["classes"] = len(set(lock_cls.values()))
    return errors, warnings, stats


def validate_file(path):
    with open(path, encoding="utf-8") as f:
        return validate_lines(f.read().splitlines())


def main(argv):
    rc = 0
    for p in argv:
        errors, warnings, stats = validate_file(p)
        print(f"{p}: 이벤트 {stats['events']}개, 오류 {len(errors)}개, 경고 {len(warnings)}개")
        print(f"  연산 수: {dict(sorted(stats['ops'].items()))}")
        print(f"  종료 작업 {stats['tasks_ended']}, 실패 {stats['tasks_failed']}, 중단 시도 {stats['aborts']}, 락 {stats['locks']}, 클래스 {stats['classes']}")
        for e in errors[:20]:
            print("  오류:", e)
        if len(errors) > 20:
            print(f"  ... 오류 {len(errors) - 20}개 더")
        for w in warnings:
            print("  경고:", w)
        rc |= 1 if errors else 0
    return rc


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
