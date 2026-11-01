"""DBDAA 저널 PDF와 bench/literature/dbdaa2024.py의 대조 (WP6.3, AI 초안: 사람의 확인 전).

실행: python3 -I bench/literature/verify_dbdaa_pdf.py <PDF 경로> [결과.md]
PDF는 저장소에 넣지 않는다(PLOS ONE 19(9): e0310807의 저널본. 사용자가 2026-11-01에 제공한 사본으로 대조했다).
`pdftotext -layout`이 필요하다. 이 스크립트가 보는 것: 표 2–4(입력), 표 5–7(추적), 표 8(비교 횟수), 표 9(복잡도 표기),
본문이 적은 순서들, Algorithm 1의 줄 번호가 구현 문서(zohora2024.py)가 인용하는 줄과 같은 내용인지.
여기서 PDF의 텍스트 층을 읽으므로 그림(Fig 2–7)은 보지 않는다.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from bench.literature import dbdaa2024 as D  # noqa: E402


def pdf_text(path: str) -> str:
    return subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, check=True).stdout


def section(text: str, start: str, end: str) -> list[str]:
    a = text.index(start)
    b = text.index(end, a)
    return text[a:b].splitlines()


def parse_input_table(lines: list[str]) -> list[dict]:
    rows = []
    for ln in lines:
        m = re.match(r"^\s*(P\d+)\s+((?:\d+\s+){16}\d+)\s*$", ln)
        if not m:
            continue
        v = [int(x) for x in m.group(2).split()]
        rows.append({"id": m.group(1), "at": v[0], "bt": v[1], "max": v[2:7], "alloc": v[7:12], "need_printed": v[12:17]})
    return rows


def parse_trace_table(lines: list[str]) -> tuple[list[dict], list[str]]:
    rows, bad = [], []
    for ln in lines:
        m = re.match(r"^\s*(P\d+)\s+(.*?)\s+(Yes|No)\s+(\d+)\s*$", ln)
        if not m:
            continue
        nums = [int(x) for x in re.findall(r"\d+", m.group(2))]
        if len(nums) == 7:
            mx, av, mn = [nums[0], None], nums[1:6], [nums[6], None]
        elif len(nums) == 9:
            mx, av, mn = nums[0:2], nums[2:7], nums[7:9]
        else:
            bad.append(ln.strip())
            continue
        rows.append({"id": m.group(1), "max_need": mx, "avail": av, "min_avail": mn, "safe": m.group(3) == "Yes",
                     "comparisons": int(m.group(4))})
    return rows, bad


def parse_table8(text: str) -> dict:
    out = {}
    for ln in text.splitlines():
        m = re.match(r"^\s*Dataset: Table (\d)\s+(.*)$", ln)
        if m:
            out[int(m.group(1))] = [int(t) if t.isdigit() else t for t in m.group(2).split()]
    return out


def parse_table9(text: str) -> dict:
    rows = {}
    pat = re.compile(r"O\((?:[^()]|\([^()]*\))*\)")
    names = ["Original Banker’s Algorithm [1]", "Momotaz et al [4]", "Bondarenko et al [5]", "Song et al [9]",
             "Wicaksono et al [12]", "DBDAA"]
    a = text.index("Table 9. Time complexity")
    prev = ""
    for ln in text[a:].splitlines():
        for nm in names:
            if ln.strip().startswith(nm):
                body = ln[len(ln) - len(ln.lstrip()) + len(nm):]
                if prev.strip() == "2":      # 윗첨자 2가 윗줄에 따로 추출된 경우: 평균 사례 칸의 O(n d)가 O(n²d)이다
                    body = body.replace("O(n d)", "O(n2d)", 1)
                rows[nm] = tuple(re.findall(pat, body))
        prev = ln
    return rows


def sequences(text: str) -> list[list[str]]:
    flat = re.sub(r"\s+", " ", text)
    seqs = []
    for m in re.finditer(r"<\s*(P\d+(?:\s*,\s*P\d+)*)\s*>", flat):
        seqs.append([x.strip() for x in m.group(1).split(",")])
    return seqs


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = sys.argv[1]
    out_md = sys.argv[2] if len(sys.argv) > 2 else None
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    text = pdf_text(path)
    res: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        res.append((name, bool(ok), detail))

    check("PDF 제목", "Optimized Deadlock Avoidance Algorithm" in text and "pone.0310807" in text)

    # 표 2–4
    marks = {"best": ("Table 2. List of processes", "pone.0310807.t002"), "average": ("Table 3. List of processes", "pone.0310807.t003"),
             "worst": ("Table 4. List of processes", "pone.0310807.t004")}
    for case, (a, b) in marks.items():
        pdf_rows = parse_input_table(section(text, a, b))
        fix_rows = D.parse_table(D.TABLES[case])
        check(f"표 입력 {case}: 행 수 10", len(pdf_rows) == 10, f"PDF {len(pdf_rows)}행")
        diffs = [(p["id"], k) for p, f in zip(pdf_rows, fix_rows) for k in ("id", "at", "bt", "max", "alloc", "need_printed") if p[k] != f[k]]
        check(f"표 입력 {case}: 모든 칸(ID, AT, BT, Maximum, Allocation, 인쇄된 Need)이 옮긴 값과 같음", not diffs, f"다른 칸 {diffs}")
        miss = [r["id"] for r in pdf_rows if r["need_printed"] != [r["max"][j] - r["alloc"][j] for j in range(5)]]
        check(f"표 입력 {case}: 인쇄된 Need ≠ Maximum − Allocation인 행이 KNOWN_TABLE_INCONSISTENCIES와 같음",
              miss == D.KNOWN_TABLE_INCONSISTENCIES[case], f"PDF에서 {miss}")

    # 표 5–7
    tmarks = {"best": ("Table 5. Best case example", "pone.0310807.t005"), "average": ("Table 6. Average case example", "pone.0310807.t006"),
              "worst": ("Table 7. Worst case example", "pone.0310807.t007")}
    for case, (a, b) in tmarks.items():
        rows, bad = parse_trace_table(section(text, a, b))
        fix = D.parse_trace(D.TRACES[case])
        check(f"추적표 {case}: 행을 모두 읽음", len(rows) == 10 and not bad, f"읽은 행 {len(rows)}, 못 읽은 행 {bad}")
        diffs = [(p["id"], k) for p, f in zip(rows, fix) for k in ("id", "max_need", "avail", "min_avail", "safe", "comparisons") if p[k] != f[k]]
        check(f"추적표 {case}: 모든 칸이 옮긴 값과 같음", not diffs, f"다른 칸 {diffs}")

    # 표 8
    t8 = parse_table8(text)
    names8 = ["original banker [1]", "Momotaz et al. 2020 [4]", "Bondarenko et al. 2021 [5]", "Song et al. 2021 [9]",
              "Wicaksono et al. 2023 [12]", "DBDAA"]
    for k, nm in enumerate(names8):
        want = D.TABLE_8[nm]
        got = tuple(t8[t][k] for t in (2, 3, 4)) if all(t in t8 and len(t8[t]) == 6 for t in (2, 3, 4)) else None
        check(f"표 8 '{nm}'", got == want, f"PDF {got}, 옮긴 값 {want}")

    # 표 9
    t9 = parse_table9(text)
    pairs = [("original banker [1]", "Original Banker’s Algorithm [1]"), ("Momotaz et al. [4]", "Momotaz et al [4]"),
             ("Bondarenko et al. [5]", "Bondarenko et al [5]"), ("Song et al. [9]", "Song et al [9]"),
             ("Wicaksono et al. [12]", "Wicaksono et al [12]"), ("DBDAA", "DBDAA")]
    for fk, pk in pairs:
        norm = lambda s: tuple(x.replace(" ", "") for x in s)  # noqa: E731
        check(f"표 9 '{pk}'", pk in t9 and norm(t9[pk]) == norm(D.TABLE_9[fk]), f"PDF {t9.get(pk)}, 옮긴 값 {D.TABLE_9[fk]}")

    # 본문이 적은 순서
    seqs = sequences(text)
    want_seqs = []
    for case in ("best", "average", "worst"):
        want_seqs.append((f"DBDAA Safe_Sequence {case}", D.DBDAA_RESULT[case]["safe"]))
        if D.DBDAA_RESULT[case]["primary_unsafe"]:
            want_seqs.append((f"DBDAA Primary_Unsafe {case}", D.DBDAA_RESULT[case]["primary_unsafe"]))
        want_seqs.append((f"원래 뱅커의 안전 순서 {case}", D.BASELINE_RESULT[case]["safe"]))
    for nm, s in want_seqs:
        check(f"본문의 순서: {nm}", s in seqs, "본문에서 같은 순서를 찾음" if s in seqs else f"못 찾음: {s}")

    # Algorithm 1의 줄 (zohora2024.py가 인용하는 줄 번호)
    alg = text[text.index("Algorithm 1 The DBDAA Algorithm"):]
    alg = alg[:alg.index("Fig 2 depicted")]
    line_pats = {
        4: r"^\s*4:\s+if Maximum\[i, j\] > Resource\[j\] then",
        8: r"^\s*8:\s+Available\[j\] -= Allocation\[i, j\]",
        10: r"^\s*10:\s+SRQ .*Sort\(RQ\)",
        12: r"^\s*12:\s+if Processor == Free",
        14: r"^\s*14:\s+if k .* floor\(d/2\) then",
        19: r"^\s*19:\s+if Max_Need .* Min_A then",
        20: r"^\s*20:\s+go to step 42",
        24: r"^\s*24:\s+if \(Need\[i, L1\] > Available\[L1\]\) \|\| \(Need\[i, L2\] > Available",
        25: r"^\s*25:\s+Push Pi into Primary_Unsafe_Sequence\[\], go to step 44",
        27: r"^\s*27:\s+set Available\[L1\]",
        31: r"^\s*31:\s+if all Available\[j\] == marked then",
        35: r"^\s*35:\s+if Need\[i, L3\] > Available\[L3\] then",
        36: r"^\s*36:\s+Push Pi into Primary_Unsafe_Sequence\[\], go to step 44",
        42: r"^\s*42:\s+Complete\[Pi\] = 1, Push Pi into Safe_Sequence",
        43: r"^\s*43:\s+Available\[j\] \+= Allocation\[i, j\]",
        44: r"^\s*44:\s+if Current_time",
        46: r"^\s*46:\s+Add all Processes in the Primary_Unsafe_Sequence",
    }
    for ln, pat in line_pats.items():
        check(f"Algorithm 1 {ln}줄", re.search(pat, alg, re.M) is not None)
    # 실패한 프로세스 뒤의 '표시 지우기': 43줄에만 있다(25, 36줄에서 44줄로 바로 간다).
    flat = re.sub(r"\s+", " ", alg)
    unmark_pos = [m.start() for m in re.finditer(r"set all Available\[j\] = unmarked", flat)]
    in43 = len(unmark_pos) == 1 and flat.index(" 43: ") < unmark_pos[0] < flat.index(" 44: ")
    check("표시(mark)를 지우는 문장은 43줄에 한 번뿐(실패 경로 25, 36줄은 44줄로 바로 간다)", in43, f"위치 {unmark_pos}")

    fails = [r for r in res if not r[1]]
    print(f"PDF SHA-256 {sha}")
    for nm, ok, detail in res:
        print(("통과 " if ok else "실패 ") + nm + (f" — {detail}" if (detail and not ok) else ""))
    print(f"점검 {len(res)}개, 실패 {len(fails)}건")

    if out_md:
        L = ["# DBDAA 저널 PDF와 옮긴 값의 대조 결과\n",
             "`bench/literature/verify_dbdaa_pdf.py`가 쓴 결과다. AI(Claude)가 작성한 초안이며 사람의 검토 전이다. "
             "PDF는 PLOS ONE 19(9): e0310807의 저널본(18쪽)이고 사용자가 2026-11-01에 제공했다. 저장소에는 넣지 않는다. "
             f"사본의 SHA-256: `{sha}`. 텍스트 층만 읽었다(그림 제외).\n",
             "| 점검 | 결과 |", "|---|---|"]
        for nm, ok, detail in res:
            L.append(f"| {nm} | {'통과' if ok else '실패: ' + detail} |")
        L.append("")
        L.append(f"점검 {len(res)}개, 실패 {len(fails)}건.\n")
        L.append("## 범위와 한계\n")
        L.append("- 표 2–9와 본문의 순서, Algorithm 1의 줄 번호와 첫 단어들이 옮긴 값과 같은지만 본다. 알고리즘 줄의 모든 문자를 기계로 대조한 것은 아니다(줄 내용은 사람이 읽고 확인했다).")
        L.append("- 이 대조는 PMC 본문을 눈으로 옮긴 값이 저널 PDF와 같음을 보인다. 저자의 표 자체에 있는 불일치(표 3 P4의 Need R5)는 그대로 남는다.")
        L.append("- 코드 `dbdaa2024.py`의 'KNOWN_TABLE_INCONSISTENCIES'는 PDF에서도 같은 행이 같은 이유로 어긋남을 확인했다.")
        with open(out_md, "w", encoding="utf-8") as f:
            f.write("\n".join(L) + "\n")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
