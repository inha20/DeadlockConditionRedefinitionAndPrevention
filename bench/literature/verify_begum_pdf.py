"""Begum 외 2020 PDF와 bench/literature/begum2020.py의 대조 (WP6.3, AI 초안: 사람의 확인 전).

실행: python3 -I bench/literature/verify_begum_pdf.py <PDF 경로> [결과.md]
PDF는 저장소에 넣지 않는다(IEEE 저작물, 모든 권리 유보. ISCAIE 2020, pp. 73–78. 사용자가 2026-11-01에 제공한 사본으로 대조했다).
`pdftotext`(배치 모드와 일반 모드)가 필요하다. 표는 배치 모드(-layout), 본문 문장은 일반 모드로 읽는다.
이 스크립트가 보는 것: 표 I–IV(입력, 처리 순서, 추적)의 모든 칸, 본문이 적은 Available 값과 안전 순서와 비교 횟수,
의사코드의 핵심 구문이 구현 문서(begum2020.py의 해석)가 인용하는 형태로 있는지.
텍스트 층만 읽으므로 그림 1(순서도)과 그림 2(자원 할당 그래프)는 보지 않는다. 순서도는 사람이 그림을 보고 확인했다(docs/rq6/variants.md).
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from bench.literature import begum2020 as B  # noqa: E402


def pdf_text(path: str, layout: bool) -> str:
    cmd = ["pdftotext"] + (["-layout"] if layout else []) + [path, "-"]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def region(text: str, start: str, end: str) -> list[str]:
    a = text.index(start)
    b = text.index(end, a)
    return text[a:b].splitlines()


def t1_rows(lines: list[str]) -> list[dict]:
    rows = []
    for ln in lines:
        m = re.match(r"^\s*(P\d)\s+((?:\d+\s+){9}\d+)\s*$", ln)
        if m:
            v = [int(x) for x in m.group(2).split()]
            rows.append({"id": m.group(1), "max": v[:5], "alloc": v[5:]})
    return rows


def t2_rows(lines: list[str]) -> list[dict]:
    """표 II는 오른쪽 단이라 줄 끝에 있다(왼쪽 단의 본문이 앞에 붙는다)."""
    rows = []
    for ln in lines:
        m = re.search(r"\s{2,}(P\d)\s+((?:\d+\s+){5}\d+)\s*$", ln)
        if m:
            v = [int(x) for x in m.group(2).split()]
            rows.append({"id": m.group(1), "need": v[:5], "max_needed": v[5]})
    return rows


def t3_rows(lines: list[str]) -> list[dict]:
    """표 III은 왼쪽 단이라 줄 앞에 있다(오른쪽 단의 본문이 뒤에 붙을 수 있다)."""
    rows = []
    for ln in lines:
        m = re.match(r"^\s*(P\d)\s+((?:\d+\s+){5}\d+)(?:\s{2,}.*)?$", ln)
        if m:
            v = [int(x) for x in m.group(2).split()]
            rows.append({"id": m.group(1), "need": v[:5], "max_needed": v[5]})
    return rows


def t4_rows(lines: list[str]) -> tuple[list[dict], list[int] | None]:
    rows, final = [], None
    for ln in lines:
        m = re.match(r"^\s*(P\d)\s+((?:\d+\s+){5})(\d+)\s+((?:\d+\s+){5})(\d+)\s+(True|False)\s*$", ln)
        if m:
            rows.append({"id": m.group(1), "need": [int(x) for x in m.group(2).split()], "max_needed": int(m.group(3)),
                         "avail": [int(x) for x in m.group(4).split()], "min_avail": int(m.group(5)), "ok": m.group(6) == "True"})
            continue
        m = re.match(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$", ln)
        if m:
            final = [int(x) for x in m.groups()]
    return rows, final


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = sys.argv[1]
    out_md = sys.argv[2] if len(sys.argv) > 2 else None
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    lay = pdf_text(path, True)
    raw = pdf_text(path, False)
    flat = re.sub(r"\s+", " ", raw)
    pages = lay.count("\f")
    res: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        res.append((name, bool(ok), detail))

    check("PDF 식별: 제목과 ISCAIE 쪽 표시(978-1-7281-5033-8/20)", "An Improved Safety Detection Algorithm Towards" in lay
          and "978-1-7281-5033-8/20" in lay)
    check("PDF 쪽 수 6", pages == 6, f"쪽 수 {pages}")

    t1 = t1_rows(region(lay, "TABLE I:", "Table 1 shows"))
    fx1 = B.parse_table1()
    check("표 I: 행 10개를 읽음", len(t1) == 10, f"읽은 행 {len(t1)}")
    diffs = [(p["id"], k) for p, f in zip(t1, fx1) for k in ("id", "max", "alloc") if p[k] != f[k]]
    check("표 I: 모든 칸(Maximum need, Current allocation)이 옮긴 값과 같음", not diffs, f"다른 칸 {diffs}")

    t2 = t2_rows(region(lay, "TABLE II:", "Now all the processes will be sorted"))
    fx2 = B.parse_table2()
    check("표 II: 행 10개를 읽음", len(t2) == 10, f"읽은 행 {len(t2)}")
    diffs = [(p["id"], k) for p, f in zip(t2, fx2) for k in ("id", "need", "max_needed") if p[k] != f[k]]
    check("표 II: 모든 칸(Needed allocation, Maximum Needed allocation)이 옮긴 값과 같음", not diffs, f"다른 칸 {diffs}")
    by_id2 = {x["id"]: x for x in t2}
    mism = [r["id"] for r in t1
            if by_id2[r["id"]]["need"] != [r["max"][j] - r["alloc"][j] for j in range(5)]
            or by_id2[r["id"]]["max_needed"] != max(by_id2[r["id"]]["need"])]
    check("표 II = 표 I의 Maximum − Allocation, Maximum Needed = 행의 최댓값 (인쇄된 값 기준)", not mism, f"다른 행 {mism}")

    t3 = t3_rows(region(lay, "TABLE III:", "The available resource for each resource types"))
    check("표 III: 행 10개를 읽음", len(t3) == 10, f"읽은 행 {len(t3)}")
    check("표 III: 처리 순서가 옮긴 SORTED_ORDER와 같음", [r["id"] for r in t3] == B.SORTED_ORDER, f"PDF {[r['id'] for r in t3]}")
    by2 = {r["id"]: r for r in fx2}
    d3 = [(r["id"], j) for r in t3 for j in range(5) if r["need"][j] != by2[r["id"]]["need"][j]]
    check("표 III: Needed allocation이 표 II와 같다. 단 하나, P7의 E칸만 다르다(5로 인쇄, 표 II는 0) — 논문 안의 인쇄 불일치",
          d3 == [("P7", 4)] and next(r for r in t3 if r["id"] == "P7")["need"][4] == 5, f"다른 칸 {d3}")
    check("표 III: Maximum Needed allocation 열이 표 II와 같음", all(r["max_needed"] == by2[r["id"]]["max_needed"] for r in t3))
    key_sorted = sorted(range(10), key=lambda i: fx2[i]["max_needed"])
    check("표 III의 순서 = Maximum Needed allocation의 안정 오름차순(같은 값은 프로세스 번호 순)",
          [fx2[i]["id"] for i in key_sorted] == [r["id"] for r in t3])

    t4, final = t4_rows(region(lay, "TABLE IV:", "of the previous algorithms."))
    fx4 = B.parse_table4()
    check("표 IV: 행 10개를 읽음", len(t4) == 10, f"읽은 행 {len(t4)}")
    check("표 IV: 처리 순서가 표 III과 같음", [r["id"] for r in t4] == [r["id"] for r in t3])
    check("표 IV: Needed allocation 열이 표 II와 같음", all(r["need"] == by2[r["id"]]["need"] for r in t4))
    d4 = [r["id"] for r in t4 if r["max_needed"] != by2[r["id"]]["max_needed"]]
    check("표 IV: Maximum Needed 열이 표 II와 같다. 단 P7만 다르다(5로 인쇄, 표 II·III은 7) — 논문 안의 인쇄 불일치",
          d4 == ["P7"] and next(r for r in t4 if r["id"] == "P7")["max_needed"] == 5, f"다른 행 {d4}")
    diffs = [(p["id"], k) for p, f in zip(t4, fx4) for k in ("id", "avail", "min_avail", "ok") if p[k] != f[k]]
    check("표 IV: Available, Minimum available, 조건(True) 열이 옮긴 값과 같음", not diffs, f"다른 칸 {diffs}")
    check("표 IV: 맨 아래 줄이 옮긴 FINAL_AVAILABLE과 같음", final == list(B.FINAL_AVAILABLE), f"PDF {final}")
    check("표 IV: 조건 열이 모두 True", all(r["ok"] for r in t4))

    # 본문(일반 모드): 값과 순서와 횟수
    for nm, pat in [("본문: 자원 인스턴스 수 25, 30, 20, 30, 35", r"25, 30, 20, 30, and 35 instances"),
                    ("본문: 프로세스 10개(P0~P9)와 자원 5종(A~E)", r"ten processes \(P0 ∼ P9 \) and five resource types \(A ∼ E\)"),
                    ("본문: 처음 Available [4 5 2 4 7]", r"\[A B C D E\] is \[4 5 2 4 7\]"),
                    ("본문: P4 뒤 Available [6 8 4 4 8]", r"\[6 8 4 4 8\]"),
                    ("본문: P2 뒤 Available [6 12 4 9 8]", r"\[6 12 4 9 8\]"),
                    ("본문: P3 뒤 Available [8 12 4 15 13]", r"\[8 12 4 15 13\]"),
                    ("본문: P4의 Minimum available 2", r"minimum available is 2\."),
                    ("본문: 안전 순서 <P4,P2,P3,P5,P0,P6,P8,P9,P1,P7>", r"P4 , P2 , P3 , P5 , P0 , P6 , P8 , P9 , P1 , and P7"),
                    ("본문: 이 예제에서 비교 10회", r"only 10 comparisons"),
                    ("본문: 원래의 뱅커는 같은 일에 적어도 50회", r"at least 50 comparisons"),
                    ("본문: 순서를 한 번 이상 확인할 필요가 없다", r"more than once"),
                    ("본문: 시간 복잡도 식 O(n + nd + nd + nd) 또는 O(nd)", r"O\(n \+ nd \+ nd \+ nd\) or O\(nd\)"),
                    ("결론: 원래 뱅커보다 n배 빠르다", r"n times faster than the original banker"),
                    ("결론: 안전성 탐지에 대해서만 실험·분석했다", r"only ?for safety detection")]:
        n = len(re.findall(pat, flat))
        check(nm, n == 1, f"일치 {n}회")

    # 의사코드의 핵심 구문(구현의 해석이 근거하는 구문)
    pats = {
        "2단계: Maximum need[i,j] > Resource[j]이면 불안전": r"if \(Maximum need\[i,j\]>Resource\[j\] \) \{ return unsafe state\}",
        "3단계: 기수 정렬(Radix Short) 호출": r"Radix Short\(Process\[n\] ,Maximum Needed allocation\[n\]\)",
        "4단계: 빠른 검사 Maximum Needed allocation[i] ≤ Minimum Available": r"Maximum Needed allocation\[i\] ≤Minimum Available and",
        "4단계: Completed process[Process[i]] == 0 조건": r"Completed process\[Process\[i\]\] == 0",
        "4단계: 통과하면 Compute(Minimum Available)": r"Compute\(Minimum Available\)",
        "4단계: 자원별 검사의 Continue/Break": r"\{ Continue ;\} else \{ Break ;\}",
        "4단계: if (j == d) 판정(문자 그대로는 모순. 해석 목록)": r"if \(j == d\)",
        "4단계: 실패하면 return unsafe state": r"else \{return unsafe state ;\}",
        "5단계: 끝나지 않은 프로세스가 있으면 불안전": r"if \(Completed process\[i\]== 0\) \{return unsafe state \}",
        "6단계: return safe state and Safe sequence": r"return safe state and Safe sequence",
        "기수 정렬: 자릿수 = Length(Max(...))": r"Run times = Length\(Max\(Maximum Needed",
        "기수 정렬: 자릿수 추출이 % (10^i)만(나눗셈 없음, 해석 목록)": r"Count\[Maximum Needed allocation\[j\]%\(10i \)\]\+\+",
        "기수 정렬: 뒤에서부터 배치(안정 정렬)": r"j = n-1 to 0, decrement by 1",
    }
    for nm, p in pats.items():
        n = len(re.findall(p, flat))
        check(nm, n >= 1, f"일치 {n}회")
    # 순서도의 흐름과 맞지 않는 읽기가 없는지: 'Needed allocation'의 자원별 검사가 j=1..d로 도는 구문
    check("4단계: for (1≤j≤d)", re.search(r"for \(1≤j≤d\)", flat) is not None)
    check("본문: 연결 리스트에 자원 요구를 감소 순으로 저장한다고 서술(자원별 검사 순서의 해석 목록)",
          re.search(r"stored in decreasing order based on the amount of resource instance", flat) is not None)

    fails = [r for r in res if not r[1]]
    print(f"PDF SHA-256 {sha}")
    for nm, ok, detail in res:
        print(("통과 " if ok else "실패 ") + nm + (f" — {detail}" if (detail and not ok) else ""))
    print(f"점검 {len(res)}개, 실패 {len(fails)}건")

    if out_md:
        L = ["# Begum 외 2020 PDF와 옮긴 값의 대조 결과\n",
             "`bench/literature/verify_begum_pdf.py`가 쓴 결과다. AI(Claude)가 작성한 초안이며 사람의 검토 전이다. "
             "PDF는 ISCAIE 2020, pp. 73–78(6쪽)이고 사용자가 2026-11-01에 제공했다. IEEE의 저작물이라 저장소에는 넣지 않는다. "
             f"사본의 SHA-256: `{sha}`. 텍스트 층만 읽었다(그림 제외).\n",
             "| 점검 | 결과 |", "|---|---|"]
        for nm, ok, detail in res:
            L.append(f"| {nm} | {'통과' if ok else '실패: ' + detail} |")
        L.append("")
        L.append(f"점검 {len(res)}개, 실패 {len(fails)}건.\n")
        L.append("## 범위와 한계\n")
        L.append("- 표 I–IV의 모든 칸과 본문이 적은 값·순서·횟수, 의사코드의 핵심 구문이 있는지를 본다. 의사코드의 모든 문자를 기계로 대조한 것은 아니다.")
        L.append("- 그림 1(순서도)은 그림이라 이 대조에 들어 있지 않다. 순서도의 흐름은 사람이 확대한 그림을 읽고 확인했다(docs/rq6/variants.md §2).")
        L.append("- 논문 안의 인쇄 불일치 두 곳(표 III의 P7 E칸 5, 표 IV의 P7 Maximum Needed 5)은 PDF에서도 그대로 있다. "
                 "둘 다 실행 결과(순서, 비교 횟수)에는 영향이 없다(표 IV의 P7 비교는 Maximum Needed 7과 5 어느 쪽이든 Minimum available 18 이하라 True다).")
        L.append("- 옮긴 값(`begum2020.py`)은 저작물의 최소 수치만 담았고 문장은 담지 않았다. 위 표의 '본문' 줄은 정규식으로 찾은 일치 횟수다.")
        with open(out_md, "w", encoding="utf-8") as f:
            f.write("\n".join(L) + "\n")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
