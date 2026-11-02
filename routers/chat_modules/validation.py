# -*- coding: utf-8 -*-
# ==============================================================================
# BEK — Validation utilities (v1.4.0)
# ★ v1.4.0 : Force des limites très hautes pour analyses multi-fichiers
# ==============================================================================
from __future__ import annotations

import ipaddress
import logging
import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any, Dict, List
from urllib.parse import urlsplit

logger = logging.getLogger("bek.validation")

# ★ v1.4.0 : Limites forcées pour ne jamais bloquer
MAX_MESSAGES = 40
MAX_MESSAGE_CHARS = 200_000
MAX_TOTAL_CHARS = 300_000
MAX_QUERY_CHARS = 4_000
MAX_URL_CHARS = 4_096
MAX_SUMMARY_CHARS = 2_000

ALLOWED_HISTORY_ROLES = frozenset({"user", "assistant"})

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"[^\W_]+", flags=re.UNICODE)
_DNS_LABEL_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", re.I)

_STERILE_URL_PATTERNS = (
    re.compile(r"^https?://(?:www\.)?google\.[^/]+/search(?:[/?#]|$)", re.I),
    re.compile(r"^https?://(?:www\.)?bing\.com/search(?:[/?#]|$)", re.I),
    re.compile(r"^https?://search\.yahoo\.com/search(?:[/?#]|$)", re.I),
    re.compile(r"^https?://duckduckgo\.com/(?:\?|html/|lite/)", re.I),
    re.compile(r"^https?://(?:www\.)?facebook\.com/(?:login|checkpoint)(?:[/?#]|$)", re.I),
    re.compile(r"^https?://accounts\.google\.com/", re.I),
    re.compile(r"^https?://[^/]+/robots\.txt(?:[?#]|$)", re.I),
    re.compile(r"^https?://[^/]+/sitemap(?:_[^/]*)?\.xml(?:[?#]|$)", re.I),
)

_QUERY_STOPWORDS = frozenset({
    "a", "à", "au", "aux", "avec", "ce", "ces", "dans", "de", "des",
    "du", "elle", "en", "et", "eux", "il", "ils", "je", "la", "le",
    "les", "leur", "lui", "ma", "mais", "me", "mes", "mon", "ne",
    "nos", "notre", "nous", "on", "ou", "par", "pas", "pour", "qu",
    "que", "qui", "sa", "se", "ses", "son", "sur", "ta", "te", "tes",
    "toi", "ton", "tu", "un", "une", "vos", "votre", "vous", "y",
    "the", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "in", "is", "it", "its", "of", "or", "that", "this",
    "to", "was", "were", "will", "with",
})

_EN_MARKERS = frozenset({
    "the", "what", "when", "where", "which", "who", "why", "how",
    "and", "with", "from", "about", "latest", "research",
})

_FR_MARKERS = frozenset({
    "le", "la", "les", "des", "une", "est", "sont", "dans", "pour",
    "avec", "quoi", "quand", "comment", "pourquoi", "recherche",
    "dernieres", "derniers",
})

def _safe_str(value: Any, max_len: int = MAX_MESSAGE_CHARS) -> str:
    if not isinstance(max_len, int) or isinstance(max_len, bool) or max_len < 0:
        max_len = MAX_MESSAGE_CHARS
    if value is None: return ""
    if isinstance(value, str): text = value
    elif isinstance(value, (int, float, bool)): text = str(value)
    else: return ""
    text = _CONTROL_CHARS_RE.sub("", text)
    return text[:max_len]

def normalize_query(query: Any, max_chars: int = MAX_QUERY_CHARS) -> str:
    if not isinstance(max_chars, int) or isinstance(max_chars, bool) or max_chars < 0:
        max_chars = MAX_QUERY_CHARS
    text = _safe_str(query, max_chars)
    return _WHITESPACE_RE.sub(" ", text).strip()

def _normalize_text_for_matching(value: Any) -> str:
    text = _safe_str(value, MAX_QUERY_CHARS).casefold()
    text = unicodedata.normalize("NFKD", text)
    return "".join(char for char in text if not unicodedata.combining(char))

def extract_significant_keywords(query: Any, min_length: int = 3, max_keywords: int = 20) -> List[str]:
    if not isinstance(max_keywords, int) or isinstance(max_keywords, bool): max_keywords = 20
    max_keywords = max(0, min(max_keywords, 100))
    if max_keywords == 0: return []
    if not isinstance(min_length, int) or isinstance(min_length, bool): min_length = 3
    min_length = max(1, min(min_length, 20))
    text = _normalize_text_for_matching(query)
    if not text: return []
    keywords: List[str] = []
    seen = set()
    for word in _WORD_RE.findall(text):
        if len(word) < min_length or word in _QUERY_STOPWORDS: continue
        if word in seen: continue
        seen.add(word)
        keywords.append(word)
        if len(keywords) >= max_keywords: break
    return keywords

def _extract_significant_keywords(query: Any, min_length: int = 3, max_keywords: int = 20) -> List[str]:
    return extract_significant_keywords(query, min_length, max_keywords)

def detect_query_language(query: Any) -> str:
    text = _normalize_text_for_matching(query)
    words = set(_WORD_RE.findall(text))
    fr_score = len(words & _FR_MARKERS)
    en_score = len(words & _EN_MARKERS)
    if fr_score == 0 and en_score == 0: return "unknown"
    if fr_score == en_score: return "unknown"
    return "fr" if fr_score > en_score else "en"

def translate_query(query: Any, target_language: str = "en") -> str:
    del target_language
    return normalize_query(query)

def _translate_query(query: Any, target_language: str = "en") -> str:
    return translate_query(query, target_language)

def _valid_hostname(hostname: str) -> bool:
    if not hostname or len(hostname) > 253: return False
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError: pass
    dns_name = hostname[:-1] if hostname.endswith(".") else hostname
    if not dns_name: return False
    try: ascii_name = dns_name.encode("idna").decode("ascii")
    except (UnicodeError, UnicodeEncodeError): return False
    if len(ascii_name) > 253: return False
    labels = ascii_name.split(".")
    if any(not label or len(label) > 63 for label in labels): return False
    return all(_DNS_LABEL_RE.fullmatch(label) for label in labels)

def validate_http_url(url: Any) -> bool:
    if not isinstance(url, str): return False
    if not url or len(url) > MAX_URL_CHARS: return False
    if _CONTROL_CHARS_RE.search(url): return False
    if any(char.isspace() for char in url) or "\\" in url: return False
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in {"http", "https"}: return False
        if not parsed.netloc or not parsed.hostname: return False
        if parsed.username is not None or parsed.password is not None: return False
        hostname = parsed.hostname
        if not _valid_hostname(hostname): return False
        port = parsed.port
        if port is not None and not (1 <= port <= 65535): return False
        return True
    except (TypeError, ValueError, UnicodeError): return False

def _is_sterile_url(url: Any) -> bool:
    if not validate_http_url(url): return True
    text = url.strip()
    return any(pattern.search(text) for pattern in _STERILE_URL_PATTERNS)

def is_sterile_url(url: Any) -> bool:
    return _is_sterile_url(url)

def _bounded_int(value: Any, default: int, low: int, high: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool): return default
    return max(low, min(value, high))

def _truncate_messages(messages: Any, max_messages: int = MAX_MESSAGES, max_content_chars: int = MAX_MESSAGE_CHARS, max_total_chars: int = MAX_TOTAL_CHARS) -> List[Dict[str, str]]:
    if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes, bytearray)): return []
    max_messages = _bounded_int(max_messages, MAX_MESSAGES, 1, 200)
    max_content_chars = _bounded_int(max_content_chars, MAX_MESSAGE_CHARS, 1, 300_000)
    max_total_chars = _bounded_int(max_total_chars, MAX_TOTAL_CHARS, 1, 500_000)
    try: input_length = len(messages)
    except (TypeError, ValueError, OverflowError): return []
    start = max(0, input_length - max_messages * 3)
    cleaned: List[Dict[str, str]] = []
    for index in range(start, input_length):
        try: item = messages[index]
        except (IndexError, KeyError, TypeError): continue
        if not isinstance(item, Mapping): continue
        role = item.get("role")
        if not isinstance(role, str): continue
        role = role.strip().lower()
        if role not in ALLOWED_HISTORY_ROLES: continue
        content = item.get("content")
        if not isinstance(content, str): continue
        content = _safe_str(content, max_content_chars).strip()
        if not content: continue
        cleaned.append({"role": role, "content": content})
    selected_reversed: List[Dict[str, str]] = []
    total_chars = 0
    for item in reversed(cleaned):
        remaining = max_total_chars - total_chars
        if remaining <= 0: break
        content = item["content"]
        if len(content) > remaining:
            if not selected_reversed:
                content = content[:remaining].rstrip()
            else:
                break
        if not content: continue
        selected_reversed.append({"role": item["role"], "content": content})
        total_chars += len(content)
        if len(selected_reversed) >= max_messages: break
    selected_reversed.reverse()
    return selected_reversed

def validate_messages(messages: Any) -> Dict[str, Any]:
    if isinstance(messages, Sequence) and not isinstance(messages, (str, bytes, bytearray)):
        try: input_count = len(messages)
        except (TypeError, ValueError, OverflowError): input_count = 0
    else: input_count = 0
    cleaned = _truncate_messages(messages)
    output_chars = sum(len(item["content"]) for item in cleaned)
    return {
        "valid": bool(cleaned),
        "messages": cleaned,
        "input_count": input_count,
        "accepted_count": len(cleaned),
        "dropped_count": max(0, input_count - len(cleaned)),
        "total_chars": output_chars,
        "errors": [] if cleaned else ["Aucun message valide après filtrage."],
    }

def _detect_user_response(value: Any) -> bool:
    if not isinstance(value, str): return False
    text = _CONTROL_CHARS_RE.sub("", value).strip()
    if not text: return False
    normalized = _normalize_text_for_matching(text)
    if normalized in {"null", "none", "undefined", "n/a"}: return False
    return True

def detect_user_response(value: Any) -> bool:
    return _detect_user_response(value)

def get_validation_summary(messages: Any = None, query: Any = None, url: Any = None, **kwargs: Any) -> Dict[str, Any]:
    del kwargs
    summary: Dict[str, Any] = {"status": "ok", "messages_valid": None, "message_count": 0, "query_valid": None, "url_valid": None, "warnings": []}
    if messages is not None:
        result = validate_messages(messages)
        summary["messages_valid"] = result["valid"]
        summary["message_count"] = result["accepted_count"]
        if not result["valid"]: summary["warnings"].append("Aucun message valide.")
    if query is not None:
        normalized_query = normalize_query(query)
        summary["query_valid"] = bool(normalized_query)
        summary["query_length"] = len(normalized_query)
        if not normalized_query: summary["warnings"].append("Requête vide ou invalide.")
    if url is not None:
        summary["url_valid"] = validate_http_url(url)
        if not summary["url_valid"]: summary["warnings"].append("URL HTTP(S) invalide.")
    if summary["warnings"]: summary["status"] = "warning"
    summary["warnings"] = [_safe_str(warning, MAX_SUMMARY_CHARS) for warning in summary["warnings"]]
    return summary

__all__ = [
    "MAX_MESSAGES", "MAX_MESSAGE_CHARS", "MAX_TOTAL_CHARS", "normalize_query",
    "extract_significant_keywords", "detect_query_language", "translate_query",
    "validate_http_url", "is_sterile_url", "validate_messages", "detect_user_response",
    "get_validation_summary", "_safe_str", "_truncate_messages", "_detect_user_response",
    "_is_sterile_url", "_extract_significant_keywords", "_translate_query",
    "_STERILE_URL_PATTERNS", "_QUERY_STOPWORDS", "_EN_MARKERS", "_FR_MARKERS",
]