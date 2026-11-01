"""문헌 예제 입력(F-lit): Dixit·Khuteta 2017의 '수정 뱅커' 예제 (R6-04). AI 초안: 사람의 확인 전.

출처: Dixit·Khuteta, "A Dynamic and Improved Implementation of Banker's Algorithm", IJRITCC 5(8): 45–49, 2017 (인벤토리 R6-04, M39).
읽은 방법과 한계
  - 2026-11-01에 SlideShare에 올라온 사본(인벤토리 W03)의 본문을 도구가 읽어 낸 텍스트로 읽었다. 저널 PDF가 아니라 제3자 사본이고
    도구가 요약한 것이라, 저널 PDF와 대조하기 전에는 이 값을 인쇄본과 같다고 단정하지 않는다. 숫자는 값 사이의 중복
    (Need = Max − Allocation, 자원 총량)으로 check_variants_dixit.py가 정합성을 점검한다.
  - 논문의 저작권 조건은 확인하지 못했다. 5개 프로세스·3종 예제의 최소 수치만 옮기고 문장은 옮기지 않았다.

옮긴 것(논문이 인쇄한 값. 표 3–5에 해당하는 예제)
  - 자원 총량 (11, 5, 10), Available (0, 2, 3), 프로세스 P0–P4의 Max, Allocation, Need.
  - 추적: P0 스택에 넣음, P1 스택에 넣음, P2 스택에 넣고 스택을 정리, P3 실행(Need = Available), P4 스택에 넣고 정리.
  - 정리를 마친 스택은 위에서부터 P2, P4, P1, P0이고 '위에서부터 실행'된다고 쓴다. 논문은 단계마다의 Available도, 최종 안전 순서도 인쇄하지 않는다.
  - 그림 2: 프로세스 수 3, 6, 9, 12 대 실행 시간. y축 눈금 0–1400(단위 없음). '평균 약 9% 개선'이라 쓰나 계산 방법과 실행 조건(자원 수, 하드웨어, 반복 수)이 없다.
    그림의 곡선 값은 옮기지 못했다. 그래서 이 주장은 재현하지 못한다(이 모듈에 값이 없다).

이 입력은 등록된 입력군이 아니다. 문헌 예제의 재현일 뿐 K1–K3의 결과가 아니다.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from bench.state import BState  # noqa: E402

TOTAL = (11, 5, 10)
NAMES = ["P0", "P1", "P2", "P3", "P4"]
MAXC = ((11, 3, 4), (8, 3, 4), (1, 3, 5), (2, 3, 4), (3, 3, 7))
ALLOC = ((3, 0, 2), (3, 0, 0), (0, 1, 3), (2, 1, 1), (3, 1, 1))
NEED_PRINTED = ((8, 3, 2), (5, 3, 4), (1, 2, 2), (0, 2, 3), (0, 2, 6))
AVAIL_PRINTED = (0, 2, 3)

# 논문의 추적: (프로세스, 조치)
TRACE_PRINTED = (("P0", "push"), ("P1", "push"), ("P2", "push"), ("P3", "execute"), ("P4", "push"))
STACK_PRINTED = ("P2", "P4", "P1", "P0")      # 정리를 마친 스택, 위(top)에서 아래로
CLAIMED_IMPROVEMENT = "평균 약 9%"            # 그림 2(조건 미기재)에서 나온 주장. 재현하지 못한다
FIG2_X = (3, 6, 9, 12)


def load() -> tuple[BState, list[str]]:
    need = [[MAXC[i][j] - ALLOC[i][j] for j in range(3)] for i in range(len(ALLOC))]
    return BState.make(TOTAL, ALLOC, need), list(NAMES)
