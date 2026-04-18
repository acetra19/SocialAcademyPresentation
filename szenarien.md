# Architektur — Szenarien

## Szenario 1 — Doppelzahlung

Make.com empfängt den EasyBill-Webhook und sucht zuerst in der INSTALLMENTS-Tabelle nach der `easybill_payment_id`. Existiert dieser Record bereits, bricht der Workflow ab — keine neuen COMMISSIONS-Records werden angelegt. Der Unique Key auf `easybill_payment_id` verhindert Duplikate auf Datenbankebene, nicht nur durch Logik.

---

## Szenario 2 — Refund

Alle COMMISSIONS-Records die zu Installments des betroffenen Deals gehören und noch nicht den Status `ausgezahlt` haben, werden auf `storniert` gesetzt. Für bereits ausgezahlte Pauschalen (Opener/Setter) werden neue COMMISSIONS-Records mit negativem Betrag und Status `forderung_offen` angelegt — weil das Geld bereits überwiesen ist und nicht einfach zurückgebucht werden kann. Die ursprünglichen Records bleiben unangetastet, der vollständige Audit-Trail bleibt erhalten.

*Einschränkung: `forderung_offen` löst keinen automatischen Prozess aus — die tatsächliche Rückforderung erfordert entweder einen manuellen Schritt oder einen separaten Mahnungs-Workflow.*

---

## Szenario 3 — Personalwechsel

Die Felder `opener_id`, `setter_id` und `closer_id` im DEALS-Record sind Snapshots zum Abschlusszeitpunkt. Rate 7 geht automatisch an den Mitarbeiter der zum Dealabschluss eingetragen war. Für den Account Manager existiert die ZUWEISUNGEN-Tabelle — Make.com sucht beim Zahlungseingang den Eintrag wo `active_from <= paid_at` und `active_until` leer oder in der Zukunft liegt.

*Einschränkung: Die Änderung der Zuweisung ist ein manueller Prozess — wird er nicht ausgeführt, bekommt die ursprüngliche Person weiterhin die Provision.*
