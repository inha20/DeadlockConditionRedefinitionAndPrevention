# 자체 점검 일괄 실행 기록 (스냅샷)

- 실행한 것: HEAD b174569에 커밋하지 않은 변경을 더한 상태의 작업 트리. Python 3.13.18, linux, 병렬 2.
- 생성: `python3 -I analysis/repo/check_repo.py --run --run-report formal/repo/run-all-check.md`
- 각 점검의 보고서는 임시 폴더에 쓰고 저장소의 보고서는 건드리지 않았다. 시간은 이 실행의 값이며 컴퓨터마다 다르다.
- 이 기록은 점검이 통과했다는 것이지 연구 결과가 아니다. AI(Claude)가 쓴 초안이며 사람의 검토 전이다.

| 이름 | 스크립트 | 결과 | 종료 코드 | 시간 | 마지막 출력 줄 |
|---|---|---|---|---:|---|
| sm | `oracle/check_sm.py` | 통과 | 0 | 61초 | 모든 검사 통과 |
| sm-mutation | `oracle/mutation_check.py` | 통과 | 0 | 91초 | [  91.1s] 대기 그래프에서 자유 단위가 있는 종류의 간선 제거: 검출됨 T2n, T8 |
| o1 | `oracle/check_banker.py` | 통과 | 0 | 77초 | TOTAL violations/failures: 0 |
| o2 | `oracle/check_locks.py` | 통과 | 0 | 23초 | 검사 35개, 실패 0개 |
| harness | `bench/check_pipeline.py` | 통과 | 0 | 17초 | 점검 80개, 실패 0개 |
| banker-policies | `bench/check_banker_policies.py` | 통과 | 0 | 159초 | 전체 위반·실패 0건, 159초 |
| variants-dbdaa | `bench/check_variants.py` | 통과 | 0 | 33초 | 점검 99개, 실패 0건, 32초 |
| variants-begum | `bench/check_variants_begum.py` | 통과 | 0 | 25초 | 점검 69개, 실패 0건, 25초 |
| variants-dixit | `bench/check_variants_dixit.py` | 통과 | 0 | 49초 | 점검 69개, 실패 0건, 48초 |
| variants-wicaksono | `bench/check_variants_wicaksono.py` | 통과 | 0 | 31초 | 점검 52개, 실패 0건, 30초 |
| variants-derivations | `bench/check_variants_derivations.py` | 통과 | 0 | 9초 | 점검 55개, 실패 0건, 9초 |
| pilot-tools | `bench/check_pilot.py` | 통과 | 0 | 6초 | 점검 55개, 실패 0건, 5초 |
| lock-policies | `bench/check_lock_policies.py` | 통과 | 0 | 640초 | 검사 80개, 실패 0개 (소요 639초) |
| workloads | `bench/check_workloads.py` | 통과 | 0 | 66초 | 검사 23개, 실패 0개 (소요 65초) -> /tmp/claude-0/-home-claude/3dab5dd8-8cbf-5e5f-b8d5-7658a40d2597/scratchpad/runall/workloads-check.md |
| trace-validator | `traces/check_validate.py` | 통과 | 0 | 3초 | 검사 45개, 실패 0개 -> /tmp/claude-0/-home-claude/3dab5dd8-8cbf-5e5f-b8d5-7658a40d2597/scratchpad/runall/trace-validator-check.md |
| codebook-tools | `analysis/rq5/check_codebook_tools.py` | 통과 | 0 | 1초 | 검사 88개, 실패 0개 -> /tmp/claude-0/-home-claude/3dab5dd8-8cbf-5e5f-b8d5-7658a40d2597/scratchpad/runall/codebook-tools-check.md, 보고서가 저장소의 것과 같음 |
| grid | `analysis/rq2/check_grid.py` | 통과 | 0 | 0초 | - 시험 29건 중 놓친 것 0건., 보고서가 저장소의 것과 같음 |

- 실행 17개, 실패 0개. 걸린 시간 931초(병렬 2, 시간은 이 실행의 값이며 컴퓨터마다 다르다).
- 실행 전후로 저장소의 모든 파일(추적 + 아직 추적하지 않은 것, 무시한 파일 제외)의 내용 해시를 견줬다: 달라진 파일 없음.
