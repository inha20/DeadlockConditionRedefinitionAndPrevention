"""RQ3 워크로드 L1(합성)과 L2(고전 문제) 생성기 (prereg/RQ3.md §4.4, 동결 전 측정 도구).

L1 매개변수(계획용 값. 동결 때 확정)
  T          스레드 수(중심값 16)
  R          락(= 락 클래스) 수(중심값 32)
  zipf_s     락 선택 치우침의 Zipf 지수. 경쟁 수준의 정의: 낮음 0, 중간 0.8, 높음 1.2
  depth      중첩 깊이 d (작업이 동시에 쥐는 락 수) ∈ {1, 2, 4}
  p_viol     순서 위반 확률 p_v ∈ {0, 0.05, 0.25}: 작업이 락을 전역 클래스 순서(번호 오름차순)대로 얻지 않을 확률
  rho_rb     롤백 비용 계수 ∈ {1, 10}(시뮬레이션이 쓴다. 이 생성기는 값을 싣기만 한다)
  cs_dist    임계구역 길이 분포: 'exp' 또는 'lognormal'(평균 cs_mean, 로그정규의 시그마 1)
  tasks_per_thread  스레드당 작업 수

작업(Task)은 직선 락 프로그램 ops(('A', l), ('R', l) 열)와 연산 뒤에 쓰는 시간 work(같은 길이)다. 락은 모두 쥔 뒤
획득의 역순으로 반납한다(중첩). 획득 뒤의 work가 그 락을 쥔 채 하는 일의 길이이고, 반납 뒤의 work는 0이다.

생성은 (마스터 시드, 매개변수, 인스턴스 번호)에서 결정적이다(bench/seeds.py). 락 인기 순위와 락 번호의 대응은
인스턴스마다 무작위 순열이다(hot_random=True): 인기 있는 락이 번호가 낮은 쪽에 몰리지 않게 해 경쟁과 순서 위반이
섞이지 않게 한다. 이 선택은 열린 항목이다(docs/rq3/workloads.md O3-19).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .. import seeds


@dataclass(frozen=True)
class Task:
    ops: tuple
    work: tuple

    @property
    def lockset(self):
        return frozenset(l for k, l in self.ops if k == "A")


@dataclass(frozen=True)
class Workload:
    name: str
    nlocks: int
    threads: tuple                  # 스레드마다 Task의 튜플
    params: dict = field(default_factory=dict)

    @property
    def T(self):
        return len(self.threads)

    def first_programs(self):
        """스레드마다 첫 작업의 프로그램(소규모 전수 검사와 락 표가 쓰는 형태)."""
        return [t[0].ops for t in self.threads]


@dataclass(frozen=True)
class L1Params:
    T: int = 16
    R: int = 32
    zipf_s: float = 0.8
    depth: int = 2
    p_viol: float = 0.05
    rho_rb: float = 1.0
    cs_dist: str = "exp"
    cs_mean: float = 1.0
    tasks_per_thread: int = 1
    hot_random: bool = True

    def label(self):
        return (f"T{self.T}-R{self.R}-s{self.zipf_s}-d{self.depth}-pv{self.p_viol}-rb{self.rho_rb}"
                f"-{self.cs_dist}-n{self.tasks_per_thread}")


def zipf_weights(R: int, s: float) -> np.ndarray:
    w = 1.0 / np.arange(1, R + 1, dtype=float) ** s
    return w / w.sum()


def _cs_length(rng, dist: str, mean: float) -> float:
    if dist == "exp":
        return float(rng.exponential(mean))
    if dist == "lognormal":
        sigma = 1.0
        mu = np.log(mean) - sigma * sigma / 2.0      # 평균이 mean이 되도록
        return float(rng.lognormal(mu, sigma))
    raise ValueError(dist)


def make_l1(params: L1Params, master: str, instance: int) -> Workload:
    p = params
    if p.depth > p.R:
        raise ValueError("중첩 깊이가 락 수보다 큼")
    rng = seeds.rng(master, "L1", p.label(), instance)
    weights = zipf_weights(p.R, p.zipf_s)
    # 인기 순위 -> 락 번호. hot_random이면 무작위 순열, 아니면 항등(인기 순위 1 = 락 0)
    rank_to_lock = rng.permutation(p.R) if p.hot_random else np.arange(p.R)
    threads = []
    for _ in range(p.T):
        tasks = []
        for _ in range(p.tasks_per_thread):
            ranks = rng.choice(p.R, size=p.depth, replace=False, p=weights)
            locks = sorted(int(rank_to_lock[r]) for r in ranks)       # 번호 오름차순 = 전역 클래스 순서
            if p.depth >= 2 and rng.random() < p.p_viol:
                order = list(locks)
                while order == sorted(order):
                    order = [int(x) for x in rng.permutation(locks)]
            else:
                order = locks
            ops, work = [], []
            for l in order:
                ops.append(("A", l))
                work.append(_cs_length(rng, p.cs_dist, p.cs_mean))
            for l in reversed(order):
                ops.append(("R", l))
                work.append(0.0)
            tasks.append(Task(tuple(ops), tuple(work)))
        threads.append(tuple(tasks))
    return Workload(f"L1:{p.label()}#{instance}", p.R, tuple(threads), dict(p.__dict__))


def violation_fraction(w: Workload) -> float:
    """작업 중 락 획득 순서가 오름차순이 아닌 작업의 비율(생성기 점검용)."""
    n = bad = 0
    for th in w.threads:
        for tk in th:
            acq = [l for k, l in tk.ops if k == "A"]
            n += 1
            bad += acq != sorted(acq)
    return bad / n if n else 0.0


# ---------------------------------------------------------------- L2 고전 문제

def dining_philosophers(n: int, asymmetric: bool = False, cs_mean: float = 1.0, master: str = "rq3", instance: int = 0):
    """식사하는 철학자 n명. 포크 i는 락 i. 철학자 i는 포크 i를 얻고 포크 (i+1) mod n을 얻는다.
    asymmetric이면 마지막 철학자만 순서를 뒤집는다(고전적 교착 회피 변형)."""
    rng = seeds.rng(master, "L2-dining", n, asymmetric, instance)
    threads = []
    for i in range(n):
        a, b = i, (i + 1) % n
        if asymmetric and i == n - 1:
            a, b = b, a
        ops = (("A", a), ("A", b), ("R", b), ("R", a))
        work = (float(rng.exponential(cs_mean)), float(rng.exponential(cs_mean)), 0.0, 0.0)
        threads.append((Task(ops, work),))
    return Workload(f"L2:dining-{n}{'-asym' if asymmetric else ''}#{instance}", n, tuple(threads), {"n": n, "asymmetric": asymmetric})


def account_transfer(T: int, accounts: int, tasks_per_thread: int = 1, cs_mean: float = 1.0, master: str = "rq3", instance: int = 0):
    """계좌 이체: 스레드마다 서로 다른 두 계좌를 고르고 인자 순서대로(보내는 쪽, 받는 쪽) 락을 얻는다."""
    rng = seeds.rng(master, "L2-transfer", T, accounts, tasks_per_thread, instance)
    threads = []
    for _ in range(T):
        tasks = []
        for _ in range(tasks_per_thread):
            a, b = (int(x) for x in rng.choice(accounts, size=2, replace=False))
            ops = (("A", a), ("A", b), ("R", b), ("R", a))
            work = (float(rng.exponential(cs_mean)), float(rng.exponential(cs_mean)), 0.0, 0.0)
            tasks.append(Task(ops, work))
        threads.append(tuple(tasks))
    return Workload(f"L2:transfer-T{T}-A{accounts}#{instance}", accounts, tuple(threads), {"T": T, "accounts": accounts})
