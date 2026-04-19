import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import settings
from .logger import app_logger as logger

try:
    import jieba
    import jieba.analyse
    _JIEBA_AVAILABLE = True
except ImportError:
    _JIEBA_AVAILABLE = False

try:
    from snownlp import SnowNLP
    _SNOWNLP_AVAILABLE = True
except ImportError:
    _SNOWNLP_AVAILABLE = False


_DICT_LOADED = False
_PURE_PUNCT_RE = re.compile(r"^[\W_]+$", re.UNICODE)
_PURE_233_RE = re.compile(r"^2?3{2,}$")
_PURE_Q_RE = re.compile(r"^[？?！!~～]+$")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_REPEATED_CHAR_RE = re.compile(r"(.)\1{4,}")
_STOPWORDS = {"这个", "那个", "真的", "感觉", "就是", "你们", "我们", "他们", "一个", "不是", "没有"}


def _ensure_jieba_user_dict_loaded() -> None:
    global _DICT_LOADED
    if _DICT_LOADED or not _JIEBA_AVAILABLE:
        return
    path = (settings.nlp_jieba_user_dict_path or "").strip()
    if path:
        candidate = Path(path)
    else:
        candidate = Path(__file__).resolve().parent / "nlp_user_dict.txt"
    if candidate.exists():
        jieba.load_userdict(str(candidate))
        logger.info("✅ NLP 已加载 Jieba 自定义词典 path={}", candidate)
    _DICT_LOADED = True


def _map_sentiment_to_signed(value_01: float) -> float:
    value = max(0.0, min(1.0, float(value_01)))
    return round(value * 2.0 - 1.0, 4)


def _normalize_text(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:500]


def _classify_special_emotion(text: str) -> Optional[str]:
    if not text:
        return "empty"
    if _PURE_233_RE.match(text):
        return "laugh"
    if _PURE_Q_RE.match(text):
        return "question_or_shock"
    if _PURE_PUNCT_RE.match(text):
        return "symbol"
    return None


def _is_spam_like(text: str) -> bool:
    return bool(_REPEATED_CHAR_RE.search(text))


def process_text_record(text: str) -> Dict[str, Any]:
    cleaned = _normalize_text(text)
    emotion = _classify_special_emotion(cleaned)
    is_noise = emotion is not None
    if not is_noise and _is_spam_like(cleaned):
        is_noise = True
        emotion = "spam_repeat"

    score: Optional[float] = None
    if is_noise:
        if emotion == "laugh":
            score = 0.3
        elif emotion == "question_or_shock":
            score = -0.2
        elif emotion == "spam_repeat":
            score = -0.1
        else:
            score = 0.0
    elif _SNOWNLP_AVAILABLE and cleaned:
        try:
            score = _map_sentiment_to_signed(SnowNLP(cleaned).sentiments)
        except Exception as exc:
            logger.debug("SnowNLP 处理失败 text={} error={}", cleaned[:20], exc)
            score = None

    return {
        "original_text": text,
        "cleaned_text": cleaned,
        "is_noise": is_noise,
        "emotion_label": emotion,
        "sentiment_score": score,
    }


def aggregate_episode_nlp(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    _ensure_jieba_user_dict_loaded()
    total = len(records)
    if total == 0:
        return {
            "sample_size": 0,
            "noise_ratio": 0.0,
            "sentiment_score": None,
            "keywords": [],
            "entities": [],
        }

    noise_count = sum(1 for r in records if r.get("is_noise"))
    sentiment_values = [r["sentiment_score"] for r in records if r.get("sentiment_score") is not None]
    sentiment_score = round(sum(sentiment_values) / len(sentiment_values), 4) if sentiment_values else None

    valid_texts = [r.get("cleaned_text", "") for r in records if not r.get("is_noise")]
    valid_texts = [t for t in valid_texts if t]

    keywords: List[str] = []
    entities: List[Dict[str, Any]] = []
    if _JIEBA_AVAILABLE and valid_texts:
        joined = "\n".join(valid_texts)
        try:
            keywords = jieba.analyse.extract_tags(joined, topK=max(1, settings.nlp_keyword_topk))
        except Exception as exc:
            logger.debug("jieba 关键词提取失败: {}", exc)
            keywords = []

        counter: Counter = Counter()
        for txt in valid_texts:
            for token in jieba.cut(txt):
                t = token.strip()
                if len(t) < 2 or t in _STOPWORDS:
                    continue
                if not _CJK_RE.search(t):
                    continue
                counter[t] += 1
        entities = [
            {"text": token, "count": count}
            for token, count in counter.most_common(max(1, settings.nlp_entity_topk))
            if count >= max(1, settings.nlp_entity_min_freq)
        ]

    return {
        "sample_size": total,
        "noise_ratio": round(noise_count / total, 4),
        "sentiment_score": sentiment_score,
        "keywords": keywords,
        "entities": entities,
    }

