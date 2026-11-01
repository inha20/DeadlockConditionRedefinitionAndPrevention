"""탐색 기록: P-WD와 P-WW의 도달 가능 상태 그래프 크기가 어떻게 대응하는가 (범위 S1, S2 전수).
실행: python3 -I bench/probe_wd_ww.py formal/rq3/wd-ww-count-probe.md

배경: `formal/rq3/lock-policies-check.md`에서 P-WD와 P-WW의 전수 범위(S1, S2) 합계가 모든 열에서 같다.
이 스크립트는 워크로드마다 두 정책의 상태 그래프를 열거해 다음을 비교한다.
  (가) WD(w)와 WW(w): 같은 워크로드, 같은 타임스탬프(스레드 번호)
  (나) WD(w)와 WW(역순 w): WW에는 스레드 순서를 뒤집은 워크로드를 준다(타임스탬프의 나이 순서가 뒤집힘)
비교 대상은 상태 수·간선 수·중단 사건 수·끝난 상태 수('개수')와, (나가는, 들어오는) 간선 수 쌍의 분포(뿌리 없는 차수 분포),
초기 상태에서의 너비 우선 층별 상태 수다.
이것은 관찰이다. 같으면 왜 같은지 이 스크립트는 설명하지 않는다. 차수쌍 분포가 다르면 두 상태 그래프(중복 간선 포함)는 동형이 아니다.
개수나 층별 상태 수가 같다고 동형이라는 뜻은 아니다(필요조건일 뿐).
AI(Claude)가 쓴 초안이며 사람의 검토 전이다.
"""
from __future__ import annotations

import itertools
import multiprocessing as mp
import os
import sys
import time
from collections import Counter, deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "oracle"))

import bench.check_lock_policies as C  # noqa: E402
from bench.lockexplore import apply, enabled  # noqa: E402
from bench.policies.lock import policies as P  # noqa: E402
from bench.policies.lock.system import LockTable  # noqa: E402

SCOPE_NAMES = ("S1", "S2")


def graph_profile(progs, pname, nlocks):
    """상태 그래프를 열거해 (상태 수, 간선 수, 중단 사건 수, 끝난 상태 수, 층별 상태 수, 차수쌍 분포, 상태 집합)을 돌려준다."""
    pol = P.make(pname)
    tb = LockTable(list(progs), nlocks=nlocks)
    init = tb.snapshot()
    seen = {init: 0}
    dist = {init: 0}
    out = {}
    indeg = Counter()
    aborts = 0
    terminal = 0
    queue = deque([init])
    while queue:
        s = queue.popleft()
        tb.restore(s)
        if tb.terminal():
            terminal += 1
            out[s] = 0
            continue
        acts = enabled(tb, pol)
        out[s] = len(acts)
        for a in acts:
            tb.restore(s)
            ab = apply(tb, pol, a)
            if ab:
                aborts += len(ab)
            n = tb.snapshot()
            indeg[n] += 1
            if n not in seen:
                seen[n] = len(seen)
                dist[n] = dist[s] + 1
                queue.append(n)
    layers = tuple(sorted(Counter(dist.values()).items()))
    degs = tuple(sorted(Counter((out[s], indeg[s]) for s in seen).items()))
    return {"states": len(seen), "edges": sum(out.values()), "aborts": aborts, "terminal": terminal,
            "layers": layers, "degs": degs, "set": frozenset(seen)}


def counts(p):
    return (p["states"], p["edges"], p["aborts"], p["terminal"])


def one(task):
    sname, L, w = task
    wd = graph_profile(w, "P-WD", L)
    ww = graph_profile(w, "P-WW", L)
    wwr = graph_profile(tuple(reversed(w)), "P-WW", L)
    return {
        "counts_rev": counts(wd) == counts(wwr),
        "degs_rev": wd["degs"] == wwr["degs"],
        "layers_rev": wd["layers"] == wwr["layers"],
        "counts_same": counts(wd) == counts(ww),
        "set_same": wd["set"] == ww["set"],
        "states_wd": wd["states"], "states_ww": ww["states"], "states_wwr": wwr["states"],
        "w": w,
    }


def fmt_workload(w):
    return "; ".join(f"T{t}: {C.fmt_prog(p)}" for t, p in enumerate(w))


def main(out_path):
    t0 = time.time()
    out_path = os.path.abspath(out_path)
    ctx = mp.get_context("fork")
    rows = []
    first_bad = {}
    for sname in SCOPE_NAMES:
        scope = next(s for s in C.SCOPES if s[0] == sname)
        L = scope[2]
        wls = list(itertools.product(C.thread_programs(L, scope[3], scope[4]), repeat=scope[1]))
        with ctx.Pool(2) as pool:
            res = pool.map(one, [(sname, L, w) for w in wls], chunksize=16)
        n = len(res)
        agg = {k: sum(r[k] for r in res) for k in ("counts_rev", "degs_rev", "layers_rev", "counts_same", "set_same")}
        tot = {k: sum(r[k] for r in res) for k in ("states_wd", "states_ww", "states_wwr")}
        rows.append((sname, scope[1], L, n, agg, tot))
        for key in ("counts_rev", "degs_rev", "layers_rev"):
            bad = [r for r in res if not r[key]]
            if bad and key not in first_bad:
                first_bad[key] = (sname, bad[0])
    elapsed = time.time() - t0

    lines = ["# P-WD와 P-WW의 상태 그래프 크기 대조 (탐색 기록, AI 초안, 사람 검토 전)", ""]
    lines.append("재현: `python3 -I bench/probe_wd_ww.py formal/rq3/wd-ww-count-probe.md` "
                 f"(코어 2개, 이 실행은 {elapsed:.0f}초). 이것은 **관찰 기록**이다. 증명도, 원인 설명도 아니다.")
    lines.append("")
    lines.append("## 1. 배경과 방법")
    lines.append("")
    lines.append("`formal/rq3/lock-policies-check.md`의 범위 S1, S2에서 P-WD와 P-WW의 상태 수·간선 수·중단 사건 수 합계가 모든 칸에서 같았다. "
                 "표본 범위(S3–S5)에서는 같지 않았다(표본이 스레드 순서를 뒤집은 쌍을 모두 담지 않는다). "
                 "아래는 S1, S2의 **모든 워크로드**(스레드 번호 순서까지 구분한 순서쌍)마다 두 정책의 도달 가능 상태 그래프를 열거해 비교한 것이다.")
    lines.append("")
    lines.append("- (나) `WD(w)`와 `WW(역순 w)`: WW에는 스레드 순서를 뒤집은 워크로드를 준다. 스레드 번호가 타임스탬프이므로 나이 순서가 뒤집힌다.")
    lines.append("- (가) `WD(w)`와 `WW(w)`: 같은 워크로드.")
    lines.append("- '개수'는 (상태 수, 간선 수, 중단 사건 수, 끝난 상태 수)다. '차수쌍 분포'는 상태마다 (나가는 간선 수, 들어오는 간선 수)를 모은 "
                 "다중집합이고 초기 상태와 무관하다. '층별 상태 수'는 초기 상태에서 너비 우선으로 센 거리별 상태 수다. "
                 "차수쌍 분포가 다르면 두 상태 그래프(같은 상태로 가는 중복 간선 포함)는 동형이 아니다. 세 값이 같다고 동형이라는 뜻은 아니다(필요조건).")
    lines.append("")
    lines.append("## 2. 결과")
    lines.append("")
    lines.append("| 범위 | 스레드 | 락 | 워크로드 | (나) 개수 같음 | (나) 차수쌍 분포 같음 | (나) 층별 상태 수 같음 | (가) 개수 같음 | (가) 상태 집합 같음 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for sname, T, L, n, agg, tot in rows:
        lines.append(f"| {sname} | {T} | {L} | {n:,} | {agg['counts_rev']:,} | {agg['degs_rev']:,} | {agg['layers_rev']:,} | "
                     f"{agg['counts_same']:,} | {agg['set_same']:,} |")
    lines.append("")
    lines.append("상태 수 합계(범위 안 모든 워크로드): " + "; ".join(
        f"{sname}: WD(w) {tot['states_wd']:,}, WW(w) {tot['states_ww']:,}, WW(역순 w) {tot['states_wwr']:,}" for sname, _, _, _, _, tot in rows))
    lines.append("")
    if first_bad:
        lines.append("### 어긋난 워크로드의 첫 예")
        lines.append("")
        for key, (sname, r) in first_bad.items():
            what = {"counts_rev": "개수", "degs_rev": "차수쌍 분포", "layers_rev": "층별 상태 수"}[key]
            lines.append(f"- {sname}, {what} 기준 (나)의 첫 어긋남: `{fmt_workload(r['w'])}` "
                         f"(WD 상태 {r['states_wd']}, WW(역순) 상태 {r['states_wwr']})")
        lines.append("")
    lines.append("## 3. 읽는 법과 한계")
    lines.append("")
    lines.append("- 이 범위(S1, S2)에서 (나)의 칸이 워크로드 수와 같으면, 모든 워크로드에서 `WD(w)`와 `WW(역순 w)`의 해당 값이 같다는 뜻이다. "
                 "범위가 스레드 순서를 뒤집어도 닫혀 있으므로 `lock-policies-check.md`의 합계 같음은 워크로드별 개수 같음에서 따른다. "
                 "범위 밖에 대해서는 아무것도 말하지 않는다.")
    lines.append("- (나)에서 개수와 층별 상태 수는 이 범위의 모든 워크로드에서 같은데 차수쌍 분포는 대부분의 워크로드에서 다르다. 따라서 대부분의 워크로드에서 "
                 "두 상태 그래프는 동형이 아니고, 같은 개수는 상태 이름을 바꾸는 것만으로는 설명되지 않는다. 설명은 열린 질문이다.")
    lines.append("- (가) 칸은 대응이 '같은 워크로드끼리'는 아님을 보이려는 대조군이다. (가)에서 상태 집합이 같은 워크로드가 적다는 것은 대부분의 워크로드에서 두 정책의 도달 가능 상태 집합이 다르다는 뜻이다.")
    lines.append("- 왜 (나)가 성립하는지(상태 그래프 사이의 대응이 있는지)는 이 스크립트가 보이지 않는다. 증명 스케치도 아직 없다. "
                 "대응이 있다면 어떤 것인지는 열린 질문이고, 이 대응을 정책의 동치로 읽어서는 안 된다(두 정책은 어떤 스레드가 중단되는지가 다르다).")
    lines.append("- 이 값들은 소규모 열거 범위의 구조 수치다. 정책의 비용·성능 비교(M1–M9)가 아니다.")
    lines.append("")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{out_path}에 썼다 ({elapsed:.0f}초)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
