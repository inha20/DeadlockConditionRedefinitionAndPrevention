#!/usr/bin/env python3
"""analysis/rq5/codebook_tools.py의 자체 점검과 코드북 문서와의 일치 점검.

실행: python3 -I analysis/rq5/check_codebook_tools.py formal/rq5/codebook-tools-check.md

점검: (1) 구성한 정상 행(실제 사례가 아님)이 오류 없이 통과, (2) 규칙마다 그 규칙을 어기는 행을 오류로 잡음,
(3) 모든 규칙이 한 번 이상 시험됨, (4) κ가 알려진 값과 같음, (5) 파일럿 추출의 결정성·비복원·회차 사이 분리,
(6) 값 집합이 docs/rq5/codebook.md의 변수별 절에 모두 적혀 있음.
사례(E2 데이터셋의 49건)는 읽지 않았고 아래 행의 커밋 해시는 모두 0으로 채운 가짜다.
AI(Claude)가 쓴 초안이며 사람의 검토 전이다.
"""
from __future__ import annotations

import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import codebook_tools as ct  # noqa: E402

DOC = os.path.join(ROOT, "docs", "rq5", "codebook.md")


def fake(n: int) -> str:
    return f"{n:040x}"          # 0000…000n: 가짜 해시임이 드러나게 0으로 채운다


BASE = {
    "e2_row": "1", "commit": fake(1), "coder": "c1", "round": "pilot1", "status": "coded", "sources": "msg+patch",
    "V1": "own", "V2": "process", "V3": "mutex", "V4": "no", "V5": "2", "V6": "no", "V7": "2", "V8": "classic2",
    "V9": "cycle", "V10": "no", "V11": "no", "V12": "general", "V13": "circular_acq",
    "V10_reason": "", "unc_reason": "", "evidence": "구성한 예(실제 사례 아님)", "note": "",
}


def row(**kw) -> dict:
    r = dict(BASE)
    r.update(kw)
    return r


# 정상 행: (이름, 행)
POSITIVE = [
    ("두 스레드의 락 순서 뒤집힘(고전 순환 대기)", row()),
    ("같은 스레드의 이중 잠금(자기 대기, 직접 호출)",
     row(V2="process", V3="mutex", V4="yes", V5="1", V6="yes", V7="1", V8="self_only", V9="dup", V12="na", V13="double_lock")),
    ("인터럽트 재진입 자기 교착, lockdep 사용 상태 규칙으로 설명됨",
     row(V1="irq_reentry", V2="hardirq+process", V3="spinlock", V4="yes", V5="1", V6="yes", V7="2", V8="no",
         V9="dup+usage", V11="yes", V12="interrupt", V13="na")),
    ("인터럽트 재진입, 고전 모델도 lockdep 규칙도 설명하지 못함(확장 필요)",
     row(V1="irq_reentry", V2="hardirq+process", V3="spinlock", V4="no", V5="2", V6="yes", V7="2", V8="no",
         V9="no", V11="yes", V12="interrupt", V13="na", V10="yes", V10_reason="구성한 예: 같은 CPU에서 처리기가 선점한 문맥이 쥔 락이 원인이라 자율 요청만으로는 기술할 수 없다")),
    ("완료 신호 대기(락이 아닌 대기), 어느 설명도 아님",
     row(V1="own", V2="process", V3="non_lock_wait", V4="no", V5="1", V6="no", V7="2", V8="no", V9="no", V12="na", V13="na")),
    ("간접 호출 경유 이중 잠금", row(V1="indirect_reentry", V4="yes", V5="1", V6="yes", V7="1", V8="self_only", V9="dup", V12="na", V13="double_lock")),
    ("집합 값 여러 개", row(V2="hardirq+process", V3="mutex+spinlock", V9="cycle+usage", V11="yes", V12="interrupt", V1="irq_reentry", V8="no")),
    ("읽을 수 없는 커밋(모든 변수 uncertain, 분모에 남김)",
     row(V1="uncertain", V2="uncertain", V3="uncertain", V4="uncertain", V5="uncertain", V6="uncertain", V7="uncertain",
         V8="uncertain", V9="uncertain", V10="uncertain", V11="uncertain", V12="uncertain", V13="uncertain", sources="other",
         unc_reason="U1", evidence="읽을 수 없음(구성한 예)")),
    ("불확실이 있는 행(전문가 검토 표시)",
     row(V1="uncertain", V8="uncertain", V9="uncertain", V10="uncertain", status="needs_expert", unc_reason="U1+U2", evidence="구성한 예")),
]

# 오류가 나야 하는 행: (이름, 행, 기대 규칙 태그)
NEGATIVE = [
    ("V1 값이 목록 밖", row(V1="autonomous"), "E-value"),
    ("V2가 정렬되지 않음", row(V2="process+hardirq"), "E-value"),
    ("V9에 no와 다른 값을 함께 씀", row(V9="no+cycle"), "E-value"),
    ("V3이 비어 있음", row(V3=""), "E-value"),
    ("sources가 비어 있음", row(sources=""), "E-value"),
    ("sources가 정렬되지 않음", row(sources="patch+msg"), "E-value"),
    ("coder가 목록 밖", row(coder="c3"), "E-value"),
    ("uncertain인데 unc_reason이 없음", row(V4="uncertain"), "E-unc"),
    ("unc_reason 코드가 목록 밖", row(V4="uncertain", unc_reason="U9"), "E-unc"),
    ("coded인데 evidence가 비어 있음", row(evidence=""), "E-evid"),
    ("V10=yes인데 근거 문장이 없음", row(V1="irq_reentry", V8="no", V9="no", V10="yes"), "E-evid"),
    ("commit이 16진수 40자가 아님", row(commit="abc"), "E-type"),
    ("e2_row가 정수가 아님", row(e2_row="x"), "E-type"),
    ("V10=yes인데 V9가 no가 아님", row(V1="irq_reentry", V2="hardirq+process", V8="no", V9="cycle", V10="yes", V10_reason="구성한 예"), "C1"),
    ("V10=yes인데 V8이 uncertain", row(V1="irq_reentry", V2="hardirq+process", V8="uncertain", V9="no", V10="yes", V10_reason="구성한 예", unc_reason="U1"), "C1"),
    ("V10=yes인데 비자율 요청도 프로세스 밖 문맥도 없음", row(V1="own", V2="process", V8="no", V9="no", V10="yes", V10_reason="구성한 예"), "C1b"),
    ("V8=classic2인데 V1이 irq_reentry", row(V1="irq_reentry"), "C2"),
    ("V8=classic2인데 문맥이 하나", row(V7="1"), "C2"),
    ("V8=classic2인데 락이 하나", row(V5="1"), "C2"),
    ("V8=classic2인데 자기 대기", row(V6="yes"), "C2"),
    ("V8=self_only인데 V6=no", row(V8="self_only", V6="no", V9="dup", V4="yes", V5="1", V7="1"), "C3"),
    ("V8=self_only인데 V1=other", row(V8="self_only", V6="yes", V1="other", V9="dup", V4="yes", V5="1", V7="1"), "C3"),
    ("V1=irq_reentry인데 V8=self_only", row(V1="irq_reentry", V8="self_only", V6="yes", V9="dup", V4="yes", V5="1", V7="2"), "C4"),
    ("V9에 dup이 있는데 V4=no", row(V8="no", V9="dup", V4="no"), "C5"),
]
MISSING_COL = dict(BASE)
del MISSING_COL["V13"]
EXTRA_COL = dict(BASE, V14="x")
NEGATIVE_RAW = [
    ("열이 빠짐", MISSING_COL, "E-field"),
    ("알 수 없는 열", EXTRA_COL, "E-field"),
]

# 경고만 나야 하는 행: (이름, 행, 기대 태그)
WARNING = [
    ("V9에 usage가 있는데 V11=no", row(V1="irq_reentry", V8="no", V9="usage", V11="no", V12="interrupt"), "W1"),
    ("V12=interrupt인데 V1=own", row(V12="interrupt"), "W2"),
    ("V3에 non_lock_wait가 있는데 고전 모델로 설명됨", row(V3="non_lock_wait"), "W3"),
    ("V13=double_lock인데 V6=no", row(V13="double_lock"), "W4"),
    ("V1=irq_reentry인데 V12=general", row(V1="irq_reentry", V8="no", V12="general"), "W5"),
]

KAPPA_CASES = [
    # (이름, a, b, 기대 κ, 기대 일치율)
    ("교과서 2x2 예(예예 20, 예아니오 5, 아니오예 10, 아니오아니오 15)",
     ["Y"] * 20 + ["Y"] * 5 + ["N"] * 10 + ["N"] * 15, ["Y"] * 20 + ["N"] * 5 + ["Y"] * 10 + ["N"] * 15, 0.4, 0.7),
    ("완전 일치", list("ABCABC"), list("ABCABC"), 1.0, 1.0),
    ("완전 불일치(균형)", list("ABAB"), list("BABA"), -1.0, 0.0),
    ("세 범주 손계산", list("AABBCC"), list("ABBBCA"), 0.5, 4 / 6),
]


def tags(msgs):
    out = set()
    for m in msgs:
        mm = re.search(r"\[([A-Z][A-Za-z0-9-]*)\]", m)
        if mm:
            out.add(mm.group(1))
    return out


def main(out_path: str) -> int:
    t0 = time.time()
    out_path = os.path.abspath(out_path)
    checks: list[tuple[str, bool, str]] = []

    def check(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    # ---- 1. 정상 행
    for name, r in POSITIVE:
        errs, warns = ct.validate_row(r)
        check(f"정상 행: {name}", not errs, "; ".join(errs))
    errs, warns = ct.validate_rows([r for _, r in POSITIVE[:1]])
    check("빈 표와 한 행 표에서 validate_rows가 오류 없이 동작", not errs and not ct.validate_rows([])[0])

    # ---- 2. 음성
    seen_tags = set()
    for name, r, tag in NEGATIVE + NEGATIVE_RAW:
        errs, _ = ct.validate_row(r)
        got = tags(errs)
        seen_tags |= got
        check(f"위반 행: {name} → {tag}", tag in got, f"실제 규칙 {sorted(got)}")
    dup_errs, _ = ct.validate_rows([POSITIVE[0][1], dict(POSITIVE[0][1])])
    seen_tags |= tags(dup_errs)
    check("위반 행: (commit, coder, round) 중복 → E-dup", "E-dup" in tags(dup_errs), "; ".join(dup_errs))
    for name, r, tag in WARNING:
        errs, warns = ct.validate_row(r)
        seen_tags |= tags(warns)
        check(f"경고 행: {name} → {tag}(오류 없음)", not errs and tag in tags(warns), f"오류 {errs} 경고 {warns}")

    # ---- 3. 규칙 커버리지: 모듈 소스에 있는 모든 규칙 태그가 시험되었는가
    src = open(os.path.join(HERE, "codebook_tools.py"), encoding="utf-8").read()
    defined = set(re.findall(r'\b[ew]\("([A-Z][A-Za-z0-9-]*)"', src))
    missing = defined - seen_tags
    check("모듈에 정의된 모든 규칙 태그를 한 번 이상 시험함", not missing, f"정의 {len(defined)}개, 시험 안 된 것 {sorted(missing)}")

    # ---- 4. 허용되는 (V1, V6, V8) 조합표 (다른 변수는 가장 너그러운 값으로 고정)
    allowed = {}
    for v1 in ct.SINGLE["V1"]:
        for v6 in ct.SINGLE["V6"]:
            for v8 in ct.SINGLE["V8"]:
                ok_any = False
                for v5 in ("1", "2"):
                    for v7 in ("1", "2"):
                        for v4 in ("yes", "no"):
                            r = row(V1=v1, V6=v6, V8=v8, V5=v5, V7=v7, V4=v4, V9="no", V12="na", V13="na",
                                    V2="hardirq+process", unc_reason="U1")
                            if not ct.validate_row(r)[0]:
                                ok_any = True
                allowed[(v1, v6, v8)] = ok_any
    # 손으로 정한 기대: 아래 세 줄은 코드북 §3의 서술이다
    exp_ok = (allowed[("own", "no", "classic2")] and allowed[("own", "yes", "self_only")] and allowed[("indirect_reentry", "yes", "self_only")]
              and not allowed[("irq_reentry", "no", "classic2")] and not allowed[("irq_reentry", "yes", "self_only")]
              and not allowed[("own", "yes", "classic2")] and not allowed[("own", "no", "self_only")])
    check("(V1, V6, V8) 조합표가 코드북 §3의 서술과 같음", exp_ok, f"허용 조합 {sum(allowed.values())}/{len(allowed)}")

    # ---- 5. κ
    for name, a, b, k, po in KAPPA_CASES:
        r = ct.cohen_kappa(a, b)
        check(f"κ: {name}", r["kappa"] is not None and abs(r["kappa"] - k) < 1e-9 and abs(r["po"] - po) < 1e-9,
              f"κ={r['kappa']}, 일치율={r['po']:.4f}")
    r = ct.cohen_kappa(list("AAAA"), list("AAAA"))
    check("κ: 두 코더가 같은 한 범주만 쓰면 정의되지 않음(None), 일치율 1", r["kappa"] is None and r["po"] == 1.0)
    b1 = ct.bootstrap_kappa(KAPPA_CASES[0][1], KAPPA_CASES[0][2])
    b2 = ct.bootstrap_kappa(KAPPA_CASES[0][1], KAPPA_CASES[0][2])
    check("부트스트랩: 같은 입력은 같은 구간(결정성)이고 점추정값 0.4를 감쌈",
          b1 == b2 and b1["lo"] <= 0.4 <= b1["hi"], f"[{b1['lo']:.3f}, {b1['hi']:.3f}], 정의 안 됨 {b1['undefined']}/{b1['reps']}")
    # 파일럿 합격선: 10건에서 변수별로 판정
    commits = [fake(i) for i in range(1, 11)]

    def mk(vals):
        return [row(commit=c, V6=v) for c, v in zip(commits, vals)]
    g = ct.pilot_gate(mk(["yes"] * 5 + ["no"] * 5), mk(["yes"] * 5 + ["no"] * 5), variables=("V6",))
    check("합격선: 완전 일치(두 범주)는 pass", g["V6"]["status"] == "pass" and abs(g["V6"]["kappa"] - 1.0) < 1e-9)
    g = ct.pilot_gate(mk(["yes"] * 5 + ["no"] * 5), mk(["yes"] * 2 + ["no"] * 3 + ["yes"] * 3 + ["no"] * 2), variables=("V6",))
    check("합격선: 일치율 0.4(κ −0.2)는 fail", g["V6"]["status"] == "fail" and g["V6"]["kappa"] < 0.61, f"κ={g['V6']['kappa']:.3f}")
    g = ct.pilot_gate(mk(["no"] * 10), mk(["no"] * 10), variables=("V6",))
    check("합격선: 둘 다 한 범주만 쓰면 undefined_agree(사람이 처리를 정함, O5-11)", g["V6"]["status"] == "undefined_agree")
    g = ct.pilot_gate(mk(["no"] * 10), mk(["no"] * 9 + ["yes"]), variables=("V6",))
    check("합격선: 한 코더만 한 범주면 κ는 0(우연 일치 이상이 아님)이고 fail", g["V6"]["status"] == "fail" and abs(g["V6"]["kappa"]) < 1e-9)
    try:
        ct.pilot_gate(mk(["no"] * 10), [row(commit=fake(99))], variables=("V6",))
        bad = False
    except ValueError:
        bad = True
    check("합격선: 두 코더의 커밋 집합이 다르면 거부", bad)

    # ---- 6. 파일럿 추출
    pool = [fake(i) for i in range(100, 149)]               # 가짜 49건
    p1, p1b = ct.draw_pilot(pool, 10, 1), ct.draw_pilot(list(reversed(pool)), 10, 1)
    p2 = ct.draw_pilot(pool, 10, 2)
    check("파일럿 추출: 결정적(입력 순서와 무관)", p1 == p1b)
    check("파일럿 추출: 10건, 비복원, 모집단의 부분집합, 정렬됨", len(p1) == 10 == len(set(p1)) and set(p1) <= set(pool) and p1 == sorted(p1))
    check("파일럿 추출: 회차 2는 회차 1과 겹치지 않고 10건", len(p2) == 10 and not (set(p1) & set(p2)))
    check("파일럿 추출: 마스터 시드 이름이 다르면 다른 표본", ct.draw_pilot(pool, 10, 1, "다른-이름") != p1)

    # ---- 7. 템플릿
    check("템플릿 머리글이 FIELDS와 같고 열 수가 23(식별 6 + 변수 13 + 부가 4)",
          ct.template_header().split(",") == ct.FIELDS and len(ct.FIELDS) == 23 and len(set(ct.FIELDS)) == 23, f"{len(ct.FIELDS)}열")

    # ---- 7b. 원소별 κ와 agree 명령
    ea = ["cycle", "cycle+usage", "no", "usage"]
    eb = ["cycle", "cycle", "no", "usage"]
    ek = ct.element_kappas(ea, eb, "V9")
    check("원소별 κ: 손계산 값(cycle 1.0, usage 0.5, dup은 쓰이지 않아 정의 안 됨)",
          abs(ek["cycle"]["kappa"] - 1.0) < 1e-9 and abs(ek["usage"]["kappa"] - 0.5) < 1e-9 and ek["dup"]["kappa"] is None,
          f"cycle={ek['cycle']['kappa']}, usage={ek['usage']['kappa']}, dup={ek['dup']['kappa']}")
    check("원소별 κ: 값 집합의 모든 원소(단독 값 포함)를 다룸",
          set(ek) == set(ct.MULTI["V9"]) | set(ct.SOLO["V9"]), f"{sorted(ek)}")

    import contextlib
    import csv
    import io
    import tempfile

    def write_csv(path, rows):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=ct.FIELDS)
            w.writeheader()
            w.writerows(rows)

    def run_agree(p1, p2):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = ct.main(["codebook_tools.py", "agree", p1, p2])
        return code, buf.getvalue()

    ten = [fake(i) for i in range(1, 11)]
    v1_vals = ["own", "indirect_reentry"] * 5
    rows_c1 = [row(commit=c, coder="c1", V1=v) for c, v in zip(ten, v1_vals)]
    rows_c2 = [row(commit=c, coder="c2", V1=v) for c, v in zip(ten, v1_vals)]
    with tempfile.TemporaryDirectory() as td:
        pa, pb, pc = (os.path.join(td, n) for n in ("c1.csv", "c2.csv", "bad.csv"))
        write_csv(pa, rows_c1)
        write_csv(pb, rows_c2)
        code, out = run_agree(pa, pb)
        check("agree: 같은 회차의 두 코더 파일에서 핵심 변수 6개를 보고하고 종료 코드 0",
              code == 0 and all(f"\n{v}: " in "\n" + out for v in ct.KEY_VARS), f"종료 {code}")
        check("agree: V1이 완전 일치하면 κ=1.000, 판정 pass", "V1: 일치율 1.00, κ=1.000" in out and "판정 pass" in out.split("V1:")[1].splitlines()[0])
        check("agree: 한 범주만 쓴 변수는 'κ 정의 안 됨'으로 보고(V6)", "V6: 일치율 1.00, κ 정의 안 됨" in out)
        write_csv(pc, [dict(r, coder="c1") for r in rows_c2])
        code, out = run_agree(pa, pc)
        check("agree: 두 파일의 coder가 같으면 거부(종료 코드 1)", code == 1 and "E-agree" in out)
        write_csv(pc, [dict(r, round="main") for r in rows_c2])
        code, out = run_agree(pa, pc)
        check("agree: 두 파일의 round가 다르면 거부", code == 1 and "E-agree" in out)
        write_csv(pc, rows_c2[:-1] + [row(commit=fake(77), coder="c2")])
        code, out = run_agree(pa, pc)
        check("agree: 커밋 집합이 다르면 거부", code == 1 and "E-agree" in out)
        write_csv(pc, [dict(rows_c2[0], V1="autonomous")] + rows_c2[1:])
        code, out = run_agree(pa, pc)
        check("agree: 값 검증에 걸리면 거부", code == 1 and "E-value" in out)

    # ---- 8. 코드북 문서와의 일치
    if not os.path.exists(DOC):
        check("코드북 문서가 있음", False, DOC)
        doc = ""
    else:
        doc = open(DOC, encoding="utf-8").read()
    secs = {}
    for m in re.finditer(r"^### (V\d+)\b.*?(?=^### V\d+\b|^## )", doc, flags=re.S | re.M):
        secs[m.group(1)] = m.group(0)
    check("문서에 V1–V13 절이 모두 있음", set(secs) == set(ct.VARS), f"있는 절 {sorted(secs, key=lambda s: int(s[1:]))}")
    for v in ct.VARS:
        vals = list(ct.SINGLE.get(v, ())) + list(ct.MULTI.get(v, ())) + list(ct.SOLO.get(v, ()))
        miss = [t for t in vals if f"`{t}`" not in secs.get(v, "")]
        check(f"문서 {v} 절에 값 {len(vals)}개가 모두 적혀 있음", not miss, f"빠진 값 {miss}")
    for name, vals in (("sources", ct.SOURCES), ("coder", ct.CODERS), ("round", ct.ROUNDS), ("status", ct.STATUSES), ("unc_reason", ct.UNC_CODES)):
        miss = [t for t in vals if f"`{t}`" not in doc]
        check(f"문서에 {name}의 값 {len(vals)}개가 적혀 있음", not miss, f"빠진 값 {miss}")

    # ---- 보고서
    nfail = sum(1 for _, ok, _ in checks if not ok)
    L = ["# RQ5 코드북 도구의 자체 점검 (AI 초안, 사람 검토 전)", ""]
    L.append("재현: `python3 -I analysis/rq5/check_codebook_tools.py formal/rq5/codebook-tools-check.md` "
             f"(약 {time.time() - t0:.0f}초). 이것은 **코딩 표의 형식·모순을 거르는 도구의 시험**이다. 49건 사례는 읽지 않았고 시험에 쓴 행은 구성한 예이며 "
             "커밋 해시를 모두 0으로 채운 가짜다.")
    L.append("")
    L.append(f"검사 {len(checks)}개, 실패 {nfail}개.")
    L.append("")
    L.append("## 1. 허용되는 (V1, V6, V8) 조합")
    L.append("")
    L.append("다른 변수를 가장 너그러운 값으로 두고 `validate_row`가 오류 없이 받아들이는 조합이다(V8의 값 `classic2`, `self_only`, `no`, `uncertain`).")
    L.append("")
    L.append("| V1 | V6 | " + " | ".join(f"V8={v8}" for v8 in ct.SINGLE["V8"]) + " |")
    L.append("|---|---|" + "---|" * len(ct.SINGLE["V8"]))
    for v1 in ct.SINGLE["V1"]:
        for v6 in ct.SINGLE["V6"]:
            L.append(f"| {v1} | {v6} | " + " | ".join("허용" if allowed[(v1, v6, v8)] else "—" for v8 in ct.SINGLE["V8"]) + " |")
    L.append("")
    L.append("## 2. 검사 목록")
    L.append("")
    L.append("| 검사 | 결과 | 비고 |")
    L.append("|---|---|---|")
    for name, ok, detail in checks:
        L.append(f"| {name} | {'통과' if ok else '**실패**'} | {detail.replace('|', '/')} |")
    L.append("")
    L.append("## 3. 확인한 것과 하지 않은 것")
    L.append("")
    L.append("- 확인함: 코딩 표 한 행의 형식, 값 집합, 불확실 처리, 근거 칸, 변수 사이의 모순 규칙(C1–C5)과 경고(W1–W5)가 문서의 서술대로 작동한다. κ가 알려진 값과 같다. 파일럿 추출이 결정적이다.")
    L.append("- 확인하지 않음: 코드북의 정의가 사례를 정확히 가르는지(사례를 읽지 않았다), 코더가 규칙을 일관되게 적용하는지, 합격선 0.61이 적절한지(계획용 값, O5-2).")
    L.append("- 한계: 규칙은 코드북의 정의에서 나온 논리적 필요조건이다. 규칙을 통과해도 코딩이 맞다는 뜻이 아니다.")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"검사 {len(checks)}개, 실패 {nfail}개 -> {out_path}")
    for name, ok, detail in checks:
        if not ok:
            print("실패:", name, detail)
    return 1 if nfail else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
