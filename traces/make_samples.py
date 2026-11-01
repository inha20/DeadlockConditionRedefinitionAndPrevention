"""합성 샘플 트레이스 생성기 (traces/FORMAT.md v0.1).

작은 L1 워크로드(T=4, R=5)를 정책별로 무작위 스케줄 실행기(bench/lockrun.py)로 돌려 traces/sample/*.jsonl을 만든다.
시드 0..199 가운데 '필요한 연산이 모두 나오고 가장 짧은' 트레이스를 고른다(결정적). 이것은 형식 시험용 견본이며
성능 측정이 아니다. 실행: python3 -I traces/make_samples.py [출력 디렉터리]
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "oracle"))

from bench.lockrun import run_random  # noqa: E402
from bench.policies.lock import policies as P  # noqa: E402
from bench.workloads.l1 import L1Params, make_l1  # noqa: E402

MASTER = "rq3-trace-samples"
PARAMS = L1Params(T=4, R=5, zipf_s=0.8, depth=2, p_viol=0.5)

# (파일 이름, 정책, 필요한 연산 집합, 필요한 'why' 집합)
SAMPLES = [
    ("synthetic-p-wd-t4r5.jsonl", "P-WD", {"BEGIN", "REQUEST", "WAIT", "ACQUIRE", "RELEASE", "ABORT", "END"}, {"deny"}),
    ("synthetic-p-ww-t4r5.jsonl", "P-WW", {"BEGIN", "REQUEST", "WAIT", "ACQUIRE", "RELEASE", "ABORT", "END"}, {"wound"}),
    ("synthetic-b1-t4r5.jsonl", "B1", {"BEGIN", "REQUEST", "WAIT", "ACQUIRE", "RELEASE", "ABORT", "END"}, {"detect"}),
    ("synthetic-p-all-t4r5.jsonl", "P-ALL", {"BEGIN", "WAIT", "ACQUIRE", "RELEASE", "END"}, set()),
    ("synthetic-p-ord-t4r5.jsonl", "P-ORD", {"BEGIN", "REQUEST", "ACQUIRE", "RELEASE", "FAIL", "END"}, {"fail"}),
]


def make_trace(policy: str, seed: int, instance: int = 0):
    w = make_l1(PARAMS, MASTER, instance)
    pol = P.make(policy)
    log: list = []
    res = run_random(w.first_programs(), pol, seed=seed, nlocks=w.nlocks, max_steps=5000, log=log)
    head = {
        "trace_format": "rq3-trace-v0.1",
        "source": "synthetic",
        "generator": f"bench/lockrun.run_random policy={policy} seed={seed} workload={w.name} master={MASTER}",
        "clock": "logical",
        "threads": w.T,
        "notes": "AI(Claude)가 만든 형식 시험용 견본. 균등 무작위 스케줄, 시간 모델 없음, ts는 걸음 번호. 성능 자료가 아님.",
    }
    return head, log, res


def pick(policy: str, need_ops: set, need_why: set, instances: int = 20, tries: int = 100):
    """인스턴스 0..instances-1, 시드 0..tries-1 가운데 조건을 만족하는 가장 짧은 트레이스(동률이면 앞선 것)."""
    best = None
    for inst in range(instances):
        for seed in range(tries):
            head, log, res = make_trace(policy, seed, inst)
            if res["status"] != "done":
                continue
            ops = {e["op"] for e in log}
            why = {e["why"] for e in log if "why" in e}
            if not need_ops <= ops or not need_why <= why:
                continue
            if best is None or len(log) < len(best[1]):
                best = (head, log, seed, inst)
    return best


def write_trace(path: str, head: dict, log: list) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(head, ensure_ascii=False, separators=(",", ":")) + "\n")
        for e in log:
            f.write(json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n")


def main(out_dir: str) -> int:
    os.makedirs(out_dir, exist_ok=True)
    for fname, policy, need_ops, need_why in SAMPLES:
        got = pick(policy, need_ops, need_why)
        if got is None:
            print(f"{fname}: 조건을 만족하는 시드가 없음", file=sys.stderr)
            return 1
        head, log, seed, inst = got
        write_trace(os.path.join(out_dir, fname), head, log)
        print(f"{fname}: 정책 {policy}, 인스턴스 {inst}, 시드 {seed}, 이벤트 {len(log)}개")
    return 0


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "traces", "sample")
    sys.exit(main(out))
