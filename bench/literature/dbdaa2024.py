"""문헌 예제 입력(F-lit): Zohora·Farhin·Kaiser 2024 (DBDAA)의 표 2–9와 본문이 밝힌 결과.

출처: Zohora MF, Farhin F, Kaiser MS (2024) "DBDAA: A real-time approach to Dynamic Banker's Deadlock Avoidance
Algorithm with optimized time complexity". PLoS ONE 19(9): e0310807. doi:10.1371/journal.pone.0310807.
크리에이티브 커먼즈 저작자표시(CC BY) 오픈 액세스 글이다(2026-11-01, PMC11414889 쪽의 문구로 확인).

표의 숫자는 논문의 표를 그대로 옮겼다(2026-11-01, 내장 브라우저로 열람. 표 번호는 논문의 번호).
옮긴 값의 정합성은 bench/check_variants.py가 점검한다: 인쇄된 Need = Maximum − Allocation, Available = Resource − Σ Allocation
(논문의 식 2, 본문이 적은 Available 벡터와 일치), 추적표(표 5–7)와 본문 서술(순서·비교 횟수)의 일치.
이 파일은 데이터만 담는다. 해석은 docs/rq6/variants.md에 있다.
"""
from __future__ import annotations

from bench.state import BState

RESOURCE = (20, 25, 30, 35, 30)   # R1..R5 (본문 '실험 데이터')
CYCLE_M = 30                       # 한 주기 m (본문)

# 표 2–4: "ID AT BT | Maximum(R1..R5) | Allocation(R1..R5) | Need(R1..R5)". 모든 AT = 0.
TABLE_2 = """
P1 0 3 | 8 4 11 11 5 | 4 2 3 4 2 | 4 2 8 7 3
P2 0 4 | 5 6 4 12 7 | 0 3 2 5 3 | 5 3 2 7 4
P3 0 2 | 7 15 12 10 5 | 2 1 2 1 3 | 5 14 10 9 2
P4 0 1 | 7 8 5 3 5 | 1 5 3 2 2 | 6 3 2 1 3
P5 0 5 | 14 8 7 7 4 | 3 1 1 3 1 | 11 7 6 4 3
P6 0 3 | 6 18 10 14 4 | 1 2 0 2 0 | 5 16 10 12 4
P7 0 2 | 5 5 4 5 5 | 3 2 1 3 4 | 2 3 3 2 1
P8 0 4 | 12 12 15 9 20 | 2 0 2 4 2 | 10 12 13 5 18
P9 0 1 | 2 5 4 10 5 | 0 2 3 5 3 | 2 3 1 5 2
P10 0 5 | 2 3 3 3 3 | 0 2 3 2 2 | 2 1 0 1 1
"""

TABLE_3 = """
P1 0 3 | 9 10 8 12 10 | 2 4 2 2 2 | 7 6 6 10 8
P2 0 4 | 10 13 12 14 14 | 1 3 3 3 4 | 9 10 9 11 10
P3 0 2 | 12 9 10 9 8 | 3 1 2 2 2 | 9 8 8 7 6
P4 0 1 | 3 3 4 4 5 | 1 1 1 1 0 | 2 2 3 3 4
P5 0 5 | 5 7 5 7 9 | 1 2 3 4 3 | 4 5 2 3 6
P6 0 3 | 6 4 5 6 2 | 2 1 1 1 1 | 4 3 4 5 1
P7 0 2 | 16 14 13 17 14 | 1 2 4 5 4 | 15 12 9 12 10
P8 0 4 | 13 12 16 20 20 | 3 0 3 3 5 | 10 12 13 17 15
P9 0 1 | 12 14 14 13 16 | 2 2 4 4 3 | 10 12 10 9 13
P10 0 5 | 15 22 14 15 20 | 0 4 4 2 0 | 15 18 10 13 20
"""

TABLE_4 = """
P1 0 3 | 15 16 17 19 18 | 5 4 2 2 4 | 10 12 15 17 14
P2 0 4 | 8 6 8 11 10 | 2 2 3 4 2 | 6 4 5 7 8
P3 0 2 | 5 5 5 8 5 | 4 3 2 4 3 | 1 2 3 4 2
P4 0 1 | 9 8 14 18 15 | 1 1 1 3 2 | 8 7 13 15 13
P5 0 5 | 16 19 22 30 24 | 0 2 2 4 0 | 16 17 20 26 24
P6 0 3 | 15 18 23 25 26 | 0 2 3 2 4 | 15 16 20 23 22
P7 0 2 | 6 7 10 12 11 | 1 1 1 3 3 | 5 6 9 9 8
P8 0 4 | 19 20 27 28 26 | 2 3 4 3 2 | 17 17 23 25 24
P9 0 1 | 10 12 13 16 17 | 1 4 3 0 3 | 9 8 10 16 14
P10 0 5 | 17 17 19 26 22 | 2 1 2 2 2 | 15 16 17 24 20
"""

TABLES = {"best": TABLE_2, "average": TABLE_3, "worst": TABLE_4}

# 표 5–7(안전 검사 추적): "프로세스 | 최대 Need 1회, 2회 | Available(R1..R5) | 최소 Available 1회, 2회 | 안전 | 비교 횟수".
# 빈 칸은 '-'. 처리 순서(SRQ) 그대로다.
TRACE_5_BEST = """
P10 | 2 - | 4 5 10 4 8 | 4 - | Yes | 1
P7 | 3 - | 4 7 13 6 10 | 4 - | Yes | 1
P9 | 5 - | 7 9 14 9 14 | 7 - | Yes | 1
P4 | 6 - | 7 11 17 14 17 | 7 - | Yes | 1
P2 | 7 - | 8 16 20 16 19 | 8 - | Yes | 1
P1 | 8 - | 8 19 22 21 22 | 8 - | Yes | 1
P5 | 11 - | 12 21 25 25 24 | 12 - | Yes | 1
P3 | 14 - | 15 22 26 28 25 | 15 - | Yes | 1
P6 | 16 - | 17 23 28 29 28 | 17 - | Yes | 1
P8 | 18 - | 18 25 28 31 28 | 18 - | Yes | 1
"""

TRACE_6_AVERAGE = """
P4 | 4 3 | 4 5 3 8 6 | 3 4 | Yes | 4
P6 | 5 4 | 5 6 4 9 6 | 4 5 | Yes | 4
P5 | 6 5 | 7 7 5 10 7 | 5 7 | Yes | 4
P3 | 9 - | 8 9 8 14 10 | 8 - | No | 2
P1 | 10 8 | 8 9 8 14 10 | 8 8 | Yes | 4
P2 | 11 10 | 10 13 10 16 12 | 10 10 | Yes | 4
P9 | 13 12 | 11 16 13 19 16 | 11 13 | Yes | 4
P7 | 15 - | 13 18 17 23 19 | 13 - | No | 2
P8 | 17 15 | 13 18 17 23 19 | 13 17 | Yes | 4
P10 | 20 18 | 16 18 20 26 24 | 16 18 | Yes | 4
"""

TRACE_7_WORST = """
P3 | 4 3 | 2 2 7 8 5 | 2 2 | Yes | 7
P2 | 8 7 | 6 5 9 12 8 | 5 6 | Yes | 7
P7 | 9 9 | 8 7 12 16 10 | 7 8 | Yes | 7
P4 | 15 13 | 9 8 13 19 13 | 8 9 | Yes | 7
P9 | 16 14 | 10 9 14 22 15 | 9 10 | Yes | 7
P1 | 17 15 | 11 13 17 22 18 | 11 13 | Yes | 7
P6 | 23 22 | 16 17 19 24 22 | 16 17 | No | 7
P10 | 24 20 | 16 17 19 24 22 | 16 17 | Yes | 7
P8 | 25 24 | 18 18 21 26 24 | 18 18 | No | 7
P5 | 26 24 | 18 18 21 26 24 | 18 18 | Yes | 7
"""

TRACES = {"best": TRACE_5_BEST, "average": TRACE_6_AVERAGE, "worst": TRACE_7_WORST}

# 본문이 밝힌 DBDAA의 결과(순서와 총 비교 횟수. 표 8)와 간트 차트가 끝난 시각.
DBDAA_RESULT = {
    "best": {"safe": ["P10", "P7", "P9", "P4", "P2", "P1", "P5", "P3", "P6", "P8"], "primary_unsafe": [],
             "comparisons": 10, "gantt_end": 30},
    "average": {"safe": ["P4", "P6", "P5", "P1", "P2", "P9", "P8", "P10"], "primary_unsafe": ["P3", "P7"],
                "comparisons": 36, "gantt_end": 26},
    "worst": {"safe": ["P3", "P2", "P7", "P4", "P9", "P1", "P10", "P5"], "primary_unsafe": ["P6", "P8"],
              "comparisons": 70, "gantt_end": 23},
}

# 표 8: 비교 대상 알고리즘의 비교 횟수. 본문이 '원래의 뱅커'([1], [5], [9], [12]가 같은 순서를 낸다)의 안전 순서를 적었다.
BASELINE_RESULT = {
    "best": {"count": 85, "safe": ["P7", "P1", "P2", "P4", "P3", "P5", "P6", "P8", "P9", "P10"]},
    "average": {"count": 100, "safe": ["P4", "P5", "P6", "P1", "P2", "P3", "P8", "P7", "P9", "P10"]},
    "worst": {"count": 125, "safe": ["P3", "P2", "P7", "P4", "P9", "P1", "P10", "P5", "P6", "P8"]},
}
TABLE_8 = {  # 알고리즘 -> (표 2, 표 3, 표 4)
    "original banker [1]": (85, 100, 125),
    "Momotaz et al. 2020 [4]": (10, "Unsafe", "Unsafe"),
    "Bondarenko et al. 2021 [5]": (85, 100, 125),
    "Song et al. 2021 [9]": (85, 100, 125),
    "Wicaksono et al. 2023 [12]": (85, 100, 125),
    "DBDAA": (10, 36, 70),
}
TABLE_9 = {  # 알고리즘 -> (최선, 평균, 최악) 시간 복잡도(논문 표기 그대로)
    "original banker [1]": ("O(nd)", "O(n2d)", "O(n2d)"),
    "Momotaz et al. [4]": ("O(n)", "O(nd)", "O(n(d + 2))"),
    "Bondarenko et al. [5]": ("O(nd)", "O(n2d)", "O(n2d)"),
    "Song et al. [9]": ("O(nd)", "O(n2d)", "O(n2d)"),
    "Wicaksono et al. [12]": ("O(nd)", "O(n2d)", "O(n2d)"),
    "DBDAA": ("O(n)", "O(n(3d + 2)/4)", "O(n(d + d/2))"),
}


def _nums(s: str) -> list[int]:
    return [int(x) for x in s.split()]


def parse_table(text: str) -> list[dict]:
    rows = []
    for line in text.strip().splitlines():
        head, mx, al, nd = [p.strip() for p in line.split("|")]
        pid, at, bt = head.split()
        rows.append({"id": pid, "at": int(at), "bt": int(bt), "max": _nums(mx), "alloc": _nums(al), "need_printed": _nums(nd)})
    return rows


def parse_trace(text: str) -> list[dict]:
    rows = []
    for line in text.strip().splitlines():
        pid, mn, av, ma, safe, comps = [p.strip() for p in line.split("|")]

        def two(s):
            return [None if x == "-" else int(x) for x in s.split()]
        rows.append({"id": pid, "max_need": two(mn), "avail": _nums(av), "min_avail": two(ma),
                     "safe": safe == "Yes", "comparisons": int(comps)})
    return rows


# 옮긴 표에서 '인쇄된 Need ≠ Maximum − Allocation'인 행(논문 쪽의 불일치. 옮기다 생긴 실수가 아님을 점검이 따로 확인한다).
# 표 3의 P4: Maximum R5 = 5, Allocation R5 = 0이라 식 1의 값은 5인데 Need R5는 4로 인쇄됐다. 표 6(최대 Need 4)과 본문('4 > 3', '4 ≤ 6')은
# 인쇄된 Need(4)를 따르고, 5를 따르는 것은 식 1과 표 3의 Maximum·Allocation 열이다(본문의 'Max_Need (5)'는 값이 아니라 자원 위치 R5를
# 가리킨다. 2026-11-01 저널 PDF로 확인). Available(R5 = 6)은 Allocation 0과 맞는다.
KNOWN_TABLE_INCONSISTENCIES = {"best": [], "average": ["P4"], "worst": []}


def inconsistent_rows(rows: list[dict]) -> list[str]:
    return [r["id"] for r in rows if r["need_printed"] != [r["max"][j] - r["alloc"][j] for j in range(len(RESOURCE))]]


def load(case: str, use_printed_need: bool = True):
    """('best'|'average'|'worst') -> (BState, 프로세스 이름 목록, 표의 행 목록).
    Need는 기본으로 인쇄된 값을 쓴다(추적표와 본문이 그 값을 따른다). use_printed_need=False면 식 1(Maximum − Allocation)로 계산한다.
    두 값이 다른 행은 표 3의 P4 하나뿐이다(KNOWN_TABLE_INCONSISTENCIES)."""
    rows = parse_table(TABLES[case])
    alloc = [r["alloc"] for r in rows]
    if use_printed_need:
        need = [r["need_printed"] for r in rows]
    else:
        need = [[r["max"][j] - r["alloc"][j] for j in range(len(RESOURCE))] for r in rows]
    return BState.make(RESOURCE, alloc, need), [r["id"] for r in rows], rows
