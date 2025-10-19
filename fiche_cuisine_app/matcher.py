from __future__ import annotations
from typing import Dict, List, Tuple
import re
from rapidfuzz import fuzz, process

COUNT_PATTERNS = [
    # 3 x pizza, 3x pizza
    re.compile(r"(?P<count>\d{1,3})\s*x\s*(?P<name>[\wÀ-ÿ'\- ]{2,})", re.IGNORECASE),
    # pizza x3
    re.compile(r"(?P<name>[\wÀ-ÿ'\- ]{2,})\s*x\s*(?P<count>\d{1,3})", re.IGNORECASE),
    # 3 pizzas / 3 pizza
    re.compile(r"(?P<count>\d{1,3})\s+(?P<name>[\wÀ-ÿ'\- ]{2,})", re.IGNORECASE),
]


def split_candidates(note: str) -> List[str]:
    # Split by separators, keep words groups
    parts = re.split(r"[;,/\n]|\band\b|\bet\b", note, flags=re.IGNORECASE)
    return [p.strip(" .:\t-") for p in parts if p.strip()]


def best_match(candidate: str, lexicon: Dict[str, List[str]], score_cutoff: int = 80) -> Tuple[str, str, int]:
    best_label, best_item, best_score = "", "", -1
    for section, items in lexicon.items():
        if not items:
            continue
        match = process.extractOne(candidate, items, scorer=fuzz.token_set_ratio, score_cutoff=score_cutoff)
        if match:
            item, score, _ = match
            if score > best_score:
                best_label, best_item, best_score = section, item, score
    return best_label, best_item, best_score


def extract_counts(candidate: str) -> Tuple[str, int]:
    for pat in COUNT_PATTERNS:
        m = pat.search(candidate)
        if m:
            name = m.group("name").strip()
            try:
                count = int(m.group("count"))
            except Exception:
                count = 1
            return name, max(1, count)
    return candidate.strip(), 1


def match_note_to_items(note: str, lexicon: Dict[str, List[str]]) -> List[Dict]:
    results: List[Dict] = []
    for cand in split_candidates(note):
        name_raw, qty = extract_counts(cand)
        section, item, score = best_match(name_raw, lexicon)
        if item:
            results.append({"section": section, "name": item, "qty": qty, "score": score, "original": cand})
        else:
            # unknown, keep as free text
            results.append({"section": "inconnu", "name": name_raw, "qty": qty, "score": 0, "original": cand})
    return results


def aggregate(items: List[Dict]) -> Dict[str, int]:
    total: Dict[str, int] = {}
    for it in items:
        key = it["name"].strip().title()
        total[key] = total.get(key, 0) + int(it.get("qty", 1))
    return total
