"""트레이스 검증기·변환기 자체 점검 (traces/validate.py, traces/convert.py).

양성 시험: 샘플 트레이스와 무작위 말뭉치(정책 11개 x 작은 L1 워크로드)가 오류 0개로 통과하는가.
왕복 시험: 비일괄 정책에서 트레이스를 락 프로그램으로 바꾸면 원래 프로그램과 같은가.
음성 시험: 손으로 만든 위반 트레이스와 정상 트레이스의 변이(mutation)를 검증기가 의도한 규칙으로 잡는가.
실행: python3 -I traces/check_validate.py [결과.md]   (결과 파일 기본값 formal/rq3/trace-validator-check.md)
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "oracle"))
sys.path.insert(0, os.path.join(ROOT, "traces"))

import convert  # noqa: E402
import validate  # noqa: E402
from bench.lockrun import run_random  # noqa: E402
from bench.policies.lock import policies as P  # noqa: E402
from bench.workloads.l1 import L1Params, make_l1  # noqa: E402

HEAD = {"trace_format": "rq3-trace-v0.1", "source": "synthetic", "generator": "hand-made", "clock": "logical", "threads": 2}


def dump(head, events):
    return [json.dumps(head, ensure_ascii=False)] + [json.dumps(e, ensure_ascii=False) for e in events]


def hand(spec, head=None, threads=2):
    """spec: (th, op, lock 또는 None[, 덮어쓸 필드 dict]) 열. seq/ts는 0,1,2.. 로 채운다."""
    h = dict(HEAD if head is None else head)
    h.setdefault("threads", threads)
    ev = []
    for i, s in enumerate(spec):
        th, op, lock = s[0], s[1], s[2]
        e = {"seq": i, "ts": i, "th": th, "task": f"{th}.0", "attempt": 0, "op": op}
        if lock is not None:
            e.update({"lock": lock, "cls": lock, "mode": "X"})
        if len(s) > 3:
            e.update(s[3])
        ev.append(e)
    return dump(h, ev)


def errs(lines):
    e, w, _ = validate.validate_lines(lines)
    return e, w


def renumber(events):
    for i, e in enumerate(events):
        e["seq"] = i
    return events


def load(path):
    with open(path, encoding="utf-8") as f:
        ls = f.read().splitlines()
    return json.loads(ls[0]), [json.loads(x) for x in ls[1:]]


def main(out_path):
    t0 = time.time()
    checks: list = []                 # (이름, 통과 여부, 상세)

    def check(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    # ---------------------------------------------------------------- 1. 샘플
    sample_rows = []
    for path in sorted(glob.glob(os.path.join(ROOT, "traces", "sample", "*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            ls = f.read().splitlines()
        e, w, st = validate.validate_lines(ls)
        sample_rows.append((os.path.basename(path), st["events"], len(e), len(w), dict(sorted(st["ops"].items()))))
        check(f"샘플 {os.path.basename(path)} 오류 0개", not e, "; ".join(e[:3]))
    check("샘플 트레이스가 5개 이상", len(sample_rows) >= 5, f"{len(sample_rows)}개")

    # ---------------------------------------------------------------- 2. 무작위 말뭉치
    combos = [(3, 3, 1, 0.0), (3, 4, 2, 0.25), (4, 4, 2, 0.5), (4, 6, 3, 0.25), (6, 6, 2, 0.5), (6, 8, 3, 0.5),
              (4, 3, 2, 0.5), (5, 5, 2, 0.0), (6, 4, 2, 0.25), (3, 3, 3, 0.5), (8, 8, 2, 0.25), (8, 6, 3, 0.5)]
    names = list(P.POLICIES)
    corpus = {n: {"runs": 0, "events": 0, "done": 0, "stall": 0, "cap": 0, "err_traces": 0, "warn_traces": 0, "rt_checked": 0, "rt_bad": 0}
              for n in names}
    first_bad = None
    for n in names:
        pol0 = P.make(n)
        for (T, R, d, pv) in combos:
            prm = L1Params(T=T, R=R, depth=d, p_viol=pv, zipf_s=0.8)
            for inst in range(2):
                w = make_l1(prm, "rq3-trace-check", inst)
                progs = w.first_programs()
                for seed in range(3):
                    pol = P.make(n)
                    log: list = []
                    res = run_random(progs, pol, seed=seed, nlocks=w.nlocks, max_steps=20000, log=log)
                    head = dict(HEAD, threads=w.T, generator=f"check {n} {w.name} seed={seed}")
                    lines = dump(head, log)
                    e, wn, st = validate.validate_lines(lines)
                    c = corpus[n]
                    c["runs"] += 1
                    c["events"] += st["events"]
                    c[res["status"]] += 1
                    if e:
                        c["err_traces"] += 1
                        if first_bad is None:
                            first_bad = (n, w.name, seed, e[:3])
                    if wn:
                        c["warn_traces"] += 1
                    if not pol0.batch:
                        got = convert.trace_to_programs(lines)
                        for th in range(w.T):
                            task = f"{th}.0"
                            if task in got:
                                c["rt_checked"] += 1
                                if got[task] != tuple(progs[th]):
                                    c["rt_bad"] += 1
    tot_runs = sum(c["runs"] for c in corpus.values())
    tot_events = sum(c["events"] for c in corpus.values())
    check("무작위 말뭉치의 모든 트레이스가 오류 0개", all(c["err_traces"] == 0 for c in corpus.values()),
          f"처음 실패: {first_bad}" if first_bad else f"트레이스 {tot_runs:,}개, 이벤트 {tot_events:,}개")
    check("경고(끝나지 않은 스레드)는 멈춘 실행에서만 나온다",
          all((c["warn_traces"] == c["stall"] + c["cap"]) for c in corpus.values()),
          "; ".join(f"{n}: 경고 {c['warn_traces']} / 멈춤+상한 {c['stall'] + c['cap']}" for n, c in corpus.items()
                    if c["warn_traces"] != c["stall"] + c["cap"]))
    check("왕복(트레이스→프로그램)이 원래 프로그램과 같다(비일괄 정책)", all(c["rt_bad"] == 0 for c in corpus.values()),
          f"비교 {sum(c['rt_checked'] for c in corpus.values()):,}건")
    check("멈춘 실행은 B0에서만 나온다(보장 정책 9개와 B1은 멈추지 않는다)",
          all(corpus[n]["stall"] == 0 and corpus[n]["cap"] == 0 for n in names if n != "B0"),
          f"B0 멈춤 {corpus['B0']['stall']}회")

    # ---------------------------------------------------------------- 3. 음성 시험
    neg: list = []                      # (이름, 기대 키워드, 오류 수, 첫 오류)

    def neg_case(name, lines, keyword):
        e, _ = errs(lines)
        hit = any(keyword in x for x in e)
        neg.append((name, keyword, len(e), e[0] if e else ""))
        check(f"음성: {name}", e and hit, f"기대 '{keyword}', 실제 {e[:2]}")

    # 손으로 만든 위반
    neg_case("BEGIN 없이 REQUEST", hand([(0, "REQUEST", 1)]), "BEGIN 없이")
    neg_case("같은 락을 두 스레드가 동시에 ACQUIRE",
             hand([(0, "BEGIN", None), (1, "BEGIN", None), (0, "REQUEST", 1), (0, "ACQUIRE", 1),
                   (1, "REQUEST", 1), (1, "ACQUIRE", 1)]), "쥐어져 있는데")
    neg_case("쥐지 않은 락을 RELEASE",
             hand([(0, "BEGIN", None), (0, "RELEASE", 1)]), "쥐지 않은 락")
    neg_case("락을 쥔 채 END",
             hand([(0, "BEGIN", None), (0, "REQUEST", 1), (0, "ACQUIRE", 1), (0, "END", None)]), "쥔 채 END")
    neg_case("이미 쥔 락을 다시 REQUEST",
             hand([(0, "BEGIN", None), (0, "REQUEST", 1), (0, "ACQUIRE", 1), (0, "REQUEST", 1)]), "이미 쥔 락")
    neg_case("REQUEST 없이 ACQUIRE(대기·일괄 아님)",
             hand([(0, "BEGIN", None), (0, "REQUEST", 1), (0, "ACQUIRE", 1), (0, "RELEASE", 1), (0, "ACQUIRE", 2)]),
             "상태에서 ACQUIRE")
    neg_case("요청하지 않은 락을 ACQUIRE",
             hand([(0, "BEGIN", None), (0, "REQUEST", 1), (0, "ACQUIRE", 2)]), "요청한 락")
    neg_case("기다리지 않은 락을 ACQUIRE",
             hand([(1, "BEGIN", None), (1, "REQUEST", 1), (1, "ACQUIRE", 1), (0, "BEGIN", None), (0, "REQUEST", 1),
                   (0, "WAIT", 1), (1, "RELEASE", 1), (0, "ACQUIRE", 2)]), "기다리지 않은 락")
    neg_case("ABORT 없이 같은 작업을 다시 BEGIN",
             hand([(0, "BEGIN", None), (0, "BEGIN", None)]), "상태에서 BEGIN")
    neg_case("ABORT 뒤 BEGIN의 attempt가 +1이 아님",
             hand([(0, "BEGIN", None), (0, "REQUEST", 1), (0, "ACQUIRE", 1), (0, "ABORT", None),
                   (0, "BEGIN", None)]), "attempt+1")
    neg_case("락의 클래스가 중간에 바뀜",
             hand([(0, "BEGIN", None), (0, "REQUEST", 1), (0, "ACQUIRE", 1),
                   (0, "RELEASE", 1, {"cls": 9})]), "cls가 바뀜")
    neg_case("알 수 없는 op", hand([(0, "BEGIN", None), (0, "LOCK", 1)]), "알 수 없는 op")
    neg_case("mode 누락", hand([(0, "BEGIN", None), (0, "REQUEST", 1, {"mode": "Z"})]), "mode가 없거나")
    neg_case("th 범위 밖", hand([(5, "BEGIN", None)]), "범위 밖")
    neg_case("FAIL을 BEGIN 전에", hand([(0, "FAIL", None)]), "BEGIN 없이")
    neg_case("END를 대기 중에", hand([(1, "BEGIN", None), (1, "REQUEST", 1), (1, "ACQUIRE", 1), (0, "BEGIN", None),
                                    (0, "REQUEST", 1), (0, "WAIT", 1), (0, "END", None)]), "상태에서 END")
    neg_case("머리 레코드의 형식 이름이 다름", hand([], head=dict(HEAD, trace_format="x")), "trace_format")
    neg_case("머리 레코드의 generator 누락", hand([], head={k: v for k, v in HEAD.items() if k != "generator"}), "generator")
    neg_case("머리 레코드의 threads가 0", hand([], head=dict(HEAD, threads=0)), "threads")
    neg_case("머리 레코드의 source가 목록 밖", hand([], head=dict(HEAD, source="guess")), "source")
    bad_json = hand([(0, "BEGIN", None)]) + ["{not json"]
    neg_case("JSON이 아닌 줄", bad_json, "JSON이 아님")
    neg_case("빈 파일", [], "빈 파일")
    # seq/ts는 렌더링 없이 직접 건드린다
    ok_lines = hand([(0, "BEGIN", None), (0, "REQUEST", 1), (0, "ACQUIRE", 1), (0, "RELEASE", 1), (0, "END", None)])
    check("양성: 손으로 만든 정상 트레이스", not errs(ok_lines)[0], str(errs(ok_lines)[0][:2]))
    ev = [json.loads(x) for x in ok_lines[1:]]
    ev2 = [dict(e) for e in ev]
    ev2[2]["seq"] = 7
    neg_case("seq에 구멍", [ok_lines[0]] + [json.dumps(e) for e in ev2], "seq가")
    ev3 = [dict(e) for e in ev]
    ev3[3]["ts"] = -1
    neg_case("ts가 줄어듦", [ok_lines[0]] + [json.dumps(e) for e in ev3], "ts가 줄어듦")

    # 샘플의 변이(seq를 다시 매겨 의미 규칙만 시험)
    wd_head, wd_ev = load(os.path.join(ROOT, "traces", "sample", "synthetic-p-wd-t4r5.jsonl"))

    def mutate(fn):
        e2 = [dict(e) for e in wd_ev]
        e2 = fn(e2)
        return dump(wd_head, renumber(e2))

    def idx(evs, op, nth=0, **kw):
        k = 0
        for i, e in enumerate(evs):
            if e["op"] == op and all(e.get(a) == b for a, b in kw.items()):
                if k == nth:
                    return i
                k += 1
        raise KeyError((op, nth, kw))

    neg_case("샘플 변이: 첫 BEGIN 삭제", mutate(lambda ev: ev[:idx(ev, "BEGIN")] + ev[idx(ev, "BEGIN") + 1:]), "BEGIN 없이")
    neg_case("샘플 변이: ACQUIRE 삭제", mutate(lambda ev: ev[:idx(ev, "ACQUIRE")] + ev[idx(ev, "ACQUIRE") + 1:]), "상태에서")
    neg_case("샘플 변이: ACQUIRE 중복", mutate(lambda ev: ev[:idx(ev, "ACQUIRE") + 1] + [dict(ev[idx(ev, "ACQUIRE")])] + ev[idx(ev, "ACQUIRE") + 1:]), "")
    neg_case("샘플 변이: RELEASE 삭제", mutate(lambda ev: ev[:idx(ev, "RELEASE")] + ev[idx(ev, "RELEASE") + 1:]), "")

    def swap_lock_in_release(ev):
        i = idx(ev, "RELEASE")
        ev[i]["lock"] = (ev[i]["lock"] + 1) % 5
        ev[i]["cls"] = ev[i]["lock"]
        return ev

    neg_case("샘플 변이: RELEASE의 락 번호 바꿈", mutate(swap_lock_in_release), "")

    def bump_attempt(ev):
        i = idx(ev, "BEGIN", attempt=1)
        ev[i]["attempt"] = 3
        return ev

    neg_case("샘플 변이: 재시작 attempt를 3으로", mutate(bump_attempt), "attempt+1")

    # 경고 시험: END를 지우면 끝나지 않은 스레드 경고
    e_, w_ = errs(mutate(lambda ev: ev[:idx(ev, "END")] + ev[idx(ev, "END") + 1:]))
    check("경고: END를 지운 트레이스는 끝나지 않은 스레드 경고를 낸다", (not e_) and bool(w_), f"오류 {e_[:1]}, 경고 {w_[:1]}")
    # 변환기 시험(손 트레이스)
    prog = convert.trace_to_programs(hand([(0, "BEGIN", None), (0, "REQUEST", 3), (0, "ACQUIRE", 3), (0, "REQUEST", 1),
                                           (0, "ACQUIRE", 1), (0, "RELEASE", 1), (0, "RELEASE", 3), (0, "END", None)]))
    check("변환기: 손 트레이스 -> 프로그램", prog == {"0.0": (("A", 3), ("A", 1), ("R", 1), ("R", 3))}, str(prog))
    # 중단된 시도는 프로그램을 정하지 않는다(재시작한 시도의 이벤트는 attempt=1을 덮어써서 만든다)
    spec2 = [(0, "BEGIN", None), (0, "REQUEST", 2), (0, "ACQUIRE", 2), (0, "ABORT", None),
             (0, "BEGIN", None, {"attempt": 1}), (0, "REQUEST", 1, {"attempt": 1}), (0, "ACQUIRE", 1, {"attempt": 1}),
             (0, "RELEASE", 1, {"attempt": 1}), (0, "END", None, {"attempt": 1})]
    l2 = hand(spec2)
    check("변환기 입력이 검증기를 통과한다(중단 뒤 재시작)", not errs(l2)[0], str(errs(l2)[0][:2]))
    check("변환기: 마지막 시도만 프로그램이 된다", convert.trace_to_programs(l2) == {"0.0": (("A", 1), ("R", 1))},
          str(convert.trace_to_programs(l2)))

    # ---------------------------------------------------------------- 보고서
    nfail = sum(1 for c in checks if not c[1])
    L: list = []
    L.append("# 트레이스 검증기·변환기 자체 점검 결과 (RQ3, SI-3)")
    L.append("")
    L.append("- 생성: `python3 -I traces/check_validate.py` (AI가 쓴 스크립트의 자동 출력. 사람의 검토 전)")
    L.append("- 대상: `traces/validate.py`(형식 검증기), `traces/convert.py`(트레이스→락 프로그램), `traces/sample/*.jsonl`(합성 견본)")
    L.append(f"- 소요 시간: {time.time() - t0:.1f}초")
    L.append("")
    L.append("## 1. 샘플 트레이스")
    L.append("")
    L.append("| 파일 | 이벤트 | 오류 | 경고 | 연산 수 |")
    L.append("|---|---:|---:|---:|---|")
    for r in sample_rows:
        L.append(f"| `{r[0]}` | {r[1]} | {r[2]} | {r[3]} | {r[4]} |")
    L.append("")
    L.append("## 2. 무작위 말뭉치 (양성 시험과 왕복 시험)")
    L.append("")
    L.append("정책 11개 x 작은 L1 워크로드 12종(T 3~8, R 3~8, 깊이 1~3, p_v 0~0.5) x 인스턴스 2 x 스케줄 시드 3 = 정책마다 72회 실행. "
             "각 실행을 트레이스로 기록해 검증기에 넣었다. 비일괄 정책은 트레이스를 프로그램으로 되돌려 원래 프로그램과 비교했다.")
    L.append("")
    L.append("| 정책 | 실행 | 이벤트 | 정상 종료 | 멈춤 | 상한 | 오류 있는 트레이스 | 경고 있는 트레이스 | 왕복 비교 | 왕복 불일치 |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for n in names:
        c = corpus[n]
        L.append(f"| {n} | {c['runs']} | {c['events']:,} | {c['done']} | {c['stall']} | {c['cap']} | {c['err_traces']} | {c['warn_traces']} | "
                 f"{c['rt_checked'] if not P.make(n).batch else '해당 없음(일괄)'} | {c['rt_bad'] if not P.make(n).batch else '-'} |")
    L.append("")
    L.append("'멈춤'은 아무 스레드도 진행할 수 없는 상태로 끝난 실행(교착)이다. 이 표는 정책의 성능을 말하지 않는다. "
             "B0(아무 대책 없음)이 멈추는 것은 워크로드에 교착이 실제로 생긴다는 확인이다.")
    L.append("")
    L.append("## 3. 음성 시험 (검증기가 위반을 잡는가)")
    L.append("")
    L.append("| 사례 | 기대한 규칙(오류 메시지에 들어갈 말) | 오류 수 | 첫 오류 |")
    L.append("|---|---|---:|---|")
    for name, kw, ne, first in neg:
        L.append(f"| {name} | {kw or '(아무 오류)'} | {ne} | {first[:90]} |")
    L.append("")
    L.append("## 4. 검사 목록")
    L.append("")
    for name, ok, detail in checks:
        L.append(f"- {'통과' if ok else '**실패**'}: {name}" + (f" — {detail}" if (detail and (not ok or '개' in detail or '건' in detail or '회' in detail)) else ""))
    L.append("")
    L.append(f"**검사 {len(checks)}개, 실패 {nfail}개**")
    L.append("")
    L.append("## 5. 확인한 것과 하지 않은 것")
    L.append("")
    L.append("- 확인한 것: 형식 문서 §3의 여섯 검사가 구현대로 동작한다. 우리 실행기가 만든 트레이스는 모두 통과하고, 의도적으로 깨뜨린 트레이스는 의도한 규칙으로 잡힌다. "
             "비일괄 정책에서 트레이스→프로그램 변환이 원래 프로그램을 되살린다.")
    L.append("- 확인하지 않은 것: 외부에서 수집한 실제 트레이스(대상 응용 O3-2와 Linux 환경 O3-3이 정해지지 않아 수집하지 않았다). "
             "검증기와 실행기를 같은 사람(AI)이 썼으므로 '둘이 서로 맞다'는 것이 '형식이 옳다'를 보장하지 않는다. "
             "공유 모드·재진입·시간 제한 대기는 형식에 없다(O3-20).")
    L.append("- 일괄 정책(P-ALL)의 트레이스는 변환하면 획득 순서가 락 번호 순서가 된다(배치 허가는 한꺼번에 이루어지므로). 원래 프로그램과의 비교에서 제외했다.")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    print(f"검사 {len(checks)}개, 실패 {nfail}개 -> {out_path}")
    for name, ok, detail in checks:
        if not ok:
            print("실패:", name, detail)
    return 1 if nfail else 0


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "formal", "rq3", "trace-validator-check.md")
    sys.exit(main(out))
