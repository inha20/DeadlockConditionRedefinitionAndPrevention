"""JSONL 결과의 요약. 지표 K1(판정 일치), K2(비교 횟수), K3(시간), K5(짝지은 비율)의 계산 보조.

여기서 계산하는 것은 도구의 점검과 파일럿(분산 추정)에 쓰는 요약이다. 동결 전에는 어떤 요약도 본 분석이 아니다.
"""
from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable

import numpy as np

from bench import stats as S


def counts(records: Iterable[dict], op: str = "is_safe") -> list[dict]:
    return [r for r in records if r.get("rec") == "count" and r.get("op") == op]


def k1(records: Iterable[dict], level: float = 0.95) -> list[dict]:
    """정책 × 셀 × op 별 판정 일치.

    is_safe  FU = 오라클 안전인데 정책 불안전(보수적), FS = 오라클 불안전인데 정책 안전(비보수적).
    request  보수적 = 오라클 GRANT인데 정책 DENY, 비보수적 = 오라클 DENY인데 정책 GRANT, 그 밖의 불일치는 other.
    비율의 구간은 Clopper–Pearson. 전수 범위에서는 구간 대신 개수를 쓴다(분모가 전수라서).
    """
    acc: dict[tuple, dict] = defaultdict(lambda: {"n": 0, "agree": 0, "FU": 0, "FS": 0, "other": 0})
    for r in records:
        if r.get("rec") != "count":
            continue
        key = (r["policy"], r["cell"], r["op"])
        a = acc[key]
        a["n"] += 1
        res, truth = r["result"], r["truth"]
        if res == truth:
            a["agree"] += 1
        elif r["op"] == "is_safe":
            a["FU" if truth else "FS"] += 1
        elif truth == "GRANT" and res == "DENY":
            a["FU"] += 1
        elif truth == "DENY" and res == "GRANT":
            a["FS"] += 1
        else:
            a["other"] += 1
    rows = []
    for (policy, cell, op), a in sorted(acc.items()):
        row = {"policy": policy, "cell": cell, "op": op, **a}
        row["FU_ci"] = S.clopper_pearson(a["FU"], a["n"], level)
        row["FS_ci"] = S.clopper_pearson(a["FS"], a["n"], level)
        rows.append(row)
    return rows


def metric_by_instance(records: Iterable[dict], policy: str, metric: str = "vec_cmp", op: str = "is_safe") -> dict:
    """{(셀, 번호): 값}. K2의 인스턴스별 비교 횟수."""
    return {(r["cell"], r["idx"]): r[metric] for r in counts(records, op) if r["policy"] == policy}


def time_by_instance(records: Iterable[dict], policy: str, which: str = "wall", agg: str = "median") -> dict:
    """{(셀, 번호): 호출당 시간(ns)}. which는 wall 또는 cpu, agg는 반복 사이의 요약(median 또는 min)."""
    key = f"{which}_ns_per_call"
    out = {}
    for r in records:
        if r.get("rec") == "time" and r["policy"] == policy:
            v = r[key]
            out[(r["cell"], r["idx"])] = float(np.median(v)) if agg == "median" else float(min(v))
    return out


def paired_by_cell(a: dict, b: dict, g: np.random.Generator, level: float = 0.95, B: int | None = None) -> dict:
    """셀별로 a/b의 짝지은 기하평균 비율과 구간. 값이 0인 쌍은 빼고 개수를 함께 돌려준다."""
    cells = sorted({k[0] for k in a} & {k[0] for k in b})
    out = {}
    for c in cells:
        idxs = sorted(i for (cc, i) in a if cc == c and (c, i) in b)
        xs = [a[(c, i)] for i in idxs]
        ys = [b[(c, i)] for i in idxs]
        keep = [(x, y) for x, y in zip(xs, ys) if x > 0 and y > 0]
        dropped = len(xs) - len(keep)
        if len(keep) >= 2:
            ci = S.paired_ratio_ci([x for x, _ in keep], [y for _, y in keep], level, B, g)
        else:
            ci = None
        out[c] = {"pairs": len(keep), "dropped_nonpositive": dropped, "ci": ci}
    return out


def variance_components(records: Iterable[dict], policy: str, cell: str, which: str = "wall") -> dict | None:
    """한 정책 × 셀의 로그 시간에 대한 일원 변량효과 분산 성분(ANOVA 추정).
    인스턴스 사이 분산 σ²_b와 같은 인스턴스를 반복해 잰 사이의 분산 σ²_w를 돌려준다. 파일럿에서 반복 수를 정하는 데 쓴다."""
    key = f"{which}_ns_per_call"
    rows = [np.log(np.asarray(r[key], dtype=float)) for r in records
            if r.get("rec") == "time" and r["policy"] == policy and r["cell"] == cell]
    if len(rows) < 2:
        return None
    R_ = min(len(x) for x in rows)
    if R_ < 2:
        return None
    mat = np.stack([x[:R_] for x in rows])                      # (I, R)
    I = mat.shape[0]
    ms_w = float(mat.var(axis=1, ddof=1).mean())
    ms_b = float(R_ * mat.mean(axis=1).var(ddof=1))
    sig_w = ms_w
    sig_b = max(0.0, (ms_b - ms_w) / R_)
    return {"instances": I, "repeats": R_, "sigma2_between": sig_b, "sigma2_within": sig_w,
            "sd_between": math.sqrt(sig_b), "sd_within": math.sqrt(sig_w)}
