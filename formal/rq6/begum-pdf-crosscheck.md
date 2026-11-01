# Begum 외 2020 PDF와 옮긴 값의 대조 결과

`bench/literature/verify_begum_pdf.py`가 쓴 결과다. AI(Claude)가 작성한 초안이며 사람의 검토 전이다. PDF는 ISCAIE 2020, pp. 73–78(6쪽)이고 사용자가 2026-11-01에 제공했다. IEEE의 저작물이라 저장소에는 넣지 않는다. 사본의 SHA-256: `c8a06077345db3b358b0c9cad901365b5c4a0c9b54aafd9ba950aed87d05b909`. 텍스트 층만 읽었다(그림 제외).

| 점검 | 결과 |
|---|---|
| PDF 식별: 제목과 ISCAIE 쪽 표시(978-1-7281-5033-8/20) | 통과 |
| PDF 쪽 수 6 | 통과 |
| 표 I: 행 10개를 읽음 | 통과 |
| 표 I: 모든 칸(Maximum need, Current allocation)이 옮긴 값과 같음 | 통과 |
| 표 II: 행 10개를 읽음 | 통과 |
| 표 II: 모든 칸(Needed allocation, Maximum Needed allocation)이 옮긴 값과 같음 | 통과 |
| 표 II = 표 I의 Maximum − Allocation, Maximum Needed = 행의 최댓값 (인쇄된 값 기준) | 통과 |
| 표 III: 행 10개를 읽음 | 통과 |
| 표 III: 처리 순서가 옮긴 SORTED_ORDER와 같음 | 통과 |
| 표 III: Needed allocation이 표 II와 같다. 단 하나, P7의 E칸만 다르다(5로 인쇄, 표 II는 0) — 논문 안의 인쇄 불일치 | 통과 |
| 표 III: Maximum Needed allocation 열이 표 II와 같음 | 통과 |
| 표 III의 순서 = Maximum Needed allocation의 안정 오름차순(같은 값은 프로세스 번호 순) | 통과 |
| 표 IV: 행 10개를 읽음 | 통과 |
| 표 IV: 처리 순서가 표 III과 같음 | 통과 |
| 표 IV: Needed allocation 열이 표 II와 같음 | 통과 |
| 표 IV: Maximum Needed 열이 표 II와 같다. 단 P7만 다르다(5로 인쇄, 표 II·III은 7) — 논문 안의 인쇄 불일치 | 통과 |
| 표 IV: Available, Minimum available, 조건(True) 열이 옮긴 값과 같음 | 통과 |
| 표 IV: 맨 아래 줄이 옮긴 FINAL_AVAILABLE과 같음 | 통과 |
| 표 IV: 조건 열이 모두 True | 통과 |
| 본문: 자원 인스턴스 수 25, 30, 20, 30, 35 | 통과 |
| 본문: 프로세스 10개(P0~P9)와 자원 5종(A~E) | 통과 |
| 본문: 처음 Available [4 5 2 4 7] | 통과 |
| 본문: P4 뒤 Available [6 8 4 4 8] | 통과 |
| 본문: P2 뒤 Available [6 12 4 9 8] | 통과 |
| 본문: P3 뒤 Available [8 12 4 15 13] | 통과 |
| 본문: P4의 Minimum available 2 | 통과 |
| 본문: 안전 순서 <P4,P2,P3,P5,P0,P6,P8,P9,P1,P7> | 통과 |
| 본문: 이 예제에서 비교 10회 | 통과 |
| 본문: 원래의 뱅커는 같은 일에 적어도 50회 | 통과 |
| 본문: 순서를 한 번 이상 확인할 필요가 없다 | 통과 |
| 본문: 시간 복잡도 식 O(n + nd + nd + nd) 또는 O(nd) | 통과 |
| 결론: 원래 뱅커보다 n배 빠르다 | 통과 |
| 결론: 안전성 탐지에 대해서만 실험·분석했다 | 통과 |
| 2단계: Maximum need[i,j] > Resource[j]이면 불안전 | 통과 |
| 3단계: 기수 정렬(Radix Short) 호출 | 통과 |
| 4단계: 빠른 검사 Maximum Needed allocation[i] ≤ Minimum Available | 통과 |
| 4단계: Completed process[Process[i]] == 0 조건 | 통과 |
| 4단계: 통과하면 Compute(Minimum Available) | 통과 |
| 4단계: 자원별 검사의 Continue/Break | 통과 |
| 4단계: if (j == d) 판정(문자 그대로는 모순. 해석 목록) | 통과 |
| 4단계: 실패하면 return unsafe state | 통과 |
| 5단계: 끝나지 않은 프로세스가 있으면 불안전 | 통과 |
| 6단계: return safe state and Safe sequence | 통과 |
| 기수 정렬: 자릿수 = Length(Max(...)) | 통과 |
| 기수 정렬: 자릿수 추출이 % (10^i)만(나눗셈 없음, 해석 목록) | 통과 |
| 기수 정렬: 뒤에서부터 배치(안정 정렬) | 통과 |
| 4단계: for (1≤j≤d) | 통과 |
| 본문: 연결 리스트에 자원 요구를 감소 순으로 저장한다고 서술(자원별 검사 순서의 해석 목록) | 통과 |

점검 48개, 실패 0건.

## 범위와 한계

- 표 I–IV의 모든 칸과 본문이 적은 값·순서·횟수, 의사코드의 핵심 구문이 있는지를 본다. 의사코드의 모든 문자를 기계로 대조한 것은 아니다.
- 그림 1(순서도)은 그림이라 이 대조에 들어 있지 않다. 순서도의 흐름은 사람이 확대한 그림을 읽고 확인했다(docs/rq6/variants.md §2).
- 논문 안의 인쇄 불일치 두 곳(표 III의 P7 E칸 5, 표 IV의 P7 Maximum Needed 5)은 PDF에서도 그대로 있다. 둘 다 실행 결과(순서, 비교 횟수)에는 영향이 없다(표 IV의 P7 비교는 Maximum Needed 7과 5 어느 쪽이든 Minimum available 18 이하라 True다).
- 옮긴 값(`begum2020.py`)은 저작물의 최소 수치만 담았고 문장은 담지 않았다. 위 표의 '본문' 줄은 정규식으로 찾은 일치 횟수다.
