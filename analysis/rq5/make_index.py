#!/usr/bin/env python3
"""E2 데이터셋에서 교착 행의 색인(커밋 해시, 원본 행 번호, 링크)만 추출해 index.csv를 만든다.

사용법:
    python3 -I make_index.py <dataset.csv 경로> <출력 index.csv 경로>

원본의 분류 열(인터럽트 의존, 문맥 수 등)은 복제하지 않는다. 빈 열(own_*)은 이 연구의 자체 코딩용이다.
행 번호는 dataset.csv의 데이터 행 순번(머리글 제외, 1부터)이며 고정 커밋 ffcad0cb9126c017d3a188fa53cf118a6553c6cd 기준이다.
"""
import csv
import sys

KERNEL_URL = "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id={}"


def main(src, dst):
    with open(src, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = []
    for i, r in enumerate(rows, 1):
        if r["Bug pattern"].strip().lower() == "deadlock":
            out.append({"e2_row": i, "commit": r["Commit"], "kernel_url": KERNEL_URL.format(r["Commit"]),
                        "own_status": "todo", "own_self_wait": "", "own_autonomy": "", "own_note": ""})
    with open(dst, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print(f"{len(out)}행을 {dst}에 썼다")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
