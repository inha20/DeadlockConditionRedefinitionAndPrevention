#!/usr/bin/env python3
"""docs/rq2/grid.md의 표를 읽어 격자 문서의 일관성을 점검한다.

사용법:
    python3 -I analysis/rq2/check_grid.py                  # 점검과 자체 시험, 요약 출력
    python3 -I analysis/rq2/check_grid.py --report PATH    # 같은 내용을 보고서 파일로 저장

점검하는 것(문헌의 내용이 아니라 문서의 형식과 일관성):
  - 칸 수 216, 상태를 가진 칸 66, 해당 없음 150이 규칙 G1–G5와 표의 '—'와 맞는지
  - 상태 어휘, 인용한 항목의 존재, 항목의 '칸' 열과 칸의 인용이 서로 맞는지
  - 상태별 조건(알려짐은 A/A− 근거, 초록 수준은 B만, 2차 서술은 2차만, 이웃만은 이웃 항목만 등)
  - 상속 칸의 부모, 이웃만/빈칸 후보와 같은 제한 행의 이웃 칸 상태
  - §0의 상태별 집계와 30% 기준 수치, §5.0의 후보 칸(후보는 표에서 빠지지 않는다.
    주 칸이 알려짐 계열이 된 후보는 정식화 열에 '문헌에서 발견'이 있어야 하고 그 역도 성립한다)
  - 본문이 언급하는 칸 ID, 항목 ID, 대장 ID의 존재
자체 시험은 읽어 들인 모델을 일부러 망가뜨려 점검이 잡아내는지 본다.
"""
import copy
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DOC = os.path.join(ROOT, "docs", "rq2", "grid.md")
LEDGER = os.path.join(ROOT, "refs", "claims-ledger.md")

TYPES = ["DET", "SAFE", "MAXP", "PRED", "VER", "DIST"]
PRIMARY = ["DET", "SAFE", "MAXP"]
NEIGHBOR = ["PRED", "VER", "DIST"]
KS = ["K0", "K1", "K2", "K3"]
RS = ["R%d" % i for i in range(9)]
STATUSES = ["알려짐", "알려짐(초록 수준)", "알려짐(상속)", "2차 서술",
            "이웃만", "빈칸 후보", "미확인"]
FILLED = ("알려짐", "알려짐(초록 수준)")          # 이웃 칸이 '채워졌다'고 보는 상태
LITERATURE = ("알려짐", "알려짐(초록 수준)", "2차 서술")   # 후보의 주 칸이 이 상태이면 '문헌에서 발견'
FOUND = "문헌에서 발견"
INSTANCE_R = {"R1", "R2", "R3", "R5", "R6", "R7", "R8"}   # 인스턴스 부분 클래스
NEIGHBOR_K = {"PRED": "K2", "VER": "K3", "DIST": "K3"}
SAME_OK = ("예", "부분")

CELL_RE = re.compile(
    r"^(알려짐\(초록 수준\)|알려짐\(상속\)|알려짐|2차 서술|이웃만|빈칸 후보|미확인|—)"
    r"(?:\s*\((.*)\))?$")
CELLID_RE = re.compile(r"\b(DET|SAFE|MAXP|PRED|VER|DIST)\.(K[0-3])\.(R[0-8])\b")
ENTRYID_RE = re.compile(r"\b(DET|SAFE|MAXP|PRED|VER|DIST)-(\d+)\b")
LEDGER_RE = re.compile(r"\bC-(?:SUR|RQ1|RQ3)-\d{3}\b")
LEDGER_RANGE_RE = re.compile(r"\bC-(SUR|RQ1|RQ3)-(\d{3})[–-](\d{3})\b")


def well_formed(t, k, r):
    """규칙 G1–G5(문서 §1.4)."""
    if t == "DET":                       # G1, G4
        return k == "K0" and r in ("R0", "R1", "R2", "R3", "R4", "R5")
    if t in ("SAFE", "MAXP"):            # G2, G4
        if k == "K0":
            return False
        if r in ("R6", "R7", "R8") and k != "K3":
            return False
        return True
    # 이웃: G3, G4, G5
    return k == NEIGHBOR_K[t] and r not in ("R5", "R6", "R7")


def all_cells():
    return [(t, k, r) for t in TYPES for k in KS for r in RS]


def pct(a, b):
    from decimal import Decimal, ROUND_HALF_UP
    if not b:
        return "0.0"
    return str((Decimal(100 * a) / Decimal(b)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def cid(cell):
    return "%s.%s.%s" % cell


def parse_cid(s):
    m = CELLID_RE.fullmatch(s.strip())
    return (m.group(1), m.group(2), m.group(3)) if m else None


# ---------------------------------------------------------------- 파싱

def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def read_table(lines, i):
    """lines[i]가 표 머리줄. (머리 칸 목록, 행 목록, 다음 인덱스)를 돌려준다."""
    head = split_row(lines[i])
    j = i + 2                              # 구분선 건너뜀
    rows = []
    while j < len(lines) and lines[j].lstrip().startswith("|"):
        rows.append(split_row(lines[j]))
        j += 1
    return head, rows, j


def level_classes(text):
    out = set()
    for tok in [x.strip() for x in text.split(",")]:
        if tok.startswith("A−(2차)"):
            out.add("second")
        elif tok in ("A", "A−"):
            out.add("A")
        elif tok in ("B", "C", "D", "V"):
            out.add(tok)
        elif tok:
            out.add("?" + tok)
    return out


def parse_cells_field(text):
    used, notes = [], []
    for part in [p.strip() for p in text.split(";")]:
        if not part:
            continue
        if part.startswith("참고:"):
            notes += [x.strip() for x in part[3:].split(",") if x.strip()]
        else:
            used += [x.strip() for x in part.split(",") if x.strip()]
    return used, notes


def parse_doc(text):
    lines = text.splitlines()
    model = {"cells": {}, "entries": {}, "tally": {}, "cands": [],
             "nums": {}, "text_cells": set(), "text_entries": set(),
             "ledger_ids": set(), "problems": []}
    section = ""
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("#"):
            section = ln
        # 격자 표
        m = re.match(r"^### 2\.\d+ (DET|SAFE|MAXP|PRED|VER|DIST)\b", ln)
        if m:
            t = m.group(1)
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith("|"):
                j += 1
            head, rows, nxt = read_table(lines, j)
            kcols = head[1:]
            for row in rows:
                r = row[0]
                for kc, raw in zip(kcols, row[1:]):
                    mm = CELL_RE.match(raw)
                    if not mm:
                        model["problems"].append("표 칸 형식 오류: %s %s %s '%s'" % (t, kc, r, raw))
                        continue
                    status, inner = mm.group(1), mm.group(2)
                    refs, parent = [], None
                    if inner:
                        if inner.startswith("←"):
                            parent = parse_cid(inner[1:])
                        else:
                            refs = [x.strip() for x in inner.split(",") if x.strip()]
                    model["cells"][(t, kc, r)] = {"status": status, "refs": refs,
                                                  "parent": parent}
            i = nxt
            continue
        # 항목 표
        m = re.match(r"^### 3\.\d+ (DET|SAFE|MAXP|PRED|VER|DIST) 항목", ln)
        if m:
            t = m.group(1)
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith("|"):
                j += 1
            head, rows, nxt = read_table(lines, j)
            col = {h: n for n, h in enumerate(head)}
            for row in rows:
                eid = row[col["ID"]]
                used, notes = parse_cells_field(row[col["칸"]])
                ent = {"type": t, "levels": level_classes(row[col["수준"]]),
                       "same": row[col["같은 문제"]] if "같은 문제" in col else None,
                       "cells": used, "notes": notes,
                       "source": row[col["출처"]]}
                model["entries"][eid] = ent
            i = nxt
            continue
        # 집계 표
        if ln.startswith("| 상태 | 기본 유형 |"):
            head, rows, nxt = read_table(lines, i)
            for row in rows:
                if row[0] == "합계":
                    model["tally"]["합계"] = tuple(int(x) for x in row[1:4])
                else:
                    model["tally"][row[0]] = tuple(int(x) for x in row[1:4])
            i = nxt
            continue
        # 후보 표
        if ln.startswith("| 후보 | 주 칸 |"):
            head, rows, nxt = read_table(lines, i)
            for row in rows:
                rel = [x.strip() for x in row[2].split(";") if x.strip() and x.strip() != "—"]
                model["cands"].append((row[0], row[1], rel, row[3] if len(row) > 3 else ""))
            i = nxt
            continue
        i += 1
    # 본문 전체의 언급
    for mm in CELLID_RE.finditer(text):
        model["text_cells"].add((mm.group(1), mm.group(2), mm.group(3)))
    for mm in ENTRYID_RE.finditer(text):
        model["text_entries"].add(mm.group(0))
    for mm in LEDGER_RE.finditer(text):
        model["ledger_ids"].add(mm.group(0))
    for mm in LEDGER_RANGE_RE.finditer(text):
        a, b = int(mm.group(2)), int(mm.group(3))
        for n in range(a, b + 1):
            model["ledger_ids"].add("C-%s-%03d" % (mm.group(1), n))
    # 수치 문장
    m1 = re.search(r"미확인이 (\d+)칸\((\d+)%\)", text)
    m2 = re.search(r"기본 유형 48칸 중 미확인 (\d+)칸\(([\d.]+)%\)", text)
    m3 = re.search(r"66칸 기준으로는 (\d+)칸\(([\d.]+)%\)", text)
    model["nums"] = {"s0": m1.groups() if m1 else None,
                     "s73": m2.groups() if m2 else None,
                     "s73all": m3.groups() if m3 else None}
    return model


def read_ledger_ids():
    ids = set()
    with open(LEDGER, encoding="utf-8") as f:
        for ln in f:
            m = re.match(r"^\| (C-[A-Z0-9]+-\d{3}) \|", ln)
            if m:
                ids.add(m.group(1))
    return ids


# ---------------------------------------------------------------- 점검

def check(model, ledger_ids):
    P = list(model["problems"])
    cells, entries = model["cells"], model["entries"]

    # 1. 칸 집합
    wf = {c for c in all_cells() if well_formed(*c)}
    if len(all_cells()) != 216:
        P.append("전체 칸 수가 216이 아니다")
    if len(wf) != 66:
        P.append("규칙에서 나온 상태 칸 수가 66이 아니다: %d" % len(wf))
    for c in wf:
        if c not in cells:
            P.append("표에 칸이 없다: " + cid(c))
        elif cells[c]["status"] == "—":
            P.append("규칙상 상태가 있어야 하는 칸이 '—'다: " + cid(c))
    for c, v in cells.items():
        if c not in wf and v["status"] != "—":
            P.append("규칙상 해당 없음인 칸에 상태가 있다: %s %s" % (cid(c), v["status"]))
        if c in wf and v["status"] not in STATUSES and v["status"] != "—":
            P.append("상태 어휘 오류: " + cid(c))
    # 2. 항목의 칸 열
    for eid, e in entries.items():
        if not re.fullmatch(r"(DET|SAFE|MAXP|PRED|VER|DIST)-\d+", eid):
            P.append("항목 ID 형식 오류: " + eid)
        if not eid.startswith(e["type"] + "-"):
            P.append("항목 ID가 표의 유형과 다르다: " + eid)
        for sref in e["cells"] + e["notes"]:
            c = parse_cid(sref)
            if c is None or c not in wf:
                P.append("항목 %s의 칸 열에 상태 칸이 아닌 ID가 있다: %s" % (eid, sref))
        for sref in e["cells"]:
            c = parse_cid(sref)
            if c and c[0] != e["type"] and e["type"] in PRIMARY:
                P.append("항목 %s가 다른 유형의 칸을 근거로 든다: %s" % (eid, sref))
        for lid in LEDGER_RE.findall(e["source"]):
            if lid not in ledger_ids:
                P.append("항목 %s의 출처에 대장에 없는 ID: %s" % (eid, lid))
        if not e["levels"] or any(x.startswith("?") for x in e["levels"]):
            P.append("항목 %s의 수준을 읽지 못했다" % eid)
        if e["type"] in PRIMARY and e["same"] not in ("예", "부분", "아니오"):
            P.append("항목 %s의 '같은 문제' 값 오류: %s" % (eid, e["same"]))
    # 3. 칸별 상태 조건
    def row_filled(r):
        """같은 제한 행에서 채워진 이웃 칸이 있는가"""
        return [c for c in wf if c[0] in NEIGHBOR and c[2] == r
                and cells[c]["status"] in FILLED]

    for c in sorted(wf):
        v = cells.get(c)
        if not v:
            continue
        t, k, r = c
        s, refs = v["status"], v["refs"]
        for ref in refs:
            if ref not in entries:
                P.append("칸 %s가 없는 항목을 인용한다: %s" % (cid(c), ref))
        ents = [entries[x] for x in refs if x in entries]
        # 인용과 항목의 칸 열이 서로 맞는가
        if s != "이웃만":
            for ref in refs:
                e = entries.get(ref)
                if e and cid(c) not in e["cells"]:
                    P.append("칸 %s가 인용한 %s의 칸 열에 이 칸이 없다" % (cid(c), ref))
        if s == "미확인" and refs:
            P.append("미확인 칸이 항목을 인용한다: " + cid(c))
        if s == "빈칸 후보" and refs:
            P.append("빈칸 후보 칸이 항목을 인용한다: " + cid(c))
        if t in PRIMARY and s in ("알려짐", "알려짐(초록 수준)", "2차 서술"):
            if not refs:
                P.append("근거 없는 %s: %s" % (s, cid(c)))
            for x, e in zip(refs, ents):
                if e["type"] != t:
                    P.append("칸 %s가 다른 유형 항목 %s를 근거로 든다" % (cid(c), x))
        if t in NEIGHBOR:
            if s in ("이웃만", "빈칸 후보", "알려짐(상속)", "2차 서술"):
                P.append("이웃 유형 칸에 쓸 수 없는 상태 %s: %s" % (s, cid(c)))
            for x, e in zip(refs, ents):
                if e["type"] != t:
                    P.append("이웃 칸 %s가 다른 유형 항목 %s를 인용한다" % (cid(c), x))
        if s == "알려짐":
            good = [e for e in ents if "A" in e["levels"]
                    and (e["same"] in SAME_OK or t in NEIGHBOR)]
            if not good:
                P.append("알려짐 칸에 A/A− 근거가 없다: " + cid(c))
        if s == "알려짐(초록 수준)":
            if not any("B" in e["levels"] for e in ents):
                P.append("초록 수준 칸에 B 근거가 없다: " + cid(c))
            if any("A" in e["levels"] for e in ents):
                P.append("A/A− 근거가 있는 칸을 초록 수준으로 적었다: " + cid(c))
        if s == "2차 서술":
            if not all("second" in e["levels"] for e in ents) or not ents:
                P.append("2차 서술 칸에 2차가 아닌 근거: " + cid(c))
        if s == "알려짐(상속)":
            if r not in INSTANCE_R:
                P.append("모델 확장 또는 R0 칸에 상속을 썼다: " + cid(c))
            par = v["parent"]
            if par != (t, k, "R0"):
                P.append("상속 칸의 부모가 같은 유형·K의 R0이 아니다: " + cid(c))
            elif cells.get(par, {}).get("status") not in FILLED:
                P.append("상속 칸의 부모가 알려짐 계열이 아니다: " + cid(c))
            if refs:
                P.append("상속 칸이 항목을 직접 인용한다: " + cid(c))
        if s == "이웃만":
            if t not in PRIMARY:
                P.append("이웃만이 기본 유형이 아닌 칸에: " + cid(c))
            if not refs:
                P.append("이웃만 칸에 이웃 항목이 없다: " + cid(c))
            for x, e in zip(refs, ents):
                if e["type"] not in NEIGHBOR:
                    P.append("이웃만 칸이 이웃 유형이 아닌 항목을 인용한다: %s %s" % (cid(c), x))
                else:
                    ok = any((parse_cid(sx) or ("", "", ""))[2] == r
                             and parse_cid(sx)[0] in NEIGHBOR for sx in e["cells"])
                    if not ok:
                        P.append("이웃만 칸이 인용한 %s가 같은 제한 행(%s)의 이웃 칸을 채우지 않는다: %s" % (x, r, cid(c)))
            if not row_filled(r):
                P.append("이웃만인데 같은 제한 행에 채워진 이웃 칸이 없다: " + cid(c))
        if s == "빈칸 후보":
            if t not in PRIMARY:
                P.append("빈칸 후보가 기본 유형이 아닌 칸에: " + cid(c))
            if row_filled(r):
                P.append("빈칸 후보인데 같은 제한 행에 채워진 이웃 칸이 있다(이웃만이어야 함): " + cid(c))
    # 4. 항목이 칸을 근거로 든다고 적었는데 칸이 인용하지 않는 경우
    for eid, e in entries.items():
        for sref in e["cells"]:
            c = parse_cid(sref)
            if c in cells and eid not in cells[c]["refs"]:
                P.append("항목 %s의 칸 열에 있으나 칸 %s가 인용하지 않는다" % (eid, sref))
    # 5. 집계
    comp = {s: [0, 0] for s in STATUSES}
    for c in wf:
        s = cells[c]["status"]
        if s in comp:
            comp[s][0 if c[0] in PRIMARY else 1] += 1
    tal = model["tally"]
    for s in STATUSES:
        got = tal.get(s)
        want = (comp[s][0], comp[s][1], comp[s][0] + comp[s][1])
        if got != want:
            P.append("집계 불일치 %s: 문서 %s, 계산 %s" % (s, got, want))
    nb = sum(v[0] for v in comp.values())
    ne = sum(v[1] for v in comp.values())
    if tal.get("합계") != (nb, ne, nb + ne):
        P.append("합계 불일치: 문서 %s, 계산 %s" % (tal.get("합계"), (nb, ne, nb + ne)))
    # 6. 30% 기준 수치
    un_b, un_n = comp["미확인"]
    share = 100.0 * un_b / nb if nb else 0.0
    share_all = 100.0 * (un_b + un_n) / (nb + ne) if nb + ne else 0.0
    n0, n73, n73a = model["nums"]["s0"], model["nums"]["s73"], model["nums"]["s73all"]
    if not n0 or int(n0[0]) != un_b or abs(int(n0[1]) - share) > 1:
        P.append("§0의 미확인 수치가 계산과 다르다: %s vs %d칸 %.1f%%" % (n0, un_b, share))
    if not n73 or int(n73[0]) != un_b or abs(float(n73[1]) - share) > 0.0501:
        P.append("§7.3의 기본 유형 수치가 계산과 다르다: %s vs %d칸 %.2f%%" % (n73, un_b, share))
    if not n73a or int(n73a[0]) != un_b + un_n or abs(float(n73a[1]) - share_all) > 0.0501:
        P.append("§7.3의 전체 수치가 계산과 다르다: %s vs %d칸 %.2f%%" % (n73a, un_b + un_n, share_all))
    # 7. 후보 표. 후보는 표에서 빠지지 않는다(prereg §8). 주 칸이 알려짐 계열로 바뀐 후보는
    #    정식화 열에 FOUND 표시가 있어야 하고, FOUND 표시가 있으면 주 칸이 알려짐 계열이어야 한다.
    names = [x[0] for x in model["cands"]]
    if names != ["(i)", "(ii)", "(iii)"]:
        P.append("후보 표의 행이 (i), (ii), (iii)이 아니다: %s" % names)
    for name, main, rel, form in model["cands"]:
        c = parse_cid(main)
        found = FOUND in form
        if c is None or c not in wf:
            P.append("후보 %s의 주 칸이 상태 칸이 아니다: %s" % (name, main))
        elif found:
            if cells[c]["status"] not in LITERATURE:
                P.append("후보 %s는 '%s'로 적혔는데 주 칸 상태가 알려짐 계열이 아니다: %s %s" % (
                    name, FOUND, main, cells[c]["status"]))
        elif cells[c]["status"] not in ("이웃만", "빈칸 후보"):
            P.append("후보 %s의 주 칸 상태가 후보 계열이 아니다(알려짐 계열이면 정식화 열에 '%s'를 적어야 한다): %s %s" % (
                name, FOUND, main, cells[c]["status"]))
        for x in rel:
            cc = parse_cid(x)
            if cc is None or cc not in wf:
                P.append("후보 %s의 관련 칸이 상태 칸이 아니다: %s" % (name, x))
    # 8. 본문의 언급
    for c in model["text_cells"]:
        if c not in wf:
            P.append("본문이 상태 칸이 아닌 칸을 언급한다: " + cid(c))
    for x in model["text_entries"]:
        if x not in entries:
            P.append("본문이 없는 항목 ID를 언급한다: " + x)
    for lid in model["ledger_ids"]:
        if lid not in ledger_ids:
            P.append("본문이 대장에 없는 ID를 언급한다: " + lid)
    # 9. 이웃 항목이 기본 유형 칸에서 근거로 쓰이지 않았는지(이웃만 제외)
    for c in sorted(wf):
        v = cells.get(c)
        if v and c[0] in PRIMARY and v["status"] not in ("이웃만",):
            for ref in v["refs"]:
                if ref in entries and entries[ref]["type"] in NEIGHBOR:
                    P.append("기본 유형 칸 %s가 이웃 항목 %s를 근거로 든다" % (cid(c), ref))
    return P


# ---------------------------------------------------------------- 자체 시험

def mutations(model):
    """(이름, 망가진 모델) 목록. 각각 점검이 문제를 하나 이상 잡아야 한다."""
    out = []

    def m(name, fn):
        mm = copy.deepcopy(model)
        fn(mm)
        out.append((name, mm))

    cells, entries = lambda x: x["cells"], lambda x: x["entries"]
    m("잘못된 상태 어휘", lambda x: x["cells"][("SAFE", "K3", "R0")].update(status="확정"))
    m("알려짐 칸의 근거를 B 항목만 남김",
      lambda x: x["cells"][("DET", "K0", "R0")].update(refs=["DET-3"]))
    m("알려짐 칸에서 근거 제거",
      lambda x: x["cells"][("SAFE", "K3", "R6")].update(refs=[]))
    m("이웃만 칸이 같은 유형 항목을 인용",
      lambda x: x["cells"][("SAFE", "K3", "R1")].update(refs=["SAFE-4"]))
    m("이웃만 칸이 인용한 이웃 항목이 다른 행의 칸을 채움",
      lambda x: x["cells"][("SAFE", "K3", "R4")].update(refs=["VER-4"]))
    m("상속 칸의 부모를 미확인 칸으로", lambda x: x["cells"][("DET", "K0", "R1")].update(
        parent=("MAXP", "K1", "R0")))
    m("모델 확장 칸에 상속", lambda x: x["cells"][("DET", "K0", "R4")].update(
        status="알려짐(상속)", refs=[], parent=("DET", "K0", "R0")))
    m("해당 없음 칸에 상태", lambda x: x["cells"].__setitem__(
        ("DET", "K0", "R6"), {"status": "알려짐", "refs": ["DET-1"], "parent": None}))
    m("상태 칸을 '—'로", lambda x: x["cells"][("SAFE", "K3", "R3")].update(status="—", refs=[]))
    m("빈칸 후보인데 이웃 행이 채워짐",
      lambda x: x["cells"][("SAFE", "K3", "R3")].update(status="빈칸 후보", refs=[]))
    m("이웃만인데 이웃 행이 비었음",
      lambda x: x["cells"][("SAFE", "K3", "R5")].update(status="이웃만", refs=["PRED-2"]))
    m("미확인 칸이 항목을 인용",
      lambda x: x["cells"][("MAXP", "K1", "R0")].update(refs=["MAXP-7"]))
    m("항목의 칸 열에서 인용 칸을 지움",
      lambda x: x["entries"]["SAFE-5"].update(cells=[]))
    m("없는 항목 인용", lambda x: x["cells"][("SAFE", "K1", "R0")].update(refs=["SAFE-1", "SAFE-77"]))
    m("집계 틀림", lambda x: x["tally"].update({"미확인": (26, 8, 34)}))
    m("후보 주 칸을 알려짐 칸으로(문헌 발견 표시 없이)",
      lambda x: x["cands"].__setitem__(1, ("(ii)", "SAFE.K3.R0", [], "§5.2")))
    m("주 칸이 알려짐이 된 후보에서 문헌 발견 표시를 지움",
      lambda x: x["cands"].__setitem__(0, x["cands"][0][:3] + ("§5.1",)))
    m("문헌 발견 표시인데 주 칸이 이웃만",
      lambda x: x["cands"].__setitem__(1, ("(ii)", "SAFE.K3.R1", [], "§5.2. 문헌에서 발견")))
    m("알려짐 칸을 빈칸 후보로 되돌리고 집계·후보 표는 그대로",
      lambda x: x["cells"][("SAFE", "K3", "R2")].update(status="빈칸 후보", refs=[]))
    m("2차 서술 칸에 A 항목", lambda x: x["cells"][("SAFE", "K3", "R7")].update(refs=["SAFE-4"]))
    m("초록 수준 칸에 A 항목", lambda x: x["cells"][("SAFE", "K1", "R5")].update(refs=["SAFE-1"]))
    m("항목의 대장 ID가 없음",
      lambda x: x["entries"]["DET-1"].update(source="M14 §2.2. C-SUR-999"))
    m("본문이 해당 없음 칸을 언급", lambda x: x["text_cells"].add(("DET", "K1", "R0")))
    m("30% 수치 틀림", lambda x: x["nums"].update(s0=("20", "40")))
    m("이웃 칸에 상속", lambda x: x["cells"][("VER", "K3", "R1")].update(
        status="알려짐(상속)", parent=("VER", "K3", "R0")))
    m("기본 유형 칸이 이웃 항목을 근거로(이웃만이 아닌 상태)",
      lambda x: x["cells"][("SAFE", "K3", "R0")].update(refs=["SAFE-4", "VER-4"]))
    return out


def run(report_path=None):
    with open(DOC, encoding="utf-8") as f:
        text = f.read()
    model = parse_doc(text)
    ledger_ids = read_ledger_ids()
    problems = check(model, ledger_ids)

    lines = []
    lines.append("# RQ2 격자 문서 점검 보고서")
    lines.append("")
    lines.append("- 대상: `docs/rq2/grid.md`")
    lines.append("- 생성: `python3 -I analysis/rq2/check_grid.py --report formal/rq2/grid-check.md`")
    lines.append("- 이 보고서는 문서의 형식과 일관성을 점검한 것이며 문헌 내용의 옳고 그름은 점검하지 않는다.")
    lines.append("")
    wf = [c for c in all_cells() if well_formed(*c)]
    lines.append("## 칸 구성")
    lines.append("")
    lines.append("| 항목 | 값 |")
    lines.append("|---|---|")
    lines.append("| 전체 칸(6 유형 × K0–K3 × R0–R8) | %d |" % len(all_cells()))
    lines.append("| 상태를 가진 칸 | %d |" % len(wf))
    lines.append("| 규칙으로 해당 없음 | %d |" % (len(all_cells()) - len(wf)))
    for t in TYPES:
        lines.append("| %s 상태 칸 | %d |" % (t, sum(1 for c in wf if c[0] == t)))
    lines.append("")
    comp = {s: [0, 0] for s in STATUSES}
    for c in wf:
        if c in model["cells"] and model["cells"][c]["status"] in comp:
            comp[model["cells"][c]["status"]][0 if c[0] in PRIMARY else 1] += 1
    lines.append("## 표에서 다시 센 상태별 칸 수")
    lines.append("")
    lines.append("| 상태 | 기본 유형 | 이웃 유형 | 합계 |")
    lines.append("|---|---|---|---|")
    for s in STATUSES:
        lines.append("| %s | %d | %d | %d |" % (s, comp[s][0], comp[s][1], sum(comp[s])))
    nb = sum(v[0] for v in comp.values())
    ne = sum(v[1] for v in comp.values())
    lines.append("| 합계 | %d | %d | %d |" % (nb, ne, nb + ne))
    lines.append("")
    if nb:
        lines.append("기본 유형의 미확인 비율: %d/%d = %s%% (계획용 기준 30%%)." % (
            comp["미확인"][0], nb, pct(comp["미확인"][0], nb)))
        lines.append("")
        lines.append("이웃 유형을 합친 미확인 비율: %d/%d = %s%%." % (
            comp["미확인"][0] + comp["미확인"][1], nb + ne,
            pct(comp["미확인"][0] + comp["미확인"][1], nb + ne)))
    lines.append("")
    lines.append("## 점검 결과")
    lines.append("")
    lines.append("- 항목 %d개, 격자 표의 칸 %d개, 후보 %d개를 읽었다." % (
        len(model["entries"]), len(model["cells"]), len(model["cands"])))
    if problems:
        lines.append("- **문제 %d건**" % len(problems))
        for p in problems:
            lines.append("  - " + p)
    else:
        lines.append("- 문제 없음.")
    lines.append("")
    lines.append("## 자체 시험")
    lines.append("")
    lines.append("읽어 들인 모델을 일부러 망가뜨려 점검이 문제를 잡는지 본다. 망가뜨리지 않은 모델은 문제 0건이어야 한다.")
    lines.append("")
    lines.append("| 망가뜨린 곳 | 잡은 문제 수 | 결과 |")
    lines.append("|---|---|---|")
    fail = 0
    base = set(problems)
    for name, mm in mutations(parse_doc(text)):
        n = len(set(check(mm, ledger_ids)) - base)
        ok = n > 0
        fail += 0 if ok else 1
        lines.append("| %s | %d | %s |" % (name, n, "잡음" if ok else "**놓침**"))
    lines.append("")
    lines.append("- 시험 %d건 중 놓친 것 %d건." % (len(mutations(parse_doc(text))), fail))
    out = "\n".join(lines) + "\n"
    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(out)
    print(out)
    return 1 if (problems or fail) else 0


if __name__ == "__main__":
    rp = None
    if "--report" in sys.argv:
        rp = sys.argv[sys.argv.index("--report") + 1]
    sys.exit(run(rp))
