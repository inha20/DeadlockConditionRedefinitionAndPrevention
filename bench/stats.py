"""통계 도구. prereg/README.md §4의 공통 규약을 구현한다. AI 초안이며 사람의 검토 전이다.

SP-2  시드(독립 입력)를 단위로 한 백분위 부트스트랩. 재표집 수 B는 10,000 이상이고 보정한 수준의 한쪽 꼬리에
      재표본이 100개 이상 들어가도록 늘린다(required_resamples).
SP-3  짝지은 비율 A/B의 기하평균 비율과 구간(paired_ratio_ci). '나쁘지 않다'와 '유의하게 좋다'는 구간 상한으로 판정한다
      (not_worse, clearly_better).
SP-4  머리 주장 가족 크기 k에 대한 수준 보정 1 - 0.05/k(adjusted_level).
K1    거짓 불안전·거짓 안전 비율의 Clopper–Pearson 정확 구간(clopper_pearson).
K4    크기 격자의 점별 중앙값에 대한 로그–로그 회귀 기울기와, 점 안에서 인스턴스를 재표집하는 부트스트랩 구간(slope_ci).

모든 무작위 함수는 numpy Generator를 인자로 받는다(bench/seeds.py의 rng). 검사는 bench/check_pipeline.py에 있다.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import numpy as np
from scipy import stats as sps


# ---------------------------------------------------------------- 수준과 재표집 수 (SP-2, SP-4)

def adjusted_level(k: int, alpha: float = 0.05) -> float:
    """머리 주장 가족 크기 k일 때의 구간 수준 1 - alpha/k (Bonferroni형)."""
    if k < 1:
        raise ValueError("k >= 1")
    return 1.0 - alpha / k


def required_resamples(level: float, minimum: int = 10_000, tail_min: int = 100) -> int:
    """B >= minimum 이고 B * (한쪽 꼬리 확률) >= tail_min 이 되는 가장 작은 B."""
    tail = (1.0 - level) / 2.0
    if not 0.0 < tail < 0.5:
        raise ValueError("level must be in (0, 1)")
    return max(minimum, math.ceil(tail_min / tail))


# ---------------------------------------------------------------- K1: Clopper–Pearson

def clopper_pearson(x: int, n: int, level: float = 0.95) -> tuple[float, float]:
    """이항 비율 x/n의 정확(Clopper–Pearson) 양쪽 구간."""
    if n < 1 or not 0 <= x <= n:
        raise ValueError("0 <= x <= n, n >= 1")
    a = 1.0 - level
    lo = 0.0 if x == 0 else float(sps.beta.ppf(a / 2.0, x, n - x + 1))
    hi = 1.0 if x == n else float(sps.beta.ppf(1.0 - a / 2.0, x + 1, n - x))
    return lo, hi


def _binom_pmf(k: int, n: int, p: float) -> float:
    if p <= 0.0:
        return 1.0 if k == 0 else 0.0
    if p >= 1.0:
        return 1.0 if k == n else 0.0
    logc = math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
    return math.exp(logc + k * math.log(p) + (n - k) * math.log1p(-p))


def clopper_pearson_bisect(x: int, n: int, level: float = 0.95) -> tuple[float, float]:
    """scipy의 베타 분위수를 쓰지 않는 독립 구현. 이항 꼬리 확률을 직접 더해 이분법으로 구한다(검사용)."""
    a = 1.0 - level

    def upper_tail(p: float) -> float:   # P(X >= x | p)
        return sum(_binom_pmf(k, n, p) for k in range(x, n + 1))

    def lower_tail(p: float) -> float:   # P(X <= x | p)
        return sum(_binom_pmf(k, n, p) for k in range(0, x + 1))

    lo = 0.0
    if x > 0:           # upper_tail(p)는 p에 대해 증가. upper_tail(lo) = a/2 인 lo
        l, h = 0.0, 1.0
        for _ in range(200):
            mid = (l + h) / 2.0
            if upper_tail(mid) < a / 2.0:
                l = mid
            else:
                h = mid
        lo = (l + h) / 2.0
    hi = 1.0
    if x < n:           # lower_tail(p)는 p에 대해 감소. lower_tail(hi) = a/2 인 hi
        l, h = 0.0, 1.0
        for _ in range(200):
            mid = (l + h) / 2.0
            if lower_tail(mid) > a / 2.0:
                l = mid
            else:
                h = mid
        hi = (l + h) / 2.0
    return lo, hi


# ---------------------------------------------------------------- SP-2: 백분위 부트스트랩

_STATS: dict[str, Callable[[np.ndarray], np.ndarray]] = {
    "median": lambda a: np.median(a, axis=1),
    "mean": lambda a: a.mean(axis=1),
}


def _percentile_interval(boot: np.ndarray, level: float) -> tuple[float, float]:
    tail = (1.0 - level) / 2.0
    return float(np.quantile(boot, tail)), float(np.quantile(boot, 1.0 - tail))


def bootstrap_distribution(values: Sequence[float], stat: str | Callable, B: int, g: np.random.Generator,
                           chunk_cells: int = 4_000_000) -> np.ndarray:
    """values를 단위로 한 B개의 부트스트랩 요약값. stat은 'median', 'mean' 또는 (B_c, n) 배열을 행마다 요약하는 함수."""
    arr = np.asarray(values, dtype=float)
    n = arr.size
    if n < 2:
        raise ValueError("부트스트랩에는 값이 2개 이상 필요하다")
    f = _STATS[stat] if isinstance(stat, str) else stat
    out = np.empty(B)
    step = max(1, chunk_cells // n)
    done = 0
    while done < B:
        b = min(step, B - done)
        idx = g.integers(0, n, size=(b, n))
        out[done:done + b] = f(arr[idx])
        done += b
    return out


def percentile_ci(values: Sequence[float], stat: str | Callable = "median", level: float = 0.95,
                  B: int | None = None, g: np.random.Generator | None = None) -> dict:
    """요약값(기본 중앙값)의 백분위 부트스트랩 구간. B를 안 주면 required_resamples(level)."""
    if g is None:
        raise ValueError("Generator가 필요하다(bench.seeds.rng)")
    arr = np.asarray(values, dtype=float)
    B = required_resamples(level) if B is None else B
    f = _STATS[stat] if isinstance(stat, str) else stat
    est = float(f(arr[None, :])[0])
    boot = bootstrap_distribution(arr, stat, B, g)
    lo, hi = _percentile_interval(boot, level)
    return {"estimate": est, "lo": lo, "hi": hi, "level": level, "B": B, "n": int(arr.size)}


def paired_ratio_ci(a: Sequence[float], b: Sequence[float], level: float = 0.95, B: int | None = None,
                    g: np.random.Generator | None = None) -> dict:
    """같은 인스턴스끼리 짝지은 비율 a_i/b_i의 기하평균 비율과 백분위 부트스트랩 구간(SP-2, SP-3).
    값은 모두 양수여야 한다. 0이 있으면 호출한 쪽이 처리 방침을 정해 따로 보고한다."""
    if g is None:
        raise ValueError("Generator가 필요하다(bench.seeds.rng)")
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.shape != b.shape:
        raise ValueError("짝이 맞지 않는다")
    if (a <= 0).any() or (b <= 0).any():
        raise ValueError("비율은 양수 값에서만 정의된다")
    r = np.log(a / b)
    B = required_resamples(level) if B is None else B
    boot = bootstrap_distribution(r, "mean", B, g)
    lo, hi = _percentile_interval(boot, level)
    return {"ratio": float(math.exp(r.mean())), "lo": math.exp(lo), "hi": math.exp(hi), "level": level, "B": B, "n": int(r.size)}


def not_worse(ci: dict, delta: float = 0.05) -> bool:
    """A/B 구간의 상한이 1 + delta 이하이면 A가 B보다 '나쁘지 않다'(SP-3)."""
    return ci["hi"] <= 1.0 + delta


def clearly_better(ci: dict) -> bool:
    """A/B 구간의 상한이 1 미만이면 A가 B보다 '유의하게 좋다'(작을수록 좋은 지표, SP-3)."""
    return ci["hi"] < 1.0


# ---------------------------------------------------------------- K4: 로그–로그 기울기

def loglog_slope(xs: Sequence[float], ys: Sequence[float]) -> dict:
    """log2 y = a + s log2 x 의 최소제곱 기울기 s. 점이 2개 이상이고 x가 서로 달라야 한다."""
    x = np.log2(np.asarray(xs, dtype=float))
    y = np.log2(np.asarray(ys, dtype=float))
    if x.size < 2 or np.ptp(x) == 0:
        raise ValueError("서로 다른 x가 2개 이상 필요하다")
    xm, ym = x.mean(), y.mean()
    sxx = float(((x - xm) ** 2).sum())
    s = float(((x - xm) * (y - ym)).sum() / sxx)
    a = float(ym - s * xm)
    ss_tot = float(((y - ym) ** 2).sum())
    ss_res = float(((y - (a + s * x)) ** 2).sum())
    r2 = 1.0 if ss_tot == 0 else 1.0 - ss_res / ss_tot
    return {"slope": s, "intercept": a, "r2": r2, "points": int(x.size)}


def slope_ci(points: Sequence[tuple[float, Sequence[float]]], level: float = 0.95, B: int | None = None,
             g: np.random.Generator | None = None, summary: str = "median") -> dict:
    """점마다 (크기 x, 그 점의 인스턴스별 값들). 점별 요약값(기본 중앙값)에 대한 기울기와,
    점 안에서 인스턴스를 재표집해 요약값과 기울기를 다시 계산하는 부트스트랩 구간(SP-2, K4)."""
    if g is None:
        raise ValueError("Generator가 필요하다(bench.seeds.rng)")
    xs = np.array([float(p[0]) for p in points])
    vals = [np.asarray(p[1], dtype=float) for p in points]
    if (np.concatenate(vals) <= 0).any():
        raise ValueError("로그를 취하므로 값은 양수여야 한다")
    f = _STATS[summary]
    est = loglog_slope(xs, [float(f(v[None, :])[0]) for v in vals])
    B = required_resamples(level) if B is None else B
    lx = np.log2(xs)
    xm = lx.mean()
    sxx = float(((lx - xm) ** 2).sum())
    cols = [np.log2(bootstrap_distribution(v, summary, B, g)) for v in vals]
    Y = np.stack(cols, axis=1)                      # (B, P)
    slopes = ((lx - xm)[None, :] * (Y - Y.mean(axis=1, keepdims=True))).sum(axis=1) / sxx
    lo, hi = _percentile_interval(slopes, level)
    return {"slope": est["slope"], "lo": lo, "hi": hi, "r2": est["r2"], "level": level, "B": B, "points": int(xs.size)}


# ---------------------------------------------------------------- 검사용 시뮬레이션

def coverage_experiment(sampler: Callable[[np.random.Generator, int], np.ndarray], true_value: float, n: int,
                        trials: int, level: float, B: int, g: np.random.Generator, stat: str = "median") -> float:
    """sampler가 만드는 크기 n의 표본에서 percentile_ci가 true_value를 덮는 비율. 방법이 거의 맞게 작동하는지 보는 점검이다."""
    hit = 0
    for _ in range(trials):
        sample = sampler(g, n)
        ci = percentile_ci(sample, stat, level, B, g)
        hit += ci["lo"] <= true_value <= ci["hi"]
    return hit / trials
