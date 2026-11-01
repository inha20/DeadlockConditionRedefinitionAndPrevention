# analysis/rq5 — 커널 교착 사례 분석(RQ5)

자료는 Gong, Lin, Wu, Lu, Fonseca, "A Comprehensive Study of Concurrency Bugs in the Linux Kernel"(ICSE 2026)의 공개 데이터셋이다.
저장소 `https://github.com/rssys/kernel-concurrency-bug-study`는 `README.md`와 `dataset.csv`만 담고 있고 LICENSE 파일이 없다(2026-10-29 확인).
그래서 이 저장소에는 원본 표를 복제하지 않는다. 여기에는 커밋 해시 색인과 이 연구의 자체 분류만 둔다.

## 재현

```bash
mkdir -p _external && git clone https://github.com/rssys/kernel-concurrency-bug-study _external/e2
git -C _external/e2 checkout ffcad0cb9126c017d3a188fa53cf118a6553c6cd
python3 -I e2_stats.py _external/e2/dataset.csv            # 열별 개수
python3 -I make_index.py _external/e2/dataset.csv index.csv # 교착 49건 색인
```

`_external/`은 `.gitignore`에 들어 있어 커밋되지 않는다.

## 파일

| 파일 | 내용 |
|---|---|
| `e2_stats.py` | 열별 개수 집계(원본 행을 출력하지 않음) |
| `make_index.py` | 교착 행의 색인 생성 |
| `index.csv` | 교착 49건의 커밋 해시, 원본 행 번호, 커널 저장소 링크, 자체 코딩 칸(`own_*`, 현재 비어 있음) |
| `codebook_tools.py` | 코딩 표(23열) 검증, 파일럿 표본 추출, 코더 일치도(Cohen의 κ). 사용법은 `docs/rq5/codebook.md` §6 |
| `check_codebook_tools.py` | 위 도구의 자체 시험(구성한 가짜 행 사용, 49건은 읽지 않음)과 코드북 문서와의 값 집합 일치 점검. 보고서는 `formal/rq5/codebook-tools-check.md` |

코드북은 `docs/rq5/codebook.md`(v0.1, AI 초안, 사람의 승인 전)다. 파일럿 표본은 아직 뽑지 않았고 `coding.csv`는 아직 없다. 사례 코딩은 사람의 결정(`prereg/RQ5.md` §9의 O5-1–O5-3, O5-9–O5-12)과 동결 뒤 일이다.

## 읽을 때 주의

- 열 이름은 `Number of contexts`이지만 논문은 스레드 수를 센다고 쓰고 인터럽트 핸들러를 별도 스레드로 세지 않는다(§4.2). 두 정의가 같은지는 확인되지 않았다.
- 데이터셋에는 같은 의미의 표기가 섞여 있다(`rwsem`과 `rw_semaphore`, 철자 `wrong-chioce`). 재사용 전에 정리가 필요하다.
- 수정된 버그만 포함한다(생존 편향). 문서 01 §2.6 참조.
