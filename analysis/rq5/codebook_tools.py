#!/usr/bin/env python3
"""RQ5 코드북(docs/rq5/codebook.md)의 기계 점검 도구: 코딩 표 검증, 파일럿 표본 추출, 코더 일치도(Cohen의 κ).

사용법:
    python3 -I analysis/rq5/codebook_tools.py template                  # coding.csv의 머리글을 출력
    python3 -I analysis/rq5/codebook_tools.py validate coding.csv       # 값과 일관성 점검(오류가 있으면 종료 코드 1)
    python3 -I analysis/rq5/codebook_tools.py pilot index.csv [회차]    # 파일럿 표본의 커밋 해시 10개(회차 1 또는 2)
    python3 -I analysis/rq5/codebook_tools.py agree c1.csv c2.csv       # 두 코더의 같은 회차 코딩에서 핵심 변수의 일치도

이 도구는 사례를 읽지 않는다. 코딩 표의 형식과 모순을 점검하고 일치도를 계산할 뿐이다. 값 집합은 이 파일이 정본이고 코드북 문서와의
일치는 analysis/rq5/check_codebook_tools.py가 점검한다. AI(Claude)가 쓴 초안이며 사람의 검토 전이다.
"""
from __future__ import annotations

import csv
import hashlib
import random
import re
import sys
from collections import Counter

# ---------------------------------------------------------------- 스키마 (docs/rq5/codebook.md §2의 값 표와 같아야 한다)
SINGLE = {
    "V1": ("own", "irq_reentry", "indirect_reentry", "other", "uncertain"),
    "V4": ("yes", "no", "uncertain"),
    "V5": ("1", "2", "3plus", "uncertain"),
    "V6": ("yes", "no", "uncertain"),
    "V7": ("1", "2", "3plus", "uncertain"),
    "V8": ("classic2", "self_only", "no", "uncertain"),
    "V10": ("yes", "no", "uncertain"),
    "V11": ("yes", "no", "uncertain"),
    "V12": ("general", "interrupt", "na", "uncertain"),
    "V13": ("missing_unlock", "double_lock", "uninit_lock_use", "release_unacquired", "circular_acq", "na", "uncertain"),
}
# 값을 '+'로 이어 쓰는 변수(집합). 정렬된 순서로 쓴다. 단독으로만 쓰는 값은 SOLO에 있다.
MULTI = {
    "V2": ("hardirq", "other", "process", "softirq", "threaded_handler"),
    "V3": ("mutex", "non_lock_wait", "other_lock", "rwsem_rwlock", "semaphore", "spinlock"),
    "V9": ("cycle", "dup", "usage"),
}
SOLO = {"V2": ("uncertain",), "V3": ("uncertain",), "V9": ("no", "uncertain")}
SOURCES = ("ml", "msg", "other", "patch")
CODERS = ("c1", "c2", "final")
ROUNDS = ("pilot1", "pilot2", "main", "final")
STATUSES = ("coded", "needs_expert", "resolved")
UNC_CODES = ("U1", "U2", "U3")
VARS = ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10", "V11", "V12", "V13"]
FIELDS = ["e2_row", "commit", "coder", "round", "status", "sources"] + VARS + ["V10_reason", "unc_reason", "evidence", "note"]
KEY_VARS = ("V1", "V2", "V6", "V8", "V9", "V10")       # 일치도 합격선을 적용하는 핵심 변수 (prereg/RQ5.md §4)
KAPPA_PASS = 0.61                                      # 계획용 값(prereg/RQ5.md O5-2). 사람이 파일럿 전에 고정한다
NON_PROCESS = ("hardirq", "softirq", "threaded_handler")


def template_header() -> str:
    return ",".join(FIELDS)


def _tokens(value: str) -> list[str]:
    return value.split("+") if value else []


def validate_row(row: dict) -> tuple[list[str], list[str]]:
    """행 하나의 오류와 경고. 오류 메시지는 '[규칙] 설명' 꼴이다."""
    errs: list[str] = []
    warns: list[str] = []

    def e(rule, msg):
        errs.append(f"[{rule}] {msg}")

    def w(rule, msg):
        warns.append(f"[{rule}] {msg}")

    # ---- 필드 존재와 형식
    for f in FIELDS:
        if f not in row:
            e("E-field", f"열 {f}가 없다")
    if errs:
        return errs, warns
    extra = set(row) - set(FIELDS)
    if extra:
        e("E-field", f"알 수 없는 열 {sorted(extra)}")
    if not re.fullmatch(r"[0-9]+", row["e2_row"] or ""):
        e("E-type", "e2_row가 정수가 아니다")
    if not re.fullmatch(r"[0-9a-f]{40}", row["commit"] or ""):
        e("E-type", "commit이 소문자 16진수 40자가 아니다")
    for f, allowed in (("coder", CODERS), ("round", ROUNDS), ("status", STATUSES)):
        if row[f] not in allowed:
            e("E-value", f"{f}={row[f]!r}는 {list(allowed)} 중 하나가 아니다")
    src = _tokens(row["sources"])
    if not src or any(t not in SOURCES for t in src) or src != sorted(set(src)):
        e("E-value", f"sources={row['sources']!r}는 {list(SOURCES)}의 정렬된 비어 있지 않은 부분집합('+'로 이음)이 아니다")

    # ---- 변수 값
    for v, allowed in SINGLE.items():
        if row[v] not in allowed:
            e("E-value", f"{v}={row[v]!r}는 {list(allowed)} 중 하나가 아니다")
    for v, allowed in MULTI.items():
        toks = _tokens(row[v])
        solo = SOLO[v]
        if not toks:
            e("E-value", f"{v}가 비어 있다")
        elif len(toks) == 1 and toks[0] in solo:
            pass
        elif any(t not in allowed for t in toks) or toks != sorted(set(toks)):
            e("E-value", f"{v}={row[v]!r}는 {list(allowed)}의 정렬된 부분집합('+'로 이음) 또는 단독 값 {list(solo)}이 아니다")

    # ---- 불확실과 근거
    unc_vars = [v for v in VARS if row[v] == "uncertain"]
    unc = _tokens(row["unc_reason"])
    if unc_vars and not unc:
        e("E-unc", f"{unc_vars}가 uncertain인데 unc_reason이 비어 있다")
    if unc and any(t not in UNC_CODES for t in unc):
        e("E-unc", f"unc_reason={row['unc_reason']!r}는 {list(UNC_CODES)}의 조합이 아니다")
    if row["status"] in ("coded", "resolved") and not row["evidence"].strip():
        e("E-evid", "status가 coded/resolved인데 evidence가 비어 있다")
    if row["V10"] == "yes" and not row["V10_reason"].strip():
        e("E-evid", "V10=yes인데 V10_reason(한 문장 근거)이 비어 있다")
    if errs:
        return errs, warns

    # ---- 일관성 규칙 (docs/rq5/codebook.md §3)
    v = {k: row[k] for k in VARS}
    v2 = set(_tokens(v["V2"]))
    v9 = set(_tokens(v["V9"]))
    if v["V10"] == "yes":
        if v["V8"] != "no" or v["V9"] != "no":
            e("C1", "V10=yes는 V8=no이고 V9=no일 때만 가능하다(불확실은 안 됨)")
        if not (v["V1"] in ("irq_reentry", "other") or (v2 & set(NON_PROCESS))):
            e("C1b", "V10=yes인데 비자율 요청(V1)도 프로세스 밖 문맥 종류(V2)도 없다")
    if v["V8"] == "classic2":
        if v["V1"] not in ("own", "indirect_reentry"):
            e("C2", "V8=classic2는 V1이 own 또는 indirect_reentry일 때만 가능하다")
        if v["V7"] not in ("2", "3plus"):
            e("C2", "V8=classic2는 문맥이 둘 이상(V7)이어야 한다")
        if v["V5"] not in ("2", "3plus"):
            e("C2", "V8=classic2는 서로 다른 락이 둘 이상(V5)이어야 한다(두 흐름의 순환은 락 둘 이상을 쓴다)")
        if v["V6"] == "yes":
            e("C2", "V8=classic2인데 V6=yes(자기 대기)이다")
    if v["V8"] == "self_only":
        if v["V6"] != "yes":
            e("C3", "V8=self_only는 V6=yes일 때만 가능하다")
        if v["V1"] not in ("own", "indirect_reentry"):
            e("C3", "V8=self_only는 V1이 own 또는 indirect_reentry일 때만 가능하다")
    if v["V1"] == "irq_reentry" and v["V8"] not in ("no", "uncertain"):
        e("C4", "V1=irq_reentry인데 V8이 no/uncertain이 아니다(비자율 요청은 고전 모델이 표현하지 못한다)")
    if "dup" in v9 and v["V4"] != "yes":
        e("C5", "V9에 dup(같은 클래스 중복 획득)이 있는데 V4가 yes가 아니다")

    # ---- 경고(드물지만 가능한 조합)
    if "usage" in v9 and v["V11"] != "yes":
        w("W1", "V9에 usage(사용 상태)가 있는데 V11이 yes가 아니다")
    if v["V12"] == "interrupt" and v["V1"] != "irq_reentry":
        w("W2", "V12=interrupt인데 V1이 irq_reentry가 아니다")
    if "non_lock_wait" in set(_tokens(v["V3"])) and v["V8"] in ("classic2", "self_only"):
        w("W3", "V3에 non_lock_wait가 있는데 V8이 고전 모델로 설명됨이다")
    if v["V13"] == "double_lock" and v["V6"] != "yes":
        w("W4", "V13=double_lock인데 V6이 yes가 아니다")
    if v["V1"] == "irq_reentry" and v["V12"] not in ("interrupt", "uncertain"):
        w("W5", "V1=irq_reentry인데 V12가 interrupt/uncertain이 아니다(보유자를 선점한 처리기의 요청은 정의상 인터럽트 의존이다)")
    return errs, warns


def validate_rows(rows: list[dict]) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    seen = {}
    for i, row in enumerate(rows, 2):                  # 머리글이 1행, 첫 데이터가 2행
        e, w = validate_row(row)
        errors += [f"행 {i}: {m}" for m in e]
        warnings += [f"행 {i}: {m}" for m in w]
        key = (row.get("commit"), row.get("coder"), row.get("round"))
        if key in seen:
            errors.append(f"행 {i}: [E-dup] (commit, coder, round)가 행 {seen[key]}와 같다")
        seen.setdefault(key, i)
    return errors, warnings


def load_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        missing = [c for c in FIELDS if c not in (r.fieldnames or [])]
        if missing:
            raise SystemExit(f"열이 없다: {missing}")
        return list(r)


# ---------------------------------------------------------------- 일치도
def cohen_kappa(a: list, b: list) -> dict:
    """명목 척도 Cohen의 κ. 기대 일치도가 1이면(두 코더가 같은 한 범주만 썼으면) κ는 정의되지 않아 None이다."""
    n = len(a)
    if n == 0 or n != len(b):
        raise ValueError("길이가 같고 0보다 커야 한다")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[c] * cb[c] for c in set(ca) | set(cb)) / (n * n)
    kappa = None if abs(1.0 - pe) < 1e-12 else (po - pe) / (1.0 - pe)
    return {"kappa": kappa, "po": po, "pe": pe, "n": n}


def derive_seed(*parts) -> int:
    key = ":".join(str(p) for p in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(key).digest()[:8], "big")


def bootstrap_kappa(a: list, b: list, reps: int = 2000, seed_name: str = "rq5-kappa", alpha: float = 0.05) -> dict:
    """사례를 복원 추출하는 백분위 부트스트랩 구간. κ가 정의되지 않는 복제는 세어 두고 구간에서 뺀다."""
    n = len(a)
    rng = random.Random(derive_seed(seed_name, n))
    ks, undefined = [], 0
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        k = cohen_kappa([a[i] for i in idx], [b[i] for i in idx])["kappa"]
        if k is None:
            undefined += 1
        else:
            ks.append(k)
    ks.sort()
    if not ks:
        return {"lo": None, "hi": None, "undefined": undefined, "reps": reps}
    lo = ks[int(alpha / 2 * len(ks))]
    hi = ks[min(len(ks) - 1, int((1 - alpha / 2) * len(ks)))]
    return {"lo": lo, "hi": hi, "undefined": undefined, "reps": reps}


def pilot_gate(rows1: list[dict], rows2: list[dict], variables=KEY_VARS, threshold: float = KAPPA_PASS) -> dict:
    """코더 1과 코더 2의 파일럿 코딩(같은 커밋 집합)에서 변수마다 κ를 구하고 합격선과 비교한다.

    판정: pass(κ >= 합격선), fail, undefined_agree(κ 정의 안 됨, 일치율 1: 변수가 파일럿에서 구별되지 않음 — 처리는 사람이 정함, O5-11),
    undefined_disagree(κ 정의 안 됨, 일치율 < 1).
    """
    m1 = {r["commit"]: r for r in rows1}
    m2 = {r["commit"]: r for r in rows2}
    if set(m1) != set(m2):
        raise ValueError("두 코더의 커밋 집합이 다르다")
    commits = sorted(m1)
    out = {}
    for v in variables:
        a = [m1[c][v] for c in commits]
        b = [m2[c][v] for c in commits]
        r = cohen_kappa(a, b)
        ci = bootstrap_kappa(a, b, seed_name=f"rq5-kappa-{v}")
        if r["kappa"] is None:
            status = "undefined_agree" if r["po"] == 1.0 else "undefined_disagree"
        else:
            status = "pass" if r["kappa"] >= threshold else "fail"
        out[v] = {**r, **{"ci_lo": ci["lo"], "ci_hi": ci["hi"], "ci_undefined": ci["undefined"]}, "status": status}
    return out


def element_kappas(a: list, b: list, v: str) -> dict:
    """집합 값 변수 v(V2, V3, V9)의 원소별 이진 κ. 원소가 값에 들어 있는지(예/아니오)로 본다. 기술용 보조 지표이며
    합격 판정에는 쓰지 않는다(정확히 같은 집합이어야 일치로 세는 기본 단위가 너무 엄격한지 보려는 것, O5-10).
    한쪽이나 양쪽 모두 그 원소를 한 번도(또는 항상) 쓰지 않아 기대 일치도가 1이면 κ는 None이다."""
    out = {}
    for el in list(MULTI[v]) + list(SOLO[v]):
        out[el] = cohen_kappa([el in _tokens(s) for s in a], [el in _tokens(s) for s in b])
    return out


def format_gate(gate: dict, threshold: float = KAPPA_PASS) -> list[str]:
    lines = [f"합격선 κ >= {threshold} (계획용 값, O5-2). 사례 {next(iter(gate.values()))['n']}건"]
    for v, g in gate.items():
        if g["kappa"] is None:
            k = "κ 정의 안 됨(기대 일치도 1)"
        else:
            k = f"κ={g['kappa']:.3f}"
        if g["ci_lo"] is None:
            ci = "구간 없음"
        else:
            ci = f"부트스트랩 95% [{g['ci_lo']:.3f}, {g['ci_hi']:.3f}]" + (f", 정의 안 된 복제 {g['ci_undefined']}/2000" if g["ci_undefined"] else "")
        lines.append(f"{v}: 일치율 {g['po']:.2f}, {k}, {ci}, 판정 {g['status']}")
    return lines


# ---------------------------------------------------------------- 파일럿 표본
def draw_pilot(commits: list[str], n: int = 10, round_no: int = 1, master: str = "rq5-pilot") -> list[str]:
    """단순 무작위 추출(비복원). 시드는 (master, 회차)에서 정한다. 회차 2는 회차 1에 뽑힌 사례를 뺀 나머지에서 뽑는다."""
    pool = sorted(set(commits))
    if round_no == 2:
        first = set(draw_pilot(pool, n, 1, master))
        pool = [c for c in pool if c not in first]
    elif round_no != 1:
        raise ValueError("회차는 1 또는 2")
    if len(pool) < n:
        raise ValueError("표본보다 사례가 적다")
    rng = random.Random(derive_seed(master, round_no))
    return sorted(rng.sample(pool, n))


def agree_files(path1: str, path2: str) -> int:
    """두 코더의 코딩 표(같은 회차, 같은 커밋 집합)에서 핵심 변수의 κ를 계산해 출력한다. 합격 여부를 정하는 것은 사람이다."""
    r1, r2 = load_csv(path1), load_csv(path2)
    problems: list[str] = []
    ids = []
    for p, rows in ((path1, r1), (path2, r2)):
        errs, _ = validate_rows(rows)
        problems += [f"{p}: {m}" for m in errs]
        pairs = {(r["coder"], r["round"]) for r in rows}
        if len(pairs) != 1:
            problems.append(f"{p}: [E-agree] 한 파일에는 (coder, round)가 하나만 있어야 한다: {sorted(pairs)}")
        ids.append(next(iter(pairs)) if len(pairs) == 1 else None)
    if not problems:
        if ids[0][0] == ids[1][0]:
            problems.append("[E-agree] 두 파일의 coder가 같다")
        if ids[0][1] != ids[1][1]:
            problems.append("[E-agree] 두 파일의 round가 다르다")
        if {r["commit"] for r in r1} != {r["commit"] for r in r2}:
            problems.append("[E-agree] 두 파일의 커밋 집합이 다르다")
    if problems:
        for m in problems:
            print("오류", m)
        return 1
    gate = pilot_gate(r1, r2)
    for line in format_gate(gate):
        print(line)
    m1 = {r["commit"]: r for r in r1}
    m2 = {r["commit"]: r for r in r2}
    commits = sorted(m1)
    print("집합 값 변수의 원소별 이진 κ(기술용. 합격 판정에 쓰지 않음, O5-10):")
    for v in MULTI:
        ek = element_kappas([m1[c][v] for c in commits], [m2[c][v] for c in commits], v)
        parts = [f"{el}={'정의 안 됨' if r['kappa'] is None else format(r['kappa'], '.2f')}" for el, r in ek.items()]
        print(f"  {v}: " + ", ".join(parts))
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "template":
        print(template_header())
        return 0
    if len(argv) == 3 and argv[1] == "validate":
        errors, warnings = validate_rows(load_csv(argv[2]))
        for m in errors:
            print("오류", m)
        for m in warnings:
            print("경고", m)
        print(f"오류 {len(errors)}개, 경고 {len(warnings)}개")
        return 1 if errors else 0
    if len(argv) == 4 and argv[1] == "agree":
        return agree_files(argv[2], argv[3])
    if len(argv) in (3, 4) and argv[1] == "pilot":
        with open(argv[2], newline="", encoding="utf-8") as f:
            commits = [r["commit"] for r in csv.DictReader(f)]
        for c in draw_pilot(commits, 10, int(argv[3]) if len(argv) == 4 else 1):
            print(c)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
