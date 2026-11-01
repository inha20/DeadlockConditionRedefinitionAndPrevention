"""트레이스 -> 락 프로그램 변환 (traces/FORMAT.md §2의 기준 구현).

작업마다 '마지막으로 정상 종료한 시도'(END로 끝난 시도)의 ACQUIRE/RELEASE 열이 그 작업의 프로그램이다.
중단된 시도와 실패한 작업은 프로그램을 정하지 않는다. 반환: {task: (('A', lock), ('R', lock), ...)}.
형식 검증(traces/validate.py)을 통과한 트레이스를 입력으로 가정한다.
"""
from __future__ import annotations

import json


def trace_to_programs(lines):
    ops: dict = {}                   # (th, task, attempt) -> [(kind, lock)]
    programs: dict = {}
    for i, line in enumerate(lines):
        if i == 0 or not line.strip():
            continue                 # 머리 레코드
        r = json.loads(line)
        key = (r["th"], r["task"], r["attempt"])
        op = r["op"]
        if op == "BEGIN":
            ops[key] = []
        elif op == "ACQUIRE":
            ops.setdefault(key, []).append(("A", r["lock"]))
        elif op == "RELEASE":
            ops.setdefault(key, []).append(("R", r["lock"]))
        elif op == "END":
            programs[r["task"]] = tuple(ops.get(key, ()))
    return programs


def trace_to_programs_file(path):
    with open(path, encoding="utf-8") as f:
        return trace_to_programs(f.read().splitlines())
