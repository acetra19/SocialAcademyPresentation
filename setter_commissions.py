#!/usr/bin/env python3
"""
Progressive Provisionsberechnung für Setter aus JSON-Rohdaten.
"""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Configuration: progressive tiers (1-indexed deal rank within month)
# ---------------------------------------------------------------------------
TIER_CONFIG: List[Dict[str, Any]] = [
    {"tier": 1, "deal_from": 1, "deal_to": 10, "base_eur": 50.0},
    {"tier": 2, "deal_from": 11, "deal_to": 20, "base_eur": 80.0},
    {"tier": 3, "deal_from": 21, "deal_to": None, "base_eur": 120.0},
]

SELF_CLOSED_FACTOR = 0.5
COMMISSIONS_FILE = Path(__file__).resolve().parent / "commissions.json"
DEFAULT_SOURCE = Path(__file__).resolve().parent / "settled_deals_sample.json"

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def tier_for_rank(rank: int) -> Tuple[int, float]:
    """Return (tier_number, base_eur) for the n-th deal in a month (rank >= 1)."""
    for row in TIER_CONFIG:
        lo, hi = row["deal_from"], row["deal_to"]
        if hi is None:
            if rank >= lo:
                return int(row["tier"]), float(row["base_eur"])
        elif lo <= rank <= hi:
            return int(row["tier"]), float(row["base_eur"])
    # Fallback: tier 3 for any rank beyond configured ranges
    last = TIER_CONFIG[-1]
    return int(last["tier"]), float(last["base_eur"])


@dataclass
class SanitizedDeal:
    deal_id: str
    setter_email: str
    closer_email: str
    self_closed: bool
    deal_value_eur: float
    closed_at_utc: datetime
    month_key: str  # YYYY-MM


@dataclass
class CommissionRecord:
    deal_id: str
    setter_email: str
    month: str
    tier_reached: int
    amount_eur: float
    reason_if_skipped: Optional[str] = None


@dataclass
class RunSummary:
    """Statistics for the current pipeline run (new rows only, plus already_processed counts)."""

    deals_processed: int
    skipped_total: int
    skipped_by_reason: Dict[str, int]
    total_provision_eur: float


def build_run_summary(
    new_rows: List[Dict[str, Any]],
    skipped_already_processed: int,
) -> RunSummary:
    processed = 0
    total_eur = 0.0
    reasons: Dict[str, int] = {}
    for row in new_rows:
        r = row.get("reason_if_skipped")
        if r is None:
            processed += 1
            total_eur += float(row.get("amount_eur") or 0.0)
        else:
            reasons[str(r)] = reasons.get(str(r), 0) + 1
    if skipped_already_processed:
        reasons["already_processed"] = (
            reasons.get("already_processed", 0) + skipped_already_processed
        )
    skipped_total = sum(reasons.values())
    return RunSummary(
        deals_processed=processed,
        skipped_total=skipped_total,
        skipped_by_reason=dict(sorted(reasons.items())),
        total_provision_eur=round(total_eur, 2),
    )


def print_run_summary(summary: RunSummary) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError, AttributeError):
            pass
    w = 52
    line = "=" * w
    print(line)
    print("  Provisionslauf - Zusammenfassung (dieser Lauf)".ljust(w - 2))
    print(line)
    print(f"  {'Verarbeitete Deals (mit Provision):':<40} {summary.deals_processed:>8}")
    print(f"  {'Übersprungene Deals (gesamt):':<40} {summary.skipped_total:>8}")
    print()
    print(f"  {'Übersprungen nach reason_if_skipped:':<40}")
    if not summary.skipped_by_reason:
        print(f"  {'  (keine)':<40}")
    else:
        for reason, cnt in summary.skipped_by_reason.items():
            label = f"  • {reason}"
            print(f"  {label:<40} {cnt:>8}")
    print("-" * w)
    print(f"  {'Gesamtprovision dieses Laufs (EUR):':<40} {summary.total_provision_eur:>8.2f}")
    print(line)


class FileHandler:
    """Loads and persists commission JSON."""

    def __init__(self, commissions_path: Path) -> None:
        self.path = commissions_path

    def load_commissions(self) -> List[Dict[str, Any]]:
        if not self.path.is_file():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                logger.error("commissions.json must be a JSON array")
                return []
            return data
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Failed to read %s: %s", self.path, e)
            return []

    def save_commissions(self, records: List[Dict[str, Any]]) -> None:
        try:
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
                f.write("\n")
        except OSError as e:
            logger.error("Failed to write %s: %s", self.path, e)
            raise

    @staticmethod
    def load_source(path: Path) -> List[Dict[str, Any]]:
        if not path.is_file():
            logger.error("Source file not found: %s", path)
            return []
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                logger.error("Source JSON must be an array")
                return []
            return data
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Failed to read source %s: %s", path, e)
            return []


class Sanitizer:
    """Validation and normalization of raw deal records."""

    @staticmethod
    def parse_utc_closed_at(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            logger.warning("closed_at has numeric type, skipping")
            return None
        if not isinstance(value, str):
            return None
        s = value.strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            logger.warning("closed_at unparseable: %r", value)
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt

    @staticmethod
    def parse_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("true", "1", "yes"):
                return True
            if v in ("false", "0", "no"):
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        return False

    @staticmethod
    def parse_float(value: Any) -> float:
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                return 0.0
        return 0.0

    def sanitize(
        self,
        raw: Dict[str, Any],
    ) -> Tuple[Optional[SanitizedDeal], Optional[str]]:
        deal_id = raw.get("deal_id")
        if deal_id is None or not isinstance(deal_id, str) or not deal_id.strip():
            return None, "invalid_deal_id"

        se = raw.get("setter_email")
        if se is None:
            return None, "missing_setter_email"
        if not isinstance(se, str):
            return None, "missing_setter_email"
        setter_email = se.strip().lower()
        if not setter_email:
            return None, "missing_setter_email"

        ca = raw.get("closed_at")
        closed = self.parse_utc_closed_at(ca)
        if closed is None:
            return None, "missing_closed_at"

        ce = raw.get("closer_email")
        closer_email = ""
        if isinstance(ce, str):
            closer_email = ce.strip().lower()

        sc = self.parse_bool(raw.get("self_closed"))
        dve = self.parse_float(raw.get("deal_value_eur"))
        month_key = f"{closed.year:04d}-{closed.month:02d}"

        return (
            SanitizedDeal(
                deal_id=deal_id.strip(),
                setter_email=setter_email,
                closer_email=closer_email,
                self_closed=sc,
                deal_value_eur=dve,
                closed_at_utc=closed,
                month_key=month_key,
            ),
            None,
        )


class Calculator:
    """Progressive tier amounts per setter and calendar month."""

    def __init__(self, self_closed_factor: float = SELF_CLOSED_FACTOR) -> None:
        self.self_closed_factor = self_closed_factor

    @staticmethod
    def count_existing_successful(
        existing_rows: List[Dict[str, Any]],
    ) -> Dict[Tuple[str, str], int]:
        """Count prior commissioned deals (not skipped) per (setter, month)."""
        counts: Dict[Tuple[str, str], int] = {}
        for row in existing_rows:
            if row.get("reason_if_skipped") is not None:
                continue
            se = row.get("setter_email")
            mo = row.get("month")
            if not isinstance(se, str) or not isinstance(mo, str):
                continue
            key = (se.strip().lower(), mo.strip())
            counts[key] = counts.get(key, 0) + 1
        return counts

    def compute_for_group(
        self,
        deals: List[SanitizedDeal],
        starting_rank: int,
    ) -> List[Tuple[SanitizedDeal, int, float]]:
        """Sort by closed_at, assign tier per rank, return (deal, tier, amount)."""
        sorted_deals = sorted(deals, key=lambda d: d.closed_at_utc)
        out: List[Tuple[SanitizedDeal, int, float]] = []
        for i, deal in enumerate(sorted_deals):
            rank = starting_rank + i + 1
            tier, base = tier_for_rank(rank)
            amount = base * (
                self.self_closed_factor if deal.self_closed else 1.0
            )
            out.append((deal, tier, round(amount, 2)))
        return out


def processed_deal_ids(existing: List[Dict[str, Any]]) -> Set[str]:
    ids: Set[str] = set()
    for row in existing:
        did = row.get("deal_id")
        if isinstance(did, str) and did.strip():
            ids.add(did.strip())
    return ids


def first_occurrence_indices(source: List[Dict[str, Any]]) -> Dict[str, int]:
    first: Dict[str, int] = {}
    for i, row in enumerate(source):
        did = row.get("deal_id")
        if not isinstance(did, str):
            continue
        key = did.strip()
        if key not in first:
            first[key] = i
    return first


def partial_display_fields(
    raw: Dict[str, Any],
    sanitizer: Sanitizer,
) -> Tuple[str, str]:
    """Best-effort setter_email and month for skipped rows (English audit fields)."""
    se = raw.get("setter_email")
    setter = ""
    if isinstance(se, str) and se.strip():
        setter = se.strip().lower()
    ca = raw.get("closed_at")
    closed = sanitizer.parse_utc_closed_at(ca)
    month = ""
    if closed is not None:
        month = f"{closed.year:04d}-{closed.month:02d}"
    return setter, month


def run_pipeline(
    source_path: Path,
    commissions_path: Path,
) -> Tuple[List[Dict[str, Any]], RunSummary]:
    fh = FileHandler(commissions_path)
    existing = fh.load_commissions()
    processed = processed_deal_ids(existing)
    source = fh.load_source(source_path)
    first_idx = first_occurrence_indices(source)

    sanitizer = Sanitizer()
    calculator = Calculator()
    skipped_already_processed = 0

    # Per-index outputs for this run (only new rows to append)
    index_to_record: Dict[int, CommissionRecord] = {}

    # Collect sanitized first-occurrence deals that are not already processed
    pending: List[Tuple[int, SanitizedDeal]] = []

    for i, raw in enumerate(source):
        deal_id_obj = raw.get("deal_id")
        if not isinstance(deal_id_obj, str) or not deal_id_obj.strip():
            index_to_record[i] = CommissionRecord(
                deal_id=str(deal_id_obj) if deal_id_obj is not None else "",
                setter_email="",
                month="",
                tier_reached=0,
                amount_eur=0.0,
                reason_if_skipped="invalid_deal_id",
            )
            continue

        deal_id = deal_id_obj.strip()

        if deal_id in processed:
            skipped_already_processed += 1
            continue

        if first_idx.get(deal_id) != i:
            ps, pm = partial_display_fields(raw, sanitizer)
            index_to_record[i] = CommissionRecord(
                deal_id=deal_id,
                setter_email=ps,
                month=pm,
                tier_reached=0,
                amount_eur=0.0,
                reason_if_skipped="duplicate_in_source",
            )
            continue

        sanitized, reason = sanitizer.sanitize(raw)
        if sanitized is None:
            ps, pm = partial_display_fields(raw, sanitizer)
            index_to_record[i] = CommissionRecord(
                deal_id=deal_id,
                setter_email=ps,
                month=pm,
                tier_reached=0,
                amount_eur=0.0,
                reason_if_skipped=reason or "validation_failed",
            )
            continue

        pending.append((i, sanitized))

    # Group pending by (setter, month)
    groups: Dict[Tuple[str, str], List[SanitizedDeal]] = {}
    for _, sd in pending:
        key = (sd.setter_email, sd.month_key)
        groups.setdefault(key, []).append(sd)

    starting = calculator.count_existing_successful(existing)

    # Map deal_id -> (tier, amount) after group computation
    computed: Dict[str, Tuple[int, float]] = {}
    for (setter, month), deals in groups.items():
        start = starting.get((setter, month), 0)
        for deal, tier, amount in calculator.compute_for_group(deals, start):
            computed[deal.deal_id] = (tier, amount)

    for i, sd in pending:
        tier, amount = computed[sd.deal_id]
        index_to_record[i] = CommissionRecord(
            deal_id=sd.deal_id,
            setter_email=sd.setter_email,
            month=sd.month_key,
            tier_reached=tier,
            amount_eur=amount,
            reason_if_skipped=None,
        )

    # Build new rows in source order
    new_rows: List[Dict[str, Any]] = []
    for i in sorted(index_to_record.keys()):
        rec = index_to_record[i]
        new_rows.append(
            {
                "deal_id": rec.deal_id,
                "setter_email": rec.setter_email,
                "month": rec.month,
                "tier_reached": rec.tier_reached,
                "amount_eur": rec.amount_eur,
                "reason_if_skipped": rec.reason_if_skipped,
            }
        )

    merged = list(existing) + new_rows
    summary = build_run_summary(new_rows, skipped_already_processed)
    return merged, summary


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    source_path = Path(argv[0]).resolve() if argv else DEFAULT_SOURCE
    commissions_path = (
        Path(argv[1]).resolve() if len(argv) > 1 else COMMISSIONS_FILE
    )

    merged, summary = run_pipeline(source_path, commissions_path)
    fh = FileHandler(commissions_path)
    fh.save_commissions(merged)
    print_run_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
