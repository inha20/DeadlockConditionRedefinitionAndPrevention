# oracle/ — 스냅샷 모델(SM)의 정확 오라클

AI(Claude)가 작성한 초안이며 사람의 검토 전이다. 정의는 `docs/spec/model-spec.md`에 있다. 성능보다 정의와의 일치를 우선한 참조 구현이다.

## 파일

| 파일 | 내용 |
|---|---|
| `sm.py` | 상태 `Inst(cap, alloc, alts)`, 교착 집합 판정 `is_deadlock_set`, 축소로 구하는 가장 큰 교착 집합 `greatest_deadlock_set`, 전체·극소 교착 집합, 의존 그래프·대기 그래프·자원 할당 그래프, 매듭 판정, `expedient`, 사람이 읽는 표기 `show` |
| `check_sm.py` | 문서 §6의 정리 진술을 작은 범위의 모든 상태에서 검사하고 결과를 마크다운으로 쓴다 |
| `mutation_check.py` | `sm.py`를 일부러 틀리게 바꿔 `check_sm.py`가 위반을 잡는지 본다 |
| `banker.py` | 뱅커 모델 오라클 O1. 상태 `Banker(total, alloc, maxc)`, 모델 명세 §3.5의 s_max 변환 `to_sm`, 안전성 판정 세 가지(`safe_oracle`: SM 축소, `safe_perm`: 완료 순서 전수, `safe_dp`: 완료 집합 위의 DP), 요청 판정 `request_outcome`(ERROR, WAIT, GRANT, DENY), 소규모 전수 열거 `all_states` |
| `check_banker.py` | `banker.py`의 소규모 전수 자체 검증. 세 판정의 일치, 안전 순서와 끝낼 수 없는 집합의 검사, 요청 판정의 성질, 일부러 넣은 오류의 검출, 교재 예제(구현 점검용) |
| `locks.py` | 락 프로그램 오라클 O2(RQ3). 스레드마다 직선 락 프로그램(획득 `('A', l)`, 반납 `('R', l)`의 열)을 두고 상태를 스레드별 진행 위치로 나타낸다. `LockProgSystem`: `safe`(모든 스레드가 끝나는 스케줄이 있는가), `has_deadlock_set`(모델 명세 §3.1의 교착 집합), `possible_deadlock`(도달 가능한 교착), `request_permissible`(prereg/RQ3.md §5 M1의 '오라클 허용 가능' 판정 부품). 독립 완전 탐색 구현 `safe_bruteforce`, `deadlock_set_bruteforce`, `possible_deadlock_bruteforce`. 프로그램 만들기 `program(order, release)` |
| `check_locks.py` | `locks.py`의 자체 검증 35개. 알려진 답(AB/BA, 같은 순서, 세 락 순환, 식사하는 철학자, 손잡기), 세 범위의 전수·표본에서 완전 탐색 구현과의 일치, 상태 사이의 관계, 일부러 넣은 오류 4개의 검출 |

## 실행

```
python3 -I oracle/check_sm.py formal/rq1/sm-check-results.md          # 약 1분
python3 -I oracle/mutation_check.py formal/rq1/sm-mutation-results.md # 약 1.5분
python3 -I oracle/check_banker.py formal/rq6/o1-check-results.md      # 약 1.3분
python3 -I oracle/check_locks.py formal/rq3/o2-check-results.md       # 약 20초
```

표준 라이브러리만 쓴다. 두 스크립트는 `-I`(격리 모드)로 실행해도 같은 폴더의 `sm.py`를 찾도록 자기 폴더를 경로에 넣는다.

## 사용 예

```python
import sys; sys.path.insert(0, "oracle")
import sm
from sm import Inst

# 용량 1짜리 자원 두 종류. P0은 0번을 쥐고 1번을 기다리고, P1은 1번을 쥐고 0번을 기다린다.
s = Inst(cap=(1, 1), alloc=((1, 0), (0, 1)),
         alts=(frozenset({(0, 1)}), frozenset({(1, 0)})))
sm.greatest_deadlock_set(s)   # frozenset({0, 1})
sm.minimal_deadlock_sets(s)   # [frozenset({0, 1})]
sm.rag_knot_exists(s)         # True
```

`alts[p]`는 대안 벡터의 집합이고 비어 있으면 대기 중이 아니다. 요청 형태(AND, OR, AND-OR, P-out-of-Q)를 대안으로 쓰는 방법은 `docs/spec/model-spec.md` §2.2에 있다.

## 확인한 것과 하지 않은 것

- 확인함: 10개 범위 595,676개 상태에서 정리 진술 위반 0건. 순열 전수 탐색(L3)이 축소 구현과 독립적으로 일치함. 일부러 넣은 오류 7개를 검사 모음이 모두 검출함. 결과는 `formal/rq1/`에 있다.
- 범위: 프로세스 3–4개, 자원 종류 2–3개, 용량 1–3, 대안은 DNF에서 최대 2개. 이보다 큰 입력에서는 전수 검증하지 않았다.
- 뱅커 오라클 O1(2026-11-01): 9개 범위(프로세스 2–5개, 종류 2–3개, 총량 1–3, 약 89만 상태)에서 세 판정이 일치하고 위반 0건. 일부러 넣은 오류 3개를 검출했다. 결과는 `formal/rq6/o1-check-results.md`. 단일 종류에서 F8의 동치와의 대조는 F8 원문을 다시 확인한 뒤에 한다.
- 락 프로그램 오라클 O2(2026-11-01): 세 범위(스레드 2–3개, 락 3–4개, 획득 1–3개, 반납 방식 nested·fifo·hoh; 표본 포함, 약 26만 상태)에서 메모를 쓴 판정이 독립 완전 탐색과 일치하고 위반 0건. 일부러 넣은 오류 4개를 검출했다. 결과는 `formal/rq3/o2-check-results.md`. 정책 구현과의 일관성 검사는 `formal/rq3/lock-policies-check.md`의 oracle 항목에 있다.
- 하지 않음: Alloy, TLA+(TLC)로의 교차 검증. 락 프로그램 오라클 O2의 크기·시간 한계표(상태 수가 스레드별 (연산 수 + 1)의 곱이라 소규모 한정이며 측정하지 않았다). 단위 테스트 프레임워크(검증은 `check_sm.py` 등이 대신한다).
- 한계: 오라클, 정리 진술, 검증이 같은 정의에서 나왔다. 일치는 정의 내부의 일관성이며 문헌의 교착 정의와 같다는 뜻이 아니다.
