#!/usr/bin/env python3
"""E2(Gong et al., ICSE 2026) 공개 데이터셋의 집계 통계.

사용법:
    python3 -I e2_stats.py <dataset.csv 경로>

원본 표는 이 저장소에 복제하지 않는다(라이선스 미표시). 이 스크립트는 열별 개수만 출력한다.
고정한 데이터셋 커밋: ffcad0cb9126c017d3a188fa53cf118a6553c6cd (rssys/kernel-concurrency-bug-study)
"""
import collections
import csv
import sys


def counts(rows, col):
    return dict(collections.Counter((r[col] if r[col] != "" else "(빈값)") for r in rows))


def main(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print("행 수:", len(rows))
    print("고유 커밋 수:", len({r["Commit"] for r in rows}))
    print("버그 패턴:", counts(rows, "Bug pattern"))
    print("전체 실행 문맥 수:", counts(rows, "Number of contexts"))
    print("전체 인터럽트 의존:", counts(rows, "Interrupt dependent"))
    le2 = sum(1 for r in rows if r["Number of contexts"] in ("1", "2"))
    print(f"전체에서 문맥 수 2 이하: {le2}/{len(rows)} = {le2 / len(rows):.1%}")

    dl = [r for r in rows if r["Bug pattern"] == "deadlock"]
    print()
    print("교착 행 수:", len(dl))
    for col in ["Number of contexts", "Interrupt dependent", "Hardware dependent",
                "Synchronization misuse", "Discovery source"]:
        print(f"교착 · {col}:", counts(dl, col))
    xt = collections.Counter((r["Number of contexts"], r["Interrupt dependent"]) for r in dl)
    print("교착 · (문맥 수, 인터럽트 의존):", dict(xt))
    le2d = sum(1 for r in dl if r["Number of contexts"] in ("1", "2"))
    print(f"교착에서 문맥 수 2 이하: {le2d}/{len(dl)} = {le2d / len(dl):.1%}")

    one = [r for r in dl if r["Number of contexts"] == "1"]
    print()
    print("단일 문맥 교착 수:", len(one), f"({len(one) / len(dl):.1%})")
    for col in ["Interrupt dependent", "Hardware dependent", "Synchronization misuse", "Discovery source"]:
        print(f"단일 문맥 교착 · {col}:", counts(one, col))
    two = [r for r in dl if r["Number of contexts"] == "2"]
    print("2문맥 교착 수:", len(two), f"({len(two) / len(dl):.1%})",
          "· 인터럽트 의존:", counts(two, "Interrupt dependent"))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
