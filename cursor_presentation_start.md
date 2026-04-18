# Cursor Start-Prompt: Social Academy Presentation

## Aufgabe

Baue eine vollständige, interaktive Präsentation und deploye sie auf **presentation.up.railway.app**.

Die Präsentation deckt eine 4-teilige Commission Engine Challenge für Social.Academy (AI Operations Manager Bewerbung) ab.

---

## Tool & Deployment

- **Plattform:** presentation.up.railway.app
- Baue die Präsentation als **single-page HTML** mit Reveal.js oder einer äquivalenten Slideshow-Library
- Dark Theme, professionell, kein generisches Corporate-Look
- Alle Slides auf Deutsch

---

## Struktur: 7 Slides

---

### Slide 1 — Titel

```
Commission Engine Challenge
Social.Academy — AI Operations Manager
Florian Kuehnast | April 2026
```

Untertitel: "4 Teile · Architektur · Code · AI-Collaboration · Code Review"

---

### Slide 2 — Architektur: Datenmodell

**Überschrift:** Airtable Datenmodell — 6 Tabellen

**Inhalt (zwei Spalten oder Liste mit Erklärung):**

| Tabelle | Zweck |
|---|---|
| DEALS | Kerndaten des Vertragsabschlusses (Snapshot der Sales-Rollen) |
| INSTALLMENTS | Eine Rate = ein Record, verknüpft mit easybill_payment_id |
| TEAM_MEMBERS | Alle Mitarbeiter (aktive + ehemalige) |
| COMMISSION_RULES | Provisionssätze je Rolle und Deal-Typ |
| COMMISSIONS | Berechnete Provision pro Empfänger und Installment |
| ZUWEISUNGEN | Dynamische AM-Zuweisung (active_from / active_until) |

**Key Design Decision:**
- `opener_id`, `setter_id`, `closer_id` → **Snapshot** im DEALS-Record (unveränderlich)
- AM-Zuweisung → **dynamisch** via ZUWEISUNGEN-Tabelle (nachträglich änderbar)
- ZUWEISUNGEN-Felder: `zuweisung_id (PK)`, `deal_id (FK)`, `employee_id (FK)`, `role`, `active_from`, `active_until`

**Miro Screenshot:** *(Platzhalter — Florian fügt Screenshot ein)*

---

### Slide 3 — Architektur: 3 Szenarien

**Überschrift:** Edge Cases — wie das Modell damit umgeht

**Szenario 1 — Doppelzahlung:**
Make.com sucht beim Webhook-Eingang die `easybill_payment_id` in INSTALLMENTS. Existiert der Record bereits → Workflow bricht ab. Unique Key auf `easybill_payment_id` als Datenbankschutz.

**Szenario 2 — Refund:**
Offene COMMISSIONS → Status `storniert`. Bereits ausgezahlte → neuer Record mit negativem Betrag + Status `forderung_offen`. Ursprüngliche Records bleiben unangetastet (Audit-Trail).

*Einschränkung: `forderung_offen` löst keinen automatischen Mahnungs-Workflow aus — manueller Schritt nötig.*

**Szenario 3 — Personalwechsel:**
Sales-Snapshots → Rate geht immer an den Deal-Closer. AM-Wechsel → ZUWEISUNGEN-Record mit neuem Eintrag anlegen. Make.com sucht beim Zahlungseingang: `active_from <= paid_at` UND `active_until` leer oder in Zukunft.

*Einschränkung: Änderung der ZUWEISUNGEN ist manuell.*

---

### Slide 4 — Code: Python Setter Commission Calculator

**Überschrift:** Teil 2 — Setter-Provision aus messy JSON

**Key Facts (Bullet Points):**

- **Input:** `settled_deals_sample.json` — reale Datenfehler enthalten
- **Output:** `commissions.json` — ein Objekt pro Deal
- **Staffel (monatlich, reset am Monatsersten):**
  - Deals 1–10 → 50 € / Deal
  - Deals 11–20 → 80 € / Deal
  - Deals 21+ → 120 € / Deal
- **Progressiv** — jeder Deal nach seinem Rang im Monat bewertet
- **Idempotent** — zweiter Lauf erzeugt 0 neue Einträge

**Datenbereinigung (4 Skip-Gründe):**
| Fehler | Behandlung |
|---|---|
| Duplikat in Input | Skip → `duplicate_in_source` |
| `setter_email` null | Skip → `missing_setter_email` |
| `closed_at` null | Skip → `missing_closed_at` |
| Bereits in commissions.json | Skip → `already_processed` |

**Verifikation:**
- 5 verarbeitet / 3 übersprungen
- 225 € Gesamtprovision
- Self-Close (Setter = Closer): 50% des Staffelsatzes

**Console Output (Screenshot-Platzhalter):**
```
Processed: 5 | Skipped: 3 | Total commission: 225.00 EUR
```

---

### Slide 5 — AI-Collaboration

**Überschrift:** Wo AI geholfen hat — und wo nicht

**Tool-Stack:** Gemini [Thinking] + Cursor [Auto]

**Wo AI beschleunigt hat:**

1. **Datenmodell-Grundstruktur** — Gemini hat die AM/Sales-Unterscheidung (Snapshot vs. dynamisch) eigenständig eingebracht → 5 auf 6 Tabellen
2. **Cursor-Prompt-Iteration** — 3 Runden bis alle Constraints korrekt abgebildet; Cursor generierte fast vollständiges Skript

**Wo AI daneben lag (Florian hat korrigiert):**

| Fehler | Was Gemini sagte | Was richtig ist |
|---|---|---|
| Self-Close | `self_closed = true` → voller Satz | 50% des Staffelsatzes |
| Null setter_email | Fallback `no_setter@company.com` | Skip + Log |
| Null closed_at | Nicht als Skip-Grund erkannt | Skip + Log (Datum fehlt für Staffel) |
| Deduplizierung | "Letzten Eintrag behalten" | Skip + Log (keine stille Datenverfälschung) |

**Fazit:** AI hat Geschwindigkeit gebracht — Urteilsvermögen musste ich selbst mitbringen.

---

### Slide 6 — Code Review: Make.com Formula Bug

**Überschrift:** Teil 4 — Root Cause & Fix

**Die buggy Formel:**
```
{{first(split(first(4.contacts[].name); " "))}}
```

**Fehlermeldung:**
```
DataError: 'Krisztina Verzar' is not a valid array.
```

**Root Cause:**
`contacts[].name` ist in Make.com kein Pfad — es ist ein **impliziter Map-Operator**.
- Mehrere Kontakte → Array → `first()` funktioniert
- **Ein einziger Kontakt** → Make.com flacht zu String ab → `first()` crasht

Der Bug tritt nur im Live-Betrieb auf. Tests mit mehreren Kontakten maskieren das Problem.

**Fix:**
```
{{first(split(4.contacts[1].name; " "))}}
```

Direkter Index-Zugriff (`[1]`) gibt immer einen String zurück — unabhängig von der Kontaktanzahl.

**Strukturelles Problem:**
- `contacts[].name` → für Loops/Aggregatoren
- `contacts[1].name` → für Single-Value-Extraktion

Make.com fügt beim Klick auf Array-Variablen automatisch `[]` ein → visuelle Täuschung → häufiger Fehler.

---

### Slide 7 — Links & Deliverables

**Überschrift:** Alle Deliverables

| Deliverable | Link |
|---|---|
| GDrive (alle Dateien) | https://drive.google.com/drive/folders/1E3-bWW1SrC6ydpYwCb0uSrf9S61nwobH?usp=sharing |
| Gemini Chat — Teil 1 Architektur | https://gemini.google.com/share/af1e59d58813 |
| Gemini Chat — Teil 2 Code/Prompts | https://gemini.google.com/share/24ec9d41151a |
| Gemini Chat — Teil 4 Code Review | https://gemini.google.com/share/8b27ddd96033 |

**GDrive enthält:**
- `setter_commissions.py` + `README.md`
- `settled_deals_sample.json` + `commissions.json` (Output)
- `ai_collaboration.md` (Reflexion + Bester Prompt)
- `szenarien.md` (Architektur-Szenarien)
- `code_review.md` (Make.com Bug-Analyse)
- Cursor Screenshots

---

## Bester Prompt (für AI-Collaboration-Slide, optional einblenden)

```
Drei Korrekturen bevor wir den Prompt finalisieren:

Erstens: Sprache ist Python, nicht JavaScript.

Zweitens: Bei Deduplizierung nicht "letzten Eintrag behalten" —
sondern überspringen und loggen. Wir wollen keine stille Datenverfälschung.

Drittens: Die Self-Close-Logik ist invertiert.
self_closed = true bedeutet Setter = Closer,
also 50% der Staffel-Provision — nicht der volle Satz.

Außerdem fehlt noch der Idempotenz-Mechanismus:
beim Start bestehende commissions.json laden und
bereits vorhandene deal_ids überspringen.

Kannst du den Cursor-Prompt mit diesen Korrekturen neu generieren?
```

---

## Technische Anforderungen

- Single-page HTML, kein Build-Step nötig
- Reveal.js via CDN einbinden
- Dark Theme (schwarz/dunkelgrau + Akzentfarbe weiß/blau)
- Code-Blöcke mit Syntax-Highlighting (highlight.js via CDN)
- Tabellen gut lesbar (borders, alternating rows)
- Navigation: Pfeiltasten + Klick
- Responsive (Desktop-Fokus)
- Slide-Nummern einblenden

---

## Deploy auf presentation.up.railway.app

1. Erstelle `index.html` mit dem vollständigen Präsentations-Code
2. Erstelle `Dockerfile`:
```dockerfile
FROM nginx:alpine
COPY index.html /usr/share/nginx/html/index.html
EXPOSE 80
```
3. Erstelle `railway.json`:
```json
{
  "build": { "builder": "DOCKERFILE" },
  "deploy": { "startCommand": "nginx -g 'daemon off;'" }
}
```
4. Push zu GitHub → Railway deployed automatisch
5. Custom Domain: presentation.up.railway.app konfigurieren

---

## Hinweis für Cursor

- Generiere zuerst den vollständigen `index.html`-Code mit allen 7 Slides
- Alle Inhalte sind oben vollständig ausgeschrieben — kein Platzhalter-Text
- Miro-Screenshot-Platzhalter und Console-Output-Screenshot-Platzhalter als `<img>`-Tag mit Border und Beschriftung darstellen
- Danach Dockerfile + railway.json generieren
