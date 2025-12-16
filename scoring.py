import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple

@dataclass
class ScoringResult:
    bucket: str  # "HIGH_CERTAINTY" | "LESS_CERTAIN" | "EXCLUDE"
    score: int
    reasons: List[str]
    exclude_reason: Optional[str] = None
    parsed_years_min: Optional[float] = None
    parsed_years_max: Optional[float] = None


SENIOR_TITLE_EXCLUDES = [
    "senior", "lead", "manager", "principal", "head", "director", "vp",
    "vice president", "chief", "c-level", "partner"
]

STRONG_POSITIVE_TITLE = [
    "graduate", "junior", "trainee", "assistant", "coordinator",
    "administrator", "admin", "apprentice", "intern", "placement"
]

STEALTH_JUNIOR_TITLE = [
    "analyst", "officer", "executive", "associate"
]

STRONG_POSITIVE_TEXT = [
    "entry level", "entry-level", "early career", "recent graduates",
    "new graduate", "graduate programme", "graduate program"
]

INTERNSHIP_EQUIVALENT_TEXT = [
    "internship", "industrial placement", "placement year",
    "part-time", "part time", "volunteer", "volunteering",
    "university project", "capstone", "student society", "society",
    "dissertation", "coursework", "or equivalent experience"
]

SENIOR_LANGUAGE_EXCLUDES = [
    "extensive experience", "significant experience", "expert",
    "seasoned", "own the strategy", "set strategy", "define strategy",
    "strategic ownership", "lead a team", "line manage", "people management"
]


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _contains_any(haystack: str, needles: List[str]) -> bool:
    return any(n in haystack for n in needles)


def _extract_years(text: str) -> Tuple[Optional[float], Optional[float], List[str]]:
    """
    Attempts to parse experience year requirements from text.
    Returns (min_years, max_years, evidence_snippets).
    """
    evidence = []
    t = text

    # Common patterns:
    # "1-2 years", "1 – 2 years", "0 to 2 years"
    range_pat = re.compile(r"(\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)\s*(?:\+?\s*)?years?", re.I)
    m = range_pat.search(t)
    if m:
        mn = float(m.group(1))
        mx = float(m.group(2))
        evidence.append(f"Years range: {mn:g}-{mx:g}")
        return mn, mx, evidence

    # "up to 2 years"
    upto_pat = re.compile(r"up to\s*(\d+(?:\.\d+)?)\s*years?", re.I)
    m = upto_pat.search(t)
    if m:
        mx = float(m.group(1))
        evidence.append(f"Years: up to {mx:g}")
        return 0.0, mx, evidence

    # "2+ years", "3+ years"
    plus_pat = re.compile(r"(\d+(?:\.\d+)?)\s*\+\s*years?", re.I)
    m = plus_pat.search(t)
    if m:
        mn = float(m.group(1))
        evidence.append(f"Years: {mn:g}+")
        return mn, None, evidence

    # "at least 2 years", "minimum of 1 year"
    atleast_pat = re.compile(r"(?:at least|min(?:imum)?(?: of)?)\s*(\d+(?:\.\d+)?)\s*years?", re.I)
    m = atleast_pat.search(t)
    if m:
        mn = float(m.group(1))
        evidence.append(f"Years: at least {mn:g}")
        return mn, None, evidence

    return None, None, evidence


def score_grad_suitability(
    title: str,
    description: str = "",
    department: str = "",
    seniority: str = "",
) -> ScoringResult:
    """
    Returns:
      - EXCLUDE if clearly senior
      - otherwise HIGH_CERTAINTY or LESS_CERTAIN based on score and strong signals
    """
    t = _norm(title)
    d = _norm(description)
    dep = _norm(department)
    lvl = _norm(seniority)

    reasons: List[str] = []
    score = 0

    # ---- HARD EXCLUDES ----
    if _contains_any(t, SENIOR_TITLE_EXCLUDES) or _contains_any(lvl, SENIOR_TITLE_EXCLUDES):
        return ScoringResult(
            bucket="EXCLUDE",
            score=-999,
            reasons=[],
            exclude_reason="Senior title/level keyword"
        )

    if _contains_any(d, SENIOR_LANGUAGE_EXCLUDES):
        return ScoringResult(
            bucket="EXCLUDE",
            score=-999,
            reasons=[],
            exclude_reason="Senior language in description"
        )

    # Parse years
    years_min, years_max, years_evidence = _extract_years(d)
    if years_evidence:
        reasons.extend(years_evidence)

    # Exclude if 5+ years or clearly senior minimum
    if years_min is not None and years_min >= 5:
        return ScoringResult(
            bucket="EXCLUDE",
            score=-999,
            reasons=reasons,
            exclude_reason="Minimum experience 5+ years",
            parsed_years_min=years_min,
            parsed_years_max=years_max
        )

    # ---- POSITIVE TITLE SIGNALS ----
    if any(k in t for k in STRONG_POSITIVE_TITLE):
        score += 2
        reasons.append("Strong junior title signal")

    # Stealth titles: only weak-positive (need supporting evidence elsewhere)
    if any(k in t for k in STEALTH_JUNIOR_TITLE):
        score += 1
        reasons.append("Stealth junior title (needs evidence)")

    # ---- POSITIVE TEXT SIGNALS ----
    if _contains_any(d, STRONG_POSITIVE_TEXT):
        score += 2
        reasons.append("Explicit entry-level / graduate language")

    if _contains_any(d, ["training provided", "full training", "we will train", "learning and development", "development opportunity"]):
        score += 1
        reasons.append("Training/development language")

    # Internship-equivalent override (important for your use case)
    internship_equiv = _contains_any(d, INTERNSHIP_EQUIVALENT_TEXT)
    if internship_equiv:
        score += 2
        reasons.append("Internship/part-time/uni-project experience accepted")

    # ---- YEARS-BASED SCORING (NOT hard filters, except 5+) ----
    if years_min is not None or years_max is not None:
        # Range within 0-2 is great
        if years_max is not None and years_max <= 2:
            score += 2
            reasons.append("Experience requirement within 0–2 years")

        # 1–2 years also great
        if years_min is not None and years_min <= 2 and (years_max is None or years_max <= 2):
            score += 1
            reasons.append("Low minimum experience (<=2 years)")

        # Borderline: 2+ years
        if years_min is not None and years_min == 2 and years_max is None:
            # keep, but slightly less certain unless internship-equivalent present
            score += 0 if internship_equiv else -1
            reasons.append("Borderline: 2+ years")

        # Likely too senior: 3+ years (soft exclude via score)
        if years_min is not None and years_min >= 3 and years_min < 5:
            score -= 3
            reasons.append("Likely mid-level: 3+ years")

    else:
        # No explicit years: don’t punish, but keep it “less certain” unless other strong signals
        reasons.append("No explicit years found")

    # ---- RESPONSIBILITY VERB HEURISTIC (light touch) ----
    positive_verbs = ["assist", "support", "coordinate", "help", "learn", "shadow", "contribute", "maintain"]
    negative_verbs = ["lead", "own", "drive strategy", "set strategy", "define roadmap", "manage a team", "line manage"]
    pos_hits = sum(1 for v in positive_verbs if v in d)
    neg_hits = sum(1 for v in negative_verbs if v in d)

    if pos_hits >= 2:
        score += 1
        reasons.append("Responsibilities look support/co-ordination focused")
    if neg_hits >= 1:
        score -= 2
        reasons.append("Responsibilities include ownership/leadership language")

    # ---- BUCKETING ----
    # Strong-positive triggers for HIGH_CERTAINTY
    strong_positive = (
        any(k in t for k in STRONG_POSITIVE_TITLE)
        or _contains_any(d, STRONG_POSITIVE_TEXT)
        or (years_max is not None and years_max <= 2)
        or internship_equiv
    )

    if score >= 4 and strong_positive:
        bucket = "HIGH_CERTAINTY"
    elif score >= 2:
        bucket = "LESS_CERTAIN"
    else:
        bucket = "LESS_CERTAIN"  # still keep it if not excluded; you can tighten later

    return ScoringResult(
        bucket=bucket,
        score=score,
        reasons=reasons,
        exclude_reason=None,
        parsed_years_min=years_min,
        parsed_years_max=years_max
    )
