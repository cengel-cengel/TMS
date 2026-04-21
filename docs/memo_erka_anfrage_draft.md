# ENTWURF — Anfrage an Operations/Fachabteilung: ERKA-Indexschreiben

**Status:** Entwurf — noch nicht versandt. Freigabe durch Projektleitung erforderlich.
**Erstellt:** 2026-04-21 | **Kontext:** TMS Migration Audit, Etappe 9a.3 / 9a.4

---

## Betreff

Benötigt für Fischerwerke-Abschluss und EBM-Papst-Validierung:
Dokumentations-Nachweis ERKA-Indexschreiben (Muster-A-Klärung)

---

## Hintergrund

Im Rahmen des TMS-Migration-Audits wurden bei zwei Kunden identische Abrechnungsmuster
gefunden:

**Fischerwerke GmbH (KNR 409480):**
Auf 6 aktiven 2026-Lanes (IT-Padova, IT-Copiano, BE-Willebroek, DK-Koge, IE-Dublin,
ES-MontRoig) wurde ab ca. **März 2026** ein konstanter Aufschlag von exakt **+7,000 %**
auf den DLV-Basistarif festgestellt (62 Zeilen, Ratio-Streuung < 0.00002 Std.abw.).

**EBM-Papst Mulfingen (KNR 410844):**
Auf 5 Lanes (IE, PL, EE, SK, HR) wurde ab **Januar 2026** derselbe konstante Aufschlag
von exakt **+7,000 %** festgestellt (50 Zeilen, floater_pct = 0.07000 ± 0.0015).

Die Präzision und Konsistenz dieses Musters schließt Zufall aus. Es gibt zwei
mögliche Erklärungen:

**Hypothese A — Archivierter Index-Mechanismus:**
Es existiert ein ERKA-Indexschreiben oder eine Konditionsanpassungs-Vereinbarung,
die einen prozentualen Aufschlag auf die DLV-Basistarife festlegt. Das Schreiben
wurde in AX korrekt konfiguriert, liegt aber nicht im Audit-Archiv vor.

**Hypothese B — AX-Konfigurations-Drift:**
In AX wurde versehentlich ein fester prozentualer Zuschlag aktiviert, der nicht
durch eine vertragliche Vereinbarung gedeckt ist. Dies wäre eine
Überfakturierungs-Abweichung.

---

## Benötigte Information

1. **Existiert ein ERKA-Indexschreiben oder eine Konditionsanpassung** für die
   betroffenen Kunden und Lanes mit einem Aufschlag in Höhe von 7 %?

2. **Geltungsbereich** (falls vorhanden):
   - Datum der Wirksamkeit (Fischerwerke: ~Mrz 2026; EBM-Papst: ~Jan 2026)
   - Betroffene Kunden (Fischerwerke, EBM-Papst, weitere?)
   - Betroffene Länder/Lanes
   - Befristung oder unbefristet

3. **Dokumentations-Nachweis:** Schriftliche Vereinbarung, E-Mail-Korrespondenz oder
   Konditionsblatt als Nachweis für das Audit-Archiv.

---

## Relevanz für den Audit-Abschluss

- **Fischerwerke-Abschluss** (Etappe 9a.3 Final-Report) ist blockiert bis RF-1 beantwortet.
- **EBM-Papst-Bewertung**: Muster-A ist im +41.283 EUR Gesamt-Delta enthalten;
  ohne Nachweis kann der Aufschlag nicht als vertragskonform eingestuft werden.
- Bei Hypothese B: Der 7 %-Aufschlag auf ~110 Zeilen (geschätzt) wäre als
  Überfakturierungs-Finding zu dokumentieren und ggf. gegenzurechnen.

---

*Entwurf. Nicht versenden ohne Freigabe durch Projektleitung.*
*Erstellt im Kontext: `docs/fischerwerke_findings_interim.md` RF-1,
`docs/9a43_report.md` §4 Muster-A-Befund.*
