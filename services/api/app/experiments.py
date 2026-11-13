"""A/B testing of the recommender against a popularity control.

Assignment
    Each visitor is a "unit": the account when signed in, otherwise the
    browser session. A unit is hashed together with the experiment name into
    [0, 1); units below ``control_share`` see the control (recent popularity),
    the rest see the treatment (the trained model). Hashing makes assignment
    stable (a visitor never flips between variants) without storing anything.

Measurement
    Every recommendation shown is logged as an impression with its variant.
    Per variant we report impressions, click-through rate (clicks on
    impressions / impressions) and conversion rate (exposed units that added
    something to the bag / exposed units), with a two-sided two-proportion
    z-test for each. Synthetic events are excluded.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Event, Impression

CONTROL = "control"
TREATMENT = "treatment"


def unit_id(user_id: int | None, session_id: str | None) -> str | None:
    if user_id is not None:
        return f"user:{user_id}"
    if session_id:
        return f"session:{session_id}"
    return None


def assign_variant(unit: str, experiment: str, control_share: float) -> str:
    digest = hashlib.sha256(f"{experiment}:{unit}".encode()).digest()
    position = int.from_bytes(digest[:8], "big") / 2**64
    return CONTROL if position < control_share else TREATMENT


def two_proportion_z_test(x1: int, n1: int, x2: int, n2: int) -> tuple[float | None, float | None]:
    """z statistic and two-sided p-value for H0: p1 == p2 (pooled variance)."""
    if n1 == 0 or n2 == 0:
        return None, None
    pooled = (x1 + x2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return None, None
    z = (x2 / n2 - x1 / n1) / se
    p = math.erfc(abs(z) / math.sqrt(2))
    return round(z, 4), round(p, 6)


def ab_results(db: Session, experiment: str, control_share: float) -> dict[str, Any]:
    impressions = db.execute(
        select(Impression.id, Impression.variant, Impression.user_id, Impression.session_id)
        .where(Impression.variant.is_not(None))
    ).all()
    variant_of_impression = {i.id: i.variant for i in impressions}
    units: dict[str, set[str]] = defaultdict(set)
    shown: dict[str, int] = defaultdict(int)
    for i in impressions:
        shown[i.variant] += 1
        u = unit_id(i.user_id, i.session_id)
        if u:
            units[i.variant].add(u)

    clicked: dict[str, set[str]] = defaultdict(set)
    for (impression_id,) in db.execute(
        select(Event.impression_id).where(
            Event.event_type == "click", Event.impression_id.is_not(None), Event.is_synthetic.is_(False)
        )
    ):
        variant = variant_of_impression.get(impression_id)
        if variant:
            clicked[variant].add(impression_id)

    converting_units = {
        unit_id(e.user_id, e.session_id)
        for e in db.execute(
            select(Event.user_id, Event.session_id).where(
                Event.event_type == "add_to_cart", Event.is_synthetic.is_(False)
            )
        )
    }

    variants = []
    for name in (CONTROL, TREATMENT):
        exposed = len(units[name])
        converted = len(units[name] & converting_units)
        variants.append({
            "variant": name,
            "units": exposed,
            "impressions": shown[name],
            "clicks": len(clicked[name]),
            "ctr": round(len(clicked[name]) / shown[name], 4) if shown[name] else 0.0,
            "converted_units": converted,
            "conversion_rate": round(converted / exposed, 4) if exposed else 0.0,
        })
    control, treatment = variants
    _, ctr_p = two_proportion_z_test(control["clicks"], control["impressions"],
                                     treatment["clicks"], treatment["impressions"])
    _, conv_p = two_proportion_z_test(control["converted_units"], control["units"],
                                      treatment["converted_units"], treatment["units"])
    lift = (
        round(treatment["ctr"] / control["ctr"] - 1, 4) if control["ctr"] > 0 else None
    )
    return {
        "experiment": experiment,
        "enabled": control_share > 0,
        "control_share": control_share,
        "variants": variants,
        "ctr_lift": lift,
        "ctr_p_value": ctr_p,
        "conversion_p_value": conv_p,
    }
