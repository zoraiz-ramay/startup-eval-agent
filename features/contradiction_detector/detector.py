from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .models import Claim, Contradiction, SUPPORTED_TOPICS, ValueComparison
from .normalization import normalize_claim_value


def detect_contradictions(claims: Iterable[Claim]) -> list[Contradiction]:
    grouped: dict[tuple[str, str], list[tuple[Claim, object]]] = defaultdict(list)

    for claim in claims:
        if claim.topic not in SUPPORTED_TOPICS:
            continue
        normalized = normalize_claim_value(claim.topic, claim.value)
        if normalized is None:
            continue
        grouped[(claim.topic, claim.entity)].append((claim, normalized))

    contradictions: list[Contradiction] = []
    for (topic, entity), items in grouped.items():
        normalized_values = {normalized for _, normalized in items}
        if len(normalized_values) <= 1:
            continue

        section = items[0][0].section
        values = [
            ValueComparison(
                raw_value=claim.value,
                normalized_value=normalized,
                source=claim.source,
            )
            for claim, normalized in items
        ]
        contradictions.append(
            Contradiction(
                topic=topic,
                entity=entity,
                section=section,
                values=values,
            )
        )

    contradictions.sort(key=lambda item: (item.section, item.topic, item.entity))
    return contradictions
