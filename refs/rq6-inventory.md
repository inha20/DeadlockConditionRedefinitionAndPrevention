# RQ6 주장 인벤토리 (WP6.1)

- 작성일: 2026-10-29 (KST)
- 작성: Claude(AI 조수) · 사람의 검토 전 (v0.1)
- 관련 문서: 문서 02 §5.1(RQ6), 문서 04(Phase 3). 문헌 ID(M6, S13 등)와 근거 수준(A–D, X)은 문서 01의 표기를 따르고, 이 문서에서 새로 붙인 ID는 문서 04 §10에 있다.
- 상태: **1차 검색을 마쳤다. 체계적 검색이라고는 말할 수 없다.** 완료 기준(검색 기록과 포함·제외 사유)은 §5~§6에 채웠으나, 서지 데이터베이스 API가 막혀 있어 포괄성은 주장하지 않는다(§7).
- 읽는 법: 근거 수준 A−는 본문을 열람 도구의 요약으로 읽은 것, B는 초록·서지 페이지만 본 것이다. "저자 주장"은 논문이 그렇게 서술한다는 뜻이며 성능이나 정확성의 사실이 아니다. 판정은 재현(WP6.3~6.6) 뒤에 한다.

---

## 1. 범위와 기준

문서 02 WP6.1의 기준을 그대로 쓴다.

- **포함**: 뱅커 계열 알고리즘의 복잡도·성능·활용도·정확성 개선 주장이고, 재구현이 가능한 설명이 있는 것.
- **분리**: 하드웨어·GPU 전용 평가. 소프트웨어 재현은 구조 수준에 한정한다.
- **분리(모델 상이)**: 요구 정보나 모델이 교재식 뱅커와 달라 동일 조건이 성립하지 않을 가능성이 높은 것(제조 시스템의 순차 자원 할당, 제어 흐름 정보를 쓰는 확장 등). 판정 범주 '비교 불가' 후보다.
- **자료**: 개선 주장이 아니라 비용표·복잡도 지도·오라클 교차 검증에 쓰는 문헌.
- **제외**: 뱅커 계열이 아니거나(탐지, 일반 교육 자료) 2차 문헌인 것.

상태 코드: **후보**(재현 대상 후보), **보류**(본문을 열람하지 못해 판단 불가), **분리**, **자료**, **제외**.

---

## 2. 인벤토리 (본문 또는 초록을 읽은 것)

| ID | 문헌 | 분류 | 저자 주장(요약) | 평가·증명·코드(저자) | 수준 | 상태·비고 |
|---|---|---|---|---|---|---|
| R6-01 | Belik 1987, BIT 27: 290–305 (M6) | 소프트웨어 | 뱅커의 변형. 원래 알고리즘은 Θ(mn²)(n 프로세스, m 자원 종류), 변형은 "특정한 있을 법한 조건" 아래 상각 최악 O(mn). 초록은 변형이 최대 두 배 빠르다고도 쓴다. 이 문장이 '최악에서도 최소 두 배'인지 '최대 두 배'인지 열람 도구 요약 둘(Unpaywall, Springer 초록 페이지)이 모두 '더 빠르다'고만 옮겨 모호하다 | 초록만 봄. 조건의 내용, 평가, 증명, 코드 모두 미확인 | B | **보류**(Springer 본문 필요). 알고리즘을 실제로 바꾸는 주장이라 재현 핵심 후보 |
| R6-02 | Lang 1999, IEEE TSE 25(3): 428–432 (M8) | 모델 확장 | 프로세스의 제어 흐름을 요청·반납 노드의 루트 트리로 모델링하고, 영역으로 나누는 이차 시간 알고리즘을 제시. 영역 진입을 OS 호출로 알리고 영역별 근사 최대 청구에 원래 뱅커를 적용하면 자원 활용도가 좋아질 수 있다고 서술 | 서지 페이지(UCF)에 평가 없음. 문서 종류는 Letter(5쪽) | B | **분리**(요구 정보가 K3에 가까워 동일 조건 비교가 어렵다. 비교 불가 후보). 본문 필요 |
| R6-03 | Lee·Mooney. ASP-DAC 2005판(S19), IEEE TPDS 2006(S11), 학위논문 2004(S20) | 하드웨어 | 하드웨어 병렬 뱅커 장치(PBAU). 장치 시간 최선 O(1), 최악 O(n), 평균 약 n/2 사이클. 소프트웨어 뱅커 대비 평균 3.32 대 5,398.4 사이클(약 1,600배, ASP-DAC판). 학위논문 초록은 약 1,000배. 응용 실행 185,716 대 221,259 사이클(속도 향상 19%, 시간 감소 16.1%) | 0.25 μm 표준 셀 합성(4 ns), 로봇 응용 하나에서 회피 22회 호출, 크기 5×5~20×20. 반복 수 미기재. 시험·시뮬레이션만 있고 형식 분석은 학위논문에 위임. 소프트웨어 기준 구현(언어, 최적화, 어느 변형인지)을 기술하지 않음. n과 m의 정의는 열람한 본문 추출에서 불분명 | A−(S19), B(S11, S20) | **분리**(하드웨어). 1,600배와 1,000배가 같은 실험의 다른 판인지 미확인 |
| R6-04 | Dixit·Khuteta 2017, IJRITCC 5(8): 45–49 (M39) | 소프트웨어 | 자원 개수를 실행 중 바꿀 수 있는 "동적 뱅커". 프로세스를 필요량 순으로 정렬하면 풀이 시간이 줄어든다고 서술. 평균 실행 시간 약 9% 개선 | 프로세스 수 대 평균 실행 시간 그림 하나와 프로세스 5개·자원 3종 예제. 하드웨어, 워크로드, 반복 수 미기재. 점근 복잡도 미기재. 증명은 페이지에서 확인되지 않음 | B | **후보**(본문으로 재구현 가능성 판단). 같은 페이지의 "75% 감소"는 다른 문헌(TNRR, Agrawal 외)의 수치이며 이 논문의 주장이 아니다 |
| R6-05 | Das 외, ISCAIE 2020 (M42) | 소프트웨어 | 프로세스별 최대 요구와 최소 가용량에 기반한 안전 상태 탐지. 요구량을 정렬된 연결 리스트에 저장. 뱅커를 포함한 비교 대상보다 시간·공간 복잡도가 낮다고 서술 | 초록에 "실험에서 비교했다"는 서술만. 복잡도 표기, 증명 미확인 | B | **보류**(IEEE 본문 필요). 서지 불일치: 한 목록은 Bimal Chandra Das만 표시하고 ISCAIE 2020(IEEE Xplore 9108818)이라 적으며, 다른 목록은 Begum·Faruque·Das, CNSA 2020이라 적는다. DBDAA(R6-07)는 Begum 외의 방법이 자기 데이터셋에서 '불안전'이라 판정한 것을 오류라고 서술한다. DBDAA의 Begum 외 인용 항목이 이 논문인지는 저자명으로 한 추정이고 인용 항목은 열람하지 못했다 → 정확성 시험(WP6.4)의 가치가 크다 |
| R6-06 | Wicaksono·Baeti·Salma·Kardian 2023, JEEMECS 6(1) (M41) | 소프트웨어 | 실행 중 새 프로세스가 도착하면 Need 행렬을 다시 계산하는 "동적" 최적화. 안전 순서를 얻으면 교착 회피가 보장된다고 서술 | Python 시뮬레이션의 예제 하나(자원 3종, 초기 프로세스 4개와 추가 1개). 복잡도, 정량 지표, 증명 없음. 뱅커를 탐지 알고리즘이라고도 불러 분류가 일관되지 않음 | A−(PDF 본문, 도구 요약) | **후보(약함)**. 정량 주장이 없어 '재구현 불가(주장 없음)' 범주가 될 가능성이 높다 |
| R6-07 | Zohora·Farhin·Kaiser 2024, PLOS ONE 19(9) (S13) DBDAA | 소프트웨어 | 프로세스가 실시간으로 도착. 최대 필요량 오름차순으로 정렬해 가용량과 비교하고, 통과하지 못한 프로세스는 '1차 불안전 시퀀스'에 넣어 주기 m 뒤에 재검사. 시간 O(n)(최선), O(nd)(평균·최악), 원래 O(n²d)(n 프로세스, d 자원 종류) | 평가는 비교 횟수뿐(실측 시간 없음). 손으로 만든 10프로세스·5자원 데이터셋 3개, 도착 시각 모두 0, 단일 프로세서, 정렬 시간 무시, 반복 수와 구현 언어 미기재. 비교 횟수: 최선 10 대 85(문헌 1·5·9·12 합산), 평균 36 대 100, 최악 70 대 125. Begum 외와 최선은 동률(10 대 10). 정리·증명 없음("수학적으로 설명했다"는 서술만). 코드 링크 없음, 보조 파일 S1은 데이터 가용성 진술(DOCX) | B(초록·IDEAS), A−(PLOS 본문, 도구 요약) | **후보(핵심)**. 내부 불일치: 관련 연구 절은 원래 알고리즘이 O(nd) 비교를 쓴다고 서술. 자원별 검사가 표준 안전 검사와 동치임을 보이는 부분이 없다는 점은 도구 요약에 의존하므로 본문 재확인 필요 |
| R6-08 | Bak 1984, RAIRO ITA 18(1): 71–80 (M23) | 고전 | 안전성 검사 시간이 자원 종류 수와 종류별 단위 수에 비례(저자 주장). 다중 종류에서는 종류별 지역 안전이 충분하지 않아 결합 정리를 씀. 특정 제약 아래 안전 상태의 약 35%를 거부한다는 선행연구 보고를 인용 | 본문 열람(OCR 손상으로 수식 일부 판독 불가) | A− | **후보**(보수적 판정 가능성). 수식 판독을 위해 PDF 재확보가 필요할 수 있음 |
| R6-09 | Shin·Choi 2012, 한국시뮬레이션학회논문지 21(4): 1–9 (M25) | 순차 자원 할당 | 2단계 선행 탐색 뱅커 알고리즘이 이전 방식보다 안전 상태를 잘 식별한다고 서술 | 안전 상태 판별률과 처리량을 수치 실험으로 측정, 대응 표본 t 검정 | B | **분리**(모델 상이: 용량 제약 자동 생산 시스템). 비교 불가 후보 |
| R6-10 | Li 2013(온라인 2012-08), LNEE 152: 277–281 (M27) | 소프트웨어(이론) | 그래프 모델 없이 뱅커 수준의 단순한 자료구조를 쓰는 새 회피 알고리즘. 시간 O(n²d²+ndM)(M은 총 자원 단위 수), 원래 알고리즘은 O(n³d). M과 d를 고정하면 O(n²d²). 공간 O(nd²)로 원래보다 나쁨. Θ(n²d)로 인용되는 값은 안전성 검사 부분만을 가리키는 오인용이라고 서술 | 점근 분석(초록). 실험·증명 여부 미확인 | B | **보류**(Springer 본문). 기준 알고리즘 복잡도 표기 불일치의 설명 후보(문서 02 §5.1) |
| R6-11 | Li·Cook 2007, Springer pp. 509–512 (M28) | 탐지 | 재사용 자원 d종(d≪n)에서 그래프·트리를 쓰지 않는 교착 탐지 알고리즘. d=O(log n)이면 비용이 "다익스트라 알고리즘"의 n/log n분의 1이라고 서술. d와 요청이 상수로 한정되면 선형 시간이며 점근적으로 최적. 뱅커 개선에도 쓸 수 있다고 서술 | 초록만 봄 | B | **보류**. 비교 대상 "다익스트라 알고리즘"이 무엇인지(안전성 검사로 추정되나 미확인) 본문 필요 |
| R6-12 | Gaur·Singh 2017, IJRITCC 5(11): 157–163 (M40) | 소프트웨어 | 동적 수정 접근. 20개 실험에서 교착을 피한 비율이 80%(16/20) 대 원래 35%(7/20), 개선 45%p라고 서술 | 표 6.1은 원래 7건인데 본문은 6건이라고 써서 서로 어긋남. 복잡도 미기재, 증명은 페이지에서 확인되지 않음. 기준 예제는 프로세스 5개, 자원 A=10·B=5·C=7 | B | **보류(약한 후보)**. '교착을 피했다'의 판정 기준이 뱅커의 안전 상태 판정과 같은지 확인 필요 |
| R6-13 | Abell 2013(Purdue 석사논문) (S21) | 하드웨어(GPU) | 교착 탐지·회피 알고리즘의 GPU 가속. 단일 단위 탐지 3.17~317.42배, 다중 단위 탐지 37.17~812.50배(직렬 CPU 대비). GPU 뱅커(GPU-PBA)는 저자가 "첫 병렬 회피 GPU 구현"이라 부르나 CPU 대비 'two orders of magnitude'(약 100배)의 가속에는 못 미친다고 쓴다 | 초록 페이지만 봄. 하드웨어 사양 미표시 | B | **분리**(GPU) |

---

## 3. 서지만 확인했거나 제목만 본 것 (내용 미열람)

| ID | 항목 | 확인한 것 | 상태 |
|---|---|---|---|
| R6-T1 | Tricas·Colom·Ezpeleta, "Some improvements to the Banker's algorithm based on the process structure", ICRA 2000. DOI 10.1109/robot.2000.846460 (M31) | Crossref 서지(성은 표기만). IEEE 페이지는 빈 응답 | **보류**. 순차 자원 할당 계열로 보이나 본문 미열람(해석) |
| R6-T2 | Zarnay·Garcia, "Enhancing banker's algorithm for avoiding deadlocks in systems with non-sequential processes", IEEE ETFA 2014. DOI 10.1109/etfa.2014.7005149 (M32) | Crossref 서지 | **보류** |
| R6-T3 | Ma·Yan, "An improved parallel banker's algorithm based on Petri net", EMEIT 2011. DOI 10.1109/emeit.2011.6023388 (M33) | Crossref 서지 | **보류** |
| R6-T4 | Song·Li·Song, "Modified Banker's algorithm with dynamically release resources", CISCE 2021. DOI 10.1109/cisce52179.2021.9445935 (M34) | Crossref 서지 | **보류** |
| R6-T5 | Jiang, "Process Security Sequence Improvement Algorithm Based on Banker Algorithm", J. Phys.: Conf. Ser. 1237(2): 022111, 2019. DOI 10.1088/1742-6596/1237/2/022111 (M35) | Crossref 서지. 게재처 페이지는 robots_disallowed | **보류**(오픈 액세스 시리즈이므로 사람이 PDF를 주면 빠르게 해결될 수 있음) |
| R6-T6 | Hensgen·Sims·Charley, "A fair Banker's Algorithm for read and write locks", Information Processing Letters 48(3): 131–137, 1993. DOI 10.1016/0020-0190(93)90255-8 (M36) | Crossref 서지(초록 없음). 락 모드(읽기·쓰기)와 공정성을 다루는 뱅커 확장으로 보임(제목 기준) | **보류** |
| R6-T7 | "Deadlock Avoidance Algorithms for Recursion-Tree Modeled Requests in Parallel Executions", IEEE Xplore 9591378 | 검색 결과의 제목과 URL만 | **보류**(서지 미대조) |
| R6-T8 | "Deadlock avoidance based on banker's algorithm for FMS", IEEE Xplore 7085321 | 검색 결과의 제목과 URL만 | **보류**(서지 미대조). 제조 시스템 계열 |
| R6-T9 | "Searching feasible resources to reduce false-positive situations for resolving deadlocks with the Banker's algorithm in railway simulation", ScienceDirect PII S2210970617300215 | 검색 결과의 제목과 URL만 | **보류**. 철도 시뮬레이션 맥락이라 모델이 다를 가능성 |
| R6-T10 | "The World Banker's Algorithm", ScienceDirect PII 0743731590901215 (J. Parallel Distrib. Comput.로 보이나 미대조) | 검색 결과의 제목과 URL만 | **보류**. 내용을 짐작할 근거가 없음 |
| R6-T11 | "Deadlock avoidance in distributed operating systems (resource allocation, starvation, banker's algorithm)", ACM DL citation id 912556 | 검색 결과의 제목만 | **보류** |
| R6-T12 | "Deadlock avoidance and concurrency", ACM DL 10.5555/238887 | 검색 결과의 제목만 | **보류** |
| R6-T13 | 김태영·박동원, "Deadlock 회피책에 대한 개선방안 연구", 공학논문집 1(1): 49–57, 1997 (M21) | 이전 세션의 서지·초록 확인(B) | **보류**(초록 외 미열람) |

---

## 4. 자료로 분류한 것과 제외한 것

### 4.1 자료(비용표·복잡도 지도·오라클 교차 검증용)

| 항목 | 용도 |
|---|---|
| Fontao 1971, SOSP '71. DOI 10.1145/800212.806502 (S18) | 병행 회피 알고리즘의 초기 문헌. 비용표 |
| Belik 1988, WDAG 1987 (M7) | 방향 비순환 그래프 표현(경로 행렬)으로 간선 삽입 시 순환을 싸게 탐지하는 분산 회피 기법. 상각 시간이 연산당 선형 또는 상수라고 초록이 서술(B). 증분 순환 탐지(G1~G4)와 같은 계열의 문제 |
| Lomet 1977, SIGMOD (M37) | 데이터베이스 락용 회피 알고리즘. 성능이 잠글 수 있는 자원 수에 크게 의존하지 않고 배타·공유 락을 지원한다고 초록이 서술(B). 락 수준 회피의 선행 사례 |
| Hauschildt·Valk 1986 (M20) | 뱅커 안전 상태 집합의 페트리 넷 표현. SM 오라클 교차 검증 후보 |
| Chang 1975(CMU 박사논문)와 DTIC ADA021732 (M22, M30) | 안전성 검사 비용의 하한을 계산 트리로 유도했다고 초록이 서술. 수치는 미확인. 복잡도 지도에서 O(nd) 같은 주장이 하한과 충돌하는지 따질 때 필요 |
| Kameda 1977·1980 (M1, M2), Minoura 1982 (M5), Gold 1978 (M3), Araki 외 1977 (M4), Lawley·Reveliotis 2001 (M9) | 복잡도 지도(문서 04 §4) |

### 4.2 제외

| 항목 | 사유 |
|---|---|
| Kim·Lee 2009, 한국시뮬레이션학회논문지 18(1): 9–16 (페트리 넷 교착 탐지 세 방법의 비교) | 탐지, 뱅커 아님 |
| Lee·Lee 2003, 한국컴퓨터정보학회논문지 8(3): 26–33 (분산 데이터베이스 탐지 기법의 성능 비교) | 탐지, 뱅커 아님. 저자 일부가 M26과 같음 |
| 울산대 학위논문 2건(순차 트랜잭션 처리의 교착 탐지·복구) | 탐지. 제목만 확인 |
| Vayadande 외, "Survey Paper on Banker's Algorithm to Remove Deadlock" (River Publishers 장으로 보이며 연도 미표시. 참고문헌 최신 연도 2021) | 2차 문헌. Lee·Mooney의 O(n) 주장을 재인용한다. 열람 도구는 이 서베이의 인용 번호가 본문과 참고문헌에서 어긋난다고 보고했다. 1차는 S19 |
| 위키독스, velog, GATE 문제 사이트, GitHub 예제, 대학 강의 슬라이드 등 | 교육 자료. 단, academia.edu의 "Bankers Algorithm"(P14, C)은 기준 표기 불일치(O(n³d))의 예로만 쓴다 |
| 제목만 본 KCI "일반화된 철학자 만찬 문제의 교착상태 예방 알고리즘" (ART002955882, 열람 거부) | 뱅커 계열이 아닌 예방 알고리즘. RQ4·RQ3의 단서로만 기록 |

---

## 5. 검색 기록

날짜는 모두 2026-10-29(KST)이고 WebSearch의 모드는 표준이다. '결과'는 도구가 돌려준 항목 수다.

| 코드 | 도구 | 질의 | 결과 | 메모 |
|---|---|---|---|---|
| Q00a | 페이지 열람(DBLP 검색 API) | q=banker deadlock | 거부 | robots_disallowed. 요약 이전에 시도 |
| Q00b | 페이지 열람(DBLP 검색 API) | q=banker algorithm | 거부 | 같음 |
| Q01 | 페이지 열람(OpenAlex API) | search="banker's algorithm", 100건, 연도 오름차순 | 실패 | client_error |
| Q02 | 페이지 열람(Crossref API) | query.bibliographic=banker's algorithm deadlock avoidance, 100건, 발행일 오름차순 | 100건(전체 828,116) | 1848~1917년의 무관한 항목뿐. 질의가 'avoidance', 'banker' 등에 느슨하게 맞고 정렬이 연도순이어서 쓸 수 없음 |
| Q03 | 페이지 열람(OpenAlex API) | search=banker's algorithm deadlock, 50건 | 실패 | client_error |
| Q04 | 페이지 열람(Crossref API) | query.title=banker's algorithm, 100건 | 실패 | client_error |
| Q05 | 페이지 열람(Semantic Scholar API) | query=banker's algorithm, 100건 | 실패 | client_error |
| Q06 | WebSearch | improved banker's algorithm deadlock avoidance time complexity paper | 10 | S13, M6, M42, M39, M8 단서 |
| Q07 | WebSearch | optimized banker's algorithm reduce complexity O(mn^2) multiple resources | 10 | 위와 같은 후보, M41 |
| Q08 | WebSearch | 은행원 알고리즘 개선 교착상태 회피 논문 | 9 | 교육 자료와 울산대 학위논문(탐지). 후보 없음 |
| Q09 | WebSearch | "banker's algorithm" modified OR improved OR enhanced safe sequence new algorithm journal 2015..2025 time complexity comparison | 10 | M40 추가, 서베이(§4.2) |
| Q10 | WebSearch | Belik "An efficient deadlock avoidance technique" IEEE Transactions on Computers 1990 banker's algorithm | 10 | 이 제목의 논문을 찾지 못함. 질의의 제목과 게재처는 AI의 기억에서 온 것이라 확인 불가(X). 다만 G2(Haeupler 외)의 서론 §1이 "Belik 1990"을 교착 탐지의 응용 사례로 인용한다(A−). 참고문헌 항목은 열람한 텍스트에 없어 제목·게재처는 미확인(D) |
| Q11 | WebSearch | 은행원 알고리즘 시간 복잡도 개선 KCI 교착상태 회피 알고리즘 제안 | 10 | 탐지 논문 2건(제외), M25 재확인 |
| Q12 | WebSearch | Agrawal "Total Need based Resource Reservation" deadlock avoidance banker's algorithm | 10 | TNRR 원문은 찾지 못함(M39, M40이 인용) |
| Q13 | WebSearch | Zohora dynamic banker's algorithm deadlock avoidance O(n^2 d) safe state | 10 | 새 후보 없음 |
| Q14 | WebSearch | Belik 1990 "efficient deadlock avoidance technique" IEEE Trans. Comput. 39 | 10 | M7, M22, M37, M23 단서. Belik 1990은 다시 찾지 못함 |
| Q15 | WebSearch | Lee Mooney "parallel banker's algorithm" hardware PBAU deadlock avoidance O(n) Verilog | 10 | 저자 사이트 PDF 다수 → S19~S21 |
| Q16 | WebSearch(ieeexplore.ieee.org) | banker's algorithm improved deadlock avoidance algorithm | 10 | M8, M31, M32, M33, M34, R6-T7, R6-T8 |
| Q17 | WebSearch(dl.acm.org) | banker's algorithm deadlock avoidance modified efficient | 10 | M6, M8, M5, R6-T11, R6-T12, Andrews·Levin 1982(예방), 주석 달린 서지(Newton 1979로 보이나 미확인) |
| Q18 | WebSearch(link.springer.com, sciencedirect.com, arxiv.org) | banker's algorithm deadlock avoidance improved | 10 | M6, M27, M28, M36, R6-T9, R6-T10 |
| Q19 | WebSearch(koreascience.kr, kci.go.kr, riss.kr, dbpia.co.kr) | 은행원 알고리즘 교착상태 회피 개선 | 10 | 뱅커 후보 없음. 철학자 만찬 예방 알고리즘(§4.2) |
| Q20 | WebSearch | "Analysis of Deadlock Avoidance Schemes and Resource Utilization for Non-Preemptible Resources" authors lower bounds safe state computation | 10 | CMU 학위 수여 목록, 수학 계보 → M30 |
| Q21 | WebSearch | banker's algorithm GPU OR FPGA OR hardware deadlock avoidance speedup multiple-instance resources | 10 | S19~S21 재확인 |
| Q22 | WebSearch | look-ahead banker's algorithm automated manufacturing systems deadlock avoidance safe state detection Reveliotis Lawley | 10 | M25 재확인, 제조 시스템 문헌 |
| Q23 | WebSearch | Habermann Holt banker's algorithm O(mn^2) complexity multiple resource types faster safety test | 10 | 교육 자료뿐 |

합계: 서지 DB·API 시도 7건(응답이 온 것은 Q02 한 건이며 쓸 수 없었음), WebSearch 18건. RQ6 외 Phase 3 질의는 문서 04 §1에 있다.

---

## 6. 관찰

1. **평가 방식**: 소프트웨어 개선 주장 8건(R6-01, 04, 05, 06, 07, 08, 10, 12) 가운데 본문을 읽은 것은 R6-06, R6-07, R6-08이다. R6-06과 R6-07에는 정리와 증명이 없다. R6-08은 결합 정리를 쓰지만 OCR 손상으로 증명을 확인하지 못했다. 나머지 5건은 본문 미열람이거나(R6-01, 05, 10) 페이지에서 증명이 확인되지 않았다(R6-04, 12). 평가는 예제 하나(R6-06), 예제 하나와 그림 하나(R6-04), 손으로 만든 데이터셋 3개와 비교 횟수(R6-07), 20개 실험(R6-12), 점근 분석(R6-10) 수준이다.
2. **기준 표기의 불일치**: 같은 뱅커의 비용을 Θ(mn²)(R6-01), O(n²d)(R6-07), O(n³d)(R6-10)로 쓴다. R6-10은 Θ(n²d)류의 표기가 안전성 검사 부분만을 가리킨다고 설명한다. 변수도 m(자원 종류, R6-01)과 d(자원 종류, R6-07, R6-10)로 갈린다.
3. **비교 횟수와 시간의 혼용**: R6-07은 비교 횟수로 "시간 복잡도"를 주장한다. 비교 한 번이 스칼라 비교인지 d차원 벡터 비교인지에 따라 같은 알고리즘의 단위 비용이 d배 달라진다.
4. **서지 불일치**: R6-05는 목록에 따라 저자와 학회가 다르다. R6-12는 표와 본문의 숫자가 어긋난다. R6-07은 관련 연구 절과 초록의 기준 복잡도가 어긋난다.
5. **정확성 문제**: R6-07은 Begum 외의 방법(R6-05로 보이나 추정)을 자기 데이터셋에서 틀리게 판정하는 방법으로 서술하고, R6-08은 안전 상태를 거부하는 보수적 판정을 보고한다. 둘 다 정확 오라클(SM의 s_max 변환, 명세 §3.5)과의 차등 시험으로 확인할 수 있는 종류의 주장이다.

위 1~5는 인벤토리에서 읽은 서술이고 개별 주장의 옳고 그름에 대한 판정이 아니다.

---

## 7. 한계

- 서지 DB(DBLP, OpenAlex, Semantic Scholar)는 열람이 거부되거나 오류였고, Crossref는 제목으로 한 건씩 대조할 때만 동작했다. 질의 결과를 한 번에 받아 오는 체계적 검색은 하지 못했다.
- IEEE Xplore, ScienceDirect, ACM DL, KCI는 본문이나 초록이 열리지 않았다. 해당 항목은 서지만 있고 내용을 모른다.
- 검색은 영어와 한국어 일반 웹 검색이며 미국 대상이다. 한국어 문헌은 KoreaScience에 노출된 것만 보았다.
- 부재 증명이 아니다. 이 목록에 없는 개선 주장이 있을 수 있다.
- 열람 도구가 요약해서 돌려준 내용은 A−/B로 표기했고, 숫자를 논증의 전제로 쓰기 전에 원문으로 다시 확인한다.

---

## 8. 재구현 가능성 1차 평가와 최소 건수 제안

| 구분 | 항목 | 설명 |
|---|---|---|
| 알고리즘 설명을 읽었고 의사코드 수준으로 재구현할 수 있어 보임 | R6-06, R6-07 | R6-06은 정량 주장이 없고, R6-07은 정량 주장(비교 횟수, 복잡도)이 있다 |
| 설명이 있을 것으로 보이나 본문 미열람 | R6-01, R6-04, R6-05, R6-10, R6-12 | 본문(또는 PDF)을 받으면 판단 |
| 본문은 읽었으나 수식 판독이 어려움 | R6-08 | PDF 재확보 필요 |
| 하드웨어·모델 상이로 분리 | R6-02, R6-03, R6-09, R6-13 | 구조 수준 재현이나 '비교 불가' 판정 후보 |

문서 02 §5.1의 중단 규칙은 "재구현 가능한 주장이 사전에 정한 최소 건수에 못 미치면 인벤토리 범위를 넓히거나 재현 없이 문헌 비교로 축소"하는 것이다. **제안: 최소 4건**(소프트웨어 전용, 교재식 뱅커 모델, 의사코드를 본문에서 확인한 것). 지금은 R6-06, R6-07 두 건만 충족하므로 R6-01, R6-04, R6-05, R6-08, R6-10, R6-12 가운데 2건 이상의 본문 확인이 필요하다. 이 숫자는 사전 분석 계획에 기록할 때 사람이 확정한다(문서 02 §10 질문 목록에 추가할 항목).

## 9. 사람에게 필요한 것 (RQ6)

원문 확보 요청 순서(영향이 큰 순):

1. R6-01 Belik 1987 (BIT 27: 290–305) · R6-10 Li 2013 (Springer LNEE 152, 277–281).
2. R6-05 Das 외 2020 (IEEE Xplore 9108818) · R6-02 Lang 1999 (IEEE TSE 25(3): 428–432).
3. R6-04, R6-12 (IJRITCC 두 편의 PDF).
4. R6-T1~T6의 본문(특히 R6-T1 Tricas 외 2000, R6-T5 Jiang 2019, R6-T6 Hensgen 외 1993).
5. R6-03의 TPDS 2006판(S11)과 학위논문(S20) 본문.

저자 코드가 있는지 확인하는 일(저자 문의 포함)은 정중하게 하고, 불일치를 곧바로 오류로 단정하지 않는다(문서 02 §5.1의 태도 규정).
