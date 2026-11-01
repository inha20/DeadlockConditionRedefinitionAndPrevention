"""RQ6 파일럿의 요약. experiments/pilot/*.jsonl을 읽어 experiments/pilot/pilot-summary.md를 쓴다 (프로토콜: docs/rq6/pilot.md §4).

AI(Claude)가 쓴 초안이며 사람의 검토 전이다. 동결 전 도구이고 본 분석이 아니다.
이 모듈은 의도적으로 다음을 계산하지 않는다: 변형의 판정과 오라클·닫힘 계산의 대조(K1), 변형/기준 비율의 평균(K5),
크기에 따른 로그–로그 기울기(K4), 해석 사이의 민감도(K6). 짝지은 비교에 필요한 인스턴스 수를 위해 로그 비율의 표준편차만 낸다.
기준 구현(교재식 둘)과 오라클 O1의 대조는 SP-5의 관문(도구 점검)이므로 낸다.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict

import numpy as np

from bench import pilot_rq6 as PR
from bench import stats as S
from bench.seeds import rng

Z = 1.959963984540054
C_MEDIAN = math.sqrt(math.pi / 2.0)          # 정규 분포에서 표본 중앙값의 표준오차 배수
H_TIME = 0.05                                # SP-1: 95% 구간 반폭 ≤ 중앙값의 5% (계획용)
H_RATIO_LOG = math.log(1.05)                 # δ_r = 0.05 (계획용)
SHORT = {"textbook-restart": "tb-R", "textbook-sweep": "tb-S", "begum-return": "begum", "dbdaa-cycle1": "dbdaa-1",
         "dbdaa-repeat": "dbdaa-r", "wicaksono-sweep": "wick", "dixit-max-once": "dx-mo", "dixit-max-top": "dx-mt",
         "dixit-max-repeat": "dx-mr", "dixit-alloc-once": "dx-ao", "dixit-alloc-top": "dx-at", "dixit-alloc-repeat": "dx-ar"}
POLICY_ORDER = list(SHORT)


# ---------------------------------------------------------------- 추정식 (check_pilot.py가 점검한다)

def anova_components(mat: np.ndarray) -> tuple[float, float]:
    """(I, R) 배열(인스턴스 × 반복)의 일원 변량효과 ANOVA 추정. 반환: (σ²_b, σ²_w). σ²_b는 0 아래로 내려가면 0."""
    mat = np.asarray(mat, dtype=float)
    I, R_ = mat.shape
    if I < 2 or R_ < 2:
        raise ValueError("인스턴스 2개 이상, 반복 2번 이상이 필요하다")
    ms_w = float(mat.var(axis=1, ddof=1).mean())
    ms_b = float(R_ * mat.mean(axis=1).var(ddof=1))
    return max(0.0, (ms_b - ms_w) / R_), ms_w


def n_needed_median(sig_b2: float, sig_w2: float, reps: int, h: float = H_TIME) -> int:
    """중앙값의 95% 구간 상대 반폭 ≈ Z·C·σ_tot/√N 이 h 이하가 되는 최소 N. σ²_tot = σ²_b + σ²_w/reps (로그 단위, 정규 가정)."""
    sig_tot = math.sqrt(max(0.0, sig_b2) + max(0.0, sig_w2) / reps)
    return max(2, math.ceil((Z * C_MEDIAN * sig_tot / h) ** 2))


def n_needed_ratio(sd_d: float, h_log: float = H_RATIO_LOG) -> int:
    """짝지은 로그 비율의 평균(기하평균 비율)의 95% 구간 반폭 Z·sd/√N 이 h_log 이하가 되는 최소 N."""
    return max(2, math.ceil((Z * sd_d / h_log) ** 2))


def smallest_reps(sig_b2: float, sig_w2: float, frac: float = 0.10, cap: int = 8) -> int:
    """σ²_w/R ≤ frac·σ²_b 가 되는 가장 작은 R (상한 cap). σ²_b = 0이면 cap."""
    if sig_b2 <= 0:
        return cap
    return int(min(cap, max(1, math.ceil(sig_w2 / (frac * sig_b2)))))


def boot_rel_halfwidth(values, g, B: int = 10_000) -> float:
    ci = S.percentile_ci(values, "median", 0.95, B, g)
    return (ci["hi"] - ci["lo"]) / (2.0 * ci["estimate"])


def formula_rel_halfwidth(sig_b2: float, sig_w2: float, reps: int, n: int) -> float:
    return Z * C_MEDIAN * math.sqrt(sig_b2 + sig_w2 / reps) / math.sqrt(n)


def ols_slope(y) -> float:
    y = np.asarray(y, dtype=float)
    x = np.arange(y.size, dtype=float)
    xm = x.mean()
    return float(((x - xm) * (y - y.mean())).sum() / ((x - xm) ** 2).sum())


def slope_boot_ci(y, g, B: int = 5000, level: float = 0.95):
    y = np.asarray(y, dtype=float)
    x = np.arange(y.size, dtype=float)
    idx = g.integers(0, y.size, size=(B, y.size))
    xs, ys = x[idx], y[idx]
    xm = xs.mean(axis=1, keepdims=True)
    sxx = ((xs - xm) ** 2).sum(axis=1)
    ok = sxx > 0
    sl = (((xs - xm) * (ys - ys.mean(axis=1, keepdims=True))).sum(axis=1))[ok] / sxx[ok]
    tail = (1 - level) / 2
    return float(np.quantile(sl, tail)), float(np.quantile(sl, 1 - tail))


# ---------------------------------------------------------------- 표 보조

def md_table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out) + "\n"


def fmt_s(x: float | None) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    if x < 1e-3:
        return f"{x * 1e6:.0f}µs"
    if x < 1:
        return f"{x * 1e3:.1f}ms"
    return f"{x:.2f}s"


def q(values, p) -> float:
    return float(np.quantile(np.asarray(values, dtype=float), p))


def time_of(rec: dict) -> float | None:
    """한 기록의 호출당 시간(초). 느린 모드는 데운 뒤의 값(둘 중 작은 쪽), 표준 모드는 반복의 중앙값."""
    w = rec.get("wall_ns_per_call")
    if not w:
        return None
    return (min(w) if rec.get("mode") == "slow" else float(np.median(w))) / 1e9


def load(out_dir: str, name: str) -> list[dict]:
    path = os.path.join(out_dir, f"{name}.jsonl")
    return PR.load_units(path) if os.path.exists(path) else []


# ---------------------------------------------------------------- S: 표집·난이도·동률

def s_sections(recs: list[dict]) -> str:
    samples = [r for r in recs if r.get("rec") == "sample"]
    inst = [r for r in recs if r.get("rec") == "instance"]
    if not samples:
        return "## S. 표집·난이도·동률\n\n자료 없음.\n"
    pts = sorted({(r["n"], r["m"]) for r in samples}, key=lambda p: (p[0] * p[1], p[0]))
    out = ["## S. 표집·난이도·동률\n"]
    out.append("### S-1 표집 수율\n")
    out.append("후보를 몇 개 만들어야 목표 개수를 채우는가(시도 수 ÷ 받은 인스턴스 수). 부족분이 있으면 `!`로 표시한다.\n")
    rows = []
    for (n, m) in pts:
        row = [n, m]
        for t in PR.TARGETS:
            s = [r for r in samples if r["n"] == n and r["m"] == m and abs(r["target_safe"] - t) < 1e-9]
            if not s:
                row.append("—")
                continue
            s = s[0]
            got = s["got_safe"] + s["got_unsafe"]
            short = s["short_safe"] + s["short_unsafe"]
            row.append(f"{s['attempts'] / max(1, got):.1f}" + (" !" if short else ""))
        rows.append(row)
    out.append(md_table(["n", "m"] + [f"목표 {t}" for t in PR.TARGETS], rows))
    tot_short = sum(r["short_safe"] + r["short_unsafe"] for r in samples)
    out.append(f"\n셀 {len(samples)}개 가운데 부족분이 있는 셀 {sum(1 for r in samples if r['short_safe'] + r['short_unsafe'])}개(부족 합계 {tot_short}).\n")
    out.append("\n### S-2 입력의 어려움 (닫힘 반복 횟수 `cl_passes`)\n")
    out.append("목표 안전 비율 세 가지를 합친 인스턴스. 안전 입력은 닫힘 반복 횟수의 중앙값·90백분위·최댓값과 2회 이하 비율, 불안전 입력은 중앙값과 끝낸 프로세스 비율(`cl_done`/n)의 중앙값.\n")
    rows = []
    for (n, m) in pts:
        sa = [r for r in inst if r["n"] == n and r["m"] == m and r["truth"]]
        un = [r for r in inst if r["n"] == n and r["m"] == m and not r["truth"]]
        row = [n, m, len(sa)]
        if sa:
            ps = [r["cl_passes"] for r in sa]
            row += [f"{q(ps, .5):.0f}", f"{q(ps, .9):.0f}", max(ps), f"{sum(1 for p in ps if p <= 2) / len(ps):.2f}"]
        else:
            row += ["—"] * 4
        row.append(len(un))
        if un:
            row += [f"{q([r['cl_passes'] for r in un], .5):.0f}", f"{q([r['cl_done'] / n for r in un], .5):.2f}"]
        else:
            row += ["—"] * 2
        rows.append(row)
    out.append(md_table(["n", "m", "안전 수", "반복 중앙", "반복 P90", "반복 최대", "≤2회 비율", "불안전 수", "반복 중앙", "끝낸 비율 중앙"], rows))
    out.append("\n### S-3 정렬 키의 동률 빈도 (V-5)\n")
    out.append("모든 인스턴스(세 목표 합침)에서 프로세스들의 키가 겹치는가. maxneed는 DBDAA·Begum의 키(성분 최댓값), sumneed는 Dixit의 키(성분 합). "
               "`일부 겹침`은 키가 같은 프로세스 쌍이 하나라도 있는 인스턴스의 비율, `겹친 프로세스`는 다른 프로세스와 키가 같은 프로세스의 비율의 평균.\n")
    rows = []
    for (n, m) in pts:
        ii = [r for r in inst if r["n"] == n and r["m"] == m]
        if not ii:
            continue
        row = [n, m, len(ii)]
        for key in ("maxneed", "sumneed"):
            row += [f"{np.mean([r['ties'][key]['any'] for r in ii]):.2f}", f"{np.mean([r['ties'][key]['frac'] for r in ii]):.2f}"]
        rows.append(row)
    out.append(md_table(["n", "m", "인스턴스", "maxneed 일부 겹침", "maxneed 겹친 프로세스", "sumneed 일부 겹침", "sumneed 겹친 프로세스"], rows))
    out.append("\nF-bound의 `chain-first`·`chain-last`는 구성상 키가 모두 다르고(필요량이 n−p), `chain-unsafe-*`는 앞 두 프로세스의 키가 같다(필요량 n)(`bench/gen_banker.py`의 구성).\n")
    return "\n".join(out)


# ---------------------------------------------------------------- C: 비용 사다리와 O1

def _cls(r: dict) -> str:
    if r["fkind"] == "rand":
        return "rand-안전" if r["truth"] else "rand-불안전"
    return r["fkind"]


def c_sections(recs: list[dict], over: list[dict]) -> str:
    cost = [r for r in recs if r.get("rec") == "cost"]
    o1 = [r for r in recs if r.get("rec") == "o1"]
    if not cost:
        return "## C. 비용 사다리와 O1\n\n자료 없음.\n"
    params = next(r for r in recs if r.get("rec") in ("header",))["params"]
    pts = sorted({(r["n"], r["m"]) for r in cost}, key=lambda p: (p[0] * p[1], p[0]))
    pols = [p for p in POLICY_ORDER if any(r["policy"] == p for r in cost)]
    out = [f"## C. 비용 사다리와 O1\n\n상한: 계수 실행 {params['cap_count']}초, 시간 실행 {params['cap_time']}초, O1 {params['cap_o1']}초. "
           "`TOc` = 계수 실행이 상한을 넘음, `TOt` = 시간 실행이 상한을 넘음, `·` = 더 작은 점에서 상한을 넘어 건너뜀(지배 건너뛰기). 값은 호출당 시간(데운 뒤 중앙값)이다. "
           "표 안의 시간은 이 환경(코어 2개 공유 가상 환경)의 절대 시간이며 정책 사이의 비율이나 기울기로 읽지 않는다.\n"]
    classes = ["rand-안전", "rand-불안전"] + [k for k in PR.C_KINDS if any(r["fkind"] == k for r in cost)]
    entries: dict = defaultdict(list)
    for r in cost:
        entries[(_cls(r), r["policy"], (r["n"], r["m"]))].append(r)

    def cell(es) -> str:
        sts = [e["status"] for e in es]
        if any(s == "timeout_count" for s in sts):
            return "TOc"
        if any(s == "timeout_time" for s in sts):
            return "TOt"
        if all(s == "skipped_dominated" for s in sts):
            return "·"
        ts = [time_of(e) for e in es if e["status"] == "ok" and time_of(e) is not None]
        return fmt_s(float(np.median(ts))) if ts else "—"

    for k, cls in enumerate(classes, 1):
        out.append(f"\n### C-{k} 호출당 시간: {cls}\n")
        rows = []
        for (n, m) in pts:
            rows.append([n, m] + [cell(entries.get((cls, p, (n, m)), [])) if entries.get((cls, p, (n, m))) else "—" for p in pols])
        out.append(md_table(["n", "m"] + [SHORT[p] for p in pols], rows))
    # 실행 가능한 범위
    out.append("\n### C-F 정책별 실행 가능한 범위\n")
    out.append("한 점이 '가능'이려면 그 점의 모든 인스턴스에서 계수 실행과 시간 실행이 상한 안에 끝나야 한다. "
               "n 스윕(m = 8)에서 가능한 가장 큰 n, m 스윕(n = 256)에서 가능한 가장 큰 m, 대각선에서 가능한 가장 큰 점.\n")
    sweep_n = [p for p in pts if p[1] == 8]
    sweep_m = [p for p in pts if p[0] == 256]
    diag = [p for p in pts if p in set(PR.DIAG)]
    rows = []
    feas_all: dict = defaultdict(lambda: True)
    for fk in ["rand"] + [k for k in PR.C_KINDS if any(r["fkind"] == k for r in cost)]:
        for p in pols:
            def ok_pt(pt) -> bool:
                es = [e for e in cost if e["fkind"] == fk and e["policy"] == p and (e["n"], e["m"]) == pt]
                return bool(es) and all(e["status"] == "ok" for e in es)
            feas = {pt: ok_pt(pt) for pt in pts}
            for pt, v in feas.items():
                feas_all[(fk, pt)] = feas_all[(fk, pt)] and v

            def top(seq, key):
                good = [pt for pt in seq if feas[pt]]
                return key(max(good, key=lambda pt: pt[0] * pt[1])) if good else "없음"
            holes = [pt for pt in pts if not feas[pt] and any(feas[q2] for q2 in pts if q2[0] >= pt[0] and q2[1] >= pt[1] and q2 != pt)]
            rows.append([fk, SHORT[p], top(sweep_n, lambda pt: pt[0]), top(sweep_m, lambda pt: pt[1]),
                         top(diag, lambda pt: f"({pt[0]},{pt[1]})"), "있음" if holes else "—"])
    out.append(md_table(["입력군", "정책", "n 최대(m=8)", "m 최대(n=256)", "대각선 최대", "구멍"], rows))
    out.append("\n모든 정책이 가능한 점(입력군별):\n")
    for fk in ["rand"] + [k for k in PR.C_KINDS if any(r["fkind"] == k for r in cost)]:
        good = [pt for pt in pts if feas_all[(fk, pt)]]
        out.append(f"- {fk}: " + (", ".join(f"({n},{m})" for n, m in good) if good else "없음") + f" ({len(good)}/{len(pts)}점)")
    out.append("")
    # 계측 비용
    out.append("\n### C-I 계수 실행(계측)의 시간 대 시간 실행의 호출당 시간\n")
    out.append("본 실행의 계수 패스 비용을 가늠하기 위한 값이다. 호출당 시간이 1 ms 이상인 기록에서 `count_s` ÷ 호출당 시간의 중앙값.\n")
    rows = []
    for p in pols:
        rs = [e["count_s"] / time_of(e) for e in cost if e["policy"] == p and e.get("status") == "ok" and time_of(e) and time_of(e) >= 1e-3
              and e.get("count_s") is not None]
        rows.append([SHORT[p], len(rs), f"{q(rs, .5):.1f}" if rs else "—", f"{q(rs, .9):.1f}" if rs else "—"])
    out.append(md_table(["정책", "기록 수", "중앙값", "90백분위"], rows))
    # 상태 재구성 비용
    if over:
        out.append("\n### C-O 과제마다 드는 고정 비용 (상태 재구성과 해시)\n")
        out.append("`runner`는 과제마다 상태를 번호로 다시 만들고 해시를 센다(계수 과제: 해시 2번, 시간 과제: 1번). 정책 시간과 별개로 들어간다.\n")
        rows = []
        for r in sorted((r for r in over if r.get("rec") == "overhead"), key=lambda r: (r["n"] * r["m"], r["n"])):
            rows.append([r["n"], r["m"], fmt_s(r["build_rand_s"]), fmt_s(r["build_bound_s"]), fmt_s(r["digest_s"])])
        out.append(md_table(["n", "m", "F-rand 재구성", "F-bound 재구성", "해시 1번"], rows))
    # O1
    out.append("\n### C-O1 정답 대조 (R-8)와 기준 구현 점검 (SP-5)\n")
    out.append("O1은 `oracle.banker.safe_oracle`이다. 기준 구현(교재식 둘)의 판정이 입력의 표지(`truth`, 닫힘 계산)와 O1에 같은지 센다. "
               "변형의 판정은 대조하지 않는다. 불일치 칸은 0이어야 한다.\n")
    rows = []
    for (n, m) in pts:
        es = [r for r in o1 if (r["n"], r["m"]) == (n, m)]
        if not es:
            continue
        ok = [r for r in es if r["status"] == "ok"]
        to = sum(1 for r in es if r["status"] == "timeout")
        sk = sum(1 for r in es if r["status"] == "skipped_dominated")
        mx = max((r["o1_s"] + r["o1_convert_s"] for r in ok), default=None)
        bad_truth = sum(1 for r in ok if r["o1_verdict"] != r["truth"])
        bad_r = sum(1 for r in ok if r.get("restart") is not None and r["restart"] != r["o1_verdict"])
        bad_s = sum(1 for r in ok if r.get("sweep") is not None and r["sweep"] != r["o1_verdict"])
        rows.append([n, m, len(es), len(ok), to, sk, fmt_s(mx), bad_truth, bad_r, bad_s])
    out.append(md_table(["n", "m", "기록", "O1 완료", "O1 초과", "건너뜀", "O1 최대(변환 포함)", "O1≠표지", "Restart≠O1", "Sweep≠O1"], rows))
    return "\n".join(out)


# ---------------------------------------------------------------- 후보 격자의 총 시간 (비용 모델)

def budget_table(cost: list[dict], over: list[dict], samples: list[dict], seeds: int = 30, sessions: int = 6, reps: int = 5,
                 target_s: float = 0.002, kinds=PR.C_KINDS, caps=(20.0, 40.0)) -> list[dict]:
    """점을 n·m 오름차순으로 쌓은 누적 시간(초, 단일 코어 직렬). 모델(프로토콜 §4):
      F-rand  점마다 목표 0.1, 0.5, 0.9 × seeds개. 목표 평균은 안전 0.5, 불안전 0.5의 가중. 과제 = 계수 과제 + 시간 과제.
      계수 과제 = count_s + 상태 재구성 + 해시 2번 + 닫힘 계산(입력 표지), 시간 과제 = 2T + reps·max(T, target) + 상태 재구성 + 해시 1번.
      F-bound 종류마다 인스턴스 1개: 계수 과제 1번 + 시간 과제 sessions번.
    측정하지 못한 값(상한 초과, 건너뜀)은 상한으로 두고 하한임을 표시한다. 측정한 두 F-bound 종류만 넣는다(나머지 종류는 포함하지 않음)."""
    ov = {(r["n"], r["m"]): r for r in over if r.get("rec") == "overhead"}
    pts = sorted({(r["n"], r["m"]) for r in cost}, key=lambda p: (p[0] * p[1], p[0]))
    pols = [p for p in POLICY_ORDER if any(r["policy"] == p for r in cost)]
    by: dict = defaultdict(list)
    for r in cost:
        by[(r["fkind"], r["truth"] if r["fkind"] == "rand" else None, r["policy"], (r["n"], r["m"]))].append(r)
    samp: dict = defaultdict(float)
    for r in samples:
        if r.get("rec") == "sample":
            samp[(r["n"], r["m"])] += r["seconds"] * (seeds / max(1, r["count"]))

    def task_costs(es: list[dict], cap_c: float, cap_t: float):
        """(계수 시간, 시간 과제의 정책 시간, 하한 여부)"""
        if not es:
            return 0.0, 0.0, True
        lower = False
        cs, ts = [], []
        for e in es:
            if e["status"] == "ok":
                cs.append(e["count_s"])
                t = time_of(e)
                ts.append(2 * t + reps * max(t, target_s))
            else:
                lower = True
                cs.append(cap_c)
                ts.append(2 * cap_t + reps * cap_t)
        return float(np.median(cs)), float(np.median(ts)), lower

    hdr = {"cap_count": caps[0], "cap_time": caps[1]}
    rows = []
    cum = 0.0
    cum_count = 0.0
    cum_lower = False
    for pt in pts:
        o = ov.get(pt)
        build_r = o["build_rand_s"] if o else 0.0
        build_b = o["build_bound_s"] if o else 0.0
        dig = o["digest_s"] if o else 0.0
        clo = o.get("closure_s", 0.0) if o else 0.0
        rand = 0.0
        bound = 0.0
        count_only = 0.0
        lower = False
        for p in pols:
            cs = {}
            cc = {}
            for cls in (True, False):
                c_, t_, lw = task_costs(by.get(("rand", cls, p, pt), []), hdr["cap_count"], hdr["cap_time"])
                cc[cls] = c_ + build_r + 2 * dig + clo
                cs[cls] = cc[cls] + (t_ + build_r + dig)
                lower = lower or lw
            rand += 0.5 * (cs[True] + cs[False]) * 3 * seeds
            count_only += 0.5 * (cc[True] + cc[False]) * 3 * seeds
            for k in kinds:
                c_, t_, lw = task_costs(by.get((k, None, p, pt), []), hdr["cap_count"], hdr["cap_time"])
                bound += (c_ + build_b + 2 * dig + clo) + sessions * (t_ + build_b + dig)
                count_only += c_ + build_b + 2 * dig + clo
                lower = lower or lw
        total = rand + bound + samp.get(pt, 0.0)
        cum += total
        cum_count += count_only + samp.get(pt, 0.0)
        cum_lower = cum_lower or lower
        rows.append({"point": pt, "rand_s": rand, "bound_s": bound, "sample_s": samp.get(pt, 0.0), "total_s": total, "cum_s": cum,
                     "count_only_s": count_only + samp.get(pt, 0.0), "cum_count_s": cum_count,
                     "lower_bound": lower, "cum_lower_bound": cum_lower})
    return rows


def budget_sections(cost: list[dict], over: list[dict], samples: list[dict], o1: list[dict], caps=(20.0, 40.0)) -> str:
    out = ["## B. 후보 격자의 본 실행 총 시간 (비용 모델)\n"]
    if not cost:
        return out[0] + "\n자료 없음.\n"
    out.append("프로토콜 §4의 모델. 단일 코어 직렬(시간 패스는 직렬이어야 한다), 정책 12개, 요청 연산(K1의 request)은 넣지 않았다(넣으면 인스턴스당 `1 + 요청 수`배 근처). "
               "누적은 점을 n·m 오름차순으로 쌓은 값이다. `≥`는 상한을 넘었거나 건너뛴 칸을 상한으로 대신 넣었다는 뜻(하한). "
               "시간은 파일럿 환경의 값이며 비교 횟수(K2)만으로 하는 본 실행이면 시간 패스 항이 빠진다.\n")
    for k_seed, seeds in enumerate((30, 100, 300), start=1):
        rows = budget_table(cost, over, samples, seeds=seeds, caps=caps)
        out.append(f"\n### B-{k_seed} 시드 {seeds} (목표 안전 비율마다)\n")
        tab = []
        for r in rows:
            mark = "≥" if r["cum_lower_bound"] else ""
            tab.append([f"({r['point'][0]},{r['point'][1]})", fmt_s(r["rand_s"]), fmt_s(r["bound_s"]), fmt_s(r["sample_s"]),
                        ("≥" if r["lower_bound"] else "") + fmt_s(r["total_s"]), f"{mark}{r['cum_s'] / 3600:.2f} h",
                        f"{r['cum_count_s'] / 3600:.2f} h"])
        out.append(md_table(["점", "F-rand", "F-bound(2종)", "표집", "점 합계", "누적", "누적(계수 패스만)"], tab))
        for hours in (2, 8, 24):
            fit = [r for r in rows if r["cum_s"] <= hours * 3600]
            fit_c = [r for r in rows if r["cum_count_s"] <= hours * 3600]
            out.append(f"- 누적 {hours}시간 안에 들어가는 가장 큰 격자: "
                       + (f"{len(fit)}점, 끝 점 ({fit[-1]['point'][0]},{fit[-1]['point'][1]}), 누적 {fit[-1]['cum_s'] / 3600:.2f} h" if fit else "없음")
                       + "; 계수 패스만이면 "
                       + (f"{len(fit_c)}점, 끝 점 ({fit_c[-1]['point'][0]},{fit_c[-1]['point'][1]}), 누적 {fit_c[-1]['cum_count_s'] / 3600:.2f} h" if fit_c else "없음"))
        out.append("")
    # O1 대조를 모든 인스턴스에 하면 드는 시간
    ok = [r for r in o1 if r.get("status") == "ok"]
    if ok:
        pts = sorted({(r["n"], r["m"]) for r in ok}, key=lambda p: (p[0] * p[1], p[0]))
        tot = 0.0
        for pt in pts:
            es = [r["o1_s"] + r["o1_convert_s"] for r in ok if (r["n"], r["m"]) == pt and r["fkind"] == "rand"]
            if es:
                tot += float(np.mean(es)) * 3 * 30
        out.append(f"\n입력마다 O1로 대조하면(F-rand, 시드 30, 목표 3가지) 파일럿이 잰 점 {len(pts)}개 합계 약 {tot / 3600:.2f} h가 더 든다(점별 평균 O1 시간 기준).\n")
    return "\n".join(out)


# ---------------------------------------------------------------- V, V2: 분산 성분

def v_groups(recs: list[dict]) -> dict:
    by: dict = defaultdict(list)
    for r in recs:
        if r.get("rec") == "time" and r.get("status") == "ok":
            by[(r["policy"], r["cell"])].append(r)
    return by


def v_components(rows: list[dict]):
    mats = [np.log(np.asarray(r["wall_ns_per_call"], dtype=float)) for r in rows]
    R_ = min(len(x) for x in mats)
    mat = np.stack([x[:R_] for x in mats])
    sb, sw = anova_components(mat)
    return mat, sb, sw, R_


def canary_paragraph(recs: list[dict], label: str) -> str:
    can = sorted((r for r in recs if r.get("rec") == "canary"), key=lambda r: r["k"])
    if len(can) < 4:
        return f"[{label}] 카나리 자료 부족."
    y = np.log([float(np.median(r["wall_ns_per_call"])) for r in can])
    sl = ols_slope(y)
    lo, hi = slope_boot_ci(y, rng(PR.PILOT_MASTER, "summary", "canary", label))
    txt = (f"[{label}] 카나리 {len(can)}회(교재식 Restart, (256, 8) 고정 인스턴스, 60과제마다). 로그 시간의 표준편차 {float(np.std(y, ddof=1)):.3f}, "
           f"카나리 한 칸당 기울기 {sl:+.4f} (95% 구간 {lo:+.4f} ~ {hi:+.4f}), 전체 구간에서 환산한 변화 {math.exp(sl * (len(can) - 1)) - 1:+.1%}. "
           + ("구간이 0을 포함하지 않아 **드리프트 있음**." if (lo > 0 or hi < 0) else "구간이 0을 포함하므로 드리프트를 가려내지 못했다."))
    vals = ", ".join(f"{float(np.median(r['wall_ns_per_call'])) / 1e6:.3f}" for r in can)
    return txt + f"\n\n카나리 값(ms): {vals}"


def cell_key(name: str):
    parts = name.split("-")
    n, m = int(parts[-2]), int(parts[-1])
    return (n * m, n)


def v3_rows(recs: list[dict]) -> list[dict]:
    """V3 기록을 (셀, 정책)별로 묶어 전체·안전·불안전의 분산 성분과 필요한 N을 낸다. 층에 인스턴스가 3개 미만이면 그 층은 없다."""
    ok = [r for r in recs if r.get("rec") == "time" and r.get("status") == "ok" and "truth" in r]
    by: dict = defaultdict(list)
    for r in ok:
        by[(r["cell"], r["policy"])].append(r)
    out = []
    for (c, p), rs in sorted(by.items(), key=lambda kv: (cell_key(kv[0][0]), POLICY_ORDER.index(kv[0][1]) if kv[0][1] in POLICY_ORDER else 99)):
        _, sb, sw, R_ = v_components(rs)
        row = {"cell": c, "policy": p, "all": {"I": len(rs), "sb": sb, "sw": sw, "R": R_, "N": n_needed_median(sb, sw, R_)}}
        for flag, nm in ((True, "safe"), (False, "unsafe")):
            sub = [r for r in rs if r["truth"] is flag]
            if len(sub) >= 3:
                _, sb2, sw2, R2 = v_components(sub)
                row[nm] = {"I": len(sub), "sb": sb2, "sw": sw2, "R": R2, "N": n_needed_median(sb2, sw2, R2), "R_rule": smallest_reps(sb2, sw2)}
        out.append(row)
    return out


def v3_sections(recs: list[dict]) -> str:
    """V3(사후 추가). 같은 F-rand 셀에서 안전/불안전을 나누어 분산 성분과 필요한 인스턴스 수를 낸다. 탐색용이며 사전에 계획한 분석이 아니다."""
    out = ["\n### V-5 안전/불안전을 나눈 분산 (V3, 사후 추가·탐색)\n"]
    rows3 = v3_rows(recs)
    if not rows3:
        return "\n".join(out) + "\n자료 없음.\n"
    hdr = next(r for r in recs if r.get("rec") == "header")["params"]
    out.append(f"V의 결과(V-1, V-2)를 본 뒤 덧붙인 측정이다. 같은 다섯 F-rand 셀에서 새 인스턴스 {hdr['count']}개(목표 안전 비율 0.5, 안전 {hdr['count'] // 2} + 불안전 {hdr['count'] // 2}), "
               f"조각 목표 {hdr['target_ns'] / 1e6:g} ms, 반복 {hdr['repeats']}회. 입력의 표지(`truth`)는 닫힘 계산으로 정한 입력의 성질이고 정책의 판정이 아니다. "
               "전체는 안전과 불안전을 섞은 분산(V-1과 같은 정의), 안전·불안전은 각각 따로 구한 분산이다. N은 R = 반복 횟수일 때 중앙값 95% 구간 반폭 5%에 필요한 그 층의 인스턴스 수.\n")
    agg: dict = defaultdict(lambda: defaultdict(list))
    rows = []
    for row in rows3:
        c, p, al = row["cell"], row["policy"], row["all"]
        cols = [c, SHORT.get(p, p), f"{math.sqrt(al['sb']):.3f}", al["N"]]
        agg[c]["전체"].append(al["N"])
        agg[c]["전체 σ_b"].append(math.sqrt(al["sb"]))
        for nm, label in (("safe", "안전"), ("unsafe", "불안전")):
            st = row.get(nm)
            if not st:
                cols += ["—", "—", "—", "—"]
                continue
            cols += [st["I"], f"{math.sqrt(st['sb']):.3f}", f"{math.sqrt(st['sw']):.3f}", st["N"]]
            agg[c][label].append(st["N"])
            agg[c][label + " σ_b"].append(math.sqrt(st["sb"]))
            agg[c][label + " R"].append(st["R_rule"])
        rows.append(cols)
    out.append(md_table(["셀", "정책", "전체 σ_b", "전체 N", "안전 I", "안전 σ_b", "안전 σ_w", "안전 N", "불안전 I", "불안전 σ_b", "불안전 σ_w", "불안전 N"], rows))
    out.append("\n셀별 요약(정책 12개 위):\n")
    rows = []
    for c in sorted(agg, key=cell_key):
        a = agg[c]
        row = [c]
        for nm in ("전체", "안전", "불안전"):
            ns = a.get(nm, [])
            sbs = a.get(nm + " σ_b", [])
            row += [f"{q(sbs, .5):.3f}" if sbs else "—", f"{q(ns, .5):.0f} / {q(ns, .9):.0f} / {max(ns)}" if ns else "—"]
        rr = a.get("안전 R", []) + a.get("불안전 R", [])
        row.append(f"{q(rr, .5):.0f}" if rr else "—")
        rows.append(row)
    out.append(md_table(["셀", "전체 σ_b 중앙", "전체 N 중앙/P90/최대", "안전 σ_b 중앙", "안전 N 중앙/P90/최대", "불안전 σ_b 중앙", "불안전 N 중앙/P90/최대", "층별 R 규칙 중앙"], rows))
    return "\n".join(out)


def v_sections(recs: list[dict], recs2: list[dict], recs3: list[dict] | None = None) -> str:
    out = ["## V. 분산 성분 (시간 측정)\n"]
    by = v_groups(recs)
    if not by:
        return out[0] + "\n자료 없음.\n"
    hdr = next(r for r in recs if r.get("rec") == "header")["params"]
    out.append(f"조각 목표 {hdr['target_ns'] / 1e6:g} ms, 반복 {hdr['repeats']}회, F-rand 인스턴스 {hdr['count']}개, F-bound 세션 {hdr['sessions']}개. "
               "σ_b는 인스턴스(F-bound는 세션) 사이, σ_w는 같은 인스턴스를 반복해 잰 사이의 표준편차(로그 시간 단위, 상대 변동에 가깝다). "
               "N(R)은 프로토콜 §4의 식으로 구한 중앙값 95% 구간 반폭 5%에 필요한 인스턴스 수. "
               "부트/식은 파일럿 표본의 부트스트랩 상대 반폭 ÷ 식의 상대 반폭이며 1.25를 넘으면 `!`.\n")
    cells = sorted({c for (_, c) in by})
    rows = []
    agg: dict = defaultdict(list)
    for (p, c), rs in sorted(by.items(), key=lambda kv: (kv[0][1], POLICY_ORDER.index(kv[0][0]) if kv[0][0] in POLICY_ORDER else 99)):
        if len(rs) < 2:
            continue
        mat, sb, sw, R_ = v_components(rs)
        vals = [float(np.median(r["wall_ns_per_call"])) for r in rs]
        g = rng(PR.PILOT_MASTER, "summary", p, c)
        hb = boot_rel_halfwidth(vals, g)
        hf = formula_rel_halfwidth(sb, sw, R_, len(rs))
        ratio = hb / hf if hf > 0 else float("nan")
        n3, n5, n8 = (n_needed_median(sb, sw, R) for R in (3, 5, 8))
        agg[c].append((p, sb, sw, n3, n5, n8, ratio, smallest_reps(sb, sw)))
        rows.append([c, SHORT.get(p, p), len(rs), R_, f"{math.sqrt(sb):.3f}", f"{math.sqrt(sw):.3f}", n3, n5, n8,
                     f"{ratio:.2f}" + (" !" if ratio > 1.25 else "")])
    out.append("### V-1 정책 × 셀\n")
    out.append(md_table(["셀", "정책", "I", "R", "σ_b", "σ_w", "N(3)", "N(5)", "N(8)", "부트/식"], rows))
    out.append("\n### V-2 셀별 요약 (정책 12개 위)\n")
    rows = []
    for c in cells:
        a = agg.get(c, [])
        if not a:
            continue
        rows.append([c, f"{q([math.sqrt(x[1]) for x in a], .5):.3f}", f"{max(math.sqrt(x[1]) for x in a):.3f}",
                     f"{q([math.sqrt(x[2]) for x in a], .5):.3f}", f"{max(math.sqrt(x[2]) for x in a):.3f}",
                     f"{q([x[3] for x in a], .9):.0f}", f"{q([x[4] for x in a], .9):.0f}", f"{q([x[5] for x in a], .9):.0f}", max(x[5] for x in a),
                     f"{q([x[7] for x in a], .5):.0f}"])
    out.append(md_table(["셀", "σ_b 중앙", "σ_b 최대", "σ_w 중앙", "σ_w 최대", "N(3) P90", "N(5) P90", "N(8) P90", "N(8) 최대", "R 규칙 중앙"], rows))
    # 드리프트
    out.append("\n### V-3 카나리와 드리프트\n")
    out.append(canary_paragraph(recs, "V") + "\n")
    if recs3:
        out.append(canary_paragraph(recs3, "V3") + "\n")
    # V2
    out.append("\n### V-4 조각 길이 (V')\n")
    by2 = v_groups(recs2)
    if by2:
        rows = []
        grp: dict = defaultdict(list)
        for r in recs2:
            if r.get("rec") == "time" and r.get("status") == "ok":
                grp[(r["policy"], r["target_ns"])].append(r)
        for (p, tn), rs in sorted(grp.items(), key=lambda kv: (POLICY_ORDER.index(kv[0][0]), kv[0][1])):
            mat, sb, sw, R_ = v_components(rs)
            task_s = float(np.mean([sum(w * r["inner"] for w in r["wall_ns_per_call"]) / 1e9 for r in rs]))
            rows.append([SHORT[p], f"{tn / 1e6:g} ms", len(rs), R_, f"{math.sqrt(sb):.3f}", f"{math.sqrt(sw):.3f}", f"{task_s * 1e3:.1f} ms",
                         smallest_reps(sb, sw)])
        out.append(md_table(["정책", "조각 목표", "I", "R", "σ_b", "σ_w", "재는 시간/과제", "R 규칙"], rows))
    else:
        out.append("자료 없음.\n")
    if recs3:
        out.append(v3_sections(recs3))
    return "\n".join(out)


# ---------------------------------------------------------------- P: 짝지은 비용의 분산 (표준편차만)

UNITS = ("vec_cmp", "sca_cmp", "iters")


MIN_STRATUM = 10


def _dist(ns) -> str:
    return f"{q(ns, .5):.0f} / {q(ns, .9):.0f} / {max(ns)}" if ns else "—"


def p_strat_sections(cnt: list[dict], variants: list[str]) -> str:
    """P-1과 P-2는 목표 안전 비율마다 안전·불안전 입력이 섞인 값이다. 입력의 표지(truth)로 나누어 다시 계산한다(사후 추가, 탐색).
    점마다 세 목표의 인스턴스를 합친 뒤 층별로 나눈다. 층에 인스턴스가 MIN_STRATUM개 미만이면 그 점은 뺀다."""
    out = ["\n### P-3 안전/불안전을 나눈 비교 횟수 → 중앙값 구간에 필요한 N (사후 추가·탐색)\n"]
    by: dict = defaultdict(lambda: defaultdict(dict))
    for r in cnt:
        by[(r["n"], r["m"])][(r["policy"], bool(r["truth"]))][(r["unit"], r["idx"])] = r["counts"]
    pts = sorted(by, key=lambda p: (p[0] * p[1], p[0]))
    out.append(f"P-1을 본 뒤 덧붙인 계산이다. 점마다 세 목표의 인스턴스를 합쳐(전체 = 안전과 불안전이 절반씩 섞인 값) 입력의 표지(`truth`)로 나눈다. "
               f"층에 인스턴스가 {MIN_STRATUM}개 미만인 점은 뺀다. 각 칸은 점 {len(pts)}개 위에서 N의 `중앙 / P90 / 최대`.\n")
    rows = []
    for p in POLICY_ORDER:
        for unit_name in ("vec_cmp", "sca_cmp"):
            res: dict = {"전체": [], "안전": [], "불안전": []}
            for pt in pts:
                g = by[pt]
                sv = [c.get(unit_name, 0) for c in g.get((p, True), {}).values()]
                uv = [c.get(unit_name, 0) for c in g.get((p, False), {}).values()]
                for name, vals in (("전체", sv + uv), ("안전", sv), ("불안전", uv)):
                    pos = [x for x in vals if x > 0]
                    if len(pos) >= MIN_STRATUM:
                        sd = float(np.std(np.log(pos), ddof=1))
                        res[name].append(n_needed_median(sd * sd, 0.0, 1))
            if res["전체"]:
                rows.append([SHORT[p], unit_name, _dist(res["전체"]), _dist(res["안전"]), _dist(res["불안전"])])
    out.append(md_table(["정책", "단위", "전체", "안전", "불안전"], rows))
    out.append("\n### P-4 안전/불안전을 나눈 짝지은 로그 비율 → 비율 구간 반폭 δ_r = 0.05에 필요한 N (사후 추가·탐색)\n")
    for base in PR.BASELINES:
        rows = []
        for unit_name in UNITS:
            for p in variants:
                res = {"전체": [], "안전": [], "불안전": []}
                for pt in pts:
                    g = by[pt]
                    for name, truths in (("전체", (True, False)), ("안전", (True,)), ("불안전", (False,))):
                        xs = []
                        for t in truths:
                            a, b = g.get((p, t), {}), g.get((base, t), {})
                            for key in set(a) & set(b):
                                x, y = a[key].get(unit_name, 0), b[key].get(unit_name, 0)
                                if x > 0 and y > 0:
                                    xs.append(math.log(x / y))
                        if len(xs) >= MIN_STRATUM:
                            res[name].append(n_needed_ratio(float(np.std(xs, ddof=1))))
                if res["전체"]:
                    rows.append([unit_name, SHORT[p], _dist(res["전체"]), _dist(res["안전"]), _dist(res["불안전"])])
        out.append(f"\n기준: {base}. 각 칸은 N의 `중앙 / P90 / 최대`.\n")
        out.append(md_table(["단위", "변형", "전체", "안전", "불안전"], rows))
    return "\n".join(out)


def p_sections(recs: list[dict]) -> str:
    out = ["## P. 짝지은 비용의 분산 (비교 횟수)\n"]
    cnt = [r for r in recs if r.get("rec") == "count" and r.get("status") == "ok"]
    if not cnt:
        return out[0] + "\n자료 없음.\n"
    out.append("로그 비교 횟수의 인스턴스 사이 표준편차와, 변형과 기준 구현을 같은 인스턴스끼리 짝지은 로그 비율의 **표준편차**만 낸다(평균은 내지 않는다, 프로토콜 §2). "
               "N은 프로토콜 §4의 식. 0인 값이 있는 쌍은 뺀 비율을 같이 적는다.\n")
    by: dict = defaultdict(dict)
    cells: set = set()
    for r in cnt:
        by[(r["unit"], r["policy"])][r["idx"]] = r["counts"]
        cells.add(r["unit"])
    cells = sorted(cells, key=lambda u: (int(u.split("-")[1]) * int(u.split("-")[2]), int(u.split("-")[1]), u))
    variants = [p for p in POLICY_ORDER if p not in PR.BASELINES and any(k[1] == p for k in by)]
    out.append("### P-1 정책의 로그 비교 횟수 사이 분산 → 중앙값 구간에 필요한 N (K2)\n")
    out.append("각 칸은 `σ_b / N`이다(목표 안전 비율 한 가지 안의 안전·불안전 입력을 섞은 값. 셀 이름 끝의 10, 50, 90이 목표 안전 비율 %). "
               "0인 값은 로그를 취할 수 없어 뺐고, 그 단위를 쓰지 않는 정책은 `—`이다.\n")
    for k_unit, unit_name in enumerate(("vec_cmp", "sca_cmp"), start=1):
        rows = []
        for u in cells:
            row = [u]
            for p in PR.BASELINES + tuple(variants):
                d = by.get((u, p))
                if not d:
                    row.append("—")
                    continue
                v = [c[unit_name] for c in d.values() if c.get(unit_name, 0) > 0]
                if len(v) < 3:
                    row.append("—")
                    continue
                sd = float(np.std(np.log(v), ddof=1))
                row.append(f"{sd:.2f}/{n_needed_median(sd * sd, 0.0, 1)}")
            rows.append(row)
        out.append(f"\n단위 `{unit_name}` (P-1{'ab'[k_unit - 1]}):\n")
        out.append(md_table(["셀"] + [SHORT[p] for p in PR.BASELINES + tuple(variants)], rows))
    out.append("\n### P-2 짝지은 로그 비율의 표준편차 → 비율 구간 반폭 δ_r = 0.05에 필요한 N\n")
    for base in PR.BASELINES:
        out.append(f"\n기준: {base}. 셀 {len(cells)}개 위에서 변형별 N의 분포(중앙값 / 90백분위 / 최대)와 뺀 쌍의 비율.\n")
        rows = []
        for unit_name in UNITS:
            for p in variants:
                ns, dropped, total, sds = [], 0, 0, []
                for u in cells:
                    a, b = by.get((u, p)), by.get((u, base))
                    if not a or not b:
                        continue
                    idxs = sorted(set(a) & set(b))
                    xs = [(a[i].get(unit_name, 0), b[i].get(unit_name, 0)) for i in idxs]
                    keep = [(x, y) for x, y in xs if x > 0 and y > 0]
                    total += len(xs)
                    dropped += len(xs) - len(keep)
                    if len(keep) >= 3:
                        d = np.log([x / y for x, y in keep])
                        sd = float(np.std(d, ddof=1))
                        sds.append(sd)
                        ns.append(n_needed_ratio(sd))
                if ns:
                    rows.append([unit_name, SHORT[p], f"{q(sds, .5):.3f}", f"{max(sds):.3f}", f"{q(ns, .5):.0f}", f"{q(ns, .9):.0f}", max(ns),
                                 f"{dropped / max(1, total):.2f}"])
        out.append(md_table(["단위", "변형", "sd 중앙", "sd 최대", "N 중앙", "N P90", "N 최대", "뺀 쌍 비율"], rows))
    out.append(p_strat_sections(cnt, variants))
    return "\n".join(out)


# ---------------------------------------------------------------- R: 재현성

def r_sections(recs: list[dict]) -> str:
    out = ["## R. 재현성\n"]
    r = next((x for x in recs if x.get("rec") == "repro"), None)
    if not r:
        return out[0] + "\n자료 없음.\n"
    b = r["baseline_runs"]
    out.append(f"- 기준 구현 두 실행(`runner.execute`, 같은 마스터 시드): 계수 기록 {b['count_records']}개, 키 집합 같음 {b['same_keys']}, 서로 다른 기록 {b['count_diffs']}개.")
    frac = b["time_fraction"]
    frac_s = "—" if frac is None else f"{frac:.2f}"
    rmin = "—" if b["ratio_min"] is None else f"{b['ratio_min']:.3f}"
    rmax = "—" if b["ratio_max"] is None else f"{b['ratio_max']:.3f}"
    out.append(f"- 시간: 호출당 중앙값 0.1 ms 이상인 (정책, 셀) 쌍 {b['time_pairs']}개 가운데 허용 범위({PR.R_TOL[0]}–{PR.R_TOL[1]}) 안 {b['time_inside']}개 "
               f"({frac_s}), 비의 범위 {rmin} ~ {rmax}. 통과 기준은 {PR.R_PASS_FRACTION:.0%} 이상.")
    out.append(f"- 기준 구현의 판정과 입력의 표지가 다른 기록: {r['baseline_result_vs_truth_mismatch']}개.")
    out.append(f"- 열두 정책의 계수 기록 {r['twelve_policy_counts']}개: 같은 프로세스 두 번 같음 {r['same_process_equal']}, 다른 프로세스(해시 시드 다름 {r['hash_seed_differs']})와 같음 {r['other_process_equal']}.")
    if b["outside"]:
        out.append("- 허용 범위 밖인 쌍(정책, 셀, 비): " + "; ".join(f"{p}/{c}/{v}" for p, c, v in b["outside"]))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- 전체

HEAD = """# RQ6 파일럿 요약 (생성 파일)

`bench/pilot_summary_rq6.py`가 `experiments/pilot/*.jsonl`에서 만든다. AI(Claude)가 작성한 초안이며 사람의 검토 전이다. 프로토콜은 `docs/rq6/pilot.md`.
이 파일은 운영 수치만 담는다. 변형의 판정 대조(K1), 비율의 평균(K5), 크기에 따른 기울기(K4), 해석 민감도(K6)는 계산하지 않았다.
파일럿 자료는 본 분석에 쓰지 않는다. 시간은 코어 2개를 공유하는 가상 환경의 절대 시간이다.
"""


def build_summary(out_dir: str) -> str:
    parts = [HEAD]
    parts.append(s_sections(load(out_dir, "S")))
    parts.append(c_sections(load(out_dir, "C"), load(out_dir, "O")))
    cc = load(out_dir, "C")
    hp = next((r["params"] for r in cc if r.get("rec") == "header"), {"cap_count": 20.0, "cap_time": 40.0})
    parts.append(budget_sections([r for r in cc if r.get("rec") == "cost"], load(out_dir, "O"), load(out_dir, "S"),
                                 [r for r in cc if r.get("rec") == "o1"], caps=(hp["cap_count"], hp["cap_time"])))
    parts.append(v_sections(load(out_dir, "V"), load(out_dir, "V2"), load(out_dir, "V3") or None))
    parts.append(p_sections(load(out_dir, "P")))
    parts.append(r_sections(load(out_dir, "R")))
    return "\n\n".join(parts) + "\n"


def write_summary(out_dir: str) -> str:
    text = build_summary(out_dir)
    path = os.path.join(out_dir, "pilot-summary.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("쓴 파일:", path, len(text.splitlines()), "줄")
    return path
