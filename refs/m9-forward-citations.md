# refs/m9-forward-citations — M9(Lawley·Reveliotis 2001)를 인용한 문헌 목록 (AV-3, AI 초안 v0.3)

- 작성일: 2026-11-07 (KST) · 작성: Claude(AI 조수) · 사람의 검토 전. v0.2는 초록 14편의 열람을, v0.3은 같은 날 사용자가 한 건에 한해 허락한 Eggermont 학위논문 3장의 화면 열람(G4-362–372)을 반영한다
- 하는 일: 문서 07 §5의 AV-3(정방향 인용 추적 재시도)에서 M9를 인용한 문헌의 목록과 제목을 모으고, 제목만으로 RQ2와의 관련을 가른 뒤, 관련이 커 보이는 것의 초록(일부는 목차)을 읽는다. 어떤 논문을 읽었는지는 '읽음' 열과 아래 §3에 적는다.
- 하지 않는 일: 읽지 않은 논문의 내용을 주장하지 않는다. 읽은 것은 §3에 범위와 수준을 붙여 옮긴다. 제목만 보고 가른 분류는 판단이 아니다. 이 목록이 M9의 모든 인용 논문이라고 말하지 않는다. G4 판정을 이 문서만으로 바꾸지 않는다.

## 1. 출처와 한계

- 목록: OpenCitations Index API v2 `citations/doi:10.1023/A:1012203214611`의 응답 72건(2026-11-07 조회. `refs/g4-search-log.md` G4-306–G4-308). 응답은 인용하는 문헌의 식별자와 연월만 준다.
- 제목·연도: OpenCitations Meta API `metadata/doi:…`의 응답을 열람 도구가 요약한 값(B)이다. URL 길이 제한 때문에 DOI 8개 이상을 묻는 호출 5건은 거부되었고(G4-309–G4-313) DOI 4개 이하로 물은 18건이 성공했다(G4-314–G4-318, G4-321–G4-333. 번호 44를 뺀 71건). 요약을 거쳤으므로 철자나 칸이 틀렸을 수 있다. IET CTA DOI 두 개(번호 54, 55)는 학술지 칸이 맞지 않아 보여 '학술지 칸 이상'으로 표시했다.
- 색인의 한계: OpenCitations는 출판사가 공개한 참고문헌 목록에서 인용 관계를 만든다. 참고문헌 목록이 공개되지 않았거나 색인에 들어오지 않은 인용은 빠진다. 그러므로 이 목록은 M9의 인용 문헌 일부일 수 있고, 목록에 없다는 것은 인용하지 않았다는 뜻이 아니다. 인용 문헌 수가 다른 색인(Google Scholar, Semantic Scholar)과 다를 수 있다.
- 번호 44(arXiv:1306.0785v1)는 Meta API 조회가 오류(client_error)여서(G4-334) arXiv 페이지로 제목을 확인했다(G4-360).

## 2. 목록과 제목만으로 가른 분류

분류(제목만으로 가른 AI의 임시 분류. 논문을 읽은 것이 아니다):

| 기호 | 뜻 |
|---|---|
| C | 제목에 복잡도·난해성·다룰 수 있음(tractability)이 있다 |
| T | 순차 자원 할당·교착 회피·안전 상태 이론으로 보이는 것 |
| P | Petri net 기반 감독 제어·교착 예방 |
| S | 스케줄링·성능 최적화 |
| R | 로봇·무인 운반차·교통 |
| V | 리뷰·책·개요 |
| O | 그 밖 또는 제목만으로는 RQ2와 관련이 없어 보임 |

| 번호 | 식별자 | 제목 | 연도 | 분류 | 읽음 |
|---:|---|---|---|---|---|
| 1 | 10.1002/net.22275 | Avoiding Deadlocks Via Weak Deadlock Sets (Networks) | 2025 | C, T | 안 읽음(§3) |
| 2 | 10.1177/1687814017693542 | Deadlock Analysis And Control Based On Petri Nets: A Siphon Approach Review | 2017 | V, P | |
| 3 | 10.1109/robot.2004.1307208 | Deadlock-free Scheduling Method For Automated Manufacturing Systems With Limited Central Buffers | 2004 | T, S | 초록(§3) |
| 4 | 10.1007/s10696-008-9046-8 | Deadlock-free Scheduling Of An Automated Manufacturing System Using An Enhanced Colored Time Resource Petri-net Model-Based Evolutionary Endosymbiotic Learning Automata Approach | 2007 | S, P | |
| 5 | 10.1007/s10696-008-9036-x | A Modular Control Design Method For A Flexible Manufacturing Cell Including Error Handling | 2007 | O | |
| 6 | 10.1109/tsmcb.2005.850141 | Modeling And Deadlock Avoidance Of Automated Manufacturing Systems With Multiple Automated Guided Vehicles | 2005 | R, T | |
| 7 | 10.1016/j.ins.2020.05.007 | Polynomial-complexity Robust Deadlock Controllers For A Class Of Automated Manufacturing Systems With Unreliable Resources Using Petri Nets | 2020 | P | |
| 8 | 10.1007/978-1-84882-244-3_7 | Comparison Of Deadlock Prevention Policies (책의 장) | 연도 칸 없음 | V, P | |
| 9 | 10.1007/978-1-84882-244-3_6 | Optimal Liveness-Enforcing Supervisors (책의 장) | 연도 칸 없음 | V, P | |
| 10 | 10.1080/0951192x.2011.552526 | Resource Failure And Blockage Control For Production Systems | 2011 | O | |
| 11 | 10.1109/tsmcc.2011.2160626 | Deadlock Control Of Automated Manufacturing Systems Based On Petri Nets—A Literature Review | 2012 | V, P | |
| 12 | 10.1109/coase.2005.1506798 | Robust Supervisory Control For Production Systems With Multiple Resource Failures | 2005 | O | |
| 13 | 10.31577/cai_2021_3_648 | Modelling And Control Of Resource Allocation Systems Within Discrete Event Systems By Means Of Petri Nets — Part 1: Invariants, Siphons And Traps In Deadlock Avoidance | 2021 | V, P | |
| 14 | 10.1007/978-3-030-30604-5_1 | Synthesis Of No-Wait Cyclic Schedules For Cascade-Like Systems Of Repetitive Processes With Fixed Periods | 2019 | S | |
| 15 | 10.1109/coase.2005.1506797 | Using Shared Resource Capacity For Robust Control Of Failure Prone Manufacturing Systems | 2005 | O | |
| 16 | 10.1080/00207540210155792 | Control Of Deadlock And Blocking For Production Systems With Unreliable Workstations | 2002 | O | |
| 17 | 10.1016/j.compind.2015.10.014 | A Deadlock Recovery Strategy For Unified Automated Material Handling Systems In 300mm Wafer Fabrications | 2016 | O | |
| 18 | 10.1109/acc.2003.1240405 | Evaluating Order Of Circuits For Deadlock Avoidance In A Flexible Manufacturing System | 2003 | T | |
| 19 | 10.1145/2406336.2406346 | One-Step Look-Ahead Maximally Permissive Deadlock Control Of AMS By Using Petri Nets | 2013 | P | |
| 20 | 10.1109/robot.2003.1241913 | Avoiding Unsafe States In Manufacturing Systems Based On Polynomial Digraph Algorithms | 2003 | T | 초록(§3) |
| 21 | 10.1109/tase.2005.861397 | Robust Supervisory Control For Production Systems With Multiple Resource Failures | 2006 | O | |
| 22 | 10.1109/tase.2005.849085 | Relative Value Function Approximation For The Capacitated Re-Entrant Line Scheduling Problem | 2005 | S | |
| 23 | 10.1109/icnsc.2019.8743334 | Maximally Permissive Supervisor Synthesis Using Reachability And Structural Analysis Of Petri Nets | 2019 | P | |
| 24 | 10.1049/iet-cta.2016.0010 | Efficient Optimal Deadlock Control Of Flexible Manufacturing Systems | 2016 | P | |
| 25 | 10.1109/icarcv.2012.6485146 | Deadlock Resolution For Navigation Of Wheeled Robots In Continuous State-Space | 2012 | R | |
| 26 | 10.1109/cdc.2004.1428879 | Scheduling Algorithms For Automated Traffic | 2004 | R, S | |
| 27 | 10.1109/tvt.2006.877472 | Scheduling Automated Traffic On A Network Of Roads | 2006 | R, S | |
| 28 | 10.1002/047134608x.w7015 | Flexible Semiconductor Manufacturing (백과사전 항목) | 1999 | O | |
| 29 | 10.1007/s10009-006-0025-7 | Model Checker Aided Design Of A Controller For A Wafer Scanner | 2006 | O | |
| 30 | 10.1109/icsmc.2008.4811598 | Tractability Of Deadlock Avoidance Problem In Automated Manufacturing Systems Modeled With Petri Net | 2008 | C | 초록(§3) |
| 31 | 10.1109/acc.2003.1239839 | Deadlock Avoidance Control Synthesis In Manufacturing Systems Using Model Checking | 2003 | T | |
| 32 | 10.1007/s00170-009-1995-x | Two Types Of Extended RSNBs And Their Application In Modeling Flexible Manufacturing Systems | 2009 | P | |
| 33 | 10.1109/tase.2018.2859741 | Throughput Maximization Of Capacitated Re-Entrant Lines Through Fluid Relaxation | 2019 | S | |
| 34 | 10.1109/icimsa.2017.7985596 | Multi-AGVs Collision-Avoidance And Deadlock-Control For Item-To-Human Automated Warehouse | 2017 | R | |
| 35 | 10.1109/9.956052 | Deadlock Avoidance In Sequential Resource Allocation Systems With Multiple Resource Acquisitions And Flexible Routings | 2001 | T | 초록(§3) |
| 36 | 10.1109/tase.2011.2159112 | A Practical Approach For Maximally Permissive Liveness-Enforcing Supervision Of Complex Resource Allocation Systems | 2011 | T, P | 초록(§3) |
| 37 | 10.1109/tase.2010.2050059 | Two Simple Deadlock Prevention Policies For S3PR Based On Key-Resource/Operation-Place Pairs | 2010 | P | |
| 38 | 10.1109/tase.2010.2043096 | Petri Net Decomposition Approach To Optimization Of Route Planning Problems For AGV Systems | 2010 | R, P | |
| 39 | 10.1109/tase.2008.917142 | Robust Supervisory Control For Product Routings With Multiple Unreliable Resources | 2009 | O | |
| 40 | 10.1109/tase.2006.884674 | A Maximally Permissive Deadlock Prevention Policy For FMS Based On Petri Net Siphon Control And The Theory Of Regions | 2008 | P | |
| 41 | 10.1109/tase.2006.888049 | Deadlock Resolution In Automated Manufacturing Systems With Robots | 2007 | O | |
| 42 | 10.1080/074081791008988 | An Exact Solution Procedure To Determine The Optimal Dispatching Times For Complex Rail Networks | 2006 | S | |
| 43 | 10.1109/cdc.2004.1428878 | Optimal Allocation Of A Divisible Good To Strategic Buyers | 2004 | O | |
| 44 | arXiv:1306.0785v1 | Robust Multirobot Coordination Using Priority Encoded Homotopic Constraints (arXiv, cs.RO) | 2013 | R | 초록(§3) |
| 45 | 10.1007/s00170-003-1907-4 | Application Of Petri Nets For Deadlock Analysis And Avoidance In Flexible Manufacturing Systems | 2004 | P | |
| 46 | 10.1109/access.2020.3022643 | On Multi-Step Look-Ahead Deadlock Prediction For Automated Manufacturing Systems Based On Petri Nets | 2020 | P | |
| 47 | 10.1109/tsmca.2008.2007947 | Optimal Petri-Net-Based Polynomial-Complexity Deadlock-Avoidance Policies For Automated Manufacturing Systems | 2009 | P, T | 초록(§3) |
| 48 | 10.1109/tsmca.2008.2003535 | Selective Siphon Control For Deadlock Prevention In Petri Nets | 2008 | P | |
| 49 | 10.1109/tsmca.2008.918616 | Using Shared-Resource Capacity For Robust Control Of Failure-Prone Manufacturing Systems | 2008 | O | |
| 50 | 10.1109/tsmca.2003.820572 | Supervisory Control For Deadlock Avoidance In Compound Processes | 2004 | T | |
| 51 | 10.1016/j.ejor.2003.08.027 | Executing Production Schedules In The Face Of Uncertainties: A Review And Some Future Directions | 2005 | S, V | |
| 52 | 10.1080/02533839.2018.1498019 | Deadlock Prevention Technique Using Additional Transitions For Petri Nets | 2018 | P | |
| 53 | 10.1109/tsmc.2018.2854158 | On Hierarchical Construction Of The State Space Of An Automated Manufacturing System Modeled With Petri Nets | 2020 | P | |
| 54 | 10.1049/iet-cta.2010.0186 | Enumeration Of Lost States Of A Suboptimal Control Model Of A Well-Known S3PR (학술지 칸 이상) | 2011 | P | |
| 55 | 10.1049/iet-cta.2010.0195 | Improved Sufficient Condition For The Controllability Of Dependent Siphons In System Of Simple Sequential Processes With Resources (학술지 칸 이상) | 2011 | P | |
| 56 | 10.1049/iet-cta.2009.0264 | New Controllability Condition For Siphons In A Class Of Generalised Petri Nets | 2010 | P | |
| 57 | 10.1109/tsmca.2012.2192923 | On Nonexistence Of A Maximally Permissive Liveness-Enforcing Pure Net Supervisor | 2013 | P, T | 초록(§3) |
| 58 | 10.1201/b14588-2 | Introduction (책 Optimal Supervisory Control Of Automated Manufacturing Systems의 장) | 2013 | V, P | |
| 59 | 10.1109/access.2018.2872572 | Improved Multi-Step Look-Ahead Control Policies For Automated Manufacturing Systems | 2018 | P | |
| 60 | 10.1109/tra.2002.802213 | Policy Mixtures: A Novel Approach For Enhancing The Operational Flexibility Of Resource Allocation Systems With Alternate Routings | 2002 | T | |
| 61 | 10.1109/tra.2002.999651 | Liveness-enforcing Supervision For Resource Allocation Systems With Uncontrollable Behavior And Forbidden States | 2002 | T | |
| 62 | 10.1109/tra.2002.1019464 | Robust Supervisory Control Policies For Manufacturing Systems With Unreliable Resources | 2002 | O | |
| 63 | 10.1109/access.2018.2867091 | State Space Characterization Of Disjunctive Single-Unit Resource Allocation Systems | 2018 | T | 초록(§3) |
| 64 | 10.1007/978-3-642-24288-5_14 | Reachability And Deadlocking Problems In Multi-stage Scheduling | 2011 | C | 초록(§3) |
| 65 | 10.1109/70.976000 | Deadlock Avoidance For Manufacturing Systems With Partially Ordered Process Plans | 2001 | T | 초록(§3) |
| 66 | 10.1080/00207543.2011.578596 | Computationally Efficient Neuro-Dynamic Programming Approximation Method For The Capacitated Re-Entrant Line Scheduling Problem | 2012 | S | |
| 67 | 10.1109/tac.2011.2179422 | Designing Compact And Maximally Permissive Deadlock Avoidance Policies For Complex Resource Allocation Systems Through Classification Theory: The Nonlinear Case | 2012 | T | |
| 68 | 10.1016/j.conengprac.2016.05.009 | Petri-net-based Robust Supervisory Control Of Automated Manufacturing Systems | 2016 | P | |
| 69 | 10.1109/tac.2010.2095612 | Designing Compact And Maximally Permissive Deadlock Avoidance Policies For Complex Resource Allocation Systems Through Classification Theory: The Linear Case | 2011 | T | 초록(§3) |
| 70 | 10.1109/tac.2010.2046111 | On The Complexity Of Maximally Permissive Deadlock Avoidance In Multi-Vehicle Traffic Systems | 2010 | C | 초록(§3) |
| 71 | 10.1007/11888116_24 | Resource Allocation Systems: Some Complexity Results On The S4PR Class | 2006 | C | 초록(§3) |
| 72 | 10.1109/mra.2015.2401295 | Coordinating Autonomy: Sequential Resource Allocation Systems For Automation | 2015 | V, T | 초록·목차(§3) |

분류 집계(번호 72개, 복수 분류는 각 기호에 한 번씩 셈. 스크립트로 센 값): C 5 · T 18 · P 28 · S 10 · R 7 · V 8 · O 14. 복수 분류인 행 18개. 이 분류는 제목만으로 가른 것이며 §3에서 읽은 것과 어긋나는 곳이 있다.

## 3. 읽은 것

읽은 범위와 수준은 열마다 적었다. 표의 것은 모두 초록 수준(B)이다. 목록 밖에서 읽은 열린 문헌은 도구 요약(A−)이거나 화면으로 읽은 원문(A, 학위논문 3.2–3.7절)이다. 초록 14편은 2026-11-07에 사용자의 승인 아래 내장 브라우저 창에서 읽었다(CAPTCHA는 나타나지 않았고 파일은 내려받지 않았다). IEEE Xplore와 Springer의 본문은 로그인이나 구독이 필요해 읽지 못했다. 대장 열은 같은 날 더한 항목이다.

| 번호 | 읽은 범위 | 서술한 것(자기 말로) | 대장 | RQ2 격자에서의 쓰임 |
|---:|---|---|---|---|
| 63 | 초록 | 불연속 단일 단위 RAS의 상태 공간을 대수 연산으로 열거하고 도달 가능 상태 수를 주며 상태 벡터의 도달 가능성을 대수적으로 판정. 복잡도 분류는 없음 | C-SUR-257 | 쓰지 않음 |
| 30 | 초록·목차 | 각 단계가 자원 하나를 요구하는 순차 할당에서 교착 회피가 다루기 쉬운 필요충분조건과 한 단계 앞보기 정책을 제시. 조건의 내용은 읽지 못함 | C-SUR-253 | 참고 항목(SAFE-13) |
| 72 | 초록·목차·서두 | 순차 RAS 감독 제어의 조사. 복잡도 절은 로그인이 필요해 읽지 못함 | C-SUR-258 | 쓰지 않음. 본문을 얻으면 항목 후보 |
| 71 | 초록 | S4PR 클래스에서 예방·회피·탐지의 최적성 문제 대부분이 NP 또는 co-NP-완전이라는 서술 | C-SUR-256 | MAXP-9에 보조(S4PR는 SU-RAS와 다른 클래스) |
| 65 | 초록·목차 | 공정이 부분 순서인 시스템에서 매우 유연한 부분 클래스의 최적 회피가 NP-완전이고 다항인 경우도 있다는 서술 | C-SUR-255 | 참고 항목(SAFE-12) |
| 70 | 초록·목차 | 차량 시스템과 선형 단일 단위 RAS에서 최대 허용 감독이 NP-난해라는 서술 | C-SUR-250 | MAXP-9, MAXP.K3.R0 |
| 47 | 초록·목차 | 서로를 포함하지 않는 둘 이상의 순환이 공유하는 단위 용량 자원이 없는 S3PR에서 한 단계 앞보기로 다항 복잡도의 최적 정책. 배경 문장은 일반 단일 단위 RAS의 최적 정책 계산이 NP-난해라고 씀 | C-SUR-251, 252 | 참고 항목(SAFE-13), MAXP-9 보조 |
| 35 | 초록 | 선택 경로와 다중 획득을 허용하는 RAS의 활성에 대한 siphon 특성화와 다항 복잡도의 회피 정책. 안전 판정의 복잡도 서술은 없음 | — | 쓰지 않음 |
| 20 | 초록·목차 | 교착은 없으나 결국 교착에 이르는 상태(DFU)의 존재 판정이 NP-완전이라는 서술과 다항 회피 정책 | C-SUR-254 | 참고 항목(SAFE-14) |
| 3 | 초록 | 중앙 버퍼가 제한된 제조 시스템의 교착 없는 일정(유전 알고리즘). 복잡도 서술 없음 | — | 쓰지 않음 |
| 69 | 초록 | 최대 허용 정책의 오프라인·온라인 계산을 구분하고 컴팩트 분류기를 만든다. 배경 문장은 이 정책 계산이 대부분의 RAS 부류에서 초다항이라고 씀 | C-SUR-251 | MAXP-9 보조, O2-7의 근거 |
| 57 | 초록 | 일부 Petri net 하위 클래스에서 최대 허용 활성 보장 순수 net 감독자가 존재하지 않을 조건. 복잡도 서술 없음 | — | 쓰지 않음 |
| 44 | 초록(arXiv) | 로봇 조정. 교착의 복잡도와 무관 | — | 쓰지 않음 |
| 36 | 초록 | 최대 허용 감독자를 오토마톤 기반으로 계산하고 컴팩트하게 표현하는 두 단계 방법. 배경 문장은 이 정책 계산이 대부분의 RAS 부류에서 NP-난해라고 씀 | C-SUR-251 | MAXP-9 보조 |
| 64 | 초록 | 부분 순서 계획의 다단계 스케줄링에서 다룰 수 있는 경우와 어려운 경우의 경계, 안전 판정과 도달 가능 교착의 난해성. 본문은 구독 필요, 열린 사본 없음 | C-SUR-261 | SAFE-11의 보조(본문은 아래 학위논문) |
| 1 | 안 읽음 | M55(arXiv:2410.05175)와 같은 제목의 학술지본으로 보임 | C-SUR-262 | 서지 갱신만 |

**목록 밖에서 읽은 것.** 번호 64의 검색에서 같은 저자들의 열린 문헌 둘을 찾아 읽었다. (a) STACS 2011의 개방형 작업장 논문(Eggermont·Schrijver·Woeginger, arXiv 1102.3029, 열린 본문의 도구 요약, A−, C-SUR-259, G4-341·342): 방문 순서가 정해지지 않은 계획에서 안전 상태 판정과 도달 가능 상태 판정은 다항이고 상태 간 도달 가능성과 도달 가능 교착은 NP-완전이며 일부 하위 경우는 다항이다. (b) Eggermont 박사학위논문(TU/e 2012, 열린 공개본). 서문과 3장 개요는 열람 도구의 요약으로 읽었고(A−, C-SUR-260, G4-343–347, 363), 3.2–3.7절은 사용자가 이 파일 한 건에 한해 허락해(2026-11-07 21:31 KST. 사용자가 따로 할 일이 없다는 조건) 내장 브라우저 창에서 PDF를 화면으로 읽었다(A, C-SUR-263–268, G4-364–372). 파일을 내려받거나 저장하지 않았고 읽기를 마친 뒤 창을 닫았다. 정리 진술은 원문 문장과 대조해 옮겼고 증명은 검증하지 않았다. 인쇄 64–65쪽(PDF 74–75쪽)은 열지 않았고 3.4.2절의 구성요소 절차는 훑기만 했다. 1–2장과 4장 이후는 읽지 않았다. 읽은 결과의 요지: 부분 순서 계획의 다단계 시스템에서 안전 상태 판정은 용량 1인 기계가 무제약·out-star 계획에만 나타나면 다항이고(정리 3.3.1), 모든 계획이 서로 다른 세 기계 위의 같은 선형 순서이고 모든 기계의 용량이 1이어도 NP-난해다(정리 3.4.1). 도달 가능 교착은 용량 1에서도 여러 모양에서 NP-난해이고(정리 3.6.6) 일곱 모양이 열려 있다(3.7절). RQ2 격자에서의 쓰임: SAFE-11, VER-9(`docs/rq2/grid.md` v0.3 §5.6).

**색인이 놓친 것의 사례.** 학위논문의 3.3절 서두는 Lawley·Reveliotis(2001) 398쪽을 인용한다(화면으로 확인, C-SUR-264). 398쪽은 M9(IJFMS 13: 385–404)의 쪽 범위 안이므로 M9를 인용한 것으로 보이나, 학위논문의 참고문헌 목록은 확인하지 않았고 같은 저자들의 2001년 글이 M9 하나뿐인지도 확인하지 않았다. 이 학위논문은 위 72건에 없다. 인용이 맞다면 OpenCitations 목록이 M9의 인용 문헌 전부가 아니라는 §1의 단서를 뒷받침한다.

## 4. 한계

- 제목만으로 가른 분류는 틀릴 수 있다. 읽어 보니 번호 20과 65는 제목의 분류(T)와 달리 복잡도 결과(NP-완전)를 초록에 서술했고, 번호 3은 스케줄링, 번호 44는 로봇 조정이었다. 읽지 않은 행(57개)의 분류는 그대로 제목만 본 것이다.
- 읽은 것은 초록 수준(B), 열린 본문의 도구 요약(A−), 그리고 학위논문 3.2–3.7절의 화면 열람(A. 증명은 검증하지 않았다)이다. 초록에 복잡도 서술이 없다는 것은 본문에 없다는 뜻이 아니다. 번호 30, 72(복잡도 절), 65, 47의 본문은 로그인이 필요해 읽지 못했다.
- 이 문서는 새 결과를 만들지 않았다. RQ2 격자나 G4 판정에 미치는 영향은 읽은 것에 한해 `docs/rq2/grid.md`(v0.3)와 문서 05에 따로 적는다.
- 읽은 범위 밖의 후보: 제목이 복잡도·허용도와 가까운 번호 9, 19, 23, 40, 46, 59, 67(최대 허용 정책 계열)은 읽지 않았다. MAXP 칸을 채우는 검색(`docs/rq2/grid.md` §7.2)에서 다룬다.
