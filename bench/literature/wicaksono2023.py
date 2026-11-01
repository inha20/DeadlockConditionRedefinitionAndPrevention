"""문헌 예제 입력(F-lit): Wicaksono·Baeti·Salma·Kardian 2023의 동적 뱅커 예제 (R6-06). AI 초안: 사람의 확인 전.

출처: JEEMECS 6(1), 2023 (PDF: jurnal.unmer.ac.id/index.php/jeemecs/article/download/8986/pdf. 인벤토리 R6-06, M41).
읽은 방법과 한계
  - 2026-11-01에 도구가 PDF 본문을 읽어 낸 텍스트로 읽었다. PDF 사본은 저장소에 없고, `pdftotext`로 하는 원문 대조(verify_*_pdf.py와 같은 것)는 아직 하지 않았다.
    그래서 아래 숫자는 '도구가 읽어 준 값'이다. 대신 값 사이의 중복(Need = Max − Allocation, 자원 총량, 표 2·5의 되짚기)이 크므로
    check_variants_wicaksono.py가 그 정합성을 기계로 점검한다. 정합성이 맞아도 인쇄본과의 일치를 보장하지는 않는다.
  - 논문의 저작권 조건(라이선스)은 확인하지 못했다. 그래서 4개 프로세스·3종 예제의 최소 수치만 옮기고 문장은 옮기지 않았다.
  - 표의 시각 표지(T0, T2, T4, T5)는 논문이 설명하지 않아 해석하지 않았다.

옮긴 것(논문이 인쇄한 값)
  - 표 1: 자원 총량 (10, 5, 5), 프로세스 p0–p3의 Max, Allocation, Need와 Available (3, 3, 2). Available은 p0 행에만 인쇄됐다.
  - 표 2(교재식 실행): p1 → p3 → p0 → p2. 단계마다 Work(그 프로세스를 끝내기 전의 Available)와 끝낸 뒤의 Available.
  - 표 4: p1·p3가 끝난 뒤 (Available (7, 4, 3)) 새 프로세스 p4가 도착한다. 논문은 (4, 3, 3)을 '요청'이라 부르나 표는 Max 열에 넣고 Allocation은 0이다.
  - 표 5(제안한 실행): p1 → p3 → p0 → p2 → p4.
이 예제의 도착 시점('p1과 p3가 끝난 직후')은 바깥 반복의 둘째 맨 앞으로 읽는다(해석 W-1. 근거는 check_variants_wicaksono.py가 보이는 재현 결과).

이 입력은 등록된 입력군이 아니다. 문헌 예제의 재현일 뿐 K1–K3의 결과가 아니다.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from bench.state import BState  # noqa: E402

TOTAL = (10, 5, 5)
NAMES = ["p0", "p1", "p2", "p3"]
MAXC = ((7, 5, 3), (3, 2, 2), (9, 0, 2), (2, 2, 2))
ALLOC = ((0, 1, 0), (2, 0, 0), (3, 0, 2), (2, 1, 1))
NEED_PRINTED = ((7, 4, 3), (1, 2, 2), (6, 0, 0), (0, 1, 1))
AVAIL_PRINTED = (3, 3, 2)

NEW_NAME = "p4"
NEW_MAX = (4, 3, 3)          # 표 4: 도착한 프로세스의 최대 청구(논문은 '요청'이라 부른다). Allocation은 (0, 0, 0)
AVAIL_AT_ARRIVAL = (7, 4, 3)  # 표 4: p1·p3가 끝난 뒤의 Available

# 표 2와 표 5의 행: (프로세스, Work = 끝내기 전의 Available, 끝낸 뒤의 Available)
TABLE_2 = (("p1", (3, 3, 2), (5, 3, 2)), ("p3", (5, 3, 2), (7, 4, 3)), ("p0", (7, 4, 3), (7, 5, 3)), ("p2", (7, 5, 3), (10, 5, 5)))
TABLE_5 = TABLE_2 + (("p4", (10, 5, 5), (10, 5, 5)),)
SEQ_STD = ["p1", "p3", "p0", "p2"]
SEQ_DYN = SEQ_STD + ["p4"]
ARRIVAL_PASS = 2             # 해석 W-1: 바깥 반복의 둘째 맨 앞에서 p4가 들어간다


def load() -> tuple[BState, list[str]]:
    """초기 상태(p0–p3)와 이름. 도착하는 p4는 상태에 없다(NEW_MAX와 도착 시점을 정책의 arrivals 인자로 준다)."""
    need = [[MAXC[i][j] - ALLOC[i][j] for j in range(3)] for i in range(len(ALLOC))]
    return BState.make(TOTAL, ALLOC, need), list(NAMES)
