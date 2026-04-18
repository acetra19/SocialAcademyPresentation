# AI-Collaboration Evidence

## Chat-Exports

- **Teil 1 — Architektur (Gemini):** https://gemini.google.com/share/af1e59d58813
- **Teil 2 — Code / Prompt-Iteration (Gemini):** https://gemini.google.com/share/24ec9d41151a
- **Teil 4 — Code Review (Gemini):** https://gemini.google.com/share/8b27ddd96033

---

## Reflexion

Für diese Aufgabe habe ich mit Gemini [Thinking] (Architektur + Prompt-Iteration) und Cursor [Auto](Code-Generierung) gearbeitet.

**Wo AI am meisten beschleunigt hat:**

Den größten Zeitgewinn brachte die iterative Verfeinerung des Cursor-Prompts über Gemini. Statt das Skript direkt zu generieren, habe ich den Prompt in mehreren Runden präzisiert bis alle Constraints korrekt abgebildet waren. Cursor hat daraus ein fast vollständiges Skript generiert — mit einer kleinen Nachkorrektur (falscher Default-Dateiname und fehlende Console-Summary), die ich selbst identifiziert habe.

Bei der Architektur hat Gemini die Unterscheidung zwischen Sales-Rollen (Snapshot) und AM (dynamische Zuweisung via ZUWEISUNGEN-Tabelle) eigenständig eingebracht — ein echter Mehrwert der das Modell von 5 auf 6 Tabellen verbessert hat.

**Wo AI daneben lag:**

Gemini hat die Self-Close-Regel invertiert: `self_closed = true` wurde als "voller Provisionssatz" interpretiert. Ich habe das sofort korrigiert bevor es in den Code geflossen ist.

Gemini schlug bei fehlender `setter_email` einen Fallback vor (`no_setter@company.com`) — das hätte eine Phantom-Commission erzeugt. Richtig: überspringen und loggen.

`null closed_at` wurde nicht als Skip-Grund erkannt — ich habe ihn ergänzt, weil ohne Datum die monatliche Gruppierung für die progressive Staffel zusammenbricht.

**Fazit:** AI hat Geschwindigkeit gebracht, Urteilsvermögen musste ich selbst mitbringen.

---

## Bester Prompt

```
Drei Korrekturen bevor wir den Prompt finalisieren:

Erstens: Sprache ist Python, nicht JavaScript.

Zweitens: Bei Deduplizierung nicht "letzten Eintrag behalten" —
sondern überspringen und loggen. Wir wollen keine stille
Datenverfälschung.

Drittens: Die Self-Close-Logik ist invertiert.
self_closed = true bedeutet Setter = Closer,
also 50% der Staffel-Provision — nicht der volle Satz.

Außerdem fehlt noch der Idempotenz-Mechanismus:
beim Start bestehende commissions.json laden und
bereits vorhandene deal_ids überspringen.

Kannst du den Cursor-Prompt mit diesen Korrekturen neu generieren?
```

**Warum er gut funktioniert hat:** Er korrigiert vier konkrete fachliche Fehler in einer Nachricht, gibt jeweils den richtigen Ansatz mit Begründung vor, und steuert das Modell ohne den Lösungsweg zu überspezifizieren.
