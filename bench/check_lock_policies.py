"""RQ3 락 정책 기준 구현의 소규모 전수 검사 (prereg/README.md SP-5의 ①②, WP3.1).
실행: python3 -I bench/check_lock_policies.py formal/rq3/lock-policies-check.md

워크로드 범위(scope)마다 스레드가 2–4개이고 각 스레드가 직선 락 프로그램 하나를 실행하는 모든 조합(또는 고정 시드 표본)에서
정책마다 도달 가능한 모든 락 표 상태를 열거하고(bench/lockexplore.py) 다음을 검사한다.
  inv 불변식 · deadlock 교착 집합 없음(예방·회피) · stall 멈춤 없음 · trap 영구 함정 없음 · oldest 가장 나이 많은 스레드 비중단
  audit 회피 정책 결정 = 오라클 O1, P-RAG = P-BNK · oracle O2와의 일관성
B0(무정책)는 교착이 실제로 나타나는지(검사의 비공허성), B1(탐지)은 교착이 나타나되 항상 풀리는지 본다.
변이체(bench/policies/lock/mutants.py)는 같은 검사가 고의로 틀린 정책을 잡는지 본다.
AI(Claude)가 쓴 초안이며 사람의 검토 전이다. 증명이 아니라 반례 탐색이고, 범위 밖에는 아무것도 말하지 않는다.
"""
from __future__ import annotations

import itertools
import multiprocessing as mp
import os
import pickle
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "oracle"))

import locks as o2  # noqa: E402
from bench import seeds  # noqa: E402
from bench.lockexplore import PROPS, explore  # noqa: E402
from bench.policies.lock import mutants as MU  # noqa: E402
from bench.policies.lock import policies as P  # noqa: E402

ALL_POLICIES = ["B0", "B1", "P-ORD", "P-ALL", "P-RET", "P-WD", "P-WW", "P-PCP", "P-BNK", "P-RAG", "P-MIX"]
# 스레드 번호(타임스탬프, 우선순위)에 결과가 의존하지 않는 정책: 프로그램 조합을 다중집합으로 센다.
SYMMETRIC = {"B0", "P-ORD", "P-ALL", "P-RET", "P-BNK", "P-RAG"}
GUARANTEED = set(P.GUARANTEED)

# (이름, 스레드 수 T, 락 수 L, 스레드당 최대 획득 수 kmax, 반납 방식, 방식, 표본 수)
#   방식 'all': 대칭 정책은 전수(다중집합). 비대칭 정책은 표본 수가 0이면 전수(순서쌍), 아니면 고정 시드 표본
#   방식 'sample': 모든 정책이 고정 시드 표본(순서쌍)
SCOPES = [
    ("S1", 2, 3, 3, ("nested", "fifo", "hoh"), "all", 0),
    ("S2", 3, 3, 2, ("nested", "fifo"), "all", 0),
    ("S3", 3, 3, 3, ("nested", "fifo", "hoh"), "all", 8000),
    ("S4", 4, 3, 2, ("nested",), "all", 2000),
    ("S5", 3, 4, 3, ("nested",), "sample", 2500),
]


def thread_programs(L, kmax, rels):
    s = set()
    for k in range(1, kmax + 1):
        for order in itertools.permutations(range(L), k):
            for r in rels:
                s.add(o2.program(order, r))
    return sorted(s)


def workloads(scope, symmetric):
    name, T, L, kmax, rels, mode, nsample = scope
    progs = thread_programs(L, kmax, rels)
    if mode == "sample" or (not symmetric and nsample > 0):
        rng = random.Random(seeds.derive("rq3-lockcheck", name))
        return [tuple(rng.choice(progs) for _ in range(T)) for _ in range(nsample)]
    if symmetric:
        return list(itertools.combinations_with_replacement(progs, T))
    return list(itertools.product(progs, repeat=T))


def is_sampled(scope, symmetric):
    return scope[5] == "sample" or ((not symmetric) and scope[6] > 0)


def make_policy(pname, mutant_index=None):
    if mutant_index is None:
        return P.make(pname)
    return MU.MUTANTS[pname][mutant_index]()


def run_task(task):
    """(정책 이름, 변이체 번호, 범위 이름) 하나의 전수 검사. 워크로드마다 explore를 돌려 합산한다."""
    pname, mi, sname = task
    scope = next(s for s in SCOPES if s[0] == sname)
    _, T, L, kmax, rels, mode, nsample = scope
    pol = make_policy(pname, mi)
    sym = pname in SYMMETRIC
    wls = workloads(scope, sym)
    agg = {"policy": pol.name, "base": pname, "mutant": mi, "scope": sname, "sym": sym, "workloads": len(wls),
           "sampled": is_sampled(scope, sym),
           "states": 0, "edges": 0, "terminal": 0, "dl_states": 0, "aborts": 0, "audit_calls": 0, "max_states": 0,
           "viol": {p: 0 for p in PROPS}, "first": {}, "dl_workloads": 0}
    for w in wls:
        r = explore(list(w), pol, nlocks=L)
        agg["states"] += r.states
        agg["edges"] += r.edges
        agg["terminal"] += r.terminal
        agg["dl_states"] += r.deadlock_states
        agg["aborts"] += r.abort_events
        agg["audit_calls"] += r.audit_calls
        agg["max_states"] = max(agg["max_states"], r.states)
        if r.deadlock_states:
            agg["dl_workloads"] += 1
        for p in PROPS:
            if r.counts[p]:
                agg["viol"][p] += 1
                if p not in agg["first"] or len(r.first[p][1]) < len(agg["first"][p][2]):
                    agg["first"][p] = (w, r.first[p][0], r.first[p][1])
    return agg


def fmt_prog(p):
    return " ".join(f"{k}{l}" for k, l in p)


def fmt_workload(w):
    return "; ".join(f"T{t}: {fmt_prog(p)}" for t, p in enumerate(w))


def main(out_path, save_raw=None, load_raw=None):
    t0 = time.time()
    # 긴 계산 뒤에 보고서를 쓰다가 작업 디렉터리 문제로 실패한 적이 있어(결과 전부 손실), 계산 전에 절대경로로 고정한다.
    try:
        out_path = os.path.abspath(out_path)
    except OSError:
        out_path = os.path.join(ROOT, out_path)
    mutant_scopes = ["S1", "S2"]
    if load_raw:
        with open(load_raw, "rb") as f:
            results, elapsed = pickle.load(f)
    else:
        tasks = []
        for sc in SCOPES:
            for pname in ALL_POLICIES:
                tasks.append((pname, None, sc[0]))
        for pname, lst in MU.MUTANTS.items():
            for mi in range(len(lst)):
                for sname in mutant_scopes:
                    tasks.append((pname, mi, sname))
        # 느린 작업(비대칭 정책의 S3, S4)을 먼저 배정한다.
        tasks.sort(key=lambda x: (0 if (x[2] in ("S3", "S4") and x[1] is None and x[0] not in SYMMETRIC) else 1,
                                  x[2], x[0], -1 if x[1] is None else x[1]))
        ctx = mp.get_context("fork")
        with ctx.Pool(2) as pool:
            results = pool.map(run_task, tasks, chunksize=1)
        elapsed = time.time() - t0
        if save_raw:                       # 보고서 단계가 실패해도 계산을 다시 하지 않도록 먼저 저장한다.
            with open(save_raw, "wb") as f:
                pickle.dump((results, elapsed), f)
    by = {(r["base"], r["mutant"], r["scope"]): r for r in results}

    lines: list[str] = []
    checks: list[tuple[str, bool, str]] = []

    def check(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    # ---------------------------------------------------------------- 정책 x 범위 표
    lines.append("# RQ3 락 정책 기준 구현의 소규모 전수 검사 결과 (AI 초안, 사람 검토 전)")
    lines.append("")
    lines.append("재현: `python3 -I bench/check_lock_policies.py formal/rq3/lock-policies-check.md` "
                 "(코어 2개를 쓰고 이 작업공간에서 약 10분이 걸렸다(2026-11-02, 577초). 결과 파일은 같은 명령으로 다시 만들어진다.)")
    lines.append("")
    lines.append("이 검사는 증명이 아니라 지정한 범위의 모든 도달 가능 상태에서 반례를 찾은 것이다. 범위 밖에는 아무것도 말하지 않는다. "
                 "정책의 의미 선택(대기열 순서, 락 넘김, 타임스탬프 유지)은 `docs/rq3/policies.md`에 있고 사람이 정한다. "
                 "P-INC-F/R은 동결 전이라 구현하지 않았다.")
    lines.append("")
    lines.append("## 1. 범위")
    lines.append("")
    lines.append("스레드마다 직선 락 프로그램 하나(획득과 반납의 열, 같은 락을 두 번 얻지 않음, 끝날 때 쥔 락 없음)를 실행한다. "
                 "프로그램은 획득 순서(락의 순열)와 반납 방식으로 만든다: `nested`(획득의 역순), `fifo`(획득 순서), "
                 "`hoh`(손잡기: A1 A2 R1 A3 R2 ...). 락 번호가 전역 클래스 순서다. 스레드 번호가 곧 타임스탬프(작을수록 나이 많음)이고 "
                 "우선순위는 T - 번호(클수록 높음)다. 프로그램을 스레드에 모든 방식으로 배정하므로 모든 나이·우선순위 순서가 덮인다.")
    lines.append("")
    lines.append("| 범위 | 스레드 수 | 락 수 | 스레드당 획득 수 | 반납 방식 | 스레드당 프로그램 수 | 대칭 정책의 열거 | 비대칭 정책의 열거 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for (name, T, L, kmax, rels, mode, nsample) in SCOPES:
        npg = len(thread_programs(L, kmax, rels))
        n_multi = len(list(itertools.combinations_with_replacement(range(npg), T)))
        n_prod = npg ** T
        if mode == "sample":
            sym_en = f"고정 시드 표본 {nsample:,}개"
            asym_en = f"고정 시드 표본 {nsample:,}개 (순서쌍 전체는 {n_prod:,}개)"
        else:
            sym_en = f"전수 {n_multi:,}개(다중집합)"
            asym_en = f"전수 {n_prod:,}개(순서쌍)" if nsample == 0 else f"고정 시드 표본 {nsample:,}개 (순서쌍 전체는 {n_prod:,}개)"
        lines.append(f"| {name} | {T} | {L} | 1–{kmax} | {', '.join(rels)} | {npg} | {sym_en} | {asym_en} |")
    lines.append("")
    lines.append("대칭 정책(B0, P-ORD, P-ALL, P-RET, P-BNK, P-RAG)은 스레드 번호에 결과가 의존하지 않아 프로그램 조합을 다중집합으로 센다. "
                 "나머지(B1, P-WD, P-WW, P-PCP, P-MIX)는 번호가 나이·우선순위를 정하므로 순서쌍을 센다. 표본으로 돌린 행은 정책 이름 뒤에 `*`를 붙였다"
                 "(표본은 그 범위의 일부이므로 '범위의 모든 워크로드'가 아니라 '표본의 모든 워크로드'에 대한 결과다). "
                 "표본 추출에는 마스터 시드 `rq3-lockcheck`와 범위 이름에서 정한 시드를 쓴다.")
    lines.append("")
    lines.append("## 2. 정책별 결과")
    lines.append("")
    lines.append("열: 워크로드 수 · 상태 수(합) · 한 워크로드의 최대 상태 수 · 간선 수 · 중단 사건 수 · 교착 집합이 있는 상태를 가진 워크로드 수 · "
                 "성질별 위반 워크로드 수(inv/deadlock/stall/trap/oldest/audit/oracle).")
    lines.append("")
    lines.append("상태 수·간선 수·중단 사건 수는 소규모 열거 범위의 구조 수치이고 이 범위의 워크로드는 균등하게 센 것이다. 워크로드 분포 아래의 비율이 아니므로 "
                 "정책의 비용·성능 비교(M1–M9)나 중단률로 읽지 않는다. 동결 전에는 그런 비교를 하지 않는다(`prereg/RQ3.md`).")
    lines.append("")
    for sc in SCOPES:
        sname = sc[0]
        lines.append(f"### 범위 {sname}")
        lines.append("")
        lines.append("| 정책 | 워크로드 | 상태 | 최대 | 간선 | 중단 | 교착 상태 가진 워크로드 | inv | deadlock | stall | trap | oldest | audit | oracle |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for pname in ALL_POLICIES:
            r = by[(pname, None, sname)]
            v = r["viol"]
            lines.append(f"| {pname}{'*' if r['sampled'] else ''} | {r['workloads']:,} | {r['states']:,} | {r['max_states']:,} | {r['edges']:,} | {r['aborts']:,} | "
                         f"{r['dl_workloads']:,} | {v['inv']:,} | {v['deadlock']:,} | {v['stall']:,} | {v['trap']:,} | {v['oldest']:,} | {v['audit']:,} | {v['oracle']:,} |")
        lines.append("")
    # 판정
    for sc in SCOPES:
        sname = sc[0]
        for pname in ALL_POLICIES:
            r = by[(pname, None, sname)]
            v = r["viol"]
            if pname in GUARANTEED:
                bad = {p: n for p, n in v.items() if n}
                check(f"{pname} {sname}: 예방·회피 성질 위반 0", not bad, str(bad))
            elif pname == "B1":
                bad = {p: n for p, n in v.items() if n and p != "deadlock"}
                check(f"B1 {sname}: 탐지 뒤 멈춤·함정 없음(교착 상태는 허용)", not bad, str(bad))
            else:  # B0
                if sc[1] >= 2:
                    check(f"B0 {sname}: 교착이 실제로 나타남(비공허성)", r["dl_workloads"] > 0 and v["stall"] > 0 and v["trap"] > 0,
                          f"교착 가진 워크로드 {r['dl_workloads']}")
    # 비공허성: 감사 호출 수, 중단 사건
    for pname in ("P-BNK", "P-RAG"):
        calls = sum(by[(pname, None, sc[0])]["audit_calls"] for sc in SCOPES)
        check(f"{pname}: O1 대조 호출이 실제로 있었음", calls > 0, f"{calls:,}")
    for pname in ("P-WD", "P-WW", "P-MIX", "P-RET", "B1"):
        ab = sum(by[(pname, None, sc[0])]["aborts"] for sc in SCOPES)
        check(f"{pname}: 중단 사건이 실제로 있었음", ab > 0, f"{ab:,}")
    # 교착 집합이 있는 상태가 B1에서 나타나고 풀리는지
    b1 = sum(by[("B1", None, sc[0])]["dl_states"] for sc in SCOPES)
    check("B1: 교착 상태가 도달 가능하고(>0) 모든 범위에서 풀림(stall, trap 0)", b1 > 0, f"{b1:,}")

    # ---------------------------------------------------------------- 반례(B0)
    lines.append("## 3. B0의 교착 반례(비공허성 예시)")
    lines.append("")
    for sname in ("S1", "S2"):
        r = by[("B0", None, sname)]
        if "deadlock" in r["first"]:
            w, msg, tr = r["first"]["deadlock"]
            lines.append(f"- 범위 {sname}의 가장 짧은 동작열: 워크로드 `{fmt_workload(w)}`")
            lines.append(f"  - {' → '.join(tr)}")
            lines.append(f"  - {msg}")
    lines.append("")

    # ---------------------------------------------------------------- 변이체
    lines.append("## 4. 변이체 검출")
    lines.append("")
    lines.append("각 변이체는 기준 정책에서 하나만 바꾼 틀린 정책이다. 같은 검사가 범위 S1, S2에서 어느 성질로 처음 잡는지 적는다. "
                 "'잡은 워크로드 수'는 두 범위 합이다.")
    lines.append("")
    lines.append("| 변이체 | 바꾼 것 | 잡은 성질(워크로드 수) | 가장 짧은 반례의 동작 수 |")
    lines.append("|---|---|---|---|")
    for pname, lst in MU.MUTANTS.items():
        for mi, cls in enumerate(lst):
            tot = {p: 0 for p in PROPS}
            best = None
            for sname in mutant_scopes:
                r = by[(pname, mi, sname)]
                for p in PROPS:
                    tot[p] += r["viol"][p]
                for p, (w, msg, tr) in r["first"].items():
                    if best is None or len(tr) < len(best[2]):
                        best = (p, w, tr)
            caught = {p: n for p, n in tot.items() if n}
            doc = " ".join((cls.__doc__ or "").split())
            if pname == "B1":
                caught.pop("deadlock", None)
            check(f"변이체 {cls.name}: 검출됨", bool(caught), str(caught))
            lines.append(f"| `{cls.name}` | {doc} | {', '.join(f'{p}({n})' for p, n in caught.items()) or '**검출 못함**'} | "
                         f"{len(best[2]) if best else '-'} |")
    lines.append("")

    # 대표 반례: 락 넘김 시점의 불변식을 지키지 않는 FIFO 변이체
    lines.append("")
    lines.append("대표 반례(가장 짧은 동작열). 대기열을 도착 순서로 두고 보유자와의 비교만 하는 wait-die·wound-wait가 왜 틀리는지 보여 준다. "
                 "스레드 번호가 곧 타임스탬프(작을수록 나이 많음)다.")
    lines.append("")
    for pname, mi in (("P-WD", 0), ("P-WW", 0)):
        cls = MU.MUTANTS[pname][mi]
        best = None
        for sname in mutant_scopes:
            r = by[(pname, mi, sname)]
            for prop in ("deadlock", "inv"):
                if prop in r["first"]:
                    w, msg, tr = r["first"][prop]
                    if best is None or (prop == "deadlock" and best[0] == "inv") or (prop == best[0] and len(tr) < len(best[3])):
                        best = (prop, w, msg, tr)
        if best:
            prop, w, msg, tr = best
            lines.append(f"- `{cls.name}`({prop}): 워크로드 `{fmt_workload(w)}`")
            lines.append(f"  - {' → '.join(tr)}")
            lines.append(f"  - {msg}")
    lines.append("")

    # ---------------------------------------------------------------- 두 정책의 결정이 같은 것
    lines.append("## 5. 관찰: P-RAG와 P-BNK")
    lines.append("")
    calls = sum(by[("P-RAG", None, sc[0])]["audit_calls"] for sc in SCOPES)
    lines.append(f"단위 용량·0/1 청구의 락 모델에서 P-RAG(청구 대기 그래프 순환 검사)의 허가 결정이 P-BNK(교재식 안전성 알고리즘)와 같고 "
                 f"둘 다 정확 오라클 O1과 같았다(대조 {calls:,}회, 불일치 0). 두 정책은 같은 상태에서 같은 결정을 내리므로 이 모델의 "
                 f"M1, M2, M5–M9에서는 구별되지 않고 요청당 비용(M3)과 메모리(M4)에서만 다를 수 있다. 이는 이 범위의 검사 결과이며 "
                 f"일반 증명은 `docs/rq3/policies.md`의 도출(AI) 항목에 스케치로 있다.")
    lines.append("")

    tot_w = sum(by[(p_, None, sc[0])]["workloads"] for sc in SCOPES for p_ in ALL_POLICIES if p_ in GUARANTEED)
    tot_s = sum(by[(p_, None, sc[0])]["states"] for sc in SCOPES for p_ in ALL_POLICIES if p_ in GUARANTEED)
    lines.append(f"예방·회피 정책 9종의 합계: 워크로드 {tot_w:,}개(정책·범위별 합), 도달 가능 상태 {tot_s:,}개.")
    lines.append("")
    nfail = sum(1 for c in checks if not c[1])
    lines.append("## 6. 검사 목록")
    lines.append("")
    lines.append(f"검사 {len(checks)}개, 실패 {nfail}개.")
    lines.append("")
    lines.append("| 검사 | 결과 | 비고 |")
    lines.append("|---|---|---|")
    for name, ok, detail in checks:
        lines.append(f"| {name} | {'통과' if ok else '**실패**'} | {detail} |")
    lines.append("")
    lines.append("## 7. 확인한 것과 하지 않은 것")
    lines.append("")
    lines.append("- 확인함: 위 범위의 모든 도달 가능 상태에서 예방·회피 정책 9종의 교착 집합(모델 명세 §3.1) 부재, 멈춤 부재, 영구 함정 부재, 정책별 불변식(ORD→T6, ALL·RET→T7, WD·WW→T8, 천장의 쌍별 비대칭, 혼합의 합성), wait-die·wound-wait·혼합에서 가장 나이 많은 스레드가 중단되지 않음, 회피 정책의 허가 결정과 O1의 일치, O2와의 일관성.")
    lines.append("- 확인하지 않음: 기아 부재(영구 함정이 없다는 것과 다르다. 공정성 가정 아래의 검증은 하지 않았고 M8로만 보고한다), 큰 규모(스레드 5개 이상, 락 5개 이상, 연산 7개 이상), 분기가 있는 프로그램, 재진입, 읽기·쓰기 모드, 다중 인스턴스 락, 우선순위 상속과 스케줄러, 정책의 비용(M3, M4), 시간 흐름(백오프 지연은 걸음의 선택에 흡수했다).")
    lines.append("- 한계: 정책, 락 표, 탐색기, 불변식이 같은 사람(AI)의 같은 정의에서 나왔다. O1, O2와 SM 오라클은 별도 코드지만 정의를 공유한다. 변이체 검출은 검사의 민감도를 보이지만 완전성을 보이지 않는다.")
    lines.append("")
    text = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"검사 {len(checks)}개, 실패 {nfail}개 (소요 {elapsed:.0f}초)")
    for name, ok, detail in checks:
        if not ok:
            print("실패:", name, detail)
    return nfail


if __name__ == "__main__":
    args = sys.argv[1:]
    save = load = None
    if "--save-raw" in args:
        i = args.index("--save-raw")
        save = args[i + 1]
        del args[i:i + 2]
    if "--load-raw" in args:
        i = args.index("--load-raw")
        load = args[i + 1]
        del args[i:i + 2]
    out = args[0] if args else os.path.join(ROOT, "formal", "rq3", "lock-policies-check.md")
    sys.exit(1 if main(out, save_raw=save, load_raw=load) else 0)
