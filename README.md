# Setter Commission Calculator

Berechnet Setter-Provisionen aus einem JSON-Export (progressive Staffel, idempotent).

## Voraussetzungen

- Python 3.9+
- Input-Datei muss valides JSON sein

## Ausführen

```bash
python3 setter_commissions.py settled_deals_sample.json
```

Optionale Argumente:
```bash
python3 setter_commissions.py [input.json] [commissions.json]
```

## Staffel (monatlich, Reset am Monatsersten)

| Deals im Monat | Provision pro Deal |
|---|---|
| 1–10 | 50 € |
| 11–20 | 80 € |
| ab 21 | 120 € |

Staffel ist **progressiv** — jeder Deal wird nach seinem Rang im Monat bewertet.

## Verhalten bei fehlerhaften Daten

| Problem | Behandlung |
|---|---|
| Duplikat in Input | Skip → `duplicate_in_source` |
| `setter_email` null | Skip → `missing_setter_email` |
| `closed_at` null | Skip → `missing_closed_at` |
| Bereits verarbeitet | Skip → `already_processed` |

Fehlerhafte Records crashen das Skript nicht — sie werden geloggt und übersprungen.

## Idempotenz

Zweimaliges Ausführen erzeugt keine doppelten Einträge. Das Skript lädt beim Start bestehende `deal_ids` aus `commissions.json` und überspringt bereits verarbeitete Deals.

## Timezone-Annahme

Alle Timestamps werden als **UTC** interpretiert. Ein Deal der um 23:55 UTC am letzten Tag eines Monats abgeschlossen wird, gehört zu diesem Monat — nicht zum Folgemonat.

## Output

`commissions.json` — Array mit einem Objekt pro Deal:

```json
{
  "deal_id": "DEAL-1042",
  "setter_email": "lisa@example.com",
  "month": "2026-03",
  "tier_reached": 1,
  "amount_eur": 25.0,
  "reason_if_skipped": null
}
```
