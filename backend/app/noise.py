"""Heuristic noise filter (cheap, runs before the LLM relevance check)."""
import re
from collections import Counter

AD = re.compile(r"(#ad\b|#sponsored|#deals?\b|#sale\b|\bdeal price\b|\d+ ?% ?off\b|\bshop (it )?(here|now)\b|"
                r"\bfree shipping\b|\bmrp\b|\bpromo code\b|\bcoupon\b|\buse code\b|\bbuy now\b|\blink in bio\b|"
                r"\baffiliate\b|\bcheck now\b|\border now\b|\bgiveaway\b)", re.I)
PROMO_LINK = re.compile(r"(amzn\.to|amzn\.eu|bit\.ly|dlvr\.it|fkrt\.it|linktr\.ee|tinyurl\.com|rebrand\.ly|shopee|aliexpress|temu\.to)", re.I)
PHONE = re.compile(r"(\+?\d[\d\s().-]{8,}\d)")
REPAIR_PROMO = re.compile(r"\b(call us|we repair|same[- ]day (service|repair)|book (a|your) (service|technician)|"
                          r"repair services?|service cent(er|re) near|whatsapp)\b", re.I)


def phone_like(text):
    for m in PHONE.findall(re.sub(r"https?://\S+", " ", text)):
        digits = re.sub(r"\D", "", m)
        if 10 <= len(digits) <= 13:
            return True
    return False


def heuristic_filter(posts, topic_terms, max_per_author=2):
    """Return (kept, dropped) where dropped items carry a 'noise_reason'."""
    kept, dropped = [], []
    authors = Counter((p.get("username") or "").lower() for p in posts)
    seen_text = set()
    per_author = Counter()
    for p in posts:
        text = p.get("text") or ""
        low = text.lower()
        user = (p.get("username") or "").lower()
        reason = None
        norm = re.sub(r"https?://\S+|[^a-z0-9 ]", "", low)[:90]
        if norm in seen_text:
            reason = "duplicate text"
        elif AD.search(text):
            reason = "ad / deal post"
        elif PROMO_LINK.search(text):
            reason = "promo / affiliate link"
        elif REPAIR_PROMO.search(text) or phone_like(text):
            reason = "repair-shop / phone-number promo"
        elif authors[user] >= 4:
            reason = "repeat-posting account"
        elif len(re.sub(r"https?://\S+|@\w+", "", text).strip()) < 25:
            reason = "too short"
        elif topic_terms and not any(t in low for t in topic_terms):
            reason = "topic not mentioned"
        elif per_author[user] >= max_per_author:
            reason = "author cap"
        if reason:
            dropped.append({**p, "noise_reason": reason})
        else:
            seen_text.add(norm)
            per_author[user] += 1
            kept.append(p)
    return kept, dropped
