# bench/ — 측정 하니스: 뱅커 계열 정책(RQ6)과 락 정책(RQ3) (동결 전)

AI(Claude)가 작성한 초안이며 사람의 검토 전이다. 측정 도구(문서 02 §3의 동결 전 허용 작업 ①)와 교재식 기준 구현(②)이다.
이 폴더의 코드로 **본 실험을 돌리지 않았다**. 점검과 파일럿에만 썼다. 파일럿(B-6)은 2026-11-01에 돌렸고(실행기 `pilot_rq6.py`, 자료 `experiments/pilot/`, 프로토콜과 결과 `docs/rq6/pilot.md`) 그 자료는 본 분석에 쓰지 않는다(`prereg/README.md` §2).
어떤 크기·시드 수·입력 분포도 동결 전에는 확정이 아니다.

RQ3(락 정책)용 초안 구현·워크로드 생성기·실행기·전수 검사는 아래 '파일' 표 뒤의 'RQ3 (락 정책)' 표에 따로 있다. RQ3의 정책 의미는 AI가 고른 것이라 사람이 정하기 전에는 '기준 정책'이 아니라 '초안 구현'이다(`docs/rq3/policies.md` §9).

## 파일

| 파일 | 내용 |
|---|---|
| `seeds.py` | 마스터 시드와 이름표에서 결정적으로 하위 시드를 만든다(SHA-256 앞 8바이트 → PCG64) |
| `ops.py` | 연산 계측. `CountingOps`는 벡터 비교, 실제로 수행한 스칼라 비교(단락 평가 반영), 벡터 덧셈, 반복 방문 수를 센다. `PlainOps`는 같은 연산을 세지 않고 수행한다 |
| `state.py` | 하네스용 뱅커 상태 `BState(total, alloc, need, avail)`와 오라클 `oracle.banker.Banker` 사이의 변환 |
| `policies/banker/base.py` | 정책 인터페이스(`is_safe`, `request`)와 교재식 자원 요청 알고리즘(ERROR, WAIT, GRANT, DENY) |
| `policies/banker/textbook.py` | 교재식 안전성 알고리즘 두 가지: `TextbookRestart`(찾을 때마다 처음부터 훑음. 기준 구현의 기본값 제안), `TextbookSweep`(훑기를 이어서 함) |
| `policies/banker/mutants.py` | 점검용으로 일부러 틀린 정책 5종. 결과 분석에는 쓰지 않는다 |
| `gen_banker.py` | 입력 생성기: F-rand(층화 거절 표집), F-bound(교재식 최악 입력 네 종류, 경계 상태), 요청 표집, 큰 입력용 numpy 닫힘 분류기 `safe_fast` |
| `stats.py` | Clopper–Pearson(구현 둘), 백분위 부트스트랩(중앙값·평균), 짝지은 기하평균 비율, 수준 보정(SP-4), 로그–로그 기울기와 그 부트스트랩 구간(K4) |
| `results.py` | JSONL 기록·읽기, 상태 해시, 실행 환경 기록(호스트·사용자 이름은 남기지 않음) |
| `runner.py` | 셀 × 정책 × 인스턴스 계획을 섞어 count 패스(K2)와 time 패스(K3)로 나누어 실행하고 기록 |
| `summarize.py` | K1(FU·FS와 구간), 인스턴스별 K2·K3, 셀별 짝지은 비율, 시간의 분산 성분(파일럿용) |
| `check_pipeline.py` | 위 전체의 자체 점검. 결과: `formal/rq6/harness-check-results.md` |
| `check_banker_policies.py` | 교재식 기준 구현의 소규모 전수 차등 테스트(O1 대조, 889,373개 상태), 속성, 변이체 검출, O1 크기·시간 한계표. 결과: `formal/rq6/policies-diff-results.md` |
| `policies/banker/variants/` | 문헌 변형의 재구현(AI 초안, 해석은 `docs/rq6/variants.md`): `zohora2024.py`(DBDAA. 정책 `dbdaa-cycle1`, `dbdaa-repeat`), `begum2020.py`(정책 `begum-return`), `wicaksono2023.py`(정책 `wicaksono-sweep`. 도착을 받는 Sweep), `dixit2017.py`(정책 `dixit-<max·alloc>-<once·top·repeat>` 여섯 개) |
| `literature/` | 문헌 예제 입력(F-lit)과 논문 PDF 대조 스크립트: `dbdaa2024.py`, `begum2020.py`, `wicaksono2023.py`, `dixit2017.py`, `botlagunta2021.py`(예제 두 상태를 O1로 판정), `verify_dbdaa_pdf.py`, `verify_begum_pdf.py`(Wicaksono와 Dixit·Khuteta는 PDF 대조 스크립트가 없다). PDF는 저장소에 넣지 않고 사람이 제공한다(SHA-256만 기록) |
| `check_variants.py` | DBDAA 구현의 예제 재현(논문 표 5–8), 줄 번호를 옮긴 두 번째 구현과의 차등, 속성, 변이체 검출, 표시(mark) 읽기 비교. 결과: `formal/rq6/variants-check-results.md` |
| `check_variants_begum.py` | Begum 외 구현의 예제 재현, 순서도를 옮긴 두 번째 구현과의 차등, 속성, 변이체 검출, 분기 적용 횟수. 결과: `formal/rq6/variants-check-begum.md` |
| `check_variants_derivations.py` | 해석 문서의 도출 D1–D5(AI)를 코드로 확인. 결과: `formal/rq6/variants-derivations.md` |
| `check_variants_wicaksono.py` | Wicaksono 외 구현의 예제 재현(표 2·5), 도착 시점 민감도, 제자리 갱신을 옮긴 두 번째 구현과의 차등, 속성, 변이체 검출, DBDAA 표 8의 열과의 대조. 결과: `formal/rq6/variants-check-wicaksono.md` |
| `check_variants_dixit.py` | Dixit·Khuteta 구현 여섯 정책의 예제 재현, 정렬 키 후보, 스택 전체 정렬을 쓴 두 번째 구현과의 차등, 속성, 변이체 검출, 도출 D7–D10. 결과: `formal/rq6/variants-check-dixit.md` |
| `pilot_rq6.py` | RQ6 파일럿(B-6)의 실행기. 단계 `s`(표집·난이도·동률), `c`(비용 사다리와 O1), `o`(과제마다 드는 고정 비용), `v`·`v2`·`v3`(시간의 분산 성분, 조각 길이, 안전/불안전을 나눈 분산), `p`(짝지은 비용의 분산. 계수만), `r`(재현성), `summary`. 마스터 시드 `rq6-pilot-v1`. 변형의 판정은 기록하지 않는다(`withheld`). 이어서 실행할 수 있다 |
| `pilot_summary_rq6.py` | 파일럿 자료에서 요약 `experiments/pilot/pilot-summary.md`를 만든다(생성 파일). K1·K4·K5·K6을 계산하는 코드가 없다 |
| `check_pilot.py` | 파일럿 실행기·요약의 자체 점검(알려진 답, 시뮬레이션, 작은 크기의 실행, 요약에 금지 표현이 없음). 결과: `formal/rq6/pilot-check-results.md` |

## RQ3 (락 정책) — 파일

| 파일 | 내용 |
|---|---|
| `policies/lock/system.py` | 락 표(`LockTable`: 보유자, 대기, 위상 START/RUN/BLOCKED/DONE/FAILED), 결정(GRANT/WAIT/DENY/FAIL/WOUND), 정책 인터페이스, 스레드 한 걸음(`step_thread`), 탐지 한 걸음(`detect_step`), SM 상태로의 변환(`to_sm`) |
| `policies/lock/policies.py` | 정책 11종 초안 구현: B0, B1(탐지), P-ORD, P-ALL, P-RET, P-WD, P-WW, P-PCP, P-BNK, P-RAG, P-MIX. P-INC-F/R은 동결 전이라 없다. 의미는 `docs/rq3/policies.md` |
| `policies/lock/mutants.py` | 점검용으로 일부러 틀린 정책 17종. 결과 분석에는 쓰지 않는다 |
| `lockexplore.py` | 직선 락 프로그램 모음의 도달 가능 상태를 모두 열거하며 불변식·교착 집합·멈춤·영구 함정·O1/O2 대조를 검사하는 탐색기 |
| `lockrun.py` | 균등 무작위 스케줄 실행기(시간 모델 없음). 걸음마다 불변식과 교착 집합을 점검하고 요청·충돌 수를 센다. 선택적으로 트레이스(`traces/FORMAT.md`)를 기록 |
| `workloads/l1.py` | L1 합성 워크로드 생성기(T, R, Zipf 지수, 깊이, 순서 위반 확률 p_v, 임계구역 길이 분포)와 L2 고전 문제(식사하는 철학자, 계좌 이체) |
| `check_lock_policies.py` | 정책 초안 구현의 소규모 전수 검사(범위 S1–S5, 변이체 17종). 결과: `formal/rq3/lock-policies-check.md` |
| `check_workloads.py` | 생성기와 무작위 스케줄 실행기의 무결성 점검, 연기 시험, 경쟁 라벨 점검. 결과: `formal/rq3/workloads-check.md` |
| `probe_wd_ww.py` | P-WD와 P-WW의 상태 그래프 크기 대조(탐색 기록, 원인은 설명하지 않음). 결과: `formal/rq3/wd-ww-count-probe.md` |

오라클 O2(`oracle/locks.py`, 검사 `oracle/check_locks.py`)와 트레이스 도구(`traces/`)는 각 폴더의 README와 `traces/FORMAT.md`에 있다.

## 실행

```
python3 -I bench/check_pipeline.py formal/rq6/harness-check-results.md   # 약 10초
python3 -I bench/check_banker_policies.py formal/rq6/policies-diff-results.md   # 약 2.5분
python3 -I bench/check_variants.py formal/rq6/variants-check-results.md   # 약 30초
python3 -I bench/check_variants_begum.py formal/rq6/variants-check-begum.md   # 약 25초
python3 -I bench/check_variants_derivations.py formal/rq6/variants-derivations.md   # 약 10초
python3 -I bench/check_variants_wicaksono.py formal/rq6/variants-check-wicaksono.md   # 약 30초
python3 -I bench/check_variants_dixit.py formal/rq6/variants-check-dixit.md   # 약 50초
python3 -I bench/literature/botlagunta2021.py   # 문헌 예제 두 상태의 판정
python3 -I bench/check_pilot.py formal/rq6/pilot-check-results.md   # 약 3초
python3 -I bench/pilot_rq6.py summary   # experiments/pilot/의 자료로 요약을 다시 만든다

# RQ3 (락 정책)
python3 -I oracle/check_locks.py formal/rq3/o2-check-results.md   # 약 20초
python3 -I bench/check_lock_policies.py formal/rq3/lock-policies-check.md   # 약 10분(코어 2개). 긴 실행이니 백그라운드로, 원자료 저장 --save-raw PATH, 보고서만 다시 만들기 --load-raw PATH
python3 -I bench/check_workloads.py formal/rq3/workloads-check.md   # 약 0.5분
python3 -I bench/probe_wd_ww.py formal/rq3/wd-ww-count-probe.md   # 약 10초
python3 -I traces/check_validate.py   # 약 2초, formal/rq3/trace-validator-check.md
```

파일럿의 단계 실행(`python3 -I bench/pilot_rq6.py s`, `c`, `o`, `v`, `v2`, `v3`, `p`, `r`)은 합쳐 20분 안팎이 걸린다(코어 2개를 공유하는 가상 환경). 기본 출력이 `experiments/pilot/`이고 그 자료는 최종본이므로 다시 돌릴 때는 `--out`으로 다른 폴더를 지정한다. 각 단계는 끝난 단위를 건너뛰며 이어서 실행한다.

PDF 대조(`verify_*_pdf.py`)는 사람이 PDF를 제공해야 하고 `pdftotext`가 필요하다. 사용법은 `docs/rq6/variants.md` §1.3.

## 설계 결정 (사람이 검토할 것)

1. **기준 구현이 둘이다.** 교재의 의사코드는 "Finish가 거짓이고 Need ≤ Work인 i를 찾는다 → 끝낸다 → 2단계로"이다. 이것을 글자 그대로 옮기면 끝낼 때마다 처음부터 훑는다(`Restart`). 훑기를 이어서 하는 형태(`Sweep`)도 흔하다. 판정은 같고(닫힘 연산) 비용이 다르다. 어느 쪽이 기준인가는 사람이 정한다(`docs/rq6/reference.md`의 열린 항목). 교재 쪽 번호와 문구는 확인하지 못했다.
2. **count 패스와 time 패스를 나눈다.** 계측 코드가 시간에 영향을 주지 않게 하려는 prereg/RQ6.md §5 K2의 요구다. 두 패스의 실행 순서는 각각 마스터 시드로 섞는다(SP-1).
3. **인스턴스는 번호로 다시 만든다.** F-rand의 후보는 (마스터 시드, 셀, n, m, 시도 번호)만으로 정해진다(`gen_banker.candidate_at`). 큰 입력을 메모리에 쌓지 않고 정책마다 같은 인스턴스를 다시 만들 수 있다(짝지은 비교).
4. **정답은 O1이 원칙이고 numpy 닫힘(`safe_fast`)은 빠른 대용이다.** 측정한 모든 크기(최대 n = 4096, m = 256)에서 O1이 입력당 수 초 안에 돌고 O1과 `safe_fast`, 교재식 구현이 같은 판정을 냈다(`formal/rq6/policies-diff-results.md` §5). 본 실행에서 모든 입력을 O1로 대조할지 표본만 대조할지는 열린 항목이다(`docs/rq6/reference.md` R-8). `safe_fast`는 교재식 알고리즘과 같은 닫힘 연산이라 O1을 쓰지 않은 큰 입력의 정답은 독립적인 정답이 아니다.
5. **K2에 반복 방문 수를 함께 센다.** `Restart`는 벡터 비교 횟수가 `Sweep`과 거의 같아도 끝난 프로세스를 건너뛰는 방문이 Θ(n²)번 생겨 시간이 다르다(점검 실행에서 시간 비가 비교 횟수 비보다 컸다). prereg/RQ6.md §5의 K2는 비교 횟수만 정하므로 방문 수를 보조 수량으로 넣을지는 열린 항목이다.
6. **파이썬 구현이다.** 시간(K3)은 인터프리터 오버헤드를 포함한다. 컴파일 언어 구현을 K3에 쓸지는 문서 06 Q6(언어 선호)에 달렸고 답이 없다. K2는 언어와 무관하다.

## 알려진 한계 (파일럿에서 다룰 것. 파일럿에서 본 것은 맨 아래)

- **F-rand의 후보 분포는 첫 제안이다.** 불안전 상태는 (보유 비율 phi, 청구 비율 s)가 모두 큰 좁은 영역에서만 나온다(점검 중 관찰: n = 16, m = 4에서 s = 0.3 이하는 불안전이 0%, s = 1.0, phi ≥ 0.8은 95% 이상 불안전. 크기가 클수록 전이가 급하다). 그래서 (a) 수율이 낮고(n = 5–6에서 인스턴스 하나에 수백 번의 시도) (b) 안전 쪽 표본이 '모두 한 번에 끝낼 수 있는' 쉬운 상태에 쏠릴 수 있다. 실행기는 입력마다 닫힘 반복 횟수(`cl_passes`)를 기록하므로 파일럿에서 난이도 분포를 보고 사전 분포나 층화 축을 정해야 한다. n ≤ 4 정도의 아주 작은 크기는 F-ex가 맡는다.
- 시간 측정은 공유 가상 환경(코어 2개)에서의 값이다. 비율과 기울기만 의미가 있다.
- 통계 도구의 덮임률 점검은 합성 분포에서 방법이 거의 맞게 작동하는지 보는 것이다. 실제 비용 분포(꼬리가 두껍거나 이봉일 수 있음)에서의 성질은 파일럿에서 본다.

**파일럿에서 본 것(B-6, `docs/rq6/pilot.md` §7, AI 초안)**

- F-rand의 난이도: 위의 (b)가 맞았다. 안전 입력의 91.5%는 닫힘 반복 1회로 끝나고 불안전 입력의 38.2%는 한 프로세스도 끝내지 못한다(§7.3). 입력군을 바꿀지는 사람이 정한다(O6-12). 새 입력군은 동결 전에 구현하지 않았다.
- 비용 분포: 시간과 비교 횟수의 인스턴스 사이 분포는 안전/불안전 두 무리로 갈라져 로그 시간의 σ_b가 σ_w보다 크다. 이봉성이 구간 추정에 주는 영향은 §7.5에 있다. 통계 도구의 덮임률은 이 분포에서 다시 점검하지 않았다.
- 시간 측정: 가상 환경에서 드리프트는 보이지 않았으나 드문 한 번짜리 튐(카나리 60회 중 최대 +15.8%)이 있었다.
