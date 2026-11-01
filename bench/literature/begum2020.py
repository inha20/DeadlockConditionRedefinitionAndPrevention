"""문헌 예제 입력(F-lit): Begum·Faruque·Miah·Das 2020의 예제(표 I–IV)와 본문이 밝힌 결과.

출처: Begum M, Faruque O, Miah MWR, Das BC (2020) "An Improved Safety Detection Algorithm Towards Deadlock Avoidance". ISCAIE 2020,
쪽 73–78(제공받은 PDF의 쪽 번호와 쪽 하단의 ©2020 IEEE 표기). IEEE Xplore 문서 번호 9108818(인벤토리 R6-05). DOI 문자열은 PDF 텍스트에 없어 확인하지 못했다.
(DBDAA 논문은 이 논문을 'Momotaz et al.'로 부른다: 첫 저자 Momotaz Begum의 이름이다. DBDAA 논문 참고문헌 4번이 이 논문이다.)

이 논문은 IEEE의 저작물이다. 재현 점검에 필요한 최소한의 숫자(예제 하나의 입력과 논문이 밝힌 결과)만 옮겼고 문장은 옮기지 않았다.
옮긴 값은 사용자가 2026-11-01에 제공한 PDF(6쪽, SHA-256 c8a06077…)에서 읽었다. PDF는 저장소에 넣지 않는다.
옮긴 값의 정합성은 bench/check_variants_begum.py가 점검한다(표 II = 표 I의 Maximum − Allocation, Available = Resource − Σ Allocation,
표 III의 정렬 순서, 표 IV의 Available 열 = 앞 행의 Available + 앞 프로세스의 Allocation). 해석은 docs/rq6/variants.md에 있다.
"""
from __future__ import annotations

from bench.state import BState

RESOURCE = (25, 30, 20, 30, 35)   # A..E (본문 III.B: 각 자원의 인스턴스 수)

# 표 I: "프로세스 | Maximum need(A..E) | Current allocation(A..E)"
TABLE_1 = """
P0 | 7 0 6 0 4 | 3 0 3 0 3
P1 | 3 8 4 0 0 | 2 1 1 0 0
P2 | 0 6 3 7 0 | 0 4 0 5 0
P3 | 2 0 0 9 7 | 2 0 0 6 5
P4 | 4 3 2 0 1 | 2 3 2 0 1
P5 | 8 7 6 2 5 | 5 6 3 2 4
P6 | 5 2 1 8 9 | 4 2 1 4 7
P7 | 3 6 9 0 0 | 3 6 2 0 0
P8 | 0 4 8 2 5 | 0 3 3 2 5
P9 | 0 0 9 7 8 | 0 0 3 7 3
"""

# 표 II: "프로세스 | Needed allocation(A..E) | Maximum_Needed_allocation"
TABLE_2 = """
P0 | 4 0 3 0 1 | 4
P1 | 1 7 3 0 0 | 7
P2 | 0 2 3 2 0 | 3
P3 | 0 0 0 3 2 | 3
P4 | 2 0 0 0 0 | 2
P5 | 3 1 3 0 1 | 3
P6 | 1 0 0 4 2 | 4
P7 | 0 0 7 0 0 | 7
P8 | 0 1 5 0 0 | 5
P9 | 0 0 6 0 5 | 6
"""

# 표 III의 순서(= 표 IV의 처리 순서): Maximum_Needed_allocation 오름차순.
SORTED_ORDER = ["P4", "P2", "P3", "P5", "P0", "P6", "P8", "P9", "P1", "P7"]

# 표 IV: "프로세스 | 그 시점의 Available(A..E) | Minimum available | 조건 Maximum_Needed ≤ Minimum available". 열 이름은 논문의 것.
TABLE_4 = """
P4 | 4 5 2 4 7 | 2 | True
P2 | 6 8 4 4 8 | 4 | True
P3 | 6 12 4 9 8 | 4 | True
P5 | 8 12 4 15 13 | 4 | True
P0 | 13 18 7 17 17 | 7 | True
P6 | 16 18 10 17 20 | 10 | True
P8 | 20 20 11 21 27 | 11 | True
P9 | 20 23 14 23 32 | 14 | True
P1 | 20 23 17 30 35 | 17 | True
P7 | 22 24 18 30 35 | 18 | True
"""
FINAL_AVAILABLE = (25, 30, 20, 30, 35)   # 표 IV의 맨 아래 줄 = Resource

INITIAL_AVAILABLE = (4, 5, 2, 4, 7)     # 본문 III.B
SAFE_SEQUENCE = ["P4", "P2", "P3", "P5", "P0", "P6", "P8", "P9", "P1", "P7"]   # 본문 III.B의 결과
CLAIMED_COMPARISONS = 10       # 본문: 이 예제에서 안전 검사에 비교 10회
CLAIMED_ORIGINAL_AT_LEAST = 50  # 본문: 원래의 뱅커라면 같은 일에 적어도 50회

# 논문 쪽에서 표들이 서로 맞지 않는 곳(옮기다 생긴 실수가 아님. PDF에서 확인). 코드는 이 값을 쓰지 않고 정합성 점검이 같은 불일치가 없음을 본다.
#   - 표 III의 P7 행: Needed allocation E가 5로 인쇄(표 II와 Maximum − Allocation은 0).
#   - 표 IV의 P7 행: Maximum_Needed_allocation 열이 5로 인쇄(표 II·III은 7). Available(18)과 비교는 어느 값이든 True다.
PRINT_ERRORS_NOTE = ("표 III의 P7 Needed allocation E가 5로 인쇄(표 II는 0)", "표 IV의 P7 Maximum_Needed_allocation이 5로 인쇄(표 II·III은 7)")


def _nums(s: str) -> list[int]:
    return [int(x) for x in s.split()]


def parse_table1() -> list[dict]:
    rows = []
    for line in TABLE_1.strip().splitlines():
        pid, mx, al = [p.strip() for p in line.split("|")]
        rows.append({"id": pid, "max": _nums(mx), "alloc": _nums(al)})
    return rows


def parse_table2() -> list[dict]:
    rows = []
    for line in TABLE_2.strip().splitlines():
        pid, nd, mn = [p.strip() for p in line.split("|")]
        rows.append({"id": pid, "need": _nums(nd), "max_needed": int(mn)})
    return rows


def parse_table4() -> list[dict]:
    rows = []
    for line in TABLE_4.strip().splitlines():
        pid, av, mn, ok = [p.strip() for p in line.split("|")]
        rows.append({"id": pid, "avail": _nums(av), "min_avail": int(mn), "ok": ok == "True"})
    return rows


def load():
    """(BState, 프로세스 이름 목록, 표 I의 행 목록). Need는 Maximum − Allocation이다(표 II와 같다. 점검이 확인한다)."""
    rows = parse_table1()
    alloc = [r["alloc"] for r in rows]
    need = [[r["max"][j] - r["alloc"][j] for j in range(len(RESOURCE))] for r in rows]
    return BState.make(RESOURCE, alloc, need), [r["id"] for r in rows], rows
