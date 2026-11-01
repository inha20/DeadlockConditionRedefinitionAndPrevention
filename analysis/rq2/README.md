# analysis/rq2 — RQ2 격자 문서의 점검 도구

| 파일 | 내용 |
|---|---|
| `check_grid.py` | `docs/rq2/grid.md`의 표를 읽어 칸 수(216칸 중 66칸에 상태), 상태 어휘, 인용 항목과 칸의 일관성, 상태별 집계, 후보 칸, 본문이 언급하는 ID의 존재를 점검한다. 읽어 들인 모델을 일부러 망가뜨리는 자체 시험 23건이 들어 있다 |

```bash
python3 -I analysis/rq2/check_grid.py                                   # 점검과 자체 시험
python3 -I analysis/rq2/check_grid.py --report formal/rq2/grid-check.md # 보고서 저장
```

점검하는 것은 문서의 형식과 일관성이다. 문헌 내용의 옳고 그름이나 칸 상태가 맞는지는 점검하지 않는다. 문서와 표의 상태 어휘는 `prereg/RQ2.md` §4와 `docs/rq2/grid.md` §1.5를 따른다.
