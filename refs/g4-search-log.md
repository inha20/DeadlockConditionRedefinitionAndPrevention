# G4 검색 기록 (Phase 4)

- 문서 05(`docs/05-phase4-gate-decisions.md`)의 판정이 근거로 삼는 검색·열람 호출의 목록이다. 날짜는 모두 2026-10-31(KST)이다.
- 경로 분류: 키워드(K), 인용 추적(C), 인접 분야(A), 직접 열람(R, 후보의 본문·문서를 읽은 호출).
- 열람 도구는 본문을 요약해 돌려주므로 R 호출로 얻은 수치와 문장은 A−다. 도구가 읽지 못한 것(이진 데이터, 오류)도 적는다.
- 이 표의 '결과'는 이번 호출에서 본 것만 적었다. 못 찾았다는 것은 부재 증명이 아니다.
- 환경 한계: 작업공간 셸은 외부 학술 API에 닿지 않는다(프록시가 api.openalex.org를 거부했다). OpenAlex의 단건 조회(`works/doi:…`)는 열람 도구로 되지만 목록 질의(`filter=`, `search=`)는 5회 모두 client_error였다. Semantic Scholar의 단건·인용 조회는 되고 검색 질의는 client_error였다. Crossref는 `query.bibliographic`이 되고 `filter=`가 붙은 질의는 client_error였다. DBLP는 robots_disallowed였다. 거부된 경로를 우회하지 않았다.

| 코드 | 경로 | 도구 | 질의 또는 주소 | 결과 | RQ |
|---|---|---|---|---|---|
| G4-001 | K | WebSearch | dynamic cycle detection lock ordering deadlock prevention incremental topological order lock graph runtime | 10건. 미국 특허 6009269(이진 데이터라 열람 못함), G2(arXiv 1105.2397)와 사본, S10, S8(Stoller 사본 PDF), Berkeley DB 문서, 무관한 페이지(tessl.io 3건) | RQ4 |
| G4-002 | C | WebFetch | OpenAlex `works/doi:10.1109/12.55690` | Belik 1990의 OpenAlex ID W2154203836, 인용 52회. 참고문헌 목록에 자기 ID가 들어 있어(W2154203836) 이 목록은 쓰지 않는다 | RQ4 |
| G4-003 | R | WebFetch | raw.githubusercontent.com/abseil/abseil-cpp/master/absl/synchronization/internal/graphcycles.h | 간선 삽입 시 순환이면 거부하고 그래프를 바꾸지 않는 증분 그래프. 알고리즘 이름·인용·용도는 이 헤더에 없다. 성능 서술은 희소 그래프에 적합, InsertEdge는 이미 있는 간선이면 매우 빠름, FindPath는 그래프 크기에 선형, 공간 O(V+E) | RQ4 |
| G4-004 | R | WebFetch | docs.rs/tracing-mutex/latest/tracing_mutex/ | 마지막으로 쥔 락에서 새로 얻는 락으로 의존을 기록하고 Pearce–Kelly로 순환을 탐지하며 순환이면 패닉(충돌하는 의존은 그래프에 추가하지 않음). stdsync 별칭은 디버그 단언이 켜졌을 때만 추적형. 백트레이스 수집이 기본으로 켜져 60% 넘는 오버헤드 | RQ4 |
| G4-005 | C | WebFetch | OpenAlex `works?filter=cites:W2154203836…` 세 형태(select·per-page 포함, 콜론 인코딩, 최소형) | 세 번 모두 client_error. 인용 목록은 얻지 못함 | RQ4 |
| G4-006 | R | WebFetch | raw.githubusercontent.com/llvm/llvm-project/main/compiler-rt/lib/sanitizer_common/sanitizer_deadlock_detector.h | 락 순서 그래프(노드는 락). 획득 전에 보유 락이 도달 가능한지 검사. 비트벡터 그래프. 동시에 살아 있는 락 수가 고정이고 한계에 닿으면 그래프를 비우고 새 세대 시작. 스레드별 보유 락 512, 재귀 64, 이벤트당 새 간선 40. 위상 순서 언급 없음. 머리말에 "아직 제대로 동작하지 않는다"는 취지의 주석 | RQ4 |
| G4-007 | R | WebFetch | docs.kernel.org/locking/lockdep-design.html | 서로 다른 락 체인은 처음 볼 때 한 번만 검증하고 64비트 체인 해시를 해시 표에 저장. 캐시 없이 모든 이벤트를 검사하면 O(N²)로 "사실상 쓸 수 없을 만큼 느리다"고 서술. 락 클래스 상한 MAX_LOCKDEP_KEYS 기본 8191. irq 사용 상태 규칙. 상시/디버그 용도는 명시 안 함(디버깅·QA 어조) | RQ4, RQ5 |
| G4-008 | K | WebSearch | lock order inversion detection production always-on low overhead lock hierarchy runtime enforcement library | 10건. Fuchsia lockdep 문서 사본 다수, 무관 페이지(tessl.io), 블로그 1건 | RQ4 |
| G4-009 | C | WebFetch | Semantic Scholar `paper/DOI:10.1109/12.55690/citations` (limit 100) | 56건(일부 중복). 증분 위상 순서·순환 탐지(Bender 외 2008·2009, G2, ESA 2021 등), 하드웨어 뱅커·회피(Lee·Mooney 계열 5건), Petri 넷·FMS·AGV 교착 회피, 런타임 검증(RV 2008 두 편, TOPLAS 2018 Armus). 제목에 락 순서 검사를 내세운 항목은 없음 | RQ4, RQ6 |
| G4-010 | R | WebFetch | fuchsia.dev/fuchsia-src/concepts/kernel/lockdep-design | 락 클래스 단위, 새 간선이 추가될 때 Tarjan SCC로 순환 탐지(최악 간선+정점), 같은 클래스는 주소 순서, 위상 순서 유지는 없음. 빌드 구성(상시/디버그)은 명시 안 함. 여러 구현 항목이 TODO | RQ4 |
| G4-011 | C | WebFetch | Semantic Scholar `paper/DOI:10.1145/1187436.1210590/citations` (limit 100) | 처음 100건 중 제목에 lock·deadlock·thread·concurren·synchroniz가 든 것은 4건이고 락 순서 교착과 관련된 것은 없음(PLDI 2021 순서 일관성 이론 논문 1건이 가장 가까움). 다음 쪽(offset 100)이 있었으나 읽지 않음 | RQ4 |
| G4-012 | K | WebFetch | Semantic Scholar `paper/search?query=lock+order+graph…` | client_error | RQ4 |
| G4-013 | R | WebFetch | image-ppubs.uspto.gov … downloadPdf/6009269 | 이진 데이터라 열람 못함 | RQ4 |
| G4-014 | R | WebFetch | raw.githubusercontent.com/abseil/abseil-cpp/master/absl/synchronization/mutex.h | 교착 탐지는 디버그 빌드에서만, 전역으로 켜졌을 때(kIgnore가 아닐 때)만 acquired-before 그래프를 추적. 기본 모드는 헤더에 없음. 자료구조·비용 수치 없음 | RQ4 |
| G4-015 | R | WebFetch | github.com/bertptrs/tracing-mutex | 순서를 기록해 의존 그래프를 만들고 순환이 생기면 즉시 패닉. 디버그 전용 옵션 있음. 벤치마크 수치 없음(benches 디렉터리는 있으나 열람 안 함). 향후 과제에 락 추적 성능 개선 | RQ4 |
| G4-016 | K | WebSearch | overhead of lock order graph deadlock detection release build benchmark mutex wrapper measured slowdown lock-order checking production | 10건. bcc deadlock 도구 문서·커밋, 미국 특허 10915424(이진), S8 사본, 무관 페이지 | RQ4 |
| G4-017 | R | WebFetch | mankier.com/8/bcc-deadlock | uprobes로 pthread_mutex_lock/unlock을 가로채 뮤텍스 그래프를 만들고 순환이면 락 순서 역전을 보고하고 종료. 실행 중 프로세스에 부착 가능. 모든 락·언락을 추적해 오버헤드가 높을 수 있다고 경고. 잠재 교착만 탐지, 공유·재귀 뮤텍스 미지원, 불안정 표시 | RQ4 |
| G4-018 | R | WebFetch | image-ppubs.uspto.gov … downloadPdf/10915424 | 이진 데이터라 열람 못함 | RQ4 |
| G4-019 | K | WebFetch | OpenAlex `works?search=lock order graph topological deadlock…` 두 형태 | 둘 다 client_error | RQ4 |
| G4-020 | A | WebFetch | Semantic Scholar `paper/DOI:10.1145/3229060` | Armus(Cogumbreiro 외, TOPLAS 2018) 초록: 배리어 동기화 교착의 동적 탐지 또는 회피, WFG와 SG 사이 그래프 선택, Coq로 기계 검증, 탐지는 오버헤드가 낮고 회피는 더 비쌈 | RQ4, RQ1 |
| G4-021 | K | WebSearch | runtime deadlock avoidance lock acquisition graph reject cycle-closing lock request fall back trylock instead of detect after the fact threads | 7건 모두 Berkeley DB 참조 가이드 사본 또는 강의 슬라이드. 새 후보 없음 | RQ4 |
| G4-022 | K | WebFetch | Crossref `query.bibliographic=lock order graph incremental topological order deadlock prevention runtime` | 14건 모두 무관(생물학·물리·그래프 이론). 주제 검색에는 쓸모없음 | RQ4 |
| G4-023 | A | WebFetch | web.stanford.edu/class/cs276a/projects/docs/berkeleydb/ref/lock/dead.html | Berkeley DB 락 관리자: 대기 그래프에서 순환을 찾음. 탐지는 상시가 아니며 db_deadlock 주기 실행, 사용자 스레드의 lock_detect 호출, 또는 `set_lk_detect`로 락 요청이 막힐 때마다 실행. 순환마다 요청 하나를 거부하고 호출자가 트랜잭션을 중단. 자동 탐지는 교착이 없을 때도 돌아 성능을 떨어뜨릴 수 있다고 서술 | RQ4, RQ3 |
| G4-024 | R | WebFetch | raw.githubusercontent.com/abseil/abseil-cpp/master/absl/synchronization/internal/graphcycles.cc | 파일 머리말이 Pearce·Kelly(JEA 2006)를 인용. 노드 순위를 위상 순서와 일관되게 유지하고 rank[x]<rank[y]이면 간선 삽입에 일이 없음. 그렇지 않으면 y에서 앞쪽 탐색(x의 순위로 한정, x에 닿으면 순환), x에서 뒤쪽 탐색 후 순위를 재배정. 복잡도 서술 없음 | RQ4 |
| G4-025 | R | WebFetch | www3.cs.stonybrook.edu/~stoller/papers/deadlock-IBM-2010.pdf | S8 본문: 락 그래프(노드=락, l1 보유 중 l2 획득 시 간선, 순환=잠재 교착). Visual Threads의 방법([3])이라고 서술. 가짜 양성 거르기 세 가지(같은 스레드, 게이트 락, 스레드 구간화). 주 방법은 실행 트레이스의 사후 분석. 일반 슬로다운 수치 없음. 회피는 다루지 않음. 저자 8명(L. Wang 포함) | RQ4, RQ2 |
| G4-026 | K | WebSearch | lockdep overhead performance impact CONFIG_PROVE_LOCKING slowdown percent benchmark kernel debug | 10건. LKML 스레드 다수(Long의 성능 개선 시리즈, Luba의 Kconfig 주석 패치, 문서 패치, defconfig에서 PROVE_LOCKING 제거 패치 등) | RQ4 |
| G4-027 | K | WebSearch | ThreadSanitizer deadlock detector lock order graph overhead slowdown detect_deadlocks evaluation | 10건. LLVM 스트레스 테스트 파일, bcc 커밋, 무관 페이지. TSan 탐지기의 오버헤드 수치는 찾지 못함 | RQ4 |
| G4-028 | R | WebFetch | lkml.iu.edu/hypermail/linux/kernel/1810.0/02181.html | W. Long, 2018-10-02, "[PATCH v2 0/5] locking/lockdep: Improve lockdep performance". 병렬 커널 빌드(4.19-rc5, gcc 8, 3회 중 최선)에서 lockdep과 관련 디버그 옵션을 켠 커널이 디버그 끈 기준 대비 1소켓 44스레드 46%, 4소켓 144스레드 83% 느렸고 패치 후 41%, 36%. 패치 시리즈가 빌드 시간을 3.7%, 25.7% 줄임 | RQ4 |
| G4-029 | R | WebFetch | lkml.iu.edu/hypermail/linux/kernel/1810.1/02953.html | L. Luba, 2018-10-09, Kconfig 도움말에 PROVE_LOCKING 등의 성능 영향을 적는 패치. 설명에 문맥 전환 최대 약 3배 느려짐. ARM 시험은 패치 후 문맥 전환 약 15µs 대 디버그 없을 때 5~6µs. Long은 고정 배수를 적는 데 반대(하드웨어·워크로드에 따라 다름) | RQ4 |
| G4-030 | R | WebFetch | docs.kernel.org/locking/ww-mutex-design.html | wait-die는 나이 많은 보유자를 만난 트랜잭션이 락을 놓고 `-EDEADLK`를 돌려받아 원래 티켓으로 재시도, wound-wait는 젊은 보유자를 부상시키고 그 보유자가 다음 경합 때 `-EDEADLK`로 물러남. w/w 클래스를 명시적으로 선언. 경쟁이 적으면 wound-wait를 권함. 전역 카운터의 예약 티켓으로 순서를 정하며 의존 그래프 기반 탐지는 서술하지 않음 | RQ4, RQ3 |
