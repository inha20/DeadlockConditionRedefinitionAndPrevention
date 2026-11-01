"""뱅커 계열 안전성 정책. 기준 구현은 textbook.py, 문헌 변형 재구현은 변형마다 파일 하나(WP6.3)."""
from bench.policies.banker.base import DENY, ERROR, GRANT, WAIT, SafetyPolicy  # noqa: F401
from bench.policies.banker.textbook import TextbookRestart, TextbookSweep

REGISTRY = {cls.name: cls for cls in (TextbookRestart, TextbookSweep)}


def get(name: str) -> SafetyPolicy:
    if name not in REGISTRY:
        raise KeyError(f"등록되지 않은 정책: {name}")
    return REGISTRY[name]()
