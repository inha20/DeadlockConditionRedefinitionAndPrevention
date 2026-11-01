# DBDAA 저널 PDF와 옮긴 값의 대조 결과

`bench/literature/verify_dbdaa_pdf.py`가 쓴 결과다. AI(Claude)가 작성한 초안이며 사람의 검토 전이다. PDF는 PLOS ONE 19(9): e0310807의 저널본(18쪽)이고 사용자가 2026-11-01에 제공했다. 저장소에는 넣지 않는다. 사본의 SHA-256: `6ca895ee3debc107e1770cfd3bfe278bfc30a0fb769ca1d15c5b357684bdcaef`. 텍스트 층만 읽었다(그림 제외).

| 점검 | 결과 |
|---|---|
| PDF 제목(DBDAA: A real-time approach to Dynamic Banker's Deadlock Avoidance Algorithm with optimized time complexity)과 DOI | 통과 |
| 표 입력 best: 행 수 10 | 통과 |
| 표 입력 best: 모든 칸(ID, AT, BT, Maximum, Allocation, 인쇄된 Need)이 옮긴 값과 같음 | 통과 |
| 표 입력 best: 인쇄된 Need ≠ Maximum − Allocation인 행이 KNOWN_TABLE_INCONSISTENCIES와 같음 | 통과 |
| 표 입력 average: 행 수 10 | 통과 |
| 표 입력 average: 모든 칸(ID, AT, BT, Maximum, Allocation, 인쇄된 Need)이 옮긴 값과 같음 | 통과 |
| 표 입력 average: 인쇄된 Need ≠ Maximum − Allocation인 행이 KNOWN_TABLE_INCONSISTENCIES와 같음 | 통과 |
| 표 입력 worst: 행 수 10 | 통과 |
| 표 입력 worst: 모든 칸(ID, AT, BT, Maximum, Allocation, 인쇄된 Need)이 옮긴 값과 같음 | 통과 |
| 표 입력 worst: 인쇄된 Need ≠ Maximum − Allocation인 행이 KNOWN_TABLE_INCONSISTENCIES와 같음 | 통과 |
| 추적표 best: 행을 모두 읽음 | 통과 |
| 추적표 best: 모든 칸이 옮긴 값과 같음 | 통과 |
| 추적표 average: 행을 모두 읽음 | 통과 |
| 추적표 average: 모든 칸이 옮긴 값과 같음 | 통과 |
| 추적표 worst: 행을 모두 읽음 | 통과 |
| 추적표 worst: 모든 칸이 옮긴 값과 같음 | 통과 |
| 표 8 'original banker [1]' | 통과 |
| 표 8 'Momotaz et al. 2020 [4]' | 통과 |
| 표 8 'Bondarenko et al. 2021 [5]' | 통과 |
| 표 8 'Song et al. 2021 [9]' | 통과 |
| 표 8 'Wicaksono et al. 2023 [12]' | 통과 |
| 표 8 'DBDAA' | 통과 |
| 표 9 'Original Banker’s Algorithm [1]' | 통과 |
| 표 9 'Momotaz et al [4]' | 통과 |
| 표 9 'Bondarenko et al [5]' | 통과 |
| 표 9 'Song et al [9]' | 통과 |
| 표 9 'Wicaksono et al [12]' | 통과 |
| 표 9 'DBDAA' | 통과 |
| 본문의 순서: DBDAA Safe_Sequence best | 통과 |
| 본문의 순서: 원래 뱅커의 안전 순서 best | 통과 |
| 본문의 순서: DBDAA Safe_Sequence average | 통과 |
| 본문의 순서: DBDAA Primary_Unsafe average | 통과 |
| 본문의 순서: 원래 뱅커의 안전 순서 average | 통과 |
| 본문의 순서: DBDAA Safe_Sequence worst | 통과 |
| 본문의 순서: DBDAA Primary_Unsafe worst | 통과 |
| 본문의 순서: 원래 뱅커의 안전 순서 worst | 통과 |
| Algorithm 1 4줄 | 통과 |
| Algorithm 1 8줄 | 통과 |
| Algorithm 1 10줄 | 통과 |
| Algorithm 1 12줄 | 통과 |
| Algorithm 1 14줄 | 통과 |
| Algorithm 1 19줄 | 통과 |
| Algorithm 1 20줄 | 통과 |
| Algorithm 1 24줄 | 통과 |
| Algorithm 1 25줄 | 통과 |
| Algorithm 1 27줄 | 통과 |
| Algorithm 1 31줄 | 통과 |
| Algorithm 1 35줄 | 통과 |
| Algorithm 1 36줄 | 통과 |
| Algorithm 1 42줄 | 통과 |
| Algorithm 1 43줄 | 통과 |
| Algorithm 1 44줄 | 통과 |
| Algorithm 1 46줄 | 통과 |
| 표시(mark)를 지우는 문장은 43줄에 한 번뿐(실패 경로 25, 36줄은 44줄로 바로 간다) | 통과 |

점검 54개, 실패 0건.

## 범위와 한계

- 표 2–9와 본문의 순서, Algorithm 1의 줄 번호와 첫 단어들이 옮긴 값과 같은지만 본다. 알고리즘 줄의 모든 문자를 기계로 대조한 것은 아니다(줄 내용은 사람이 읽고 확인했다).
- 이 대조는 PMC 본문을 눈으로 옮긴 값이 저널 PDF와 같음을 보인다. 저자의 표 자체에 있는 불일치(표 3 P4의 Need R5)는 그대로 남는다.
- 코드 `dbdaa2024.py`의 'KNOWN_TABLE_INCONSISTENCIES'는 PDF에서도 같은 행이 같은 이유로 어긋남을 확인했다.
