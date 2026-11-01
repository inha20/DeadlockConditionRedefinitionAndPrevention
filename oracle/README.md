# oracle/ — 스냅샷 모델(SM)의 정확 오라클

AI(Claude)가 작성한 초안이며 사람의 검토 전이다. 정의는 `docs/spec/model-spec.md`에 있다. 성능보다 정의와의 일치를 우선한 참조 구현이다.

## 파일

| 파일 | 내용 |
|---|---|
| `sm.py` | 상태 `Inst(cap, alloc, alts)`, 교착 집합 판정 `is_deadlock_set`, 축소로 구하는 가장 큰 교착 집합 `greatest_deadlock_set`, 전체·극소 교착 집합, 의존 그래프·대기 그래프·자원 할당 그래프, 매듭 판정, `expedient`, 사람이 읽는 표기 `show` |
| `check_sm.py` | 문서 §6의 정리 진술을 작은 범위의 모든 상태에서 검사하고 결과를 마크다운으로 쓴다 |
| `mutation_check.py` | `sm.py`를 일부러 틀리게 바꿔 `check_sm.py`가 위반을 잡는지 본다 |

## 실행

```
python3 -I oracle/check_sm.py formal/rq1/sm-check-results.md          # 약 1분
python3 -I oracle/mutation_check.py formal/rq1/sm-mutation-results.md # 약 1.5분
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
- 하지 않음: Alloy, TLA+(TLC)로의 교차 검증. 단일 인스턴스 락 프로그램의 상태 공간 탐색(문서 02의 O2). 뱅커 모델 전용 입력 형식(문서 02의 O1. `docs/spec/model-spec.md` §3.5의 s_max 변환으로 SM에서 쓸 수는 있다). 크기·시간 한계표. 단위 테스트 프레임워크(검증은 `check_sm.py`가 대신한다).
- 한계: 오라클, 정리 진술, 검증이 같은 정의에서 나왔다. 일치는 정의 내부의 일관성이며 문헌의 교착 정의와 같다는 뜻이 아니다.
