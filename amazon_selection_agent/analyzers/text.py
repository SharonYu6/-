"""文本匹配工具：把关键词 / 标题 / 评论映射到词典标签。"""

from __future__ import annotations

import re
from functools import lru_cache


@lru_cache(maxsize=None)
def _pattern(term: str) -> re.Pattern[str]:
    # 整词匹配，允许复数 s；短语中的空格匹配任意空白或连字符
    body = r"[\s\-]+".join(re.escape(part) for part in term.lower().split())
    return re.compile(rf"(?<![a-z0-9]){body}s?(?![a-z0-9])")


def match_labels(text: str, mapping: dict[str, list[str]]) -> list[str]:
    """返回 text 命中的所有标签（每个标签最多一次）。"""
    text = str(text).lower()
    return [label for label, terms in mapping.items() if any(_pattern(t).search(text) for t in terms)]


_DIM_RE = re.compile(r"(\d{2,3})(?:\.\d+)?\s*(?:\"|''|in|inch|inches)?\s*(?:x|×|by|\*)\s*(\d{2,3})")
_SINGLE_IN_RE = re.compile(r"(\d{2,3})(?:\.\d+)?\s*(?:\"|in\b|inch|inches)")


def parse_inches(text: str) -> tuple[int, int] | int | None:
    """从关键词/标题解析英寸尺寸：'63x20' -> (63, 20)，'48 inch' -> 48。"""
    text = str(text).lower()
    m = _DIM_RE.search(text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return (max(a, b), min(a, b))
    m = _SINGLE_IN_RE.search(text)
    if m:
        return int(m.group(1))
    return None


def size_bucket(inches: tuple[int, int] | int | None) -> str | None:
    """按最长边分档，适用于镜子/置物架/收纳等大多数家居品。"""
    if inches is None:
        return None
    longest = inches[0] if isinstance(inches, tuple) else inches
    if longest < 24:
        return "小号 (<24in)"
    if longest < 48:
        return "中号 (24-47in)"
    if longest < 66:
        return "大号 (48-65in)"
    return "超大号 (66in+)"
