from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

_GITHUB_MANAGEMENT_SEGMENTS = {
    "compare",
    "issues",
    "pulls",
    "releases",
}
_GITHUB_CHROME_SEGMENTS = {
    "collections",
    "commits",
    "insights",
    "marketplace",
    "pulse",
    "search",
    "tags",
}


@dataclass(slots=True, frozen=True)
class WebPageSignals:
    visible_text_chars: int
    link_text_chars: int
    paragraph_count: int
    heading_count: int
    path_depth: int


@dataclass(slots=True, frozen=True)
class BoundaryDecision:
    accepted: bool
    reasons: tuple[str, ...]
    score: float


def decide_page_admission(
    *,
    canonical_locator: str,
    seed_locator: str,
    signals: WebPageSignals,
) -> BoundaryDecision:
    reasons: list[str] = []
    score = 0.0
    seed_parts = [part for part in urlparse(seed_locator).path.split("/") if part]
    seed_depth = len(seed_parts)

    link_density = 0.0
    if signals.visible_text_chars > 0:
        link_density = signals.link_text_chars / max(signals.visible_text_chars, 1)

    if signals.visible_text_chars >= 400 and signals.paragraph_count >= 1:
        score += 2.0
        reasons.append("content_rich")
    elif signals.visible_text_chars >= 200:
        score += 1.0

    if signals.heading_count >= 1:
        score += 0.5
        reasons.append("heading_rich")

    if link_density > 0.75:
        score -= 2.0
        reasons.append("link_density")
    elif link_density > 0.5:
        score -= 1.0

    shared_prefix_depth = _shared_prefix_depth(canonical_locator, seed_locator)
    if seed_depth >= 2 and shared_prefix_depth < min(2, seed_depth):
        reasons.append("seed_path_escape")
        return BoundaryDecision(accepted=False, reasons=tuple(reasons), score=-10.0)

    if _is_github_repo_chrome(canonical_locator, seed_locator):
        reasons.append("github_chrome")
        return BoundaryDecision(accepted=False, reasons=tuple(reasons), score=-5.0)

    if _path_affinity(canonical_locator, seed_locator):
        score += 1.0
        reasons.append("path_affinity")
        if signals.path_depth > seed_depth:
            score += 1.5
            reasons.append("deeper_in_docset")
    else:
        score -= 1.0
        reasons.append("path_distance")

    if signals.path_depth <= 1 and signals.heading_count == 0:
        score -= 0.5

    return BoundaryDecision(accepted=score > 0.0, reasons=tuple(reasons), score=score)


def _path_affinity(canonical_locator: str, seed_locator: str) -> bool:
    shared = _shared_prefix_depth(canonical_locator, seed_locator)
    seed_parts = [part for part in urlparse(seed_locator).path.split("/") if part]
    if not seed_parts:
        return True
    return shared >= max(1, len(seed_parts) - 1)


def _shared_prefix_depth(canonical_locator: str, seed_locator: str) -> int:
    candidate_parts = [
        part for part in urlparse(canonical_locator).path.split("/") if part
    ]
    seed_parts = [part for part in urlparse(seed_locator).path.split("/") if part]
    if not seed_parts:
        return 0
    shared = 0
    for candidate, seed in zip(candidate_parts, seed_parts, strict=False):
        if candidate != seed:
            break
        shared += 1
    return shared


def _is_github_repo_chrome(canonical_locator: str, seed_locator: str) -> bool:
    seed = urlparse(seed_locator)
    candidate = urlparse(canonical_locator)
    if seed.netloc.lower() != "github.com" or candidate.netloc.lower() != "github.com":
        return False

    seed_parts = [part for part in seed.path.split("/") if part]
    candidate_parts = [part for part in candidate.path.split("/") if part]
    if len(seed_parts) < 2 or len(candidate_parts) < len(seed_parts):
        return False
    if candidate_parts[:2] != seed_parts[:2]:
        return False
    if len(candidate_parts) == 2:
        return False
    return candidate_parts[2].lower() in _GITHUB_CHROME_SEGMENTS
