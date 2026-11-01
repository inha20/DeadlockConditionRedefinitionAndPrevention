"""문헌 예제 입력(F-lit): Botlagunta·Agrawal·Rao 2021의 예제에서 뱅커의 판정이 갈리는 두 상태.

출처: Botlagunta MD, Agrawal S, Rao RR (2021) "A novel resource management technique for deadlock-free systems".
Int J Inf Technol 14(2): 627–635, DOI 10.1007/s41870-021-00670-6 (PMC8107812). 인벤토리 R6-14. 2026-11-01에 브라우저 창에서 본문 텍스트를 읽었다.

이 논문의 제안(자원 예약 기법)은 이 저장소의 재현 대상이 아니다(인벤토리 R6-14: 분리, 모델·지표 상이). 여기서 옮긴 것은 논문이 뱅커의
판정으로 보고한 두 가지를 오라클(O1)과 맞춰 보기 위한 숫자뿐이다: 표 1의 최대 요구와 자원 총량, 표 3과 표 5의 보유 행렬.
  - 표 3(뱅커의 상태, 가용 (2, 2, 3, 3)): 논문은 뱅커가 안전 순서를 얻었다고 쓴다.
  - 표 3에서 마지막 프로세스가 (0, 0, 0, 1)을 요청해 얻은 상태(표 5): 논문은 뱅커가 안전 순서를 찾지 못한다고 쓴다.
한계: 읽은 텍스트에서 프로세스 이름(첨자)과 안전 순서의 기호가 빠져 있었다. 행 순서가 논문의 프로세스 번호 순서와 같다는 것,
요청한 프로세스가 마지막 행이라는 것은 표 5가 표 3과 마지막 행에서만 다르다는 사실에서 읽은 쪽이 정한 것이다. 논문이 적은 안전 순서는 옮기지 못했다.

옮긴 값의 정합성은 이 파일을 실행하면 점검한다(표 3의 가용이 논문 본문의 (2, 2, 3, 3)과 같음, 표 5의 가용이 (2, 2, 3, 2)임, 두 판정).
실행: python3 -I bench/literature/botlagunta2021.py
이 입력은 등록된 입력군이 아니다. 판정 점검일 뿐 K1–K3의 결과가 아니다.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "oracle"))

TOTAL = (12, 9, 7, 7)                      # 표 1의 자원 총량(자원 4종)
MAXC = ((5, 6, 3, 4), (2, 0, 6, 0), (3, 0, 3, 4), (6, 6, 3, 3), (4, 3, 4, 5))   # 표 1의 최대 요구, 프로세스 5개
ALLOC_T3 = ((3, 4, 0, 1), (0, 0, 3, 0), (1, 0, 0, 1), (4, 3, 0, 0), (2, 0, 1, 2))   # 표 3
ALLOC_T5 = ((3, 4, 0, 1), (0, 0, 3, 0), (1, 0, 0, 1), (4, 3, 0, 0), (2, 0, 1, 3))   # 표 5(표 3에서 마지막 행의 네 번째 칸만 +1)
AVAIL_T3_PAPER = (2, 2, 3, 3)              # 본문이 적은 값
REQUEST = (0, 0, 0, 1)                     # 본문이 적은 요청


def main() -> int:
    from oracle.banker import Banker, DENY, request_outcome, safe_dp, safe_oracle, safe_perm  # noqa: PLC0415

    t3 = Banker(TOTAL, ALLOC_T3, MAXC)
    t5 = Banker(TOTAL, ALLOC_T5, MAXC)
    checks = [
        ("표 3의 가용이 본문의 (2, 2, 3, 3)과 같음", t3.avail() == AVAIL_T3_PAPER),
        ("표 5의 가용이 (2, 2, 3, 2)", t5.avail() == (2, 2, 3, 2)),
        ("표 5 = 표 3 + 마지막 프로세스의 (0, 0, 0, 1)", all(
            t5.alloc[p][r] == t3.alloc[p][r] + (REQUEST[r] if p == 4 else 0) for p in range(5) for r in range(4))),
        ("표 3은 안전(O1 세 판정이 일치)", safe_oracle(t3) and safe_perm(t3)[0] and safe_dp(t3)),
        ("표 5는 불안전(O1 세 판정이 일치)", not safe_oracle(t5) and not safe_perm(t5)[0] and not safe_dp(t5)),
        ("표 3에서 마지막 프로세스의 (0, 0, 0, 1) 요청은 O1이 거부", request_outcome(t3, 4, REQUEST) == DENY),
    ]
    bad = 0
    for name, ok in checks:
        print(("통과" if ok else "실패"), name)
        bad += 0 if ok else 1
    print(f"점검 {len(checks)}개, 실패 {bad}건")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
