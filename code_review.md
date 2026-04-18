# Code Review — Make.com Formula Bug

## Die Formel

```
{{first(split(first(4.contacts[].name); " "))}}
```

**Fehlermeldung:**
```
DataError
Failed to map 'Vorname':
Function 'first' finished with error!
Function 'split' finished with error!
Function 'first' finished with error!
'Krisztina Verzar' is not a valid array.
```

---

## 1. Root Cause

Der Übeltäter ist das innere `first()`. Die Syntax `contacts[].name` ist in Make.com kein statischer Pfad, sondern ein impliziter Map-Operator — er iteriert über alle Kontakte und sammelt alle Namen in einem Array.

Bei einem Lead mit **mehreren Kontakten** gibt `contacts[].name` ein Array zurück (`["Krisztina Verzar", "Max Mustermann"]`), und `first()` extrahiert daraus korrekt den ersten String.

Bei einem Lead mit **einem einzigen Kontakt** flacht Make.com das Ergebnis zu einem einfachen String ab (`"Krisztina Verzar"`). Das innere `first()` erwartet aber zwingend ein Array — und crasht.

Der Fehler tritt also nur im Live-Betrieb auf, wenn ein Lead mit einem einzigen Kontakt verarbeitet wird. In Testdaten mit mehreren Kontakten funktioniert die Formel scheinbar problemlos.

---

## 2. Fix

```
{{first(split(4.contacts[1].name; " "))}}
```

`contacts[1].name` greift per direktem Index auf den ersten Kontakt zu (Make.com-Arrays sind 1-basiert) und gibt immer einen String zurück — unabhängig davon ob ein oder mehrere Kontakte vorhanden sind. Das innere `first()` entfällt damit vollständig.

Für zusätzliche Absicherung gegen leere Kontaktlisten:

```
{{ifempty(first(split(4.contacts[1].name; " ")); "Kein Name")}}
```

---

## 3. Strukturelles Problem

Der Grundfehler ist die Verwechslung von **Iterator-Syntax** (`[]`) und **Index-Zugriff** (`[1]`).

`contacts[].name` bedeutet: "Iteriere über alle Kontakte und sammle alle Namen." Das ist der richtige Operator für Aggregatoren und Loop-Kontexte — nicht für die Extraktion eines einzelnen Werts.

Dieser Fehler passiert in Make.com-Projekten immer wieder aus drei Gründen:

1. **Singleton-Fluch:** APIs wie Close CRM geben Daten unterschiedlich zurück je nachdem ob ein oder mehrere Elemente vorhanden sind. Aus `["Krisztina"]` wird `"Krisztina"` — und die Formel bricht.

2. **Visuelle Täuschung:** Der Make.com-Editor fügt beim Klick auf Array-Variablen automatisch `[]` ein. Das suggeriert dass dies der normale Zugriffsweg ist — ist es aber nicht für Single-Value-Extraktion.

3. **Kein Compile-Time-Fehler:** Make.com wirft den Fehler erst zur Laufzeit, wenn das erste problematische Bundle reinkommt. In Tests mit Standarddaten bleibt der Bug unsichtbar.

**Regel:** `contacts[].name` für Loops und Aggregatoren — `contacts[1].name` wenn nur der erste Wert gebraucht wird.
