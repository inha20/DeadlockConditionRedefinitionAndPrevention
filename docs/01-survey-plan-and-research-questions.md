# 교착상태 조건의 재정의와 효율적인 예방 알고리즘

## 선행연구 조사 계획 및 연구 질문 후보 (v0.3.1)

- 작성일: 2026-10-29 (KST)
- 초안 작성: Claude(AI 조수) · 사람의 검토 전
- 상태: 1차 서지 확인 완료 · 원문 대조 1차 완료(유료 원문 일부는 접근 불가, 문서 03) · Phase 3 정리 반영(문서 04, G3 조건부 통과 초안) · 연구 질문 미확정
- 변경: v0.3.1(2026-10-31) — 문서 04 §10.3의 사후 확인을 반영했다(M38 저자·서지 확정, E5 본문 열람, Belik 1990 후보 서지 M48). v0.3(2026-10-30) — 문서 04 §9의 정정 목록 중 문서 01에 해당하는 6건을 반영했다(§1.2 AND·OR·AND-OR 행, §1.3 뱅커 개선·그래프 기반 회피 행, §3 판정표, §7 참고문헌). v0.2(2026-10-29) — 문서 03(G1 원문 대조)의 정정·갱신을 반영했다. 변경 내역은 §9.
- 원칙: 이 문서는 어떤 아이디어의 참신성도 주장하지 않는다. "새롭다"는 판정은 §5의 게이트(동일/부분/없음 + 근거 링크)를 통과한 뒤에만 한다. 확인하지 못한 것은 추측으로 채우지 않고 X로 남긴다.

---

## 0. 읽는 법

### 0.1 확인 수준 표기

| 표기 | 의미 |
|---|---|
| A | 본문(전문 또는 해당 절)을 직접 읽고 확인 |
| A− | 원문의 일부 발췌만 확인 |
| B | 출판사·DBLP·arXiv·공식 문서 등의 서지/초록 페이지에서 확인(본문 미확인) |
| C | 교과서·강의노트·블로그 등 2차 자료로만 확인(원 논문 대조 필요) |
| D | 다른 문헌의 참고문헌 목록에서 존재만 확인(내용 미확인) |
| X | 확인 실패 또는 미확인 |

C 이하 항목은 연구의 전제로 쓰지 않고 단서(lead)로만 쓴다. 문헌 ID(F1, M6 등)는 §7 참고문헌의 ID다.

### 0.2 용어

- 브리프 4장의 구분(예방/회피/탐지, 필요/충분/필요충분)을 유지한다. 뱅커 알고리즘은 회피다.
- 다만 역사 문헌은 뱅커 계열에도 '예방(prevention)'이라는 단어를 썼다(§1.6). 인용할 때는 원문 표현과 본 연구의 현대 분류를 함께 적는다.

---

## 1. 1차 조사에서 확인된 것

### 1.1 코프만 네 조건의 논리적 지위: 문헌마다 서술이 다르다

1. 코프만 외(F1)는 이 조건들을 교착이 존재하기 위한 필요조건으로 정리하고, 예방을 그중 하나 이상을 처음부터 제거하는 설계로 소개한다. [A−] 원문 §2가 충분성을 어떻게 다루는지는 아직 읽지 못했다. [X]
2. 하벤더(F6)는 코프만보다 3년 앞서 실무 접근법 네 가지를 제시했다: 모든 과제가 같은 순서로 요청하기, 자원을 한꺼번에 요청하기, 추가 자원을 얻기 전에 보유 자원을 반납하고 함께 다시 요청하기, 요청이 거부되면 보유 자원을 쥔 채 기다리지 않고 대안 행동을 택하기. [A] 조건 목록 형태로 쓰지는 않았다.
   - 하벤더의 OS/360 사례는 정적 순서가 암묵적 획득 경로 때문에 뒤집힐 수 있음을 보여준다. 다음 작업 단계의 장치 할당 루틴이 이전 단계에서 얻은 영역(region) 안에서 실행되어, 의도한 순서가 실제로는 반대가 되는 문제다. [A] → 순서화 예방의 실무적 함정.
3. 탄넨바움은 네 조건 각각이 시스템이 가질 수도, 갖지 않을 수도 있는 정책과 관련된다고 쓴다. [B] (T2) 같은 계열로 보이는 교재 발췌 사본(저자·판본 미표시, T9)은 순환 대기를 둘 이상의 프로세스가 이루는 순환 사슬로 서술하고 네 조건이 모두 필요하다고만 쓰며 충분성은 다루지 않는다. [C] 이 서술이 길이 1의 자기 대기(한 프로세스가 이미 쥔 자원을 다시 요청)를 정의에서 제외하는지는 원문(F1, F2)으로 확인해야 한다. [X]
4. 필요/충분 표기가 일관되지 않다. 버지니아대 노트는 필요조건이지 충분조건이 아니라고 쓰고 [C], 켄트주립대 노트는 같은 내용에 필요충분이라는 제목을 붙이며 [C], 한 미국 특허 문서는 코프만을 필요충분으로 인용한다. [C] 레바인(F10)은 'deadlock'의 정의와 처리 방식이 문헌마다 일관되지 않다고 지적하고 죽은 상태(dead state)의 분류가 필요하다고 주장한다. [B]
5. 독립성은 새 주제가 아니다. 실버샤츠 교과서(사본)는 순환 대기가 점유-대기를 함의하므로 네 조건이 완전히 독립은 아니며, 그래도 각각을 따로 보는 것이 유용하다고 쓴다. [C] (T1)
6. 교육 자료 수준의 형식 증명이 있다. UIUC 코스북은 (교착 ⇒ 네 조건)과 (상호배제·점유-대기·비선점이 성립하는 시스템에서 자원 할당 그래프의 순환 ⇒ 교착)을 증명하고, 다중 인스턴스에서는 순환이 필요조건이지만 충분조건은 아니라고 설명한다. [C] (T4)

시사점: 조건의 논리적 지위를 먼저 고정해야 한다는 브리프의 문제의식은 문헌 상태와 맞는다. 다만 정책 수준 조건과 상태 수준 술어를 구분하는 관점은 일부 교과서·교육 자료가 이미 암묵적으로 쓴다(위 3, 6). 기여가 가능하다면 이 구분을 모델 매개변수화, 기계 검증, 예방 기법의 분류로 확장하는 데서 나온다. (가설, §4 RQ1)

### 1.2 모델별 상태 판별 결과

C 항목은 홀트(F2) 원문과 대조하기 전에는 근거로 쓰지 않는다.

| 모델 | 결과 | 출처 | 수준 |
|---|---|---|---|
| 단일 단위 자원(expedient 상태) | 순환 ⟺ 교착 | T4, T6 | C |
| 다중 단위 자원 + 단일 단위 요청 | 매듭(knot) ⟺ 교착 | T6 | C |
| 일반 자원 그래프(재사용·소모성 자원) | 순환은 필요조건. expedient이면 매듭은 충분조건(필요조건은 아님). 현재 상태의 교착 여부는 그래프 축소가 완료되는지로 결정 | T6 | C |
| 최대 청구(claim) 그래프의 축소 가능성 | 교착 없음(안전)의 충분조건이며 필요조건은 아님 | T6 | C |
| AND 요청 모델 | 교착이려면 대기 그래프에 순환이 필요하고, 탐지 알고리즘은 순환이 있을 때 교착을 선언한다(Knapp §2.2). Knapp은 이를 단일 단위 자원으로 한정한다고 쓰지 않았다. 이 저장소의 모델(SM)에서는 모든 자원 용량이 1일 때 순환 ⇔ 교착이다(T2). 다중 단위 자원에서는 순환이 교착을 뜻하지 않는 반례가 있다(B4). v0.2의 '순환이 필요충분'은 강의 노트의 서술이었으며(T6, C) 단일 단위 자원에 한정해 읽어야 한다 | M14 §2.2, 명세 T2·B4, T6 | A−, V, C |
| OR 요청 모델 | 순환은 충분하지 않다(순환 구성원 중 나가는 간선이 없는 프로세스가 진행할 수 있는 예). 교착은 매듭(knot)에 대응하고(Knapp은 Holt에 귀속) 매듭의 구성원은 교착 집합이다. 매듭 밖의 프로세스도 도달 가능한 프로세스가 모두 교착이면 교착이다. 매듭의 존재가 필요하다는 서술은 M17 §1 | M14 §2.3, M17 §1 | A− |
| AND-OR / P-out-of-Q 모델 | 순환은 필요하나 충분하지 않고, 매듭은 충분하나 필요하지 않다(M17 §1). Knapp §2.4는 AND-OR에 표준 그래프 구조가 없고 OR 검사를 반복하면 되지만 비효율이라고 쓰며, §2.5의 k-of-n은 정의가 부실해 순환·매듭 특성화를 주지 않는다고 쓴다. Knapp은 'P-out-of-Q'라는 용어를 쓰지 않는다 | M17 §1, M14 §2.4~2.5 | A− |
| 재사용 자원 m종을 공유하는 n개 프로세스 시스템의 교착 자유성(가능한 요청은 즉시 허용하는 정책 기준) | 다항 시간 O(n³m) 테스트 존재(1977년판 초록). M21은 이 테스트가 Habermann 모델을 이분 그래프로 바꾸는 방식이라고 설명 | M1, M2, M21 | B |
| 뱅커 모델의 안전 상태 | 순서 탐색으로 정확히 판정하며 증명이 있음 | F8 | A |
| 단일 단위 순차 자원 할당(Petri net) | 교착을 빈(unmarked) siphon으로 구조적으로 설명 | M11, M12 | B |

v0.3 주: AND, OR, AND-OR 세 행은 문서 04 §9의 정정 1·2에 따라 고쳤다(v0.2에서는 OR와 AND-OR를 한 행에 두었다). Knapp 서술(M14)은 열람 도구의 요약을 거친 A−이므로 본문과 다시 대조하기 전에는 논증의 전제로 쓰지 않는다. 'SM'은 이 저장소의 스냅샷 모델(`docs/spec/model-spec.md`)이고 V는 소규모 범위의 전수 검증이며 증명이 아니다. 모델별 현재 상태 판별의 더 자세한 지도는 문서 04 §4(a)에 있다.

### 1.3 알고리즘의 비용과 요구 정보

| 접근(분류) | 대표 문헌 | 비용·성질 | 요구 정보·한계 | 수준 |
|---|---|---|---|---|
| 자원 순서화(예방: 순환 대기 제거) | F6, T3 | 런타임 비용 서술 없음 | 전역 순서 설계 부담, 캡슐화와 충돌, 자원 종류가 많을 때 전순서 만들기 어려움(교육 자료) | A, C |
| 일괄 요청(예방: 점유-대기 제거) | F6, T3 | 위와 같음 | 필요 자원을 미리 알아야 함, 동시성 저하 | A, C |
| 반납 후 재시도(예방: 비선점 제거) | F6, T3 | 위와 같음 | 반납 가능한 자원에 한정, trylock 기반 재시도 프로토콜 | A, C |
| 뱅커 알고리즘(회피) | F7, F8, F3 | n개 프로세스·m개 자원 종류에서 Θ(mn²)(M6). 표기가 문헌마다 다르다: Li(M27)의 초록은 원래 알고리즘의 시간을 O(n³d)로 쓰고, 문헌에서 Θ(n²d)로 인용되는 값은 안전성 검사 부분만을 가리키는 오인용이라고 설명한다. 이 불일치를 오류로 단정하지 않는다(O(n³d)가 무엇을 센 값인지는 본문이 필요하다. 문서 04 §2.3) | 최대 요구량 사전 선언 필요. 멀티스레드 프로그램 맥락에서는 필요한 정보가 흔히 없고 런타임 계산도 비싸다는 지적(S5) | B, A− |
| 뱅커 개선 주장 | M6, M8, S11(S19, S20), S13, M27, M39, M40 | M6: 변형 알고리즘이 "특정한 있을 법한 조건" 아래 상각 최악 O(mn)이라고 초록이 쓴다(조건의 내용은 초록에 없다. 초록의 "최대 두 배 빠름" 문장은 열람 도구 요약 둘이 방향을 다르게 옮겨 확정하지 못했다). S11: 하드웨어 병렬화로 최악 O(n)·최선 O(1) 주장(ASP-DAC판으로 보이는 S19는 본문 A−, 학위논문 S20은 초록 B). S13: O(nd) 대 O(n²d) 주장이며 평가는 비교 횟수로 한다. M27: O(n²d²+ndM) 대 O(n³d)이고 공간은 더 나쁘다. M39·M40: 점근 복잡도 없이 실험 수치만 제시한다 | 모두 저자 주장이다. 논문마다 모델 가정과 비용 단위가 다르다 → 동일 조건 재현 전에는 비교하지 않는다. 후보 인벤토리는 `refs/rq6-inventory.md`, 비용 단위 정규화는 문서 04 §2 | B, A− |
| 그래프 기반 회피 | M7 | 방향 비순환 그래프를 경로 행렬(path matrix)로 표현해 간선 삽입 시 순환을 효율적으로 탐지한다. 초록은 순환 탐지가 싸서 나머지 연산을 상각하면 연산당 선형 또는 상수 시간이며, 메시지 수도 빠른 환경에서 연산당 상수로 상각된다고 쓴다 | 초록만 확인했고 본문은 읽지 못했다. 초록은 뱅커 알고리즘을 언급하지 않는다 | B |
| 일반 순차 자원 할당 계의 회피 | M3, M4, M5, M9, M10 | 안전성 판정은 넓은 클래스에서 NP-완전, 쉬운/어려운 경계 연구 | 모델 가정(순차 단계, 다중 자원 획득, 유연 라우팅)이 핵심 | B, D |
| 허용도 높은 정책 설계(Petri net/DES) | M12, M13 | 구조 복잡도·행동 허용도·계산 복잡도 세 축으로 비교(서베이) | 제조 시스템(FMS) 맥락. OS로의 이전은 별도 검증 | B |
| 타임스탬프 예방(wait-die/wound-wait) | S14(기원은 후속 문헌의 인용으로만 확인, D), S15, S2, S3, S17 | 경쟁 수준에 따라 롤백 수·경과 시간의 우열이 역전(패치 측정) | 롤백 가능한 트랜잭션 모델 | B, A− |
| 우선순위 천장 프로토콜 | S4 | 교착 형성 방지, 블로킹은 하위 우선순위 작업의 임계구역 1개 이하 | 우선순위와 세마포어 사용을 사전에 알아야 함(S6의 지적) | B, A− |
| 오프라인 제어 합성 + 온라인 경량 제어 | S5 | 벤치마크에서 오버헤드 최대 18% | 정적 분석·모델링 필요 | A− |
| 학습형 회피(패턴 지문) | S6 | 낮은 오버헤드, 1,024 스레드까지 확장(저자 주장) | 한 번 겪은 패턴을 회피 | A− |
| 스핀락 내장 탐지 | S7 | 스레드별 다이제스트로 대기 그래프 일부를 표현 | 타임아웃 가능한 스핀락 | B |
| 잠재 교착(락 순서 순환) 탐지 | S1, S8, S9 | S9: 건전·완전 예측은 일반적으로 난해, sync-preserving 부분 클래스는 선형 시간 | 실제 교착이 아니라 잠재 교착을 보고 | A, B |

### 1.4 실제 OS·런타임

- 교과서의 서지 노트(T1)는 OS가 보통 교착 예방 기능을 제공하지 않고 교착 없는 프로그램을 설계하는 일은 프로그래머 몫이라고 쓴다. 자원 순서화는 하벤더가 OS/360용으로 고안했다. FreeBSD의 witness 락 순서 검증기는 Baldwin(2002)으로 소개된다. [B, 후자는 D]
- 리눅스 lockdep(S1)은 락 클래스(인스턴스 수만 개가 하나의 클래스) 단위로 사용 상태와 클래스 간 의존성을 추적하고, 실제로는 아직 일어나지 않은 시나리오도 잠재적 역전으로 검증한다. 같은 클래스 안의 계층적 중첩은 어노테이션(nesting level)이 필요하며 잘못 매핑하면 오탐·미탐이 생길 수 있다고 문서가 경고한다. [A]
- 리눅스 ww_mutex(S2, S3): 락 클래스 단위로 wound-wait와 wait-die 중 하나를 고른다. 문서는 경쟁 트랜잭션이 적을 때 wound-wait를 권한다. 패치 설명의 마이크로벤치마크(4코어 x86_64): 4스레드에서 wound-wait는 롤백 약 100회·약 17초, wait-die는 약 15만 회·약 19초. 16스레드에서는 wound-wait 약 36만 회·약 109초, wait-die 약 45만 회·약 82초. 동료 심사를 거치지 않은 단일 환경 측정이다. [A−]
- 구글 Spanner 논문(OSDI 2012) §4.2.1은 읽기-쓰기 트랜잭션의 읽기에 wound-wait를 써서 교착을 피한다고 서술하고 Rosenkrantz 외(1978)를 인용한다(S17). [A−] S16도 같은 사실을 서술한다. [C]
- Abseil의 Mutex 디버그 모드는 락 획득 순서 DAG를 유지하고 순서가 어긋나면 잠재 교착을 보고하며, 증분 갱신에 Pearce–Kelly 알고리즘을 쓴다는 저자 블로그 글이 있다. [C] (S10)

### 1.5 실증 데이터: 실제 교착은 어떤 모양인가

| 항목 | 사용자 공간(E1, 2008) | 리눅스 커널(E2, 2026) |
|---|---|---|
| 표본 | MySQL·Apache·Mozilla·OpenOffice의 동시성 버그 105건(교착 31건) | 2019-01-01~2023-06-01 mainline 수정 커밋에서 확인한 동시성 버그 200건(교착 49건) |
| 교착 비중 | 29.5% (31/105) | 24.5% (49/200) |
| 단일 스레드 교착 | 7/31 (22.6%) | 16/49 (32.7%). 논문은 이중 락(double-lock)의 원인으로 함수 포인터 간접 호출과 인터럽트에 의한 재진입을 든다(§4.2). 단, 논문은 교착의 스레드 수를 셀 때 인터럽트 핸들러를 별도 스레드로 세지 않으므로(§4.2) 이 16건에는 스레드가 락을 쥔 채 인터럽트되어 핸들러가 같은 락을 요청하는 사례가 들어갈 수 있다. 공개 데이터셋에서 이 16건의 '인터럽트 의존' 열은 true가 0건(false 15, 결측 1)이다. 논문은 인터럽트에 의한 재진입을 이중 락의 또 다른 주요 원인이라고 쓰지만 16건 안의 건수는 제시하지 않으며, 두 사실이 어떻게 양립하는지는 미확인이다(열의 정의는 관련 코드 영역이 인터럽트 처리로만 도달 가능할 것을 요구한다, §3.1). 16건의 내역(인터럽트 재진입, 간접 호출, 그 밖)은 RQ5에서 사례별로 코딩한다 [A, 문서 03 §3] |
| 관여 자원·스레드 | 교착의 97%(30/31)가 자원 2개 이하. 3스레드·3자원 사례는 1건 | 전체 동시성 버그의 98.5%가 스레드 2개 이하로 재현. 교착만 보면 공개 데이터셋의 '실행 문맥 수' 열이 2개 31건·1개 16건·3개 이상 2건이어서 2개 이하가 47/49(95.9%)다. 이 열의 정의와 논문의 스레드 수 정의가 같은지는 추가 확인이 필요하다 [A, 문서 03 §3] |
| 수정 전략 | 자원 획득 포기 19, 획득 순서 변경 7, 자원 분할 1, 기타 4 | 교착 전용 수치는 이번 조사에서 미확인 |
| 저자가 밝힌 한계 | OS·과학계산·다른 언어는 대표하지 못할 수 있음 | 키워드 필터로 고른 표본, 재현 대신 커밋·메일링 리스트 분석 |

두 연구 모두 수정된 버그만 본다(미보고·미수정 교착은 표본 밖). [A]

해석(가설): 사용자 공간의 교착은 대부분 2자원 사이클이지만, 커널에서는 단일 스레드로도 발생하는 교착(이중 락)이 무시할 수 없는 비중이다. 논문이 드는 원인은 함수 포인터 간접 호출과 인터럽트 재진입이며, 후자의 비중은 위 열 때문에 확인되지 않았다. 이런 사례는 순환 대기를 둘 이상의 프로세스 사이의 사슬로 서술하는 교재 서술(T9, C)이나 프로세스가 스스로 요청한다는 고전 모델의 가정과 어긋날 수 있다. 다만 실제로 어긋나는지는 원문 정의(F1, F2)와 사례별 코딩으로 확인해야 하며, 간접 호출 사례는 모델의 문제가 아니라 요청 집합을 정적으로 알 수 없다는 정보의 문제일 수 있다. → RQ5의 동기 후보.

### 1.6 용어 주의: '예방'이라는 단어의 역사적 쓰임

- 뱅커 알고리즘 원고(EWD108)의 제목은 네덜란드어로 치명적 포옹의 예방을 위한 알고리즘이다. [A−] (F7, 전사본 제목 확인) EWD623은 서두에서 뱅커 알고리즘을 교착 예방 방법의 예로 소개한다. [A] (F8)
- 하버만(1969)의 논문 제목도 시스템 교착의 예방이다(F3). 홀트의 논평(F4)은 하버만의 방법을 논하면서, 스케줄러가 그 방법이 막지 못하는 인공적 교착을 만들 수 있고 교착 예방이 영구 봉쇄(기아)를 자동으로 없애지는 않는다고 지적한다. [B]
- 현대 교과서 분류는 뱅커 알고리즘을 회피로 둔다. [B] (T1) → 인용할 때는 "원문 표현: prevention / 본 연구 분류: avoidance"로 병기한다.

---

## 2. 선행연구 조사 계획

### 2.1 목표와 산출물

목표: (1) 기존 이론의 정확한 정리, (2) 해결된 문제와 남은 문제의 구분, (3) 연구 질문 후보의 선행연구 중복 판정, (4) 연구 질문 확정.

산출물:

1. 모델×결과 매트릭스(§1.2의 확장판. 칸마다 정의·가정·정리·증명 위치·확인 수준)
2. 알고리즘×비용·가정 표(§1.3의 확장판. 동일한 모델 가정으로 정규화)
3. 해결/미해결 표(§3의 확정판)
4. RQ 게이트 판정표(§5)
5. 주장 대장(claims ledger)과 BibTeX

### 2.2 조사 축

| 축 | 핵심 질문 | 시작 문헌 | 검색어 예 | 완료 기준 |
|---|---|---|---|---|
| A1 조건의 정의·논리 구조 | 네 조건과 deadlock의 정의가 문헌별로 어떻게 다르게 정식화되는가 | F1, F2, F6, F10, T1~T5, T7 | "Coffman conditions" necessary sufficient / "defining deadlock" / 교착상태 필요조건 충분조건 | 정의·가정 비교표, 불일치 항목별 원문 근거 |
| A2 상태 판별 이론 | 모델(인스턴스 수, 요청 형태, 소모성 자원)별로 교착과 상태 조건은 어떤 관계인가 | F2, M1, M2, M14~M18, F8, M20 | "general resource graph" knot expedient / "AND-OR model" deadlock / "P-out-of-Q" | 모델 매트릭스 완성(원문 대조) |
| A3 알고리즘 비용·복잡도 | 예방·회피·탐지 알고리즘의 비용과 요구 정보는 무엇이고 어디서 어려워지는가 | F3, F7, F8, M3–M10, M20, S11–S13 | "banker's algorithm" complexity / deadlock avoidance NP-complete / maximally permissive | 비용표, 복잡도 경계 지도 |
| A4 실제 시스템·실증 | 실제 OS·런타임은 무엇을 쓰고 실제 교착은 어떤 구조인가 | S1~S10, E1, E2, T1, T3 | lockdep / ww_mutex / priority ceiling deadlock-free / Linux kernel deadlock study | 시스템별 정책·비용 표, 실증 데이터 재분석 계획 |
| A5 인접 분야 | DES·Petri net, DB 동시성 제어, 분산 탐지, 형식 검증의 결과 중 이전 가능한 것은 | M11–M13, M16–M19, S14–S16, V1 | siphon deadlock prevention / wait-die wound-wait / generalized deadlock detection / mechanized deadlock freedom Coq Isabelle TLA+ Alloy | 이전 가능·불가 판정과 근거 |
| A6 알고리즘 도구 | 증분 순환 탐지·위상 순서 같은 자료구조가 이미 어디에 쓰이는가 | G1~G4, M7, S10 | incremental cycle detection / dynamic topological order lock graph | 응용 사례·비용 한계 표 |

국내 문헌: KCI·RISS·DBpia·KoreaScience에서 교착상태 예방·회피 알고리즘, 뱅커 알고리즘 개선을 검색한다(현재 M21 1건만 확인).

### 2.3 단계

| 단계 | 내용 | 완료 기준 |
|---|---|---|
| Phase 0 (완료) | 핵심 문헌 서지 1차 확인, 확인 수준 표기 | §7 표 |
| Phase 1 | 원문 대조: §6의 X·C 항목. 본문 접근이 필요한 문헌의 PDF 확보 방법 결정 | 각 항목 A 또는 사유 기록 |
| Phase 2 | 모델 매트릭스(A1, A2) 완성 | 칸마다 원문 위치 |
| Phase 3 | 비용표·복잡도 지도(A3), 시스템·실증(A4), 인접 분야(A5, A6) | 동일 가정으로 정규화된 표 |
| Phase 4 | 공백 후보 도출, 게이트 판정(§5) | 판정표 |
| Phase 5 | 연구 질문 확정, 증명·실험 설계 | 설계 문서 |

알고리즘 구현은 Phase 5 이전에 시작하지 않는다(브리프 §6). 단, RQ6·RQ3의 벤치마크 하네스는 구현이 아니라 측정 도구이므로 Phase 3 이후 선행 착수를 검토한다.

### 2.4 검색·선정 규칙

- 출처 우선순위: ① 원 논문·공식 문서 ② 출판사/DBLP/arXiv 서지 ③ 교과서 ④ 강의자료·블로그(단서로만)
- 포함: OS·런타임 수준 자원 교착의 정의·판별·예방·회피·탐지·비용·실증. 인접 분야는 이전 가능성이 있을 때만 포함한다.
- 기본 제외: 순수 통신 교착(네트워크 라우팅), 라이브락·기아 단독 주제(예방 기법의 부작용으로 나오면 기록), 출처 확인이 불가능한 주장
- 역·정방향 인용 추적은 F1, F2, M9, S1, E1, E2에서 시작한다.
- 검색 도구의 한계(미국 대상 검색, 유료 본문 접근 제한)를 기록하고 DBLP·OpenAlex·Crossref로 교차 확인한다.

### 2.5 인용·검증 프로토콜

모든 주장은 주장 대장에 한 줄로 기록한다.

| ID | 주장(자기 말로) | 출처 ID | 위치(절·표·쪽) | 수준 | 확인일 | 비고 |
|---|---|---|---|---|---|---|

- 수준이 C 이하인 주장은 논증의 전제로 쓰지 않는다.
- 숫자(복잡도, 비율)는 원문에서 직접 확인한 것만 옮긴다.
- 새 알고리즘의 복잡도 같은 개선 주장은 저자 주장으로 표기하고, 동일 조건 재현 전에는 비교표에 넣지 않는다.
- 기억에 의존한 서지(저자, 쪽수, 연도)는 쓰지 않는다. 확인하지 못하면 X로 둔다.

### 2.6 편향 통제

- 생존 편향: E1, E2 모두 수정된 버그만 본다.
- 대표성: E1은 사용자 공간 4개 앱, E2는 mainline 커밋의 키워드 필터 표본이다.
- 검색 편향: 영어·미국 검색 중심이므로 국내·비영어 문헌을 보완한다.
- 확증 편향: RQ 후보마다 반증 조건을 먼저 적는다(§4).

---

## 3. 해결된 문제와 열린 문제 (잠정. v0.3에서 문서 04 §8의 판정으로 갱신)

| 주제 | 현재 상태(근거) | 판정 | 비고 |
|---|---|---|---|
| 단일 인스턴스의 상태 판별 | AND 요청, 모든 자원 용량 1에서 순환 ⟺ 교착(SM T2, 소규모 전수 검증 V). Knapp §2.2(A−)는 AND 모델에서 교착이려면 순환이 필요하고 탐지가 순환이 있을 때 교착을 선언한다고 서술하며 단일 단위 한정은 명시하지 않는다. 교육 자료의 증명(T4, T6, C) | 해결(AND, 모든 자원 용량 1에 한정) | F2 원문 대조는 남음. V는 증명이 아님 |
| 다중 인스턴스의 현재 상태 판별 | 코프만 외가 다중 인스턴스 탐지 알고리즘을 제시했다고 교과서 서지 노트가 적음(T1), 그래프 축소(T6). **대기 그래프 순환은 교착을 뜻하지 않는다**(반례 B4, V). 일반 문제는 로그 공간 환원에서 P-완전(M29 초록, B) | 해결(알고리즘 수준) | 비용 O(mn²)는 교재 슬라이드 수준(C) |
| 뱅커 모델의 안전성 판정 | Θ(mn²)(M6), 정확성 증명(F8) | 해결 | 개선 주장은 미결: 비용 표기와 모델 가정이 문헌마다 다르다(문서 04 §2). 재현은 RQ6 |
| 일반 순차 자원 할당 계의 안전성 | 넓은 클래스에서 NP-완전(M9, M10), 다항 준최적 정책 존재 | 어려움 확인 | 경계 사례 연구 계속. M9는 본문 A−, M5·M22 본문 미확인 |
| 일반화(AND/OR) 요청의 판별 | OR는 매듭에 대응(Knapp §2.3), AND-OR는 표준 그래프 구조가 없음(Knapp §2.4). 모델별 필요·충분 관계(M17 §1), 분산 탐지 알고리즘 다수(M14~M16) | 부분 해결(v0.2 서술을 §1.2에서 정정) | 비용 비교 X |
| 정책 비교(허용도·비용) | Petri net 계열 비교 서베이(M13), DB 알고리즘 비교(S15), DB 교착 처리 방식 비교 보고서 2건(M46, M47. 서지 페이지에 초록 없음) | OS 정책 비교는 이번 조사에서 확인 못함 | 부재 증명 아님 |
| 모델 통합·기계 검증 | 해당 모델의 기계 증명은 확인 못함(인접: V1). 이 저장소의 소규모 전수 검증(V)은 있음 | 미확인 | 전수 검증은 증명이 아님. 추가 검색 필요 |
| 인터럽트·간접 호출을 포함한 교착 모델 | lockdep이 사용 상태 규칙으로 운영(S1), 커널 실증(E2) | 형식 모델 선행 미확인 | RQ5 |
| 증분 순환 탐지 기반 락 순서 검사 | Abseil 디버그 모드(S10, C), Belik(M7, M48), Haeupler 외가 서론에서 교착 탐지를 응용으로 인용(G2 §1. 인용 항목은 열람한 텍스트에 없고, M48이 그 후보라는 것은 저자·연도 일치로 한 추정) | 부분 선점(근거 보강) | RQ4 중복 위험 높음 유지 |
| 실제 교착의 구조 통계 | 사용자 공간(E1), 커널(E2). 자기 대기에 해당하는 사례의 비중이 표본마다 22.6%~78.9%(E1·E2는 '단일 스레드 교착', E3·E4는 '이중 락'으로 센 값이고 분모도 달라 서로 비교할 수 없음, 문서 04 §6) | 존재 | 다중 인스턴스 자원이 관여하는 비율은 미확인 |
| 락 프로그램 정적 분석의 결정 가능성(신규) | 락 접근이 중첩 구조면 효율적으로 결정 가능, 중첩이 아니면 스레드가 둘뿐이어도 도달 가능성이 결정 불가능(M38 초록, B) | 경계 확인 | M38은 Kahlon·Ivančić·Gupta의 CAV 2005 논문(§7.2). RQ2 중복 위험 요인(문서 04 §4 읽는 법 4) |

v0.2의 판정에서 바뀐 곳과 사유는 문서 04 §8의 '변경 사유' 열에 있다. 이 판정은 AI 초안이며 사람의 검토 전이다.

---

## 4. 연구 질문 후보

방향 표기는 브리프 §3의 A(조건 재정의·완화), B(필요충분조건), C(조건 기반 알고리즘 설계)다. 중복 위험은 지금까지 본 문헌에 대한 잠정 평가이며 §5 게이트 전에는 확정이 아니다.

### 4.0 비교표

| RQ | 방향 | 한 줄 요약 | 이론 난도 | 실험·검증 가능성 | 중복 위험(잠정) | 첫 산출물 |
|---|---|---|---|---|---|---|
| RQ1 | A+B | 정책 수준/상태 수준 조건 분리와 모델별 관계의 통합·기계 검증 | 중 | 높음 | 중~높음 | 모델 매트릭스, 소규모 반례 생성기 |
| RQ2 | B | 커널 현실 제한 가정 아래 정확한 판정·회피의 복잡도 경계 | 상 | 중 | 높음(v0.3에서 상향: M9, M38) | 가정 목록, 복잡도 지도 |
| RQ3 | C | 정책별 허용도–비용 프런티어 측정 | 하~중 | 높음 | 중 | 시뮬레이터, 정책 구현, 정확 오라클 |
| RQ4 | C | 증분 위상 순서 기반의 상시 락 순서 승인 | 하 | 중~높음 | 높음 | 기존 구현 비교표, 프로토타입 |
| RQ5 | A | 인터럽트·간접 호출을 포함한 조건 모델 확장 | 중~상 | 중 | 중 | 커널 교착 49건 재분류표 |
| RQ6 | C(기반) | 뱅커 개선 주장의 동일 조건 재현 | 하 | 높음 | 낮음~중(확인 필요) | 벤치마크, 정확성 테스트 |

### RQ1. 조건의 층위 분리와 모델별 관계의 통합 형식화 (방향 A+B)

- 질문: 네 조건을 (i) 정책 수준 속성(상호배제·점유-대기·비선점이 허용되는지, 순환 대기가 가능한지)과 (ii) 상태 수준 술어(실제 순환, 그래프 축소 불가능성)로 나누고, 자원 모델(인스턴스 수, AND/OR/P-out-of-Q 요청, 재사용/소모성)별로 교착과 상태 술어의 관계, 정책 조건과 안전성의 관계를 한 틀에서 정리하고 증명할 수 있는가? 그 틀 위에서 기존 예방 기법(순서화, 일괄 요청, 선점, 천장 프로토콜, wound-wait)이 어떤 조건을 어떤 모델에서 깨는지 분류할 수 있는가?
- 근거: §1.1~1.2. 서술 불일치, 모델별 결과의 분산, 교육 자료 수준의 부분 증명.
- 아직 모르는 것: 홀트·레바인·싱할 계열 서베이가 이미 통합 표를 주는지. 기계 검증 선행연구(이번 검색에서는 확인 못함).
- 이론 난도 중, 검증 가능성 높음: 작은 모델(예: 프로세스 ≤4, 자원 종류 ≤3, 인스턴스 ≤3)을 전수 열거해 정리를 검사하고 반례를 생성한다(Alloy·TLA+·SAT). 이후 Lean·Coq·Isabelle 증명.
- 반증 조건: 같은 통합이 이미 문헌에 있다 → 폐기 또는 축소. 일부 모델에서 통합 틀이 성립하지 않음이 증명된다 → 범위 한정.
- 첫 작업: 모델 매트릭스를 원문 대조로 채운다.

### RQ2. 커널 현실 제한 가정 아래의 정확 판정 복잡도 (방향 B)

- 질문: 안전 상태 판정이 일반적으로 어렵더라도, 실제 사례의 구조(사이클 길이 ≤2, 락 중첩 깊이 ≤k, 인터럽트 문맥 포함)를 가정으로 삼으면 과잉 거부 없이 정확한 판정·회피가 다항 이하 비용으로 가능한 클래스가 있는가? 그 경계는 어디인가?
- 근거: E1(교착의 97%가 자원 2개 이하), E2(98.5%가 스레드 2개 이하), DES 계열의 쉬운/어려운 경계 연구(M9).
- 아직 모르는 것: 위 가정을 형식 클래스로 정의한 선행 복잡도 결과가 있는지. 커널에서 다중 인스턴스 자원이 교착에 관여하는 비율.
- 이론 난도 상, 검증 가능성 중(정확 오라클 구현 필요).
- 반증 조건: 제한 클래스에서도 NP-난해이거나 이미 다항 알고리즘이 있다. 가정이 실제 데이터와 맞지 않는다.
- 첫 작업: 제한 가정 후보와 각 가정의 실증 근거·한계 표.

### RQ3. 정책별 허용도–비용 프런티어 측정 (방향 C)

- 질문: 같은 자원·락 트레이스에서 순서화, 천장 프로토콜, wait-die/wound-wait, 뱅커 계열, 일괄 요청, 혼합 정책을 (a) 정확한 안전 오라클 대비 불필요한 거부·지연 비율, (b) 요청당 비용, (c) 롤백·대기 시간 분포로 측정하면 다른 정책에 지배되지 않는 설계점이 있는가?
- 근거: ww_mutex 문서·패치 수치(경쟁 수준에 따라 우열 역전), Li–Zhou–Wu의 비교 축(M13), Carey–Livny(S15). 혼합 정책은 1973년 CACM 논문(F11)과 일부 강의 노트(C)에 이미 있는 개념이므로 정책 목록의 한 항목으로 둔다.
- 아직 모르는 것: OS 정책을 같은 기준으로 비교한 연구(이번 조사에서는 못 찾았으나 부재 증명 아님). M22 보고서의 내용.
- 이론 난도 하~중, 검증 가능성 높음.
- 반증 조건: 한 정책이 모든 워크로드에서 우세해 프런티어가 퇴화한다. 동일한 비교가 이미 존재한다.
- 첫 작업: 트레이스 포맷, 정확 오라클(소규모 완전 탐색), 정책 레퍼런스 구현.

### RQ4. 증분 위상 순서 기반의 상시 락 순서 승인 (방향 C)

- 질문: 락 클래스 의존 그래프를 증분 위상 순서로 유지하면서 순환을 닫는 의존 추가를 거부하거나 우회하는 방식으로 상시(always-on) 예방을 하되, 디버그 전용이 아닌 환경에서 요청당 비용과 거부율을 허용 가능한 수준으로 만들 수 있는가?
- 근거: G1(증분 순환 탐지의 총 시간 상한), G3, S10(Abseil 디버그 모드), M7(1988년의 path matrix).
- 중복 위험이 높은 이유: 같은 자료구조가 이미 락 순서 검사에 쓰이고(S10, C), 증분 순환 탐지 논문이 교착 탐지를 응용으로 든다(G2). 차별점이 있다면 상시 적용과 대안 경로(trylock·wound) 결합 정도이며 이는 가설이다.
- 이론 난도 하, 검증 가능성 중~높음.
- 반증 조건: 디버그 전용 도구 대비 의미 있는 비용 절감이 없다. 거부율이 실제 워크로드에서 과다하다.
- 첫 작업: Abseil·lockdep·Goodlock 계열 구현의 자료구조·비용 비교표.

### RQ5. 인터럽트·간접 호출을 포함한 조건 모델 확장 (방향 A)

- 질문: 고전 조건은 인터럽트 재진입과 함수 포인터 간접 호출에서 생기는 단일 스레드 자기 교착, irq-safe/unsafe 락 의존을 어떻게 포착하는가, 혹은 포착하지 못하는가? 요청의 자율성 가정을 완화한 모델에서 필요(충분)조건을 어떻게 다시 정의해야 하는가?
- 근거: E2(교착의 32.7%가 단일 스레드), S1(hardirq/softirq 사용 상태 규칙).
- 아직 모르는 것: 이 현상을 형식 모델로 다룬 선행연구(정적 분석, Petri net 계열). 고전 조건에서 어떤 가정이 정확히 깨지는지.
- 이론 난도 중~상, 검증 가능성 중: E2의 공개 데이터셋(교착 49건)을 재분류해 모델의 포괄성을 점검한다.
- 반증 조건: 확장 모델이 기존 lockdep 상태 규칙 이상을 설명하지 못한다. 데이터의 다수가 기존 모델로 이미 설명된다.
- 첫 작업: 49건 분류표와 현행 조건으로 설명되는 비율.

### RQ6. 뱅커 개선 주장의 동일 조건 재현 (방향 C 기반 연구)

- 질문: Belik(1987), Lang(1999), Lee–Mooney(2006), Zohora 외(2024) 등의 개선 주장을 같은 모델 가정·같은 오라클·같은 워크로드에서 재현하고 비교하면 어떤 주장이 유지되는가?
- 근거: 브리프 §5의 7항(동일 조건 비교)과 8항(성립하지 않으면 폐기).
- 아직 모르는 것: 같은 종류의 재현·비교 연구가 이미 있는지.
- 이론 난도 하, 검증 가능성 높음.
- 반증 조건: 각 주장이 서로 다른 모델을 전제해 동일 조건 비교 자체가 성립하지 않는다.
- 첫 작업: 기준 구현, 안전/불안전 판정 일치 테스트, 복잡도 측정.

### 4.1 잠정 우선순위

RQ6과 RQ3은 측정 중심이라 선행연구 결과와 무관하게 하네스를 재사용할 수 있어 먼저 착수하기 좋다. RQ1은 이론 기여 가능성이 있지만 중복 판정(§5)에 크게 좌우된다. RQ4는 중복 위험이 높아 새 주장보다는 비교·측정 항목으로 흡수하는 쪽이 안전해 보인다. RQ5와 RQ2는 커널 전문 지식과 데이터가 더 필요하며 Phase 3 결과를 보고 결정한다.

v0.3 주: Phase 3 결과(문서 04 §11.2)는 다음과 같다. RQ2는 M9(구조 조건 아래 다항 클래스)와 M38(락 중첩 여부에 따른 결정 가능성)이 이미 인접 경계를 주어 중복 위험을 높음으로 올렸고, G4에서 '부분'을 예상한다(해석). RQ4는 높음을 유지한다. RQ6는 재현 대상의 최소 건수를 사람이 정해야 한다(후보는 `refs/rq6-inventory.md`). RQ5는 H5a의 동기(자기 대기 비중)가 지지되며, 자기 대기를 조건 모델의 일부로 둘지 락 타입의 계약으로 볼지를 함께 검토할 질문 후보로 둔다(문서 04 §5, §6). 이 후보는 위 RQ5 본문에는 아직 넣지 않았다. 이 판단은 모두 AI 초안이다.

---

## 5. 연구 질문 확정 전 게이트

각 RQ에 대해 다음 표를 채운 뒤에만 참신성을 논한다.

| RQ | 선행연구 후보 | 판정(동일/부분/없음) | 근거 링크 | 차이점 | 결정 |
|---|---|---|---|---|---|

- 동일: 같은 문제, 같은 가정, 같은 결론이 이미 있다 → 폐기 또는 재현 연구로 전환
- 부분: 일부 가정·결론이 겹친다 → 차이점을 명시하고 범위를 좁힌다
- 없음: 3개 이상의 독립적 검색 경로(키워드, 인용 추적, 인접 분야)에서 찾지 못했다. 단, 검색 한계를 함께 적고 부재를 증명했다고 쓰지 않는다.

---

## 6. 아직 확인하지 못한 것

| 항목 | 내용 | 접근 방법 |
|---|---|---|
| F1 §2 | 충분성 서술, 조건의 원래 명칭, 그래프 방법 | 기관 구독(ACM DL) 또는 PDF 제공 |
| F2 | 일반 자원 그래프의 정리들(현재는 강의노트로 대체) | 위와 같음 |
| F3 | 하버만 방법의 구체 | 위와 같음 |
| M3, M4, M5 | 복잡도 결과의 정확한 명제와 모델 | 위와 같음, 저자 사이트 |
| M15 | (정정) 확인한 1989년 논문은 자원 할당 그래프와 TWF 그래프 모델 중심이며 AND/OR/AND-OR/P-out-of-Q 분류나 knot 서술이 없다. 그 분류의 출처는 별도로 찾아야 한다 | 문서 03 §2 |
| M18, M19 | AND 모델 관련 내용 | Springer, IEEE 접근 |
| S14 | wait-die/wound-wait의 기원 | 원문 |
| F11 | 저자와 내용 | ACM DL |
| M20, M22 | 저자·연도·내용 | Springer, DTIC |
| 기계 검증 선행연구 | TLA+, Alloy, Isabelle AFP, Coq, Lean 대상 추가 검색 | 추가 검색 |
| 국내 문헌 | KCI·RISS·DBpia 체계적 검색 | 추가 검색 |
| E2 데이터셋 | 교착 49건 열람 | 논문에 적힌 공개 저장소 |
| 커널 락 사용 통계 | 다중 인스턴스 자원이 관여하는 교착의 비율 | 커널 소스·커밋 분석 |

### 6.1 G1 이후 상태 (2026-10-29, 문서 03)

| 항목 | 상태 |
|---|---|
| F1 §2, F2, F3 | 공개 사본을 찾지 못함. 본문 대조는 사용자가 PDF를 제공해야 가능 |
| M3, M4 | 결과 내용을 M9 본문(§2)에서 2차로 확인. 원문 대조는 여전히 필요 |
| M5, M18, M19 | 서지·초록 수준 유지 |
| M15 | 위와 같이 정정 |
| M20 | 저자 확인(Hauschildt, Valk, 1986) |
| S14 | 후속 문헌 2건의 인용으로만 확인(D) |
| F11, M22 | 저자·연도 미확인 유지 |
| 기계 검증 선행연구, 국내 문헌 | 1차 검색 수행, 직접 일치 없음. 부재 증명이 아니며 G4에서 계속 |
| E2 데이터셋 | 49건 확인 완료 |
| 커널 락 사용 통계 | 미착수(RQ5 코딩 단계) |

### 6.2 Phase 3 이후 상태 (확인일 2026-10-29, 문서 04)

| 항목 | 상태 |
|---|---|
| M6 | 초록을 두 경로로 재확인. 변형 알고리즘의 "특정한 있을 법한 조건"의 내용과 "최대 두 배 빠름" 문장의 방향은 본문이 필요 |
| M14 | §2.2~2.5의 모델별 서술을 확인(열람 도구 요약 경유, A−). 본문과 재대조 필요 |
| M22 | 저자·연도 후보: H.-C. Chang, CMU 박사논문 1975(M30). 동일성은 제목 유사성뿐(C). 하한의 수치는 읽지 못함 |
| S11 | ASP-DAC판으로 보이는 저자 사이트 PDF(S19, 본문 A−)와 학위논문 초록(S20, B)을 확인. TPDS판 본문과의 관계는 미확인 |
| S18 | Crossref 서지에 SOSP '71로 등록됨(B) |
| G2 | 서론 §1이 교착 탐지를 응용으로 [Belik 1990]을 인용(A−). 그 참고문헌 항목은 열람한 텍스트에 없다(D). 후보 서지로 F. Belik, IEEE Trans. Computers 39(7), 1990(M48)을 Crossref에서 찾았고(2026-10-31) 같은 논문이라는 것은 저자·연도 일치에 의한 추정(C)이다 |
| M38 | 저자·서지 확정(2026-10-31): Kahlon, Ivančić, Gupta, CAV 2005, DOI 10.1007/11513988_49. 세 곳이 일치한다(문서 04 §10.3). 내용은 초록 수준(B) |
| E5 | 본문 PDF를 읽음(2026-10-31, A−). 블로킹 85건 중 Mutex 28, RWMutex 5이고 이중 락 건수는 본문에 없다. Go 내장 교착 탐지기는 재현한 블로킹 버그 21건 중 2건을 탐지(문서 04 §10.3) |
| 새 서지 | M27–M47, S19–S26, E3–E5를 §7에 추가(M48, M49는 2026-10-31에 추가). M31–M36은 Crossref 서지만 확인했고 내용은 읽지 못함 |
| 읽지 못한 원문 | Belik 1987 본문(M6), Belik 1990 본문(M48), Li 2013 본문(M27), Minoura 1982 명제(M5), Chang 1975 하한의 수치(M22, M30), Gold(M3)·Araki(M4) 원문, Dimmunix(S6)의 수치, FreeBSD WITNESS 매뉴얼. 사람이 PDF를 주거나 다른 접근 경로가 필요하다(문서 04 §12) |

---

## 7. 참고문헌

수준 표기는 §0.1을 따른다. URL은 이번 조사에서 실제로 확인된 주소다.

### 7.1 고전·기초 (F)

| ID | 서지 | 수준 | URL |
|---|---|---|---|
| F1 | E. G. Coffman Jr., M. J. Elphick, A. Shoshani, "System Deadlocks", ACM Computing Surveys 3(2): 67–78, 1971. DOI 10.1145/356586.356588 | B, A− | https://vldb.org/dblp/db/journals/csur/csur3.html · 미러 PDF(바이너리로 열람 불가): https://carlstrom.com/stanford/quals/mirror/www-db.stanford.edu/~manku/quals/zpapers/71-deadlocks.pdf.gz |
| F2 | R. C. Holt, "Some Deadlock Properties of Computer Systems", ACM Computing Surveys 4(3): 179–196, 1972 (SOSP 1971: 64–71). DOI 10.1145/356603.356607 | B | https://biblio.cerist.dz/index.php/show/ar/00000000000000606635000000 · https://plg.uwaterloo.ca/~holt/cv/morepapers.html · https://dblp.org/db/conf/sosp/sosp71.html |
| F3 | A. N. Habermann, "Prevention of System Deadlocks", CACM 12(7): 373–377, 385, 1969. DOI 10.1145/363156.363160 | B, D | https://os-book.com/OS9/bib-dir/7.pdf · https://api.crossref.org/works/10.1007%2FBF00289247 |
| F4 | R. C. Holt, "Comments on prevention of system deadlocks", CACM 14(1): 36–38, 1971 | B | https://cacm.acm.org/?p=15297 |
| F5 | D. L. Parnas, A. N. Habermann, "Comment on deadlock prevention method", CACM 15(9): 840–841, 1972. DOI 10.1145/361573.361586 | B | https://experts.mcmaster.ca/scholarly-works/2168965 |
| F6 | J. W. Havender, "Avoiding deadlock in multitasking systems", IBM Systems Journal 7(2): 74–84, 1968 | A | https://bitsavers.org/pdf/ibm/IBM_Systems_Journal/072/ibmsj0702B.pdf |
| F7 | E. W. Dijkstra, EWD108, "Een algorithme ter voorkoming van de dodelijke omarming" (연도는 열람한 전사본 머리말에 없음, 교과서는 1965로 인용). 돈 비유의 단일 자원 뱅커 알고리즘과 안전 상태를 서술 | A− | https://www.cs.utexas.edu/~EWD/transcriptions/EWD01xx/EWD108.html · 해설문: https://arxiv.org/pdf/cs/0210001 |
| F8 | E. W. Dijkstra, EWD623, "The mathematics behind the Banker's Algorithm", Selected Writings on Computing: A Personal Perspective, Springer, 1982, pp. 308–312 | A | https://www.cs.utexas.edu/~EWD/transcriptions/EWD06xx/EWD623.html |
| F9 | S. S. Isloor, T. A. Marsland, "The Deadlock Problem: An Overview", IEEE Computer 13(9), 1980. DOI 10.1109/MC.1980.1653786 | B | https://api.openalex.org/works/doi:10.1109%2FMC.1980.1653786 |
| F10 | G. N. Levine, "Defining Deadlock", ACM SIGOPS Operating Systems Review 37(1), 2003. DOI 10.1145/881775.881781 | B | https://unpaywall.org/10.1145%2F881775.881781 |
| F11 | "Mixed solutions for the deadlock problem", CACM 16(7), 1973 (저자 X). DOI 10.1145/362280.362290 | B | https://cacmb4.acm.org/magazines/1973/7/11865-mixed-solutions-for-the-deadlock-problem |
| F12 | A. Shoshani, E. G. Coffman, "Prevention, detection, and recovery from system deadlocks", Proc. 4th Princeton Conf. on Information Sciences and Systems, 1970 | D | https://unpaywall.org/10.1145%2F362280.362290 (참고문헌 목록) |
| F13 | E. G. Coffman, P. J. Denning, Operating Systems Theory, Prentice-Hall, 1973 | D | https://www.rairo-ita.org/articles/ita/ref/1984/01/ita1984180100711/ita1984180100711.html (참고문헌 목록) |

### 7.2 모델·특성화·복잡도 (M)

| ID | 서지 | 수준 | URL |
|---|---|---|---|
| M1 | T. Kameda, "A polynomial-time test for the deadlock-freedom of computer systems", LNCS 48, 1977. DOI 10.1007/3-540-08138-0_24 | B | https://unpaywall.org/10.1007%2F3-540-08138-0_24 |
| M2 | T. Kameda, "Testing deadlock-freedom of computer systems", JACM 27(2): 270–280, 1980 | B | https://projects.csail.mit.edu/jacm/References/kameda1980:270.html |
| M3 | Gold, "Deadlock prediction: easy and difficult cases", SIAM J. Comput. 7(3): 320–336, 1978 | B, D | https://unpaywall.org/10.1145%2F362280.362290 (초록) · https://link.springer.com/article/10.1023/A:1012203214611 (참고문헌 목록) |
| M4 | T. Araki, Y. Sugiyama, T. Kasami, J. Okui, "Complexity of the deadlock avoidance problem", 2nd IBM Symp. on Mathematical Foundations of Computer Science, Tokyo, pp. 229–252, 1977 | D | https://link.springer.com/article/10.1023/A:1012203214611 (참고문헌 목록) |
| M5 | T. Minoura, "Deadlock avoidance revisited", JACM 29(4): 1023–1048, 1982 (키워드: NP-complete, PSPACE-complete) | B | https://projects.csail.mit.edu/jacm/References/minoura1982:1023.html |
| M6 | F. Belik, "Deadlock avoidance with a modified banker's algorithm", BIT 27: 290–305, 1987. DOI 10.1007/BF01933724. 초록: 원래 알고리즘은 Θ(mn²), 변형은 "특정한 있을 법한 조건" 아래 상각 최악 O(mn)이다. "최대 두 배 빠름" 문장의 방향은 열람 도구 요약 둘이 갈려 확정하지 못했다(문서 04 §9). 본문은 읽지 못함 | B | https://unpaywall.org/10.1007%2FBF01933724 · https://link.springer.com/article/10.1007/BF01933724 (초록) |
| M7 | F. Belik, "A distributed deadlock avoidance technique", Distributed Algorithms (WDAG 1987), LNCS 312, 1988. DOI 10.1007/BFb0019801. 초록: 방향 비순환 그래프를 경로 행렬로 표현해 간선 삽입 시 순환을 효율적으로 탐지하고, 상각하면 연산당 선형 또는 상수 시간이라고 쓴다. 뱅커 알고리즘은 언급하지 않는다 | B | https://www.doi.org/10.1007/BFB0019801 |
| M8 | S. D. Lang, "An extended banker's algorithm for deadlock avoidance", IEEE TSE 25(3): 428–432, 1999 | B | https://stars.library.ucf.edu/scopus1990/4271 |
| M9 | M. Lawley, S. Reveliotis, "Deadlock avoidance for sequential resource allocation systems: hard and easy cases", Int. J. Flexible Manufacturing Systems 13: 385–404, 2001. DOI 10.1023/A:1012203214611 | B, A− | https://link.springer.com/article/10.1023/A:1012203214611 · https://www2.isye.gatech.edu/~spyros/publications/accept-SU-compl.pdf |
| M10 | S. Reveliotis, A. Nazeem, "Optimal linear separation of the safe and unsafe subspaces of sequential resource allocation systems as a set-covering problem: algorithmic procedures and geometric insights"(SICON 게재본으로 보이는 저자 사이트 PDF; 정식 서지 확인 필요) | B | https://www2.isye.gatech.edu/~spyros/publications/SICON-paper.pdf |
| M11 | J. Park, S. A. Reveliotis, "Deadlock avoidance in sequential resource allocation systems with multiple resource acquisitions and flexible routings"(저자 사이트 사본; 게재 서지 확인 필요) | B | https://www2.isye.gatech.edu/~spyros/publications/cor-TAC01.pdf |
| M12 | J. Ezpeleta, J. M. Colom, J. Martínez, "A Petri net based deadlock prevention policy for flexible manufacturing systems", IEEE Trans. Robotics and Automation 11(2): 173–184, 1995 | B | https://www.informatik.uni-hamburg.de/TGI/pnbib/e/ezpeleta_j7.html |
| M13 | Z. Li, M. Zhou, N. Wu, "A survey and comparison of Petri net-based deadlock prevention policies for flexible manufacturing systems", IEEE Trans. SMC-C 38(2): 173–188, 2008. DOI 10.1109/TSMCC.2007.913920 | B | https://digitalcommons.njit.edu/fac_pubs/12869 |
| M14 | E. Knapp, "Deadlock detection in distributed databases", ACM Computing Surveys 19(4): 303–328, 1987. DOI 10.1145/45075.46163. §2.2~2.5의 모델별(AND, OR, AND-OR, k-of-n) 서술을 확인했다(열람 도구의 요약을 거침) | B, A− | https://ics.uci.edu/~cs223/papers/p303-knapp.pdf |
| M15 | M. Singhal, "Deadlock detection in distributed systems", IEEE Computer 22(11), 1989 | B, A− | https://www.ics.uci.edu/~cs237/reading/files/Deadlock%20Detection%20in%20Distributed%20systems.pdf |
| M16 | G. Bracha, S. Toueg, "Distributed deadlock detection", Distributed Computing 2(3): 127–138, 1987; PODC 1984: 285–301 | B | https://dblp.dagstuhl.de/pid/54/4334.html |
| M17 | S. Srinivasan, R. Rajaram, "Message-optimal algorithm for detection and resolution of generalized deadlocks in distributed systems", Informatica 35: 489–498, 2011 | A− | https://www.dlib.si/stream/URN:NBN:SI:DOC-VZOW2GMK/5bc8388d-58ca-408d-aa94-604529e3d696/TEXT |
| M18 | Y. C. Tay, W. T. Loke, "On deadlocks of exclusive AND-requests for resources", Distributed Computing 9: 77–94, 1995. DOI 10.1007/s004460050011 | B | https://link.springer.com/article/10.1007/s004460050011 |
| M19 | H. Wu, W.-N. Chin, J. Jaffar, "An efficient distributed deadlock avoidance algorithm for the AND model", IEEE TSE 28(1): 18–29, 2002. DOI 10.1109/32.979987 | B | https://ftp.math.utah.edu/pub/tex/bib/idx/ieeetranssoftweng2000/28/1/18_29.html |
| M20 | D. Hauschildt, R. Valk, "Safe states in Banker like resource allocation problems", Advances in Petri Nets 1985, LNCS 222, 1986. DOI 10.1007/BFb0016216 | B | https://link.springer.com/chapter/10.1007/BFb0016216 |
| M21 | 김태영, 박동원, "Deadlock 회피책에 대한 개선방안 연구", 공학논문집 1(1): 49–57, 1997 | B | https://koreascience.kr/article/JAKO199741548012786.pub?lang=en |
| M22 | "Analysis of Deadlock Avoidance Schemes and Resource Utilization for Non-Preemptible Resources", 기술 보고서 ADA021732 (페이지에 저자·날짜가 없다. 저자·연도 후보는 H.-C. Chang, CMU 박사논문 1975(M30)이며 동일성은 제목 유사성뿐이다, C). 초록: 회피 알고리즘의 계산 오버헤드와 자원 이용률을 다루며, 계산 트리로 안전성 검사 비용의 하한을 유도하고 상한도 제시. 하한의 수치는 읽지 못함 | B | https://apps.dtic.mil/sti/html/tr/ADA021732/index.html |
| M23 | P. Bak, "A fast method of deadlock avoidance", RAIRO Informatique théorique 18(1): 71–80, 1984 | A− | https://www.numdam.org/item/ITA_1984__18_1_71_0/ · PDF: https://www.numdam.org/item/ITA_1984__18_1_71_0.pdf (OCR 손상으로 수식 일부 판독 불가) |
| M24 | "Game interpretation of the deadlock avoidance problem", CACM, 1977-10(URL 경로 기준; 저자·쪽수 X). 회피를 운영체제와 프로세스 사이의 게임으로 정식화하고 이분 그래프로 안전 상태 집합을 구성 | B | https://cacmb4.acm.org/magazines/1977/10/11294-game-interpretation-of-the-deadlock-avoidance-problem |
| M25 | Hee Chul Shin, Jin Young Choi, "Simulation-based Design and Performance Analysis of Two Phase Banker's Algorithm for Efficient Operation of Capacitated Automated Production Systems", Journal of the Korea Society for Simulation 21(4): 1–9, 2012. DOI 10.9709/JKSS.2012.21.4.001 | B | https://koreascience.or.kr/article/JAKO201205740752845.page |
| M26 | 이원섭, "분산 데이터베이스 시스템에서의 교착상태 탐지기법", 한국컴퓨터정보학회논문지 6(2): 34–40, 2001 | B | https://koreascience.or.kr/article/JAKO200111921433528.page |
| M27 | Y. Li, "A Modified Banker's Algorithm", LNEE 152, Springer, pp. 277–281, 2013(온라인 2012-08-28). DOI 10.1007/978-1-4614-3535-8_23. 초록: 새 알고리즘의 시간 O(n²d²+ndM)(M은 총 자원 단위 수) 대 원래 알고리즘 O(n³d), 공간 O(nd²)로 원래보다 나쁨. 평가는 점근 분석 | B | https://link.springer.com/chapter/10.1007/978-1-4614-3535-8_23 |
| M28 | Y. Li, R. Cook, "A New Algorithm and Asymptotical Properties for the Deadlock Detection Problem for Computer Systems with Reusable Resource Types", Springer, 2007, pp. 509–512. DOI 10.1007/978-1-4020-6264-3_88. 초록: 재사용 자원 d종(d≪n)의 교착 탐지에서 그래프·트리 자료구조를 쓰지 않는 알고리즘을 제시하고, d와 요청이 상수로 한정되면 선형 시간이며 점근적으로 최적이라고 쓴다 | B | https://link.springer.com/chapter/10.1007/978-1-4020-6264-3_88 |
| M29 | P. Spirakis, "The parallel complexity of deadlock detection", MFCS 1986, LNCS 233. 조회 주소의 DOI는 10.1007/BFb0016285(페이지의 DOI 칸은 비어 있고 저자는 한 명만 표시). 초록: 다중 단위 재사용 자원의 일반 문제는 로그 공간 환원에서 P-완전, 요청이 단일 단위이거나 자원이 단일 단위이면 NC | B | https://unpaywall.org/10.1007%2FBFb0016285 |
| M30 | H.-C. Chang, CMU 박사논문 1975, "An Analysis of Deadlock Avoidance Schemes and the Resource Utilization For Non-pre-emptible Resources"(지도: A. N. Habermann). M22(DTIC ADA021732)와 같은 연구인지는 제목 유사성만으로 추정한다(C) | B | https://mathgenealogy.org/id.php?id=50241 |
| M31 | Tricas, Colom, Ezpeleta, "Some improvements to the Banker's algorithm based on the process structure", Proc. 2000 IEEE Int. Conf. on Robotics and Automation (ICRA). DOI 10.1109/robot.2000.846460. Crossref가 발행 연도를 비워 두어 2000은 회의록 제목에서 읽었다. 내용 미열람 | B(서지) | Crossref 조회(제목·DOI) |
| M32 | Zarnay, Garcia, "Enhancing banker's algorithm for avoiding deadlocks in systems with non-sequential processes", Proc. 2014 IEEE Emerging Technology and Factory Automation (ETFA). DOI 10.1109/etfa.2014.7005149. 내용 미열람 | B(서지) | Crossref 조회(제목·DOI) |
| M33 | Ma, Yan, "An improved parallel banker's algorithm based on Petri net", Proc. 2011 Int. Conf. on Electronic & Mechanical Engineering and Information Technology (EMEIT). DOI 10.1109/emeit.2011.6023388. 내용 미열람 | B(서지) | Crossref 조회(제목·DOI) |
| M34 | Song, Li, Song, "Modified Banker's algorithm with dynamically release resources", 2021 Int. Conf. on Communications, Information System and Computer Engineering (CISCE). DOI 10.1109/cisce52179.2021.9445935. 내용 미열람(IEEE Xplore 페이지는 빈 응답) | B(서지) | Crossref 조회(제목·DOI) |
| M35 | Jiang, "Process Security Sequence Improvement Algorithm Based on Banker Algorithm", J. Phys.: Conf. Ser. 1237(2): 022111, 2019. DOI 10.1088/1742-6596/1237/2/022111. 내용 미열람(게재처 페이지는 robots_disallowed) | B(서지) | Crossref 조회(제목·DOI) |
| M36 | D. A. Hensgen, D. L. Sims, D. Charley, "A fair Banker's Algorithm for read and write locks", Information Processing Letters 48(3): 131–137, 1993. DOI 10.1016/0020-0190(93)90255-8. Crossref에 초록 없음 | B(서지) | https://api.crossref.org/works/10.1016/0020-0190(93)90255-8 |
| M37 | D. B. Lomet, "A practical deadlock avoidance algorithm for data base systems", ACM SIGMOD Int. Conf. on Management of Data, 1977 | B | https://research.ibm.com/publications/a-practical-deadlock-avoidance-algorithm-for-data-base-systems |
| M38 | V. Kahlon, F. Ivančić, A. Gupta, "Reasoning about threads communicating via locks", Computer Aided Verification (CAV 2005), LNCS 3576, pp. 505–518, 2005. DOI 10.1007/11513988_49. 저자와 서지는 Princeton 기록 '-2', springerprofessional.de 페이지, arXiv:2307.04925의 참고문헌 항목 세 곳이 일치한다(문서 04 §10.3, 대장 C-SUR-079). 처음 열람한 Princeton 기록에는 저자가 없었다. 초록: 락 접근이 중첩 구조이면 효율적으로 결정 가능하고, 중첩이 아니면 스레드가 둘뿐이어도 도달 가능성이 결정 불가능 | B | https://collaborate.princeton.edu/en/publications/reasoning-about-threads-communicating-via-locks-2/ |
| M39 | K. Dixit, A. Khuteta, "A Dynamic and Improved Implementation of Banker's Algorithm", IJRITCC 5(8): 45–49, 2017 | B | https://www.academia.edu/36875137/A_Dynamic_and_Improved_Implementation_of_Banker_s_Algorithm |
| M40 | M. Gaur, D. Singh, "Implementation of Banker's Algorithm Using Dynamic Modified Approach", IJRITCC 5(11): 157–163, 2017 | B | https://www.academia.edu/36852573/Implementation_of_Banker_s_Algorithm_Using_Dynamic_Modified_Approach |
| M41 | H. R. Wicaksono 외, "Banker's Algorithm Optimization to Dynamically Avoid Deadlock in Operating System", JEEMECS 6(1), 2023 | A− | https://jurnal.unmer.ac.id/index.php/jeemecs/article/download/8986/pdf |
| M42 | "An Improved Safety Detection Algorithm Towards Deadlock Avoidance", 2020. 목록마다 서지가 다르다: 한 대학 연구자 페이지는 저자를 Bimal Chandra Das 한 명만 적고 2020 IEEE 10th Symposium on Computer Applications & Industrial Electronics (ISCAIE)로 표시하며 IEEE Xplore 9108818로 연결한다. 다른 목록은 저자를 Momotaz Begum, Omar Faruque, Md. Das로 적고 CNSA 2020으로 표시한다. 어느 쪽이 맞는지 확인하지 못했다 | B | https://research.daffodilvarsity.edu.bd/scopus-article/1230 · https://citation.thinkst.com/talk/75660 |
| M43 | K. Vayadande 외, "Survey Paper on Banker's Algorithm to Remove Deadlock"(Vishwakarma Institute of Technology, Pune. 연도·게재처 미표시, 가장 새로운 참고문헌은 2021). 서베이이므로 2차 자료이고 RQ6 후보에서 제외 | C | https://www.riverpublishers.com/pdf/ebook/chapter/RP_P9788770229852C23.pdf |
| M44 | 김종욱, 이종근, "패트리 넷에서의 교착 상태 확인 알고리즘 성능분석", 한국시뮬레이션학회 논문지 18(1): 9–16, 2009. 뱅커 알고리즘을 다루지 않음 | B | https://www.koreascience.kr/article/JAKO200924448123730.pdf |
| M45 | 이원섭, 이상희, "분산 데이터베이스 시스템에서의 교착상태 탐지기법의 성능평가", 한국컴퓨터정보학회논문지 8(3): 26–33, 2003. 뱅커 알고리즘을 다루지 않음 | B | https://koreascience.or.kr/article/JAKO200311922045289.pub |
| M46 | R. Agrawal, M. Carey, D. DeWitt, "Deadlock Detection is Cheap", UC Berkeley EECS 기술 보고서 UCB/ERL M83/5, 1983. 서지 페이지에 초록이 없고 PDF는 열람하지 않음 | B | https://www2.eecs.berkeley.edu/Pubs/TechRpts/1983/109.html |
| M47 | R. Agrawal, M. J. Carey, L. W. McVoy, "The Performance of Alternative Strategies for Dealing with Deadlocks in Database Management Systems", Univ. of Wisconsin–Madison 기술 보고서 TR590, 1985. 저자 표기는 페이지 본문이 세 명이고 인용 메타데이터는 McVoy만 적는다. 초록 칸이 비었고 PDF는 이진 데이터로 받아 읽지 못함 | B | https://minds.wisc.edu/items/2b72db1d-d09f-47e9-a431-6020ff0202b4 |
| M48 | F. Belik, "An efficient deadlock avoidance technique", IEEE Transactions on Computers 39(7): 882–888, 1990. DOI 10.1109/12.55690. 초록(OpenAlex, 역색인에서 재구성): 시간에 따라 바뀌되 비순환을 유지하는 방향 비순환 그래프로 시스템을 표현하는 회피 기법이며 자원 종류마다 인스턴스가 하나인 시스템에 적용된다. 경로 행렬로 순환을 효율적으로 탐지하고 그 비용을 다른 할당 연산에 상각해 밀집 시스템에서 연산당 선형 또는 상수 상각 시간을 얻는다고 쓴다. 본문은 읽지 못함. G2의 [Belik1990]이 이 논문이라는 것은 저자·연도 일치에 의한 추정(C) | B | https://api.openalex.org/works/doi:10.1109/12.55690 |
| M49 | R. A. Finkel, H. Madduri, "An efficient deadlock avoidance algorithm", Information Processing Letters 24(1): 25–30, 1987. DOI 10.1016/0020-0190(87)90195-5. 서지만 확인(Crossref, OpenAlex 모두 초록 없음). 내용을 몰라 뱅커 알고리즘 관련인지 알 수 없다 | B(서지) | https://api.openalex.org/works/doi:10.1016/0020-0190(87)90195-5 |

### 7.3 시스템·실무 (S)

| ID | 서지 | 수준 | URL |
|---|---|---|---|
| S1 | Linux kernel documentation, "Runtime locking correctness validator" (lockdep 설계; I. Molnar, A. van de Ven) | A | https://docs.kernel.org/locking/lockdep-design.html |
| S2 | Linux kernel documentation, "Wound/Wait Deadlock-Proof Mutex Design" | A− | https://docs.kernel.org/5.3/locking/ww-mutex-design.html |
| S3 | T. Hellstrom, "[PATCH v4 2/3] locking: Implement an algorithm choice for Wound-Wait mutexes", LKML, 2018-06 | A− | https://lkml.iu.edu/hypermail/linux/kernel/1806.2/02158.html |
| S4 | L. Sha, R. Rajkumar, J. P. Lehoczky, "Priority inheritance protocols: an approach to real-time synchronization", IEEE Trans. Computers 39(9): 1175–1185, 1990 | A− | https://www.math.unipd.it/~tullio/RTS/2009/SRL-1990.pdf · https://researcher.ibm.com/publications/priority-inheritance-protocols-an-approach-to-real-time-synchronization |
| S5 | Y. Wang, T. Kelly, M. Kudlur, S. Lafortune, S. Mahlke, "Gadara: Dynamic Deadlock Avoidance for Multithreaded Programs", OSDI 2008 | A− | https://static.usenix.org/events/osdi08/tech/full_papers/wang/wang_html/index.html |
| S6 | H. Jula, D. Tralamazza, C. Zamfir, G. Candea, "Deadlock Immunity: Enabling Systems To Defend Against Deadlocks", OSDI 2008 | A− | https://www.usenix.org/conference/osdi-08/deadlock-immunity-enabling-systems-defend-against-deadlocks |
| S7 | E. Koskinen, M. Herlihy, "Dreadlocks: efficient deadlock detection", SPAA 2008, pp. 297–303. DOI 10.1145/1378533.1378585 | B | https://unpaywall.org/10.1145%2F1378533.1378585 |
| S8 | R. Agarwal, S. Bensalem, E. Farchi, K. Havelund, Y. Nir-Buchbinder, S. D. Stoller, S. Ur, "Detection of deadlock potentials in multithreaded programs", IBM J. Res. Dev., 2010-09. DOI 10.1147/JRD.2010.2060276 | B | https://www3.cs.stonybrook.edu/~stoller/deadlocks-IBM.html |
| S9 | H. C. Tunç, U. Mathur, A. Pavlogiannis, M. Viswanathan, "Sound Dynamic Deadlock Prediction in Linear Time", PLDI 2023 (PACMPL 7, Art. 177). DOI 10.1145/3591291 | A− | https://arxiv.org/pdf/2304.03692 |
| S10 | D. J. Pearce, "Dynamic Cycle Detection for Lock Ordering"(블로그), 2020-12-19 | C | https://whileydave.com/2020/12/19/dynamic-cycle-detection-for-lock-ordering/ |
| S11 | J. J. Lee, V. J. Mooney III, "A novel O(n) parallel banker's algorithm for System-on-a-Chip", IEEE TPDS 17(12): 1377–1389, 2006. 같은 제목의 저자 사이트 PDF(S19)와 Lee의 학위논문 초록(S20)을 따로 확인했다. 이들과 TPDS판이 같은 실험의 다른 판인지는 미확인 | B (S19: A−, S20: B) | https://www.bibsonomy.org/bibtex/34935013956038fde4e0103afb163781?lang=de |
| S12 | X. Xiao, 박사학위 논문(Purdue), "Hardware-oriented parallel deadlock detection algorithms with reduced run-time complexity"; X. Xiao, J. J. Lee, IEEE TPDS 21(1): 4–19, 2010 | B, D | https://docs.lib.purdue.edu/dissertations/AAI10161392 |
| S13 | M. F. Zohora, F. Farhin, M. S. Kaiser, "DBDAA: A real-time approach to Dynamic Banker's Deadlock Avoidance Algorithm with optimized time complexity", PLOS ONE, 2024-09-20. DOI 10.1371/journal.pone.0310807 (복잡도 주장은 검증 대상). PLOS 본문 페이지를 열람해 평가가 비교 횟수 기준임을 확인했다. 그 비교 횟수가 스칼라 비교인지 벡터 비교인지는 열람한 본문에서 불분명하다(문서 04 §2.2) | B, A− | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11414889/ · https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0310807 |
| S14 | D. J. Rosenkrantz, R. E. Stearns, P. M. Lewis, "System level concurrency control for distributed database systems", ACM TODS 3(2): 178–198, 1978. wait-die/wound-wait를 이 논문에 귀속하는 근거는 S16과 S17의 인용뿐이다(D). 아래 URL은 같은 제목의 2009년 Springer 재수록 장이며 쪽 설명에는 wait-die/wound-wait 언급이 없다 | B, D | https://www.doi.org/10.1007/978-1-4020-9688-4_4 |
| S15 | M. J. Carey, M. Livny, "Distributed concurrency control performance: a study of algorithms, distribution, and replication", VLDB 1988 | B | https://vldb.org/dblp/db/conf/vldb/CareyL88.html |
| S16 | "Releasing Locks As Early As You Can: Reducing Contention of Hotspots by Violating Two-Phase Locking (Extended Version)", arXiv:2103.09906 (wound-wait 사용 사례 서술; wait-die/wound-wait의 출처로 Rosenkrantz 외 1978과 Bernstein·Goodman 1981을 인용) | C | https://arxiv.org/pdf/2103.09906 |
| S17 | J. C. Corbett 외, "Spanner: Google's Globally-Distributed Database", OSDI 2012. §4.2.1이 읽기-쓰기 트랜잭션의 읽기에 wound-wait를 쓴다고 서술하고 Rosenkrantz 외(1978)를 인용 | A− | https://www.cs.princeton.edu/courses/archive/fall15/cos518/papers/spanner.pdf (강의 사본) |
| S18 | R. O. Fontao, "A Concurrent Algorithm for Avoiding Deadlocks in Multiprocess Multiple Resource Systems" (스탠퍼드 디지털 시스템 연구실 방문연구원. 열람한 사본에는 연도·게재처가 없고 1971년 1월자 문헌까지 인용하며 Holt의 effective deadlock 개념을 쓴다. Crossref 서지에는 Proceedings of the third symposium on Operating systems principles, SOSP '71(1971)로 등록되어 있다. DOI 10.1145/800212.806502) | B | https://static.aminer.org/pdf/20170130/pdfs/sosp/zltf0mynekqcpcz6asxn3rfwjghuq28o.pdf |
| S19 | J. J. Lee, V. J. Mooney III, "A Novel O(n) Parallel Banker's Algorithm for System-on-a-Chip"(저자 사이트 PDF. 파일명이 aspdac_2005이고 본문에는 게재처 표기가 없다). 하드웨어 장치의 비용과 평가 설정은 문서 04 §3의 하드웨어 뱅커 행. 소프트웨어 기준 구현은 기술되지 않음 | A− | https://users.ece.gatech.edu/mooney/codesign/publications/jaehwan/paper/aspdac_2005.pdf |
| S20 | J. J. Lee, 조지아공대 학위논문(2004-11-23), "Hardware/Software Deadlock Avoidance for Multiprocessor Multiresource System-on-a-Chip". 초록만 확인 | B | https://repository.gatech.edu/entities/publication/91b62fea-6d75-44b3-a69b-124b6a18cb6d |
| S21 | S. W. Abell, 퍼듀대 석사논문(2013), "Parallel acceleration of deadlock detection and avoidance algorithms on GPUs". 초록만 확인 | B | https://docs.lib.purdue.edu/dissertations/AAI1549534 |
| S22 | Rust 표준 라이브러리 문서, `std::sync::Mutex`. 이미 쥔 뮤텍스를 다시 잠글 때의 동작은 규정하지 않는다(패닉하거나 교착할 수 있음) | A− | https://doc.rust-lang.org/std/sync/struct.Mutex.html |
| S23 | The Open Group, POSIX `pthread_mutex_lock`. 뮤텍스 타입별 재잠금 계약: NORMAL은 교착, ERRORCHECK는 `EDEADLK` 오류 반환, RECURSIVE는 횟수 증가, DEFAULT는 미정의. 교착 탐지는 선택 사항 | A− | https://pubs.opengroup.org/onlinepubs/9699919799/functions/pthread_mutex_lock.html |
| S24 | Oracle, Java SE 21 `java.lang.management.ThreadMXBean`. `findDeadlockedThreads`와 `findMonitorDeadlockedThreads`는 진단용이며 비쌀 수 있다고 문서가 경고 | A− | https://docs.oracle.com/en/java/javase/21/docs/api/java.management/java/lang/management/ThreadMXBean.html |
| S25 | parking_lot 크레이트 문서, `deadlock` 모듈. 교착 탐지는 선택적·실험적 기능 | A− | https://docs.rs/parking_lot/latest/parking_lot/deadlock/index.html |
| S26 | Linux kernel documentation, "Mutex design". 재귀 잠금을 불허하며 `CONFIG_DEBUG_MUTEXES`가 자기 재귀와 다중 태스크 순환을 탐지 | A− | https://docs.kernel.org/locking/mutex-design.html |

### 7.4 실증 (E)

| ID | 서지 | 수준 | URL |
|---|---|---|---|
| E1 | S. Lu, S. Park, E. Seo, Y. Zhou, "Learning from mistakes: a comprehensive study on real world concurrency bug characteristics", ASPLOS XIII, pp. 329–339, 2008. DOI 10.1145/1353534.1346323 | A | https://www.cs.columbia.edu/~junfeng/08fa-e6998/sched/readings/concurrency-bugs.pdf |
| E2 | S. Gong, C.-E. Lin, K. Wu, E. Lu, P. Fonseca, "A Comprehensive Study of Concurrency Bugs in the Linux Kernel", ICSE 2026. DOI 10.1145/3744916.3787790 (공개 데이터셋 주소는 논문 기재: https://github.com/rssys/kernel-concurrency-bug-study, 미접속) | A | https://cs.purdue.edu/homes/lin1963/publications/icse26_kernel_concurrency_bug_study.pdf |
| E3 | "Fearless Concurrency? Understanding Concurrent Programming Safety in Real-World Rust Software", arXiv:1902.01906. 교착 10건 중 7건이 이중 락이다(§4.2, 표 4의 Mutex 열. 본문이 이를 이중 락이라 부른다). 표본은 Servo, TiKV, Rand 세 응용 | A− | https://arxiv.org/pdf/1902.01906 |
| E4 | B. Qin 외, "Understanding and Detecting Real-World Safety Issues in Rust"(본문이 학회 논문의 확장판이라고 밝히지만 어느 논문인지는 확인하지 않았다. 열람한 텍스트에 게재처·연도가 없고 가장 새로운 자료는 2019년 6월). 블로킹 버그 59건 중 Mutex/RwLock 관련 38건이고 그중 이중 락 30건, 잠금 순서 충돌 7건(§5.1, 표 3) | A− | https://par.nsf.gov/servlets/purl/10509785 |
| E5 | T. Tu, X. Liu, L. Song, Y. Zhang, "Understanding Real-World Concurrency Bugs in Go", ASPLOS'19(2019-04-13~17, Providence). 응용 6개에서 동시성 버그 171건(블로킹 85건, 비블로킹 86건). 블로킹 85건 중 Mutex 28, RWMutex 5(Table 6). 이중 락 등 유형별 건수는 본문에 없다. Go 내장 교착 탐지기는 재현한 블로킹 버그 21건 중 2건을 탐지(Table 8). 처음에는 블로그 요약(https://blog.acolyer.org/2019/05/17/understanding-real-world-concurrency-bugs-in-go/, C)으로만 확인했고 2026-10-31에 본문을 읽었다(열람 도구 요약 경유. §5.2 텍스트와 Table 7이 맞지 않는다는 도구 보고가 있어 수정 방식 건수는 쓰지 않음) | A− | https://songlh.github.io/paper/go-study.pdf |

### 7.5 알고리즘 도구 (G)

| ID | 서지 | 수준 | URL |
|---|---|---|---|
| G1 | M. A. Bender, J. T. Fineman, S. Gilbert, R. E. Tarjan, "A new approach to incremental cycle detection and related problems", arXiv:1112.0784 (저널판 서지 X) | A− | https://arxiv.org/abs/1112.0784 |
| G2 | B. Haeupler, T. Kavitha, R. Mathew, S. Sen, R. E. Tarjan, "Incremental cycle detection, topological ordering, and strong component maintenance", ACM Trans. Algorithms (사전 인쇄본, arXiv:1105.2397). 서론 §1이 증분 순환 탐지가 교착 탐지에서 나타난다고 [Belik 1990]을 인용한다. 그 참고문헌 항목은 열람한 텍스트에 없다(D). 후보 서지는 M48(저자·연도 일치에 의한 추정) | A− | https://arxiv.org/pdf/1105.2397 |
| G3 | D. J. Pearce, P. H. J. Kelly, "A dynamic topological sort algorithm for directed acyclic graphs", ACM J. Exp. Algorithmics 11, Art. 1.7, 2006(저자 페이지는 2007로 표기) | B | https://whileydave.com/publications/pk07_jea/ |
| G4 | E. Cohen, A. Fiat, H. Kaplan, L. Roditty, "A labeling approach to incremental cycle detection", arXiv:1310.8381 | B | https://arxiv.org/pdf/1310.8381 |

### 7.6 교과서·강의자료 (T) 및 인접 분야 (V)

| ID | 서지 | 수준 | URL |
|---|---|---|---|
| T1 | A. Silberschatz, P. B. Galvin, G. Gagne, Operating System Concepts, Ch. 7 Deadlocks (사본·서지 노트; 판본 X) | C, B | https://elearn.daffodilvarsity.edu.bd/mod/resource/view.php?id=655597 · https://os-book.com/OS9/bib-dir/7.pdf |
| T2 | A. S. Tanenbaum, Modern Operating Systems 발췌, §3.2 (InformIT) | B | https://www.informit.com/articles/article.aspx?p=25193 |
| T3 | R. Arpaci-Dusseau, A. Arpaci-Dusseau, OSTEP 32장 "Common Concurrency Problems"(강의 슬라이드로 확인; 원문 PDF는 미열람) | C | https://pages.cs.wisc.edu/~remzi/OSTEP/Educators-Slides/Youjip/Part2.Concurrency/pdf/32.Common_Concurrency_Problems.pdf |
| T4 | UIUC CS 341 코스북 "Deadlock" | C | https://cs341.cs.illinois.edu/coursebook/Deadlock |
| T5 | 버지니아대 강의 노트 "deadlock" | C | https://www.cs.virginia.edu/~cr4bd/3130/F2023/readings/deadlock.html |
| T6 | 일반 자원 그래프 강의 노트: FSU COP5611, UTD CS6378, CSUSB CS461, UCSD CSE120, UMBC CMSC621 | C | https://www.cs.fsu.edu/~xyuan/cop5611/lecture9.html · https://personal.utdallas.edu/~ravip/cs6378/slides/node3.html · http://web.cse.csusb.edu/tongyu/courses/cs461/notes/deadlock.php · https://cseweb.ucsd.edu/classes/sp02/cse120_B/deadlock.pdf · https://courses.cs.umbc.edu/graduate/621/fall02/lectures/ch3.pdf |
| T7 | 켄트주립대 강의 노트 "Necessary and Sufficient Deadlock Conditions" | C | https://www.personal.kent.edu/~rmuhamma/OpSystems/Myos/deadlockCondition.htm |
| T8 | 미국 특허 US 5784556(URL 기준)의 코프만 인용 서술 | C | https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/5784556 |
| T9 | 교재 발췌(제3장 교착상태 §3.2, 163–165쪽으로 보이는 사본. 저자·제목·판본 미표시). 네 조건과 정책의 대응을 서술하고 코프만(1971)과 홀트(1972)를 인용 | C | https://www.tud.ttu.ee/im/Vladimir.Viies/materials/YLDINEkaust/OS-systeemid/loengumat/KIRJANDUS_INGL/TUPIKUD.pdf |
| V1 | "Connectivity Graphs: A Method for Proving Deadlock Freedom Based on Separation Logic", POPL 2022. DOI 10.1145/3498662 (인접 분야: 세션 타입의 교착 자유성을 Coq로 기계화; 저자 X) | B | https://dl.acm.org/doi/pdf/10.1145/3498662 |
| V2 | X. Zhang, C. Urban, C. Wu, "Priority Inheritance Protocol Proved Correct" (Isabelle/HOL 형식화. 열람한 LaTeX 원고에서 제목·저자·초록만 확인했고 게재처·연도는 X. RAG·순환·교착에 관한 정리는 확인하지 못함) | B | https://cflmark.nms.kcl.ac.uk/hg/pip/file/tip/Paper/document/root.tex |
| V3 | 제목만 확인한 인접 단서(내용 미열람): "Correct Black-Box Monitors for Distributed Deadlock Detection: Formalisation and Implementation (Technical Report)", arXiv:2508.14851 · "Constraint-Based Deadlock Checking of High-Level Specifications", arXiv:1109.2015 · "Efficiently verifiable conditions for deadlock-freedom of large concurrent programs"(저자·연도 X) | D | https://arxiv.org/pdf/2508.14851 · https://arxiv.org/pdf/1109.2015 · https://ubmr.hds.hebis.de/EdsRecord/edscal%252Cedscal.16546768 |

---

## 8. 저장소 구성 제안 (이름 확정 후 반영)

```
<repo>/
├─ docs/          # 이 문서, 모델 매트릭스, 비용표, 게이트 판정표
├─ refs/          # references.bib, claims-ledger.md
├─ formal/        # 기계 검증(RQ1)
├─ experiments/   # 시뮬레이터·트레이스·벤치마크(RQ3, RQ6)
└─ README.md
```

---

## 9. 변경 이력

| 버전 | 일자 | 내용 |
|---|---|---|
| v0.1 | 2026-10-29 | 최초 작성 |
| v0.2 | 2026-10-29 | 문서 03(G1)의 정정·갱신 반영: M15 서술 정정, E2 해석 보완(스레드 수 계수 규칙, '인터럽트 의존' 열 정의), F7·S17 근거 수준 상향, M20 저자 확인, S14 URL 성격 명시, 문헌 M23–M26·S17–S18·T9·V2–V3 추가 |
| v0.3 | 2026-10-30 | 문서 04(Phase 3)의 정정 목록 반영(문서 04 §9의 1~6): §1.2의 AND 행을 Knapp §2.2·SM T2·반례 B4에 맞춰 고치고 OR와 AND-OR/P-out-of-Q를 두 행으로 나눔, §1.3의 뱅커 행에 표기 불일치(M27)를, 뱅커 개선 주장 행에 M6의 조건부 상각 O(mn)·S13의 평가 방식·M27·M39·M40을, 그래프 기반 회피 행에 M7의 초록 내용을 반영, §3 판정표를 문서 04 §8의 판정으로 갱신(락 프로그램 정적 분석 행 추가), §4.0의 RQ2 중복 위험을 높음으로 올리고 §4.1에 Phase 3 결과 요약 추가, §6.2 신설. §7: M6, M7, M14, M22, S11, S13, S18, G2 보강, 새 문헌 M27–M47·S19–S26·E3–E5 추가. M38 저자는 확인하지 못해 적지 않음. 문서 04 §9 정정 7·8(문서 02)은 문서 02 v0.3에서 처리 |
| v0.3.1 | 2026-10-31 | 문서 04 §10.3의 사후 확인 반영: M38의 저자·서지 확정(Kahlon, Ivančić, Gupta, CAV 2005)을 §3, §6.2, §7.2에, E5(Go 연구)의 본문 열람 결과(근거 수준 C에서 A−로. 블로킹 85건 중 Mutex 28, RWMutex 5. 이중 락 건수 없음)를 §6.2, §7.4에 반영. v0.3 행의 'M38 저자는 확인하지 못해 적지 않음'은 당시 상태의 기록이라 그대로 둔다. 같은 날 Belik 1990의 서지를 Crossref에서 찾아 M48(Belik 1990), M49(Finkel·Madduri 1987)를 §7.2에 추가하고 G2의 Belik 1990 인용에 후보 서지로 연결(§3, §6.2, §7.5) |
