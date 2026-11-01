# experiments/ — 원자료와 실행 스크립트 보관 (SP-6)

이 폴더는 측정 실행의 원자료(JSONL), 시드, 실행 설정을 보관하는 자리다. **본 실험의 자료는 아직 없다.** 본 실험은 사전 분석 계획 동결(`prereg-RQx-v1` 태그) 뒤에 돌린다. 지금 있는 것은 RQ6 파일럿의 자료뿐이다.

- `pilot/` (RQ6 파일럿 자료, 2026-11-01): 마스터 시드 `rq6-pilot-v1`. 단계별 JSONL 8개(`S`, `C`, `O`, `V`, `V2`, `V3`, `P`, `R`. 합계 약 9.5 MB), 생성 요약 `pilot-summary.md`, 전체 해시 `SHA256SUMS`. 프로토콜과 결과의 해석은 `docs/rq6/pilot.md`, 만든 도구는 `bench/pilot_rq6.py`다. 무결성 확인은 `cd experiments/pilot && sha256sum -c SHA256SUMS`, 요약은 `python3 -I bench/pilot_rq6.py summary`로 다시 만들 수 있다. 이 자료는 최종본이며 고치지 않는다. 변형 정책의 판정은 기록하지 않았다(`withheld`).
- 파일럿 자료는 본 분석에 쓰지 않는다. 쓸 때에는 해당 `prereg/RQx.md`에 사전에 적는다(`prereg/README.md` §2).
- 실행 한 번마다 JSONL 하나와 그 실행의 머리 기록(마스터 시드, 셀 설정, 정책 목록, 환경 정보, git 커밋)이 함께 남는다(`bench/runner.py`, `bench/pilot_rq6.py`).
- 제3자 자료는 두지 않고 링크와 해시만 둔다.
