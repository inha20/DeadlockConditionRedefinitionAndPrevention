# 자체 점검 일괄 실행 기록 (스냅샷)

- 실행한 것: HEAD bc1d77f의 작업 트리. Python 3.13.18, linux, 병렬 2.
- 생성: `python3 -I analysis/repo/check_repo.py --run --run-report formal/repo/run-all-check.md`
- 각 점검의 보고서는 임시 폴더에 쓰고 저장소의 보고서는 건드리지 않았다. 시간은 이 실행의 값이며 컴퓨터마다 다르다. 두 점검이 같은 코어를 나눠 썼으므로 한 점검씩 돌릴 때보다 길다.
- 이 기록은 점검이 통과했다는 것이지 연구 결과가 아니다. AI(Claude)가 쓴 초안이며 사람의 검토 전이다.

| 이름 | 스크립트 | 결과 | 종료 코드 | 시간 | 오래 걸림(`--quick`에서 뺌) | 마지막 출력 줄 |
|---|---|---|---|---:|---|---|
| sm | `oracle/check_sm.py` | 통과 | 0 | 93초 | 아니오 | 모든 검사 통과 |
| sm-mutation | `oracle/mutation_check.py` | 통과 | 0 | 140초 | 아니오 | [ 139.6s] 대기 그래프에서 자유 단위가 있는 종류의 간선 제거: 검출됨 T2n, T8 |
| o1 | `oracle/check_banker.py` | 통과 | 0 | 119초 | 아니오 | TOTAL violations/failures: 0 |
| o2 | `oracle/check_locks.py` | 통과 | 0 | 34초 | 아니오 | 검사 35개, 실패 0개 |
| harness | `bench/check_pipeline.py` | 통과 | 0 | 22초 | 아니오 | 점검 80개, 실패 0개 |
| banker-policies | `bench/check_banker_policies.py` | 통과 | 0 | 241초 | 예 | 전체 위반·실패 0건, 240초 |
| variants-dbdaa | `bench/check_variants.py` | 통과 | 0 | 50초 | 아니오 | 점검 99개, 실패 0건, 50초 |
| variants-begum | `bench/check_variants_begum.py` | 통과 | 0 | 41초 | 아니오 | 점검 69개, 실패 0건, 40초 |
| variants-dixit | `bench/check_variants_dixit.py` | 통과 | 0 | 80초 | 아니오 | 점검 69개, 실패 0건, 79초 |
| variants-wicaksono | `bench/check_variants_wicaksono.py` | 통과 | 0 | 47초 | 아니오 | 점검 52개, 실패 0건, 47초 |
| variants-derivations | `bench/check_variants_derivations.py` | 통과 | 0 | 13초 | 아니오 | 점검 55개, 실패 0건, 13초 |
| pilot-tools | `bench/check_pilot.py` | 통과 | 0 | 7초 | 아니오 | 점검 55개, 실패 0건, 5초 |
| lock-policies | `bench/check_lock_policies.py` | 통과 | 0 | 883초 | 예 | 검사 80개, 실패 0개 (소요 883초) |
| workloads | `bench/check_workloads.py` | 통과 | 0 | 33초 | 아니오 | 검사 23개, 실패 0개 (소요 33초) -> <출력 폴더>/workloads-check.md |
| trace-validator | `traces/check_validate.py` | 통과 | 0 | 2초 | 아니오 | 검사 45개, 실패 0개 -> <출력 폴더>/trace-validator-check.md |
| codebook-tools | `analysis/rq5/check_codebook_tools.py` | 통과 | 0 | 0초 | 아니오 | 검사 88개, 실패 0개 -> <출력 폴더>/codebook-tools-check.md, 보고서가 저장소의 것과 같음 |
| grid | `analysis/rq2/check_grid.py` | 통과 | 0 | 0초 | 아니오 | - 시험 29건 중 놓친 것 0건., 보고서가 저장소의 것과 같음 |

- 실행 17개, 실패 0개. 걸린 시간 916초(병렬 2).
- 실행 전후로 저장소의 모든 파일(추적 + 아직 추적하지 않은 것, 무시한 파일 제외)의 내용 해시를 견줬다: 달라진 파일 없음.
