#!/usr/bin/env python3
"""저장소 점검(AV-4): 문서 사이의 상호 참조와 집계, 위생, 자체 점검의 일괄 실행.

사용법(저장소 루트에서):
    python3 -I analysis/repo/check_repo.py                      # 정적 점검과 자체 시험, 요약 출력
    python3 -I analysis/repo/check_repo.py --report PATH        # 같은 내용을 보고서 파일로 저장
    python3 -I analysis/repo/check_repo.py --run [--quick] [--jobs N] [--only 이름[,이름]] [--out DIR] [--run-report PATH]
                                                                # 모든 자체 점검을 실행한다. 점검의 보고서는 DIR(기본: 임시 폴더)에
                                                                # 쓰고 저장소의 파일은 건드리지 않는다. 실행 뒤 작업 트리가 달라졌으면 알린다.

정적 점검(읽기만 한다. 작업 트리의 파일과 git의 커밋 목록을 본다):
  경로      문서의 `백틱` 경로, 코드 블록 안의 경로, 마크다운 링크가 가리키는 파일·폴더가 있는가. 아직 만들지 않은 산출물은
            PLANNED에 이유와 함께 적는다(이미 생겼거나 아무 문서도 인용하지 않으면 목록에서 빼라고 알린다).
  절 참조   `경로` §N.M 과 문서 NN §N.M 이 가리키는 절(번호가 붙은 제목 또는 굵은 소제목)이 있는가
  해시      7자리 커밋 해시가 이 저장소의 커밋인가(외부 저장소의 커밋은 EXTERNAL_COMMITS), `git log -- 경로` 같은 안내가
            해시를 대신하지 않는가
  대장      주장 대장의 행(8열, ID 중복·틈 없음, 수준 어휘, 전제로 사용 규칙, 확인일 형식)과 문서가 인용한 대장 번호(범위 포함)
  검색기록  G4-nnn 행이 1부터 연속인가, 문서의 인용(범위 포함)이 있는 번호인가, 'G4-nnn부터'가 다음 번호인가
  열린항목  O1-n–O6-n이 prereg/RQ?.md에 정의되어 있고 번호에 틈이 없는가
  문서07    §3.1의 집계, '전체 행은 N개', 'N행', AI가 할 수 있는 일의 개수와 목록, BL·AV 참조, 다른 문서가 적은 '하지 못한 일 N건'
  수치인용  README·문서 07·대장이 적은 점검 개수(예: 자체 시험 29건)가 보고서의 값과 같은가, 보고서가 실패를 적지 않았는가
  현재상태  README의 '현재 상태' 날짜가 진행 기록의 마지막 날짜보다 이르지 않은가, 문서에 적은 버전(격자, prereg/RQ2)이 맞는가
  구성      README 구성 표에 최상위 폴더가 모두 있는가, docs/·formal/·analysis/의 하위 폴더를 README가 설명하는가
  주장수위  'G5 … 통과'를 단정한 문장이나 동결 태그(spec-v1, prereg-RQ*-v1)가 생기지 않았는가(알림만 낸다)
  위생      PDF·압축 파일·__pycache__ 등이 추적되지 않는가, 비밀값처럼 보이는 문자열, 개인 경로·이메일(알림)
  러너      모든 check_*.py가 실행 목록(CHECKS)에 있고 목록의 스크립트와 보고서 파일이 있는가, 문서가 적은 점검·규칙 개수가 목록과 같은가

자체 시험: 일부러 망가뜨린 저장소 사본(메모리 안)을 같은 점검에 넣어 규칙마다 잡히는지 본다. 잡지 못한 시험이 있으면 실패다.
종료 코드: 오류가 있거나 자체 시험을 놓치면 1. '알림'은 사람에게 알릴 것이며 종료 코드를 바꾸지 않는다.
표준 라이브러리만 쓴다. AI(Claude)가 쓴 초안이며 사람의 검토 전이다. 이 점검은 문서의 형식과 일관성을 보며 문헌의 내용이 옳은지는 보지 않는다.
"""
from __future__ import annotations

import concurrent.futures
import functools
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter, namedtuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SELF = "analysis/repo/check_repo.py"
TEXT_LIMIT = 8 * 1024 * 1024
ERR, NOTE, OK = "오류", "알림", "정상"

# ---------------------------------------------------------------------------------------------
# 설정: 사람이 읽고 고치는 목록
# ---------------------------------------------------------------------------------------------

# 문서가 인용하지만 아직 만들지 않은 산출물(계획에만 있다). 생기면 이 목록에서 뺀다.
PLANNED = {
    "analysis/rq5/coding.csv": "RQ5 전체 코딩 결과(49건 코딩은 동결 뒤)",
    "bench/policies/inc": "P-INC 구현(새 설계점이라 동결 전에는 만들지 않음)",
    "docs/rq5/model.md": "RQ5 확장 모델 정의 문서(WP5.4)",
    "formal/rq1/counterexamples.md": "RQ1 반례 기록(탐색은 동결 뒤)",
    "formal/rq1/proofs": "RQ1 기계 증명(선택 항목, CP4)",
    "formal/rq2/attempts.md": "RQ2 증명·알고리즘 시도 기록(WP2.4, 동결 뒤)",
    "prereg/RQ3-crosscheck.md": "RQ3 교차 확인 표(사람이 원문을 확인한 뒤)",
    "prereg/RQ6-claims.md": "RQ6 주장 단위 부록(동결 뒤 WP6.3 전)",
    "prereg/RQx.md": "파일 이름 형식의 자리표시(RQx)",
}

# 이 저장소의 것이 아닌 커밋 해시(다른 저장소의 커밋을 인용한 곳).
EXTERNAL_COMMITS = {
    "ffcad0c": "E2 공개 데이터셋 저장소의 커밋(문서 02, prereg/RQ5, 대장 C-SUR-012)",
}

Check = namedtuple("Check", "name script mode report slow same")
# mode: 'path' = 보고서 경로를 첫 인자로, 'report' = --report PATH
# slow: 가장 오래 걸리는 두 점검(--quick이면 건너뜀. 시간은 formal/repo/run-all-check.md의 기록에 있고 컴퓨터와 동시에 도는 점검에 따라 달라진다).
# same: 다시 실행한 보고서가 저장소의 것과 바이트까지 같아야 함
CHECKS = [
    Check("sm", "oracle/check_sm.py", "path", "formal/rq1/sm-check-results.md", False, False),
    Check("sm-mutation", "oracle/mutation_check.py", "path", "formal/rq1/sm-mutation-results.md", False, False),
    Check("o1", "oracle/check_banker.py", "path", "formal/rq6/o1-check-results.md", False, False),
    Check("o2", "oracle/check_locks.py", "path", "formal/rq3/o2-check-results.md", False, False),
    Check("harness", "bench/check_pipeline.py", "path", "formal/rq6/harness-check-results.md", False, False),
    Check("banker-policies", "bench/check_banker_policies.py", "path", "formal/rq6/policies-diff-results.md", True, False),
    Check("variants-dbdaa", "bench/check_variants.py", "path", "formal/rq6/variants-check-results.md", False, False),
    Check("variants-begum", "bench/check_variants_begum.py", "path", "formal/rq6/variants-check-begum.md", False, False),
    Check("variants-dixit", "bench/check_variants_dixit.py", "path", "formal/rq6/variants-check-dixit.md", False, False),
    Check("variants-wicaksono", "bench/check_variants_wicaksono.py", "path", "formal/rq6/variants-check-wicaksono.md", False, False),
    Check("variants-derivations", "bench/check_variants_derivations.py", "path", "formal/rq6/variants-derivations.md", False, False),
    Check("pilot-tools", "bench/check_pilot.py", "path", "formal/rq6/pilot-check-results.md", False, False),
    Check("lock-policies", "bench/check_lock_policies.py", "path", "formal/rq3/lock-policies-check.md", True, False),
    Check("workloads", "bench/check_workloads.py", "path", "formal/rq3/workloads-check.md", False, False),
    Check("trace-validator", "traces/check_validate.py", "path", "formal/rq3/trace-validator-check.md", False, False),
    Check("codebook-tools", "analysis/rq5/check_codebook_tools.py", "path", "formal/rq5/codebook-tools-check.md", False, True),
    Check("grid", "analysis/rq2/check_grid.py", "report", "formal/rq2/grid-check.md", False, True),
]

# 문서가 적은 점검 개수와 보고서의 값을 맞춘다: (문서, 정규식(캡처 그룹 하나당 보고서 하나), [보고서...])
LOCK = "formal/rq3/lock-policies-check.md"
WORK = "formal/rq3/workloads-check.md"
TRACE = "formal/rq3/trace-validator-check.md"
O2 = "formal/rq3/o2-check-results.md"
CODEBOOK = "formal/rq5/codebook-tools-check.md"
GRID = "formal/rq2/grid-check.md"
HARNESS = "formal/rq6/harness-check-results.md"
PILOT = "formal/rq6/pilot-check-results.md"
REPO_REPORT = "formal/repo/repo-check.md"
RUN_REPORT = "formal/repo/run-all-check.md"
# 문서가 적은 개수와 이 스크립트의 목록 길이를 맞춘다: (문서, 정규식, 이름)
COUNT_DOCS = [
    ("README.md", r"자체 점검 (\d+)개를 한 번에", "CHECKS"),
    ("README.md", r"점검 규칙 (\d+)개", "RULES"),
    ("analysis/repo/README.md", r"자체 점검 (\d+)개를 한 번에", "CHECKS"),
    ("analysis/repo/README.md", r"정적 점검: 규칙 (\d+)개", "RULES"),
    ("docs/07-followup-scope.md", r"자체 점검 (\d+)개를 한 번에", "CHECKS"),
]
PAIRS = [
    ("README.md", r"정책 검사 (\d+)개", [LOCK]),
    ("README.md", r"생성기 점검 (\d+)개", [WORK]),
    ("README.md", r"트레이스 검증기 점검 (\d+)개", [TRACE]),
    ("README.md", r"정책 초안 구현 (\d+)개 검사\(변이체 17종 포함\), 워크로드 생성기 (\d+)개 점검, 트레이스 검증기 (\d+)개 점검",
     [LOCK, WORK, TRACE]),
    ("README.md", r"코딩 표 검증·표본 추출·일치도 도구\(점검 (\d+)개\)", [CODEBOOK]),
    ("README.md", r"자체 점검 보고서\((\d+)개\)", [CODEBOOK]),
    ("README.md", r"집계, 자체 시험 (\d+)건", [GRID]),
    ("README.md", r"저장소 점검 스크립트\(`analysis/repo/check_repo\.py`\)와 자체 시험 (\d+)건", [REPO_REPORT]),
    ("analysis/rq2/README.md", r"자체 시험 (\d+)건", [GRID]),
    ("docs/07-followup-scope.md", r"RQ6용 하네스\(SI-4\) \| 점검 (\d+)개", [HARNESS]),
    ("docs/07-followup-scope.md", r"파일럿 점검 (\d+)개", [PILOT]),
    ("docs/07-followup-scope.md", r"오라클 (\d+)개, 정책 (\d+)개, 생성기 (\d+)개, 트레이스 (\d+)개", [O2, LOCK, WORK, TRACE]),
    ("docs/07-followup-scope.md", r"도구 점검 (\d+)개", [CODEBOOK]),
    ("docs/07-followup-scope.md", r"문서 점검 문제 없음, 자체 시험 (\d+)건", [GRID]),
    ("docs/07-followup-scope.md", r"저장소 점검 스크립트\(AV-4\).*?자체 시험 (\d+)건", [REPO_REPORT]),
    ("refs/claims-ledger.md", r"일부러 망가뜨린 모델 (\d+)종", [GRID]),
]

# ---------------------------------------------------------------------------------------------
# 정규식
# ---------------------------------------------------------------------------------------------

TOP = r"(?:analysis|bench|docs|experiments|formal|oracle|prereg|refs|traces)"
# 경로의 글자는 ASCII뿐이다(이 저장소에는 한글 파일 이름이 없다). 한글은 <회차>처럼 꺾쇠 안의 자리표시에만 허용한다.
# 그래야 '# experiments/pilot/의 자료'처럼 조사가 붙은 경로가 조사까지 경로로 읽히지 않는다.
PATH_CH = r"(?:[A-Za-z0-9_.\-/{},*?…]|<[^<>\s`]*>)"
PATH_RE = re.compile(rf"(?<![A-Za-z0-9_./\-])(?:{TOP}/{PATH_CH}+|README\.md)")
SPAN_RE = re.compile(r"`([^`\n]+)`")
LINK_RE = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)\)")
SEC = r"§\s*\d+(?:\.\d+)*"
SEC_SEQ = rf"{SEC}(?:\s*[,·]\s*{SEC})*"
REF_PATH_SEC = re.compile(rf"`(?P<p>(?:{TOP}/[^`\s]+|README\.md))`\s*(?P<s>{SEC_SEQ})")
REF_DOC_SEC = re.compile(rf"문서\s*(?P<d>\d\d)(?:의)?\s*(?P<s>{SEC_SEQ})")
SEC_NUM = re.compile(r"§\s*(\d+(?:\.\d+)*)")
HEAD_RE = re.compile(r"^#{2,6}\s+(?:§\s*)?(\d+(?:\.\d+)*)(?:[.\s)]|$)")
BOLD_RE = re.compile(r"^\s*(?:[-*]\s+)?\*\*(\d+(?:\.\d+)*)[.\s)]")
HASH_RE = re.compile(r"(?<![0-9A-Za-z_\-/.])([0-9a-f]{7})(?![0-9A-Za-z_\-])")
PLACEHOLDER_RE = re.compile(r"`git log\s+--[^`]*`")
LEDGER = "refs/claims-ledger.md"
LROW = re.compile(r"^\| (C-[A-Z0-9]+-\d{3}) \|")
LEVEL_RE = re.compile(r"^(A−|A|B|C|D|X|V|—)")
DATE_RE = re.compile(r"^(이전 세션|\d{4}-\d{2}-\d{2})(, .+)?$")
ID_REF = re.compile(r"\bC-([A-Z0-9]+)-(\d{3})(?:\s*[–~]\s*(?:C-[A-Z0-9]+-)?(\d{3}))?")
G4_LOG = "refs/g4-search-log.md"
G4_ROW = re.compile(r"^\| G4-(\d{3}) \|")
G4_REF = re.compile(r"\bG4-(\d{3})(?:\s*[–~]\s*(?:G4-)?(\d{3}))?(부터)?")
O_REF = re.compile(r"\bO([1-6])-(\d+)(?:\s*[–~]\s*(?:O\1-)?(\d+))?\b")
DOC7 = "docs/07-followup-scope.md"
KNUM = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}

SECRET_PATTERNS = [
    ("GitHub 토큰", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("GitHub 토큰(세분화형)", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}")),
    ("API 키(sk-)", re.compile(r"\bsk-[A-Za-z0-9_-]{32,}")),
    ("AWS 접근 키", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack 토큰", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("개인 키 블록", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("키=값 형태", re.compile(r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token)\b[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9/+_\-]{16,}")),
]
WINPATH = re.compile(r"\b[A-Za-z]:\\Users\\[^\\\s`'\"]+\\")
UNIXHOME = re.compile(r"(?:/Users/|/home/)[A-Za-z0-9._-]+/")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b")
BAD_EXT = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz",
           ".7z", ".rar", ".pyc", ".pyo", ".so", ".dll", ".exe", ".dylib"}
REPORT_PATTERNS = [
    re.compile(r"검사 (\d+)개, 실패 (\d+)개"),
    re.compile(r"점검 (\d+)개, 실패 (\d+)개"),
    re.compile(r"점검 (\d+)개: 모두 통과"),
    re.compile(r"시험 (\d+)건 중 놓친 것 (\d+)건"),
    re.compile(r"검출하지 못한 변이: (\d+)개 / (\d+)개"),
    re.compile(r"시험 (\d+)건\(망가뜨린 입력 \d+건, 정상 입력 \d+건\) 중 놓친 것 (\d+)건"),
]


# ---------------------------------------------------------------------------------------------
# 저장소 보기
# ---------------------------------------------------------------------------------------------

class Repo:
    """점검 대상. 파일 이름, 텍스트 파일의 내용, 크기, 커밋 목록만 안다(자체 시험은 이 사본을 바꾼다)."""

    def __init__(self, files, texts, sizes, commits, tags=()):
        self.files = set(files)
        self.texts = dict(texts)
        self.sizes = dict(sizes)
        self.commits = list(commits)
        self.tags = list(tags)

    def copy(self):
        return Repo(self.files, self.texts, self.sizes, self.commits, self.tags)


def git(*args, root=ROOT):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True).stdout


def load_repo(root=ROOT):
    names = [n for n in git("ls-files", "-co", "--exclude-standard", "-z", root=root).decode("utf-8").split("\0") if n]
    texts, sizes = {}, {}
    for n in names:
        p = os.path.join(root, n)
        if not os.path.isfile(p):
            continue  # 추적하지만 작업 트리에서 지워진 파일
        sizes[n] = os.path.getsize(p)
        if sizes[n] <= TEXT_LIMIT:
            with open(p, "rb") as f:
                b = f.read()
            if b"\0" not in b[:8192]:
                texts[n] = b.decode("utf-8", errors="replace")
    commits = git("rev-list", "--all", root=root).decode().split()
    tags = git("tag", "-l", root=root).decode().split()
    return Repo(set(sizes), texts, sizes, commits, tags)


class Ctx:
    def __init__(self, repo):
        self.repo = repo
        self.files = repo.files
        d = set()
        for f in repo.files:
            parts = f.split("/")[:-1]
            for i in range(1, len(parts) + 1):
                d.add("/".join(parts[:i]))
        self.dirs = d
        self.md = sorted(p for p in repo.texts if p.endswith(".md"))
        self.lines = {p: t.split("\n") for p, t in repo.texts.items() if p.endswith((".md", ".py"))}
        self.sections = {p: sections(repo.texts[p]) for p in self.md}
        self.docnum = {}
        for f in repo.files:
            m = re.match(r"docs/(\d\d)-[^/]+\.md$", f)
            if m:
                self.docnum.setdefault(m.group(1), []).append(f)

    def exists(self, q):
        return q in self.files or q in self.dirs


@functools.lru_cache(maxsize=None)
def sections(text):
    out = set()
    for line in text.split("\n"):
        m = HEAD_RE.match(line) or BOLD_RE.match(line)
        if m:
            out.add(m.group(1))
    return frozenset(out)


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def expand_braces(s):
    m = re.search(r"\{([^{}]*)\}", s)
    if not m:
        return [s]
    out = []
    for alt in m.group(1).split(","):
        out += expand_braces(s[:m.start()] + alt + s[m.end():])
    return out


def norm_path(tok):
    tok = re.split(r"::|\(", tok)[0]
    return tok.rstrip(",.;:)]}»”’'\"")


# ---------------------------------------------------------------------------------------------
# 규칙. 각 규칙은 (문제 목록, 살펴본 항목 수)를 돌려준다. 문제는 (규칙, 파일, 줄, 설명, 종류) 튜플이다.
# ---------------------------------------------------------------------------------------------

def rule_paths(c):
    P, n, used = [], 0, set()
    for path in c.md:
        in_fence = False
        for ln, line in enumerate(c.lines[path], 1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            toks = []
            if in_fence:
                toks += PATH_RE.findall(line)
            else:
                for span in SPAN_RE.findall(line):
                    toks += PATH_RE.findall(span)
                for tgt in LINK_RE.findall(line):
                    if tgt.startswith(("http://", "https://", "mailto:", "#")):
                        continue
                    tgt = tgt.split("#")[0]
                    if not tgt:
                        continue
                    q = os.path.normpath(os.path.join(os.path.dirname(path), tgt)).replace(os.sep, "/")
                    n += 1
                    if not c.exists(q):
                        P.append(("경로", path, ln, f"링크 대상이 없다: {tgt}", ERR))
            for tok in toks:
                t = norm_path(tok)
                if not t or any(ch in t for ch in "*<>…?$"):
                    continue
                for p in expand_braces(t):
                    if "{" in p or "}" in p:
                        continue
                    q = p.rstrip("/")
                    n += 1
                    m = re.fullmatch(r"docs/(\d\d)", q)
                    if (m and any(f.startswith(f"docs/{m.group(1)}-") for f in c.files)) or (not m and c.exists(q)):
                        continue
                    if q in PLANNED:
                        used.add(q)
                        continue
                    P.append(("경로", path, ln, f"없는 경로: {p}", ERR))
    for q in PLANNED:
        if c.exists(q):
            P.append(("경로", SELF, 0, f"PLANNED에 있으나 이미 존재한다(목록에서 뺄 것): {q}", ERR))
        elif q not in used:
            P.append(("경로", SELF, 0, f"PLANNED의 {q}를 인용한 문서가 없다(목록에서 뺄 것)", NOTE))
    return P, n


def rule_sections(c):
    P, n = [], 0

    def check_nums(path, ln, target, seq):
        nonlocal n
        for s in SEC_NUM.findall(seq):
            n += 1
            if s not in c.sections[target]:
                P.append(("절 참조", path, ln, f"{target}에 §{s}가 없다", ERR))

    for path in c.md:
        for ln, line in enumerate(c.lines[path], 1):
            for m in REF_PATH_SEC.finditer(line):
                tp = norm_path(m.group("p"))
                if tp in c.sections:  # 없는 파일은 '경로' 규칙이 본다
                    check_nums(path, ln, tp, m.group("s"))
            for m in REF_DOC_SEC.finditer(line):
                cand = c.docnum.get(m.group("d"), [])
                if len(cand) != 1:
                    P.append(("절 참조", path, ln, f"문서 {m.group('d')}에 해당하는 파일이 {len(cand)}개다", ERR))
                else:
                    check_nums(path, ln, cand[0], m.group("s"))
    return P, n


def rule_hashes(c):
    P, n = [], 0
    commits = c.repo.commits
    used_ext = set()
    for path in sorted(p for p in c.repo.texts if p.endswith((".md", ".py"))):
        for ln, line in enumerate(c.lines[path], 1):
            for m in HASH_RE.finditer(line):
                tok = m.group(1)
                if not (re.search(r"\d", tok) and re.search(r"[a-f]", tok)):
                    continue
                n += 1
                if any(h.startswith(tok) for h in commits):
                    continue
                if tok in EXTERNAL_COMMITS:
                    used_ext.add(tok)
                    continue
                P.append(("해시", path, ln, f"이 저장소의 커밋이 아니다: {tok}", ERR))
            if path.endswith(".md") and PLACEHOLDER_RE.search(line):
                n += 1
                P.append(("해시", path, ln, "커밋 해시 대신 `git log -- 경로` 안내를 적었다(해시를 적을 것)", ERR))
    for tok in EXTERNAL_COMMITS:
        if any(h.startswith(tok) for h in commits):
            P.append(("해시", SELF, 0, f"EXTERNAL_COMMITS의 {tok}가 이 저장소의 커밋과 겹친다(목록에서 뺄 것)", ERR))
        elif tok not in used_ext:
            P.append(("해시", SELF, 0, f"EXTERNAL_COMMITS의 {tok}를 인용한 문서가 없다(목록에서 뺄 것)", NOTE))
    return P, n


def ledger_rows(text):
    return [(i, line) for i, line in enumerate(text.split("\n"), 1) if LROW.match(line)]


def rule_ledger(c):
    P, n = [], 0
    text = c.repo.texts.get(LEDGER)
    if text is None:
        return [("대장", LEDGER, 0, "주장 대장 파일이 없다", ERR)], 0
    ids = []
    for ln, line in ledger_rows(text):
        n += 1
        cs = cells(line)
        if len(cs) != 8:
            P.append(("대장", LEDGER, ln, f"{cs[0]}: 열이 {len(cs)}개다(8개여야 한다)", ERR))
            continue
        ids.append(cs[0])
        lvl, src, loc, prem, date = cs[4], cs[2], cs[3], cs[6], cs[5]
        m = LEVEL_RE.match(lvl)
        if not m:
            P.append(("대장", LEDGER, ln, f"{cs[0]}: 수준 칸이 어휘(A, A−, B, C, D, X, V, —)로 시작하지 않는다: {lvl[:20]}", ERR))
        elif (m.group(1) in ("C", "D", "X") or "2차" in lvl or "2차" in loc) and prem == "가":
            P.append(("대장", LEDGER, ln, f"{cs[0]}: 수준이 낮거나 2차 경로인데 '전제로 사용'이 '가'다", ERR))
        if prem not in ("가", "불가"):
            P.append(("대장", LEDGER, ln, f"{cs[0]}: '전제로 사용'이 가/불가가 아니다: {prem[:10]}", ERR))
        if not DATE_RE.match(date):
            P.append(("대장", LEDGER, ln, f"{cs[0]}: 확인일 형식이 아니다: {date[:20]}", ERR))
    dup = [k for k, v in Counter(ids).items() if v > 1]
    for k in dup:
        P.append(("대장", LEDGER, 0, f"ID가 둘 이상의 행에 있다: {k}", ERR))
    fam = {}
    for i in ids:
        m = re.match(r"C-([A-Z0-9]+)-(\d{3})$", i)
        fam.setdefault(m.group(1), set()).add(int(m.group(2)))
    for f, nums in sorted(fam.items()):
        gaps = [k for k in range(1, max(nums) + 1) if k not in nums]
        if gaps:
            P.append(("대장", LEDGER, 0, f"C-{f}의 번호에 틈이 있다(행을 지우지 않는다): {gaps[:5]}", ERR))
    defined = {(f, k) for f, nums in fam.items() for k in nums}
    for path in c.md:
        for ln, line in enumerate(c.lines[path], 1):
            for m in ID_REF.finditer(line):
                f, a = m.group(1), int(m.group(2))
                b = int(m.group(3)) if m.group(3) else a
                n += 1
                if b < a:
                    P.append(("대장", path, ln, f"범위가 거꾸로다: {m.group(0)}", ERR))
                    continue
                miss = [k for k in range(a, b + 1) if (f, k) not in defined]
                if miss:
                    P.append(("대장", path, ln, f"대장에 없는 번호: C-{f}-{miss[0]:03d}" + (f" 외 {len(miss) - 1}개" if len(miss) > 1 else ""), ERR))
    return P, n


def rule_g4(c):
    P, n = [], 0
    text = c.repo.texts.get(G4_LOG)
    if text is None:
        return [("검색기록", G4_LOG, 0, "검색 기록 파일이 없다", ERR)], 0
    nums = [int(m.group(1)) for line in text.split("\n") for m in [G4_ROW.match(line)] if m]
    n += len(nums)
    if nums != list(range(1, len(nums) + 1)):
        bad = next((i + 1 for i, v in enumerate(nums) if v != i + 1), None)
        P.append(("검색기록", G4_LOG, 0, f"G4 번호가 1부터 연속이 아니다(첫 어긋남: {bad}번째 행이 G4-{nums[bad - 1]:03d})" if bad else "G4 번호가 연속이 아니다", ERR))
    last = max(nums) if nums else 0
    have = set(nums)
    for path in c.md:
        for ln, line in enumerate(c.lines[path], 1):
            for m in G4_REF.finditer(line):
                a = int(m.group(1))
                b = int(m.group(2)) if m.group(2) else a
                n += 1
                if m.group(3):  # 'G4-nnn부터'는 다음 번호여야 한다
                    if a != last + 1:
                        P.append(("검색기록", path, ln, f"'G4-{a:03d}부터'가 다음 번호(G4-{last + 1:03d})가 아니다", ERR))
                    continue
                if b < a:
                    P.append(("검색기록", path, ln, f"범위가 거꾸로다: {m.group(0)}", ERR))
                    continue
                miss = [k for k in range(a, b + 1) if k not in have]
                if miss:
                    P.append(("검색기록", path, ln, f"검색 기록에 없는 번호: G4-{miss[0]:03d}", ERR))
    return P, n


def o_numbers(k, text):
    """'O3-10–O3-18, O3-20' 같은 목록에서 번호를 낸다. 목록이 아닌 글자가 섞이면 None."""
    item = rf"O{k}-(\d+)(?:\s*[–~]\s*(?:O{k}-)?(\d+))?"
    if not re.fullmatch(rf"{item}(?:\s*,\s*{item})*", text.strip()):
        return None
    nums = set()
    for m in re.finditer(item, text):
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        nums.update(range(a, max(a, b) + 1))
    return nums


def o_definitions(k, text):
    """prereg/RQk.md에서 열린 항목의 정의를 찾는다: 표의 첫 칸, 또는 글머리표·굵은 글씨로 시작하는 줄의 머리."""
    out = set()
    for line in text.split("\n"):
        if line.startswith("|"):
            head = cells(line)[0].replace("**", "")
        else:
            m = re.match(r"^\s*(?:[-*]\s+)?\*{0,2}(O\d-[0-9,\s–~O\-]*\d)(?=\*{0,2}(?:[\s:.)]|$))", line)
            head = m.group(1) if m else ""
        nums = o_numbers(k, head) if head else None
        if nums:
            out |= nums
    return out


def rule_open_items(c):
    P, n = [], 0
    defs = {k: set() for k in range(1, 7)}
    for k in range(1, 7):
        t = c.repo.texts.get(f"prereg/RQ{k}.md")
        if t is None:
            continue
        defs[k] = o_definitions(k, t)
        if defs[k]:
            gaps = [i for i in range(1, max(defs[k]) + 1) if i not in defs[k]]
            if gaps:
                P.append(("열린항목", f"prereg/RQ{k}.md", 0, f"O{k}의 번호에 틈이 있다: {gaps[:5]}", ERR))
    for path in c.md:
        for ln, line in enumerate(c.lines[path], 1):
            for m in O_REF.finditer(line):
                k, a = int(m.group(1)), int(m.group(2))
                b = int(m.group(3)) if m.group(3) else a
                n += 1
                if f"prereg/RQ{k}.md" not in c.repo.texts:
                    P.append(("열린항목", path, ln, f"O{k}-{a}: prereg/RQ{k}.md가 없다", ERR))
                    continue
                if b < a:
                    P.append(("열린항목", path, ln, f"범위가 거꾸로다: {m.group(0)}", ERR))
                    continue
                miss = [i for i in range(a, b + 1) if i not in defs[k]]
                if miss:
                    P.append(("열린항목", path, ln, f"prereg/RQ{k}.md에 정의되지 않은 열린 항목: O{k}-{miss[0]}"
                              + (f" 외 {len(miss) - 1}개" if len(miss) > 1 else ""), ERR))
    return P, n


def parse_doc07(text):
    L = text.split("\n")

    def find(pat):
        return next((i for i, l in enumerate(L) if re.match(pat, l)), None)

    i1, i3, i31, i4, i5, i6 = (find(p) for p in (r"^## 1\.", r"^## 3\.", r"^### 3\.1", r"^## 4\.", r"^## 5\.", r"^## 6\."))
    if None in (i1, i3, i31, i4, i5, i6):
        return None
    cats = []
    for k in range(i1, i3):
        if L[k].startswith("| 분류 | 뜻 |"):
            j = k + 2
            while j < i3 and L[j].startswith("|"):
                cats.append(cells(L[j])[0])
                j += 1
            break
    bl = [cells(l) for l in L[i3:i31] if re.match(r"^\| BL-", l)]
    tally = {}
    for l in L[i31:i4]:
        m = re.match(r"^\| (\S+) \| (\d+) \|$", l)
        if m:
            tally[m.group(1)] = int(m.group(2))
    av = [cells(l) for l in L[i5:i6] if re.match(r"^\| AV-", l)]
    return cats, bl, tally, av


def rule_doc07(c):
    P, n = [], 0
    text = c.repo.texts.get(DOC7)
    parsed = parse_doc07(text) if text else None
    if not parsed:
        return [("문서07", DOC7, 0, "문서 07의 절 구조(§1, §3, §3.1, §4, §5, §6)를 읽지 못했다", ERR)], 0
    cats, bl, tally, av = parsed
    count = Counter()
    multi = 0
    for r in bl:
        n += 1
        if len(r) != 6:
            P.append(("문서07", DOC7, 0, f"{r[0]}: 열이 {len(r)}개다(6개여야 한다)", ERR))
            continue
        parts = [p.strip() for p in r[2].split("+")]
        for p in parts:
            if p not in cats:
                P.append(("문서07", DOC7, 0, f"{r[0]}: 사유 '{p}'가 §1의 분류에 없다", ERR))
            count[p] += 1
        multi += len(parts) > 1
    for k in cats:
        n += 1
        if tally.get(k) != count.get(k, 0):
            P.append(("문서07", DOC7, 0, f"§3.1의 '{k}'가 {tally.get(k)}인데 §3 표를 세면 {count.get(k, 0)}이다", ERR))
    for k in tally:
        if k not in cats:
            P.append(("문서07", DOC7, 0, f"§3.1에 §1의 분류에 없는 '{k}'가 있다", ERR))
    m = re.search(r"전체 행은 (\d+)개다", text)
    n += 1
    if not m or int(m.group(1)) != len(bl):
        P.append(("문서07", DOC7, 0, f"'전체 행은 N개다'가 {m.group(1) if m else '없음'}인데 BL 행은 {len(bl)}개다", ERR))
    m = re.search(r"둘 이상일 수 있다\((\d+)행\)", text)
    n += 1
    if not m or int(m.group(1)) != multi:
        P.append(("문서07", DOC7, 0, f"분류가 둘 이상인 행 수가 {m.group(1) if m else '없음'}인데 세면 {multi}이다", ERR))
    remaining = {r[0] for r in av if not r[1].startswith("**했다")}
    m = re.search(r"아직 하지 않은 일이 ([가-힣]+) 가지 있다\(([^)]*)\)", text)
    n += 1
    if not m:
        P.append(("문서07", DOC7, 0, "§0의 'AI가 할 수 있는데 아직 하지 않은 일이 N가지' 문장을 찾지 못했다", ERR))
    else:
        num = KNUM.get(m.group(1))
        listed = set(re.findall(r"AV-\d+", m.group(2)))
        if num != len(remaining):
            P.append(("문서07", DOC7, 0, f"§0이 AI가 할 수 있는 일을 '{m.group(1)} 가지'라 하는데 §5에서 '했다'가 아닌 행은 {len(remaining)}개다", ERR))
        if listed != remaining:
            P.append(("문서07", DOC7, 0, f"§0이 든 AV 목록 {sorted(listed)}이 §5의 남은 행 {sorted(remaining)}과 다르다", ERR))
    ids = {r[0] for r in bl} | {r[0] for r in av}
    for path in c.md:
        for ln, line in enumerate(c.lines[path], 1):
            for m2 in re.finditer(r"\b(BL-[A-Z]?\d+|AV-\d+)\b", line):
                n += 1
                if m2.group(1) not in ids:
                    P.append(("문서07", path, ln, f"문서 07에 없는 항목: {m2.group(1)}", ERR))
            for m2 in re.finditer(r"하지 못한 일 (\d+)건", line):
                n += 1
                if int(m2.group(1)) != len(bl):
                    P.append(("문서07", path, ln, f"'하지 못한 일 {m2.group(1)}건'인데 문서 07의 BL 행은 {len(bl)}개다", ERR))
    return P, n


def report_total(texts, path):
    t = texts.get(path)
    if t is None:
        return None
    if path == PILOT:
        return len(re.findall(r"(?m)^- 통과", t)), len(re.findall(r"(?m)^- (?:실패|FAIL)", t))
    for i, p in enumerate(REPORT_PATTERNS):
        m = p.search(t)
        if not m:
            continue
        if i == 2:
            return int(m.group(1)), 0
        if i == 4:
            return int(m.group(2)), int(m.group(1))
        return int(m.group(1)), int(m.group(2))
    return None


def rule_citations(c):
    P, n = [], 0
    texts = c.repo.texts
    for doc, pat, reports in PAIRS:
        t = texts.get(doc)
        m = re.search(pat, t) if t else None
        n += 1
        if not m:
            P.append(("수치인용", doc, 0, f"인용 문구를 찾지 못했다(문서를 고쳤다면 PAIRS도 고칠 것): {pat[:40]}", ERR))
            continue
        for i, rep in enumerate(reports):
            tot = report_total(texts, rep)
            if tot is None:
                P.append(("수치인용", rep, 0, "보고서에서 점검 개수를 읽지 못했다", ERR))
            elif int(m.group(i + 1)) != tot[0]:
                P.append(("수치인용", doc, 0, f"문서는 {m.group(i + 1)}이라 적었는데 {rep}는 {tot[0]}이다", ERR))
    for ck in CHECKS:
        tot = report_total(texts, ck.report)
        if tot is not None:
            n += 1
            if tot[1] != 0:
                P.append(("수치인용", ck.report, 0, f"보고서가 실패·놓친 것 {tot[1]}건을 적었다", ERR))
    for doc, pat, what in COUNT_DOCS:
        t = texts.get(doc)
        n += 1
        if t is None:
            P.append(("수치인용", doc, 0, "문서가 없다", ERR))
            continue
        m = re.search(pat, t)
        if not m:
            P.append(("수치인용", doc, 0, f"인용 문구를 찾지 못했다(문서를 고쳤다면 COUNT_DOCS도 고칠 것): {pat[:40]}", ERR))
            continue
        want = len(CHECKS) if what == "CHECKS" else len(RULES)
        if int(m.group(1)) != want:
            P.append(("수치인용", doc, 0, f"문서는 {what} {m.group(1)}개라 적었는데 스크립트의 목록은 {want}개다", ERR))
    n += 1
    if REPO_REPORT not in texts:
        P.append(("수치인용", REPO_REPORT, 0, "저장소 점검 보고서가 없다(`--report`로 만든다. 처음에는 두 번 돌린다)", ERR))
    else:
        tot = report_total(texts, REPO_REPORT)
        if tot is None:
            P.append(("수치인용", REPO_REPORT, 0, "보고서에서 자체 시험 개수를 읽지 못했다", ERR))
        elif tot[0] != len(mutants()):
            P.append(("수치인용", REPO_REPORT, 0, f"보고서의 자체 시험은 {tot[0]}건인데 스크립트는 {len(mutants())}건이다(보고서를 다시 만들 것)", ERR))
        elif tot[1] != 0:
            P.append(("수치인용", REPO_REPORT, 0, f"보고서가 놓친 것 {tot[1]}건을 적었다", ERR))
    return P, n


def rule_state(c):
    P, n = [], 0
    texts = c.repo.texts
    readme, log = texts.get("README.md", ""), texts.get("docs/00-progress-log.md", "")
    m = re.search(r"## 현재 상태 \((\d{4}-\d{2}-\d{2})\)", readme)
    dates = []
    for line in log.split("\n"):
        mm = re.match(r"^\| (\d{4})-(\d{2})-(\d{2})(?:–(\d{2})-(\d{2}))? \|", line)
        if mm:
            dates.append(f"{mm.group(1)}-{mm.group(4)}-{mm.group(5)}" if mm.group(4) else f"{mm.group(1)}-{mm.group(2)}-{mm.group(3)}")
    n += 1
    if not m or not dates:
        P.append(("현재상태", "README.md", 0, "README의 '현재 상태 (날짜)' 제목이나 진행 기록의 날짜 행을 찾지 못했다", ERR))
    elif m.group(1) < max(dates):
        P.append(("현재상태", "README.md", 0, f"'현재 상태' 날짜 {m.group(1)}가 진행 기록의 마지막 날짜 {max(dates)}보다 이르다", ERR))

    def version(path):
        t = texts.get(path)
        vs = re.findall(r"v(\d+\.\d+)", t.split("\n")[0]) if t else []
        return vs[-1] if vs else None

    gv, pv = version("docs/rq2/grid.md"), version("prereg/RQ2.md")
    n += 2
    if gv is None or pv is None:
        P.append(("현재상태", "docs/rq2/grid.md", 0, "문서 머리의 버전을 읽지 못했다", ERR))
        return P, n
    for v in re.findall(r"`grid\.md` v(\d+\.\d+)", readme):
        n += 1
        if v != gv:
            P.append(("현재상태", "README.md", 0, f"README는 grid.md v{v}라 적었는데 문서 머리는 v{gv}다", ERR))
    for line in texts.get(DOC7, "").split("\n"):
        if line.startswith("| RQ2 |"):
            for v in re.findall(r"격자 v(\d+\.\d+)", line):
                n += 1
                if v != gv:
                    P.append(("현재상태", DOC7, 0, f"문서 07은 격자 v{v}라 적었는데 문서 머리는 v{gv}다", ERR))
            for v in re.findall(r"`prereg/RQ2\.md` v(\d+\.\d+)", line):
                n += 1
                if v != pv:
                    P.append(("현재상태", DOC7, 0, f"문서 07은 prereg/RQ2 v{v}라 적었는데 문서 머리는 v{pv}다", ERR))
    return P, n


@functools.lru_cache(maxsize=None)
def scan_hygiene(text):
    out = []
    for ln, line in enumerate(text.split("\n"), 1):
        for label, rx in SECRET_PATTERNS:
            if rx.search(line):
                out.append((ln, f"비밀값처럼 보이는 문자열({label}). 값은 적지 않는다", ERR))
        if WINPATH.search(line):
            out.append((ln, "사용자 PC 경로(Windows 사용자 이름 포함). 이름은 보고서에 적지 않는다", NOTE))
        if UNIXHOME.search(line):
            out.append((ln, "사용자 홈 경로(사용자 이름 포함). 이름은 보고서에 적지 않는다", NOTE))
        if EMAIL.search(line):
            out.append((ln, "이메일 주소. 주소는 보고서에 적지 않는다", NOTE))
    return tuple(out)


def rule_hygiene(c):
    P, n = [], 0
    for f in sorted(c.files):
        n += 1
        ext = os.path.splitext(f)[1].lower()
        if ext in BAD_EXT:
            P.append(("위생", f, 0, "추적하면 안 되는 형식(제3자 원문, 압축 파일, 바이트코드)", ERR))
        if "__pycache__/" in f:
            P.append(("위생", f, 0, "__pycache__는 추적하지 않는다", ERR))
        sz = c.repo.sizes.get(f, 0)
        if sz > 50 * 1024 * 1024:
            P.append(("위생", f, 0, f"파일이 50MB를 넘는다({sz // (1024 * 1024)}MB). GitHub의 한도는 100MB다", ERR))
        elif sz > 10 * 1024 * 1024:
            P.append(("위생", f, 0, f"파일이 10MB를 넘는다({sz // (1024 * 1024)}MB)", NOTE))
    for f, text in sorted(c.repo.texts.items()):
        for ln, label, kind in scan_hygiene(text):
            P.append(("위생", f, ln, label, kind))
    return P, n


def rule_runner(c):
    P, n = [], 0
    scripts = [ck.script for ck in CHECKS]
    for f in sorted(c.files):
        if f != SELF and (re.search(r"(?:^|/)check_[A-Za-z0-9_]+\.py$", f) or f == "oracle/mutation_check.py"):
            n += 1
            if f not in scripts:
                P.append(("러너", f, 0, "자체 점검 스크립트가 실행 목록(CHECKS)에 없다", ERR))
    for ck in CHECKS:
        n += 1
        if ck.script not in c.files:
            P.append(("러너", SELF, 0, f"CHECKS의 {ck.name}: 스크립트가 없다: {ck.script}", ERR))
        if ck.report not in c.files:
            P.append(("러너", SELF, 0, f"CHECKS의 {ck.name}: 보고서 파일이 없다: {ck.report}", ERR))
    for k, v in Counter(ck.name for ck in CHECKS).items():
        if v > 1:
            P.append(("러너", SELF, 0, f"CHECKS의 이름이 겹친다: {k}", ERR))
    return P, n


def rule_layout(c):
    """README의 구성 표가 실제 폴더를 빠뜨리지 않는가."""
    P, n = [], 0
    readme = c.repo.texts.get("README.md", "")
    firsts = " ".join(cells(l)[0] for l in readme.split("\n") if l.startswith("| `"))
    for top in sorted({f.split("/")[0] for f in c.files if "/" in f}):
        n += 1
        if f"`{top}/" not in firsts:
            P.append(("구성", "README.md", 0, f"구성 표에 {top}/ 행이 없다", ERR))
    for top in ("docs", "formal", "analysis"):
        for sub_dir in sorted({"/".join(f.split("/")[:2]) for f in c.files if f.startswith(top + "/") and f.count("/") >= 2}):
            n += 1
            if f"{sub_dir}/" not in readme:
                P.append(("구성", "README.md", 0, f"README가 {sub_dir}/ 폴더를 설명하지 않는다", ERR))
    return P, n


# 'G5 ... 통과'가 들어간 줄에 이 말이 없으면 통과를 단정한 문장일 수 있다(2026-11-07에 저장소 전체를 조사해 맞춘 목록).
G5_NEG = ("미통과", "않았", "않는", "않은", "아니", "않다", "못", "아직", "전이다", "전에", "전 ", "전(", "전,", "전의",
          "뒤에", "이후", "까지", "해야", "하면", "한 뒤", "때")
FREEZE_TAG = re.compile(r"spec-v\d+|prereg-RQ\w+-v\d+")


def rule_claims(c):
    """사람의 검토 없이 G5 통과나 동결을 단정하지 않았는가(알림만 낸다)."""
    P, n = [], 0
    for path in c.md:
        if path.startswith("formal/repo/"):
            continue  # 이 도구가 만든 보고서는 자체 시험의 이름을 표에 적는다('G5 통과를 단정한 문장' 같은 이름이 들어 있다)
        for ln, line in enumerate(c.lines[path], 1):
            if "G5" in line and "통과" in line:
                n += 1
                if not any(w in line for w in G5_NEG):
                    P.append(("주장수위", path, ln, "G5 통과를 단정한 문장일 수 있다(사람의 검토 전에는 통과라고 쓰지 않는다)", NOTE))
    for t in c.repo.tags:
        n += 1
        if FREEZE_TAG.fullmatch(t):
            P.append(("주장수위", "(git 태그)", 0, f"동결 태그가 있다: {t}. 문서의 '동결 전'과 'G5 미통과' 표기를 사람이 확인해 갱신할 것", NOTE))
    return P, n


RULES = [
    ("경로", rule_paths), ("절 참조", rule_sections), ("해시", rule_hashes), ("대장", rule_ledger),
    ("검색기록", rule_g4), ("열린항목", rule_open_items), ("문서07", rule_doc07), ("수치인용", rule_citations),
    ("현재상태", rule_state), ("구성", rule_layout), ("주장수위", rule_claims), ("위생", rule_hygiene), ("러너", rule_runner),
]


def check(repo):
    c = Ctx(repo)
    problems, stats = [], {}
    for name, fn in RULES:
        p, n = fn(c)
        problems += p
        stats[name] = n
    return problems, stats


# ---------------------------------------------------------------------------------------------
# 자체 시험: 일부러 망가뜨린 저장소 사본이 규칙마다 잡히는가
# ---------------------------------------------------------------------------------------------

def sub(repo, path, old, new, count=1):
    t = repo.texts[path]
    if t.count(old) < 1:
        raise SystemExit(f"자체 시험의 기준 문구가 {path}에서 사라졌다(시험을 고칠 것): {old[:40]!r}")
    repo.texts[path] = t.replace(old, new, count)


def add_text(repo, path, extra):
    repo.texts[path] = repo.texts[path] + extra


def edit_group(repo, path, rx, fn, group=1):
    """정규식의 첫 일치에서 group 칸의 글을 fn(글)으로 바꾼다. 기준 문구가 없어지면 시험을 고치라고 알린다."""
    t = repo.texts[path]
    m = re.search(rx, t)
    if not m:
        raise SystemExit(f"자체 시험의 기준 문구가 {path}에서 사라졌다(시험을 고칠 것): {rx[:50]!r}")
    s, e = m.span(group)
    repo.texts[path] = t[:s] + fn(m.group(group)) + t[e:]


def bump(repo, path, rx, delta=1):
    edit_group(repo, path, rx, lambda v: str(int(v) + delta))


def set_cell(line, idx, value):
    cs = cells(line)
    cs[idx] = value
    return "| " + " | ".join(cs) + " |"


def ledger_line_matching(repo, pred):
    for i, line in ledger_rows(repo.texts[LEDGER]):
        if pred(cells(line)):
            return line
    raise SystemExit("자체 시험의 기준 행을 대장에서 찾지 못했다")


def ledger_set(repo, pred, idx, value):
    ln = ledger_line_matching(repo, pred)
    sub(repo, LEDGER, ln, set_cell(ln, idx, value))


def drop_lines(repo, path, pred):
    t = repo.texts[path]
    keep = [l for l in t.split("\n") if not pred(l)]
    if len(keep) == len(t.split("\n")):
        raise SystemExit(f"자체 시험의 기준 줄이 {path}에서 사라졌다(시험을 고칠 것)")
    repo.texts[path] = "\n".join(keep)


def dup_line(repo, path, pred):
    t = repo.texts[path]
    ln = next((l for l in t.split("\n") if pred(l)), None)
    if ln is None:
        raise SystemExit(f"자체 시험의 기준 줄이 {path}에서 사라졌다(시험을 고칠 것)")
    repo.texts[path] = t + "\n" + ln


def first_bl_row(repo):
    return next(l for l in repo.texts[DOC7].split("\n") if re.match(r"^\| BL-", l))


def other_number_word(w):
    return next(k for k in KNUM if k != w)


def drop_last_av(s):
    items = [x.strip() for x in s.split(",")]
    return ", ".join(items[:-1])


def ensure_repo_report(repo):
    """이 도구의 보고서가 아직 없는 저장소(처음 만들 때)에서도 보고서와 맞춰 보는 시험이 돌게 맞는 개수의 보고서를 둔다."""
    if REPO_REPORT not in repo.texts:
        repo.texts[REPO_REPORT] = f"시험 {len(mutants())}건(망가뜨린 입력 0건, 정상 입력 0건) 중 놓친 것 0건"


def stale_repo_report(repo):
    """이 도구의 보고서가 가진 시험 개수를 어긋나게 한다(보고서가 아직 없으면 어긋난 보고서를 만든다)."""
    if REPO_REPORT not in repo.texts:
        repo.texts[REPO_REPORT] = "시험 1건(망가뜨린 입력 1건, 정상 입력 0건) 중 놓친 것 0건"
    else:
        bump(repo, REPO_REPORT, r"시험 (\d+)건\(망가뜨린 입력")


def shrink_o3_range(repo):
    """prereg/RQ3.md에서 범위로 정의한 행의 끝을 하나 줄인다."""
    t = repo.texts["prereg/RQ3.md"]
    m = re.search(r"(?m)^\| (O3-\d+–O3-)(\d+) \|", t)
    if not m:
        raise SystemExit("자체 시험의 기준 줄(범위로 정의한 열린 항목)이 prereg/RQ3.md에서 사라졌다(시험을 고칠 것)")
    s, e = m.span(2)
    repo.texts["prereg/RQ3.md"] = t[:s] + str(int(m.group(2)) - 1) + t[e:]


def mutants():
    """(이름, 규칙, 변형 함수, 종류). 종류가 오류·알림이면 그 규칙이 새로 내야 하고, 정상이면 아무 문제도 새로 내면 안 된다."""
    win = "C" + ":" + "\\Users\\" + "tester" + "\\x"
    fake_token = "gh" + "p_" + "A1b2C3d4" * 5
    mail = "tester" + "@" + "example.org"
    bad_hash = "1234" + "abc"
    out = []

    def m(name, rule, fn, kind=ERR):
        out.append((name, rule, fn, kind))

    # 경로
    m("없는 경로를 백틱으로 인용", "경로", lambda r: add_text(r, "README.md", "\n`docs/zz-missing-doc.md`\n"))
    m("코드 블록 안의 없는 경로", "경로", lambda r: add_text(r, "README.md", "\n```\npython3 -I oracle/missing_check.py x\n```\n"))
    m("링크 대상이 없음", "경로", lambda r: add_text(r, "README.md", "\n[없음](docs/missing.md)\n"))
    m("PLANNED 항목이 이미 존재", "경로", lambda r: (r.files.add("formal/rq2/attempts.md"), r.texts.setdefault("formal/rq2/attempts.md", "")))
    m("링크 대상이 있음(앵커 포함)", "경로", lambda r: add_text(r, "README.md", "\n[문서 07](docs/07-followup-scope.md#3-하지-않은-일)\n"), OK)
    m("조사가 붙은 경로(코드 블록 주석)", "경로", lambda r: add_text(r, "README.md", "\n```\npython3 -I bench/pilot_rq6.py summary   # experiments/pilot/의 자료\n```\n"), OK)
    m("자리표시 경로(꺾쇠 안의 한글)", "경로", lambda r: add_text(r, "README.md", "\n`analysis/rq5/coding/<회차>-<코더>.csv`\n"), OK)
    m("중괄호로 묶은 경로", "경로", lambda r: add_text(r, "README.md", "\n`bench/{policies,literature}`\n"), OK)
    # 절 참조
    m("없는 절을 경로로 인용", "절 참조", lambda r: add_text(r, "README.md", "\n`docs/rq2/grid.md` §99\n"))
    m("없는 절을 문서 번호로 인용", "절 참조", lambda r: add_text(r, "README.md", "\n문서 05 §99.1\n"))
    m("없는 문서 번호", "절 참조", lambda r: add_text(r, "README.md", "\n문서 99 §1\n"))
    m("있는 절 인용", "절 참조", lambda r: add_text(r, "README.md", "\n`docs/07-followup-scope.md` §3.1\n"), OK)
    # 해시
    m("저장소에 없는 커밋 해시", "해시", lambda r: add_text(r, "README.md", f"\n커밋 {bad_hash}\n"))
    m("해시 대신 git log 안내", "해시", lambda r: add_text(r, "README.md", "\n`git log -- docs/rq2/grid.md`\n"))
    m("외부 커밋 목록이 이 저장소의 커밋과 겹침", "해시", lambda r: r.commits.append("ffcad0c" + "0" * 33))
    # 대장
    m("없는 대장 번호", "대장", lambda r: add_text(r, "README.md", "\nC-SUR-999\n"))
    m("끝이 없는 대장 범위", "대장", lambda r: add_text(r, "README.md", "\nC-SUR-260–999\n"))
    m("거꾸로 된 대장 범위", "대장", lambda r: add_text(r, "README.md", "\nC-SUR-200–100\n"))
    m("있는 대장 범위", "대장", lambda r: add_text(r, "README.md", "\nC-SUR-250–260\n"), OK)
    m("대장 행 중복", "대장", lambda r: sub(r, LEDGER, ledger_line_matching(r, lambda c: c[0] == "C-SUR-002"),
                                           ledger_line_matching(r, lambda c: c[0] == "C-SUR-002") + "\n"
                                           + ledger_line_matching(r, lambda c: c[0] == "C-SUR-002")))
    m("대장 행 삭제(번호 틈)", "대장", lambda r: sub(r, LEDGER, ledger_line_matching(r, lambda c: c[0] == "C-SUR-100") + "\n", ""))
    m("대장 행의 열이 모자람", "대장", lambda r: sub(r, LEDGER, ledger_line_matching(r, lambda c: c[0] == "C-SUR-001"),
                                                  ledger_line_matching(r, lambda c: c[0] == "C-SUR-001").rstrip("|").rstrip().rsplit("|", 1)[0] + "|"))
    m("대장의 수준 어휘 밖", "대장", lambda r: ledger_set(r, lambda c: c[0] == "C-SUR-001", 4, "Z"))
    m("낮은 수준인데 전제로 사용 '가'", "대장", lambda r: ledger_set(r, lambda c: c[4] == "C" and c[6] == "불가", 6, "가"))
    m("대장 전제로 사용 칸이 가/불가가 아님", "대장", lambda r: ledger_set(r, lambda c: c[0] == "C-SUR-001", 6, "예"))
    m("대장 확인일 형식이 아님", "대장", lambda r: ledger_set(r, lambda c: c[5] == "2026-11-07", 5, "2026/11/07"))
    # 검색 기록
    m("없는 G4 번호", "검색기록", lambda r: add_text(r, "README.md", "\nG4-999\n"))
    m("있는 G4 범위", "검색기록", lambda r: add_text(r, "README.md", "\nG4-300–G4-310\n"), OK)
    m("G4 행 삭제(번호 틈)", "검색기록", lambda r: drop_lines(r, G4_LOG, lambda l: l.startswith("| G4-100 |")))
    m("G4 행 중복", "검색기록", lambda r: dup_line(r, G4_LOG, lambda l: l.startswith("| G4-050 |")))
    m("거꾸로 된 G4 범위", "검색기록", lambda r: add_text(r, "README.md", "\nG4-310–G4-300\n"))
    m("'G4-nnn부터'가 다음 번호가 아님", "검색기록", lambda r: add_text(r, "README.md", "\n새 검색은 G4-300부터 적는다\n"))
    # 열린 항목
    m("정의되지 않은 열린 항목", "열린항목", lambda r: add_text(r, "README.md", "\nO2-99\n"))
    m("열린 항목 정의 삭제(번호 틈)", "열린항목", lambda r: drop_lines(r, "prereg/RQ2.md", lambda l: re.match(r"^\|\s*O2-5\b", l) is not None))
    m("범위로 정의한 열린 항목의 끝을 줄임", "열린항목", shrink_o3_range)
    m("열린 항목 범위 참조의 끝이 정의 밖", "열린항목", lambda r: add_text(r, "README.md", "\nO3-10–O3-99\n"))
    m("거꾸로 된 열린 항목 범위", "열린항목", lambda r: add_text(r, "README.md", "\nO3-18–O3-10\n"))
    m("정의된 열린 항목 범위", "열린항목", lambda r: add_text(r, "README.md", "\nO3-10–O3-18, O3-22–O3-26\n"), OK)
    # 문서 07
    m("문서 07 §3.1 집계가 다름", "문서07", lambda r: bump(r, DOC7, r"(?m)^\| 동결 \| (\d+) \|$"))
    m("문서 07 '전체 행은 N개'가 다름", "문서07", lambda r: bump(r, DOC7, r"전체 행은 (\d+)개다"))
    m("문서 07 '둘 이상' 행 수가 다름", "문서07", lambda r: bump(r, DOC7, r"둘 이상일 수 있다\((\d+)행\)"))
    m("문서 07 AI 할 일 개수가 다름", "문서07", lambda r: edit_group(r, DOC7, r"아직 하지 않은 일이 ([가-힣]+) 가지", other_number_word))
    m("문서 07 AI 할 일 목록에서 항목 누락", "문서07", lambda r: edit_group(r, DOC7, r"아직 하지 않은 일이 [가-힣]+ 가지 있다\(([^)]*)\)", drop_last_av))
    m("문서 07의 사유가 분류 밖", "문서07", lambda r: sub(r, DOC7, first_bl_row(r), set_cell(first_bl_row(r), 2, "미정")))
    m("문서 07 BL 행의 열이 모자람", "문서07", lambda r: sub(r, DOC7, first_bl_row(r), "| " + " | ".join(cells(first_bl_row(r))[:-1]) + " |"))
    m("문서 07에 없는 BL 참조", "문서07", lambda r: add_text(r, "README.md", "\nBL-99\n"))
    m("'하지 못한 일 N건'이 다름", "문서07", lambda r: bump(r, "README.md", r"하지 못한 일 (\d+)건의 사유"))
    # 수치 인용
    m("README의 격자 점검 개수가 보고서와 다름", "수치인용", lambda r: bump(r, "README.md", r"집계, 자체 시험 (\d+)건"))
    m("README의 저장소 점검 시험 개수가 보고서와 다름", "수치인용",
      lambda r: (ensure_repo_report(r), bump(r, "README.md", r"저장소 점검 스크립트\(`analysis/repo/check_repo\.py`\)와 자체 시험 (\d+)건")))
    m("보고서가 실패를 적음", "수치인용", lambda r: edit_group(r, CODEBOOK, r"검사 \d+개, 실패 (\d+)개", lambda v: str(int(v) + 1)))
    m("README의 자체 점검 개수가 목록과 다름", "수치인용", lambda r: bump(r, "README.md", r"자체 점검 (\d+)개를 한 번에"))
    m("README의 점검 규칙 개수가 목록과 다름", "수치인용", lambda r: bump(r, "README.md", r"점검 규칙 (\d+)개"))
    m("이 도구의 보고서가 낡음(시험 개수가 다름)", "수치인용", stale_repo_report)
    m("인용 문구가 사라짐", "수치인용", lambda r: sub(r, "README.md", "정책 검사 ", "정책 점검 "))
    # 현재 상태
    m("README의 현재 상태 날짜가 낡음", "현재상태", lambda r: edit_group(r, "README.md", r"## 현재 상태 \((\d{4}-\d{2}-\d{2})\)", lambda v: "2000-01-01"))
    m("README의 격자 버전이 문서와 다름", "현재상태", lambda r: edit_group(r, "README.md", r"`grid\.md` v(\d+\.\d+)", lambda v: "9.9"))
    m("문서 07의 prereg 버전이 문서와 다름", "현재상태", lambda r: edit_group(r, DOC7, r"`prereg/RQ2\.md` v(\d+\.\d+)", lambda v: "9.9"))
    # 구성
    m("구성 표에서 최상위 폴더의 행을 지움", "구성", lambda r: drop_lines(r, "README.md", lambda l: l.startswith("| `traces/")))
    m("README가 설명하지 않는 하위 폴더", "구성", lambda r: (r.files.add("formal/zzz/x.md"), r.sizes.__setitem__("formal/zzz/x.md", 10)))
    # 주장 수위
    m("G5 통과를 단정한 문장(알림)", "주장수위", lambda r: add_text(r, "README.md", "\nG5가 통과했다.\n"), NOTE)
    m("G5 통과를 부정한 문장", "주장수위", lambda r: add_text(r, "README.md", "\nG5는 통과하지 않았다.\n"), OK)
    m("동결 태그가 생김(알림)", "주장수위", lambda r: r.tags.append("prereg-RQ6-v1"), NOTE)
    # 위생
    m("PDF 추적", "위생", lambda r: (r.files.add("refs/원문.pdf"), r.sizes.__setitem__("refs/원문.pdf", 10)))
    m("__pycache__ 추적", "위생", lambda r: (r.files.add("bench/__pycache__/x.cpython-313.pyc"), r.sizes.__setitem__("bench/__pycache__/x.cpython-313.pyc", 10)))
    m("너무 큰 파일", "위생", lambda r: (r.files.add("experiments/big.jsonl"), r.sizes.__setitem__("experiments/big.jsonl", 60 * 1024 * 1024)))
    m("10MB가 넘는 파일(알림)", "위생", lambda r: (r.files.add("experiments/mid.jsonl"), r.sizes.__setitem__("experiments/mid.jsonl", 12 * 1024 * 1024)), NOTE)
    m("사용자 홈 경로(알림)", "위생", lambda r: add_text(r, "README.md", "\n`/home/" + "tester" + "/x`\n"), NOTE)
    m("비밀값처럼 보이는 문자열", "위생", lambda r: add_text(r, "README.md", f"\n토큰 {fake_token}\n"))
    m("개인 경로(알림)", "위생", lambda r: add_text(r, "README.md", f"\n`{win}`\n"), NOTE)
    m("이메일 주소(알림)", "위생", lambda r: add_text(r, "README.md", f"\n{mail}\n"), NOTE)
    # 러너
    m("실행 목록에 없는 점검 스크립트", "러너", lambda r: (r.files.add("bench/check_zzz.py"), r.sizes.__setitem__("bench/check_zzz.py", 10)))
    m("실행 목록의 스크립트가 없음", "러너", lambda r: r.files.discard("oracle/check_sm.py"))
    m("실행 목록의 보고서가 없음", "러너", lambda r: r.files.discard("formal/rq2/grid-check.md"))
    return out


def self_tests(repo, base_problems):
    base = Counter(base_problems)
    res = []
    for name, rule, fn, kind in mutants():
        r = repo.copy()
        fn(r)
        new = Counter(check(r)[0]) - base
        if kind == OK:
            caught = not new  # 정상 입력이 새 문제를 내지 않아야 한다
        else:
            caught = any(p[0] == rule and p[4] == kind for p in new)
        res.append((name, rule, kind, caught))
    return res


# ---------------------------------------------------------------------------------------------
# 보고
# ---------------------------------------------------------------------------------------------

def head_info(root=ROOT):
    try:
        head = git("rev-parse", "--short=7", "HEAD", root=root).decode().strip()
        dirty = bool(git("status", "--porcelain", root=root).decode().strip())
    except Exception:
        head, dirty = "알 수 없음", False
    return head, dirty


def fmt_report(repo, problems, stats, tests, head, dirty):
    errs = [p for p in problems if p[4] == ERR]
    notes = [p for p in problems if p[4] == NOTE]
    missed = [t for t in tests if not t[3]]
    L = ["# 저장소 상호 참조 점검 보고서 (스냅샷)", "",
         f"- 점검한 것: 작업 트리(HEAD {head}{'에 커밋하지 않은 변경을 더한 상태' if dirty else ''}). 이 보고서를 담은 커밋의 직전 상태다. 다시 실행하면 저장소가 바뀐 만큼 수가 달라진다.",
         "- 생성: `python3 -I analysis/repo/check_repo.py --report formal/repo/repo-check.md`",
         "- 이 점검은 문서의 형식과 일관성(경로, 절, 해시, 번호, 집계, 위생)을 본 것이며 문헌의 내용이 옳은지는 보지 않는다. 증명이 아니다.",
         "- AI(Claude)가 쓴 초안이며 사람의 검토 전이다.", "",
         "## 저장소", "", "| 항목 | 값 |", "|---|---|",
         f"| 파일(추적 + 아직 추적하지 않은 것) | {len(repo.files)} |",
         f"| 마크다운 문서 | {sum(1 for p in repo.texts if p.endswith('.md'))} |",
         f"| 커밋 | {len(repo.commits)} |", "",
         "## 규칙별 결과", "", "| 규칙 | 살펴본 항목 | 오류 | 알림 |", "|---|---:|---:|---:|"]
    for name, _ in RULES:
        L.append(f"| {name} | {stats[name]} | {sum(1 for p in errs if p[0] == name)} | {sum(1 for p in notes if p[0] == name)} |")
    L += ["", "## 오류", ""]
    L += [f"- {p[0]}: {p[1]}{':' + str(p[2]) if p[2] else ''} {p[3]}" for p in errs] or ["문제 없음."]
    L += ["", "## 알림(사람에게 알릴 것)", ""]
    L += [f"- {p[0]}: {p[1]}{':' + str(p[2]) if p[2] else ''} {p[3]}" for p in notes] or ["없음."]
    n_bad = sum(1 for t in tests if t[2] != OK)
    n_ok = len(tests) - n_bad
    L += ["", "## 자체 시험", "",
          "일부러 망가뜨린 저장소 사본(메모리 안)을 같은 점검에 넣어 해당 규칙이 새 문제를 내는지 본다(종류 '오류'·'알림'). "
          "종류 '정상'은 거꾸로, 올바른 표기를 더했을 때 아무 문제도 새로 나지 않는지(오탐이 없는지) 본다.", "",
          "| 시험 | 규칙 | 종류 | 결과 |", "|---|---|---|---|"]
    for name, rule, kind, caught in tests:
        res = ("오탐 없음" if caught else "**오탐**") if kind == OK else ("잡음" if caught else "**놓침**")
        L.append(f"| {name} | {rule} | {kind} | {res} |")
    L += ["", f"- 시험 {len(tests)}건(망가뜨린 입력 {n_bad}건, 정상 입력 {n_ok}건) 중 놓친 것 {len(missed)}건.", "",
          "## 이 점검이 하지 않는 것", "",
          "- 문서가 말하는 내용이 사실인지, 칸의 상태가 맞는지, 판정이 옳은지는 보지 않는다.",
          "- 문서 07의 사유 분류가 맞는지, README의 요약이 충분한지도 보지 않는다. 숫자와 이름이 서로 맞는지만 본다.",
          "- 경로는 전체 경로(analysis/, bench/, docs/, experiments/, formal/, oracle/, prereg/, refs/, traces/로 시작하거나 README.md)만 본다. 짧은 파일 이름은 보지 않는다.",
          "- 7자리가 아닌 해시, 외부 문헌의 번호, 문서 안의 문장 사이의 모순은 보지 않는다.",
          "- 자체 점검의 일괄 실행(`--run`)은 이 보고서와 따로 기록한다(`formal/repo/run-all-check.md`)."]
    return "\n".join(L) + "\n"


def run_static(report_path=None):
    repo = load_repo()
    problems, stats = check(repo)
    tests = self_tests(repo, problems)
    head, dirty = head_info()
    errs = [p for p in problems if p[4] == ERR]
    notes = [p for p in problems if p[4] == NOTE]
    missed = [t for t in tests if not t[3]]
    print(f"저장소 점검: 파일 {len(repo.files)}개, 문서 {sum(1 for p in repo.texts if p.endswith('.md'))}개, 커밋 {len(repo.commits)}개 (HEAD {head}{', 변경 있음' if dirty else ''})")
    for name, _ in RULES:
        print(f"  {name:<8} 항목 {stats[name]:>5}  오류 {sum(1 for p in errs if p[0] == name):>3}  알림 {sum(1 for p in notes if p[0] == name):>3}")
    for p in errs:
        print(f"[오류] {p[0]}: {p[1]}{':' + str(p[2]) if p[2] else ''} {p[3]}")
    for p in notes:
        print(f"[알림] {p[0]}: {p[1]}{':' + str(p[2]) if p[2] else ''} {p[3]}")
    for t in missed:
        print(f"[{'오탐' if t[2] == OK else '놓침'}] 자체 시험: {t[0]} ({t[1]})")
    print(f"자체 시험 {len(tests)}건 중 놓친 것 {len(missed)}건. 오류 {len(errs)}건, 알림 {len(notes)}건.")
    if report_path:
        os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(fmt_report(repo, problems, stats, tests, head, dirty))
    return 1 if errs or missed else 0


# ---------------------------------------------------------------------------------------------
# 모든 자체 점검의 일괄 실행
# ---------------------------------------------------------------------------------------------

def tree_state(root):
    """무시되지 않는 모든 파일(추적 + 아직 추적하지 않은 것)의 내용 해시. 실행 전후를 견주어 바뀐 파일을 찾는다."""
    import hashlib
    out = {}
    for n in git("ls-files", "-co", "--exclude-standard", "-z", root=root).decode("utf-8").split("\0"):
        p = os.path.join(root, n)
        if n and os.path.isfile(p):
            with open(p, "rb") as f:
                out[n] = hashlib.sha256(f.read()).hexdigest()
    return out


def diff_state(before, after):
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


def run_all(out_dir, only, quick, jobs, run_report):
    out_dir = os.path.abspath(out_dir)  # 점검 스크립트는 저장소 루트에서 돌므로 상대 경로면 보고서가 엉뚱한 곳에 쓰인다
    if run_report:
        # 긴 실행이 끝난 뒤에 상대 경로를 풀면 작업 폴더가 낡아(마운트된 저장소에서 겪음) 실패할 수 있어 처음에 절대 경로로 바꾼다
        run_report = os.path.abspath(run_report)
    os.makedirs(out_dir, exist_ok=True)
    names = {ck.name for ck in CHECKS}
    for o in only or []:
        if o not in names:
            print(f"알 수 없는 점검 이름: {o} (가능한 이름: {', '.join(sorted(names))})")
            return 2
    sel = [ck for ck in CHECKS if (not only or ck.name in only) and not (quick and ck.slow)]
    before = tree_state(ROOT)
    t_all = time.time()

    def one(ck):
        outp = os.path.join(out_dir, os.path.basename(ck.report))
        cmd = [sys.executable, "-I", "-B", ck.script] + (["--report", outp] if ck.mode == "report" else [outp])
        t0 = time.time()
        try:
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=3600)
            last = (r.stdout + r.stderr).strip().split("\n")[-1].replace(out_dir, "<출력 폴더>")  # 컴퓨터마다 다른 임시 경로를 기록에 남기지 않는다
            rc, tail = r.returncode, last[:160]
        except subprocess.TimeoutExpired:
            rc, tail = "시간 초과", ""
        dt = time.time() - t0
        same = None
        if ck.same and rc == 0:
            try:
                with open(outp, encoding="utf-8") as a, open(os.path.join(ROOT, ck.report), encoding="utf-8") as b:
                    same = a.read() == b.read()
            except OSError:
                same = False
        return ck, rc, dt, same, tail

    order = sorted(sel, key=lambda ck: not ck.slow)  # 오래 걸리는 것을 먼저 시작한다(전체 시간이 줄어든다)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        done = list(ex.map(one, order))
    results = sorted(done, key=lambda r: CHECKS.index(r[0]))
    wall = time.time() - t_all
    after = tree_state(ROOT)
    bad = [r for r in results if r[1] != 0 or r[3] is False]
    lines = []
    for ck, rc, dt, same, tail in results:
        ok = rc == 0 and same is not False
        extra = "" if same is None else (", 보고서가 저장소의 것과 같음" if same else ", **보고서가 저장소의 것과 다름(낡음)**")
        lines.append(f"| {ck.name} | `{ck.script}` | {'통과' if ok else '**실패**'} | {rc} | {dt:.0f}초 | {tail.replace('|', '/')}{extra} |")
    changed = diff_state(before, after)
    print(f"자체 점검 {len(results)}개 실행(작업 폴더 {out_dir}):")
    for ln in lines:
        print(ln)
    print(f"실패 {len(bad)}개. 걸린 시간 {wall:.0f}초(병렬 {jobs}).")
    if changed:
        print(f"[경고] 실행 뒤 작업 트리가 달라졌다({len(changed)}개 파일: {', '.join(changed[:8])}). 점검이 저장소의 파일을 바꿨는지 확인할 것.")
    head, dirty = head_info()
    skipped = [ck.name for ck in CHECKS if ck not in sel]
    R = ["# 자체 점검 일괄 실행 기록 (스냅샷)", "",
         f"- 실행한 것: HEAD {head}{'에 커밋하지 않은 변경을 더한 상태' if dirty else ''}의 작업 트리. Python {sys.version.split()[0]}, {sys.platform}, 병렬 {jobs}.",
         "- 생성: `python3 -I analysis/repo/check_repo.py --run" + (" --quick" if quick else "") + " --run-report formal/repo/run-all-check.md`",
         "- 각 점검의 보고서는 임시 폴더에 쓰고 저장소의 보고서는 건드리지 않았다. 시간은 이 실행의 값이며 컴퓨터마다 다르다. 두 점검이 같은 코어를 나눠 썼으므로 한 점검씩 돌릴 때보다 길다.",
         "- 이 기록은 점검이 통과했다는 것이지 연구 결과가 아니다. AI(Claude)가 쓴 초안이며 사람의 검토 전이다.", "",
         "| 이름 | 스크립트 | 결과 | 종료 코드 | 시간 | 오래 걸림(`--quick`에서 뺌) | 마지막 출력 줄 |", "|---|---|---|---|---:|---|---|"]
    for (ck, rc, dt, same, tail), ln in zip(results, lines):
        R.append(ln.replace(f"| {dt:.0f}초 |", f"| {dt:.0f}초 | {'예' if ck.slow else '아니오'} |", 1))
    R += ["",
          f"- 실행 {len(results)}개, 실패 {len(bad)}개. 걸린 시간 {wall:.0f}초(병렬 {jobs}).",
          "- 실행 전후로 저장소의 모든 파일(추적 + 아직 추적하지 않은 것, 무시한 파일 제외)의 내용 해시를 견줬다: "
          + (f"달라진 파일 {len(changed)}개(확인 필요): {', '.join(changed[:8])}." if changed else "달라진 파일 없음.")]
    if skipped:
        R.append(f"- 이번에 실행하지 않은 것: {', '.join(skipped)}.")
    text = "\n".join(R) + "\n"
    saved = os.path.join(out_dir, "run-all-check.md")
    with open(saved, "w", encoding="utf-8") as f:
        f.write(text)  # 먼저 출력 폴더에 남겨 긴 실행의 결과를 잃지 않는다
    if run_report:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(run_report)), exist_ok=True)
            with open(run_report, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError as e:
            print(f"[경고] 기록을 {run_report}에 쓰지 못했다({e}). 내용은 {saved}에 있다.")
    return 1 if bad or changed else 0


def main(argv):
    args = argv[1:]
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0

    def opt(flag, default=None):
        return args[args.index(flag) + 1] if flag in args else default

    if "--run" in args:
        only = opt("--only")
        return run_all(opt("--out", os.path.join(tempfile.gettempdir(), f"repo-check-{os.getpid()}")),
                       only.split(",") if only else None, "--quick" in args, int(opt("--jobs", "2")), opt("--run-report"))
    return run_static(opt("--report"))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
