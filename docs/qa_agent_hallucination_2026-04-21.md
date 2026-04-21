# QA-Incident: Explore-Agent-Halluzinierung bei Build-Script-Zahlen

**Datum:** 2026-04-21 | **Schweregrad:** Mittel (erkannt vor Dokument-Commit)
**Branch:** `claude/audit-billing-migration-wfgWR`

---

## Incident-Beschreibung

Bei der Erstellung des `docs/zwischenstand_2026-04-21.md` wurde ein Explore-Agent
eingesetzt, um Scope-Kaskade-Zahlen aus den Python-Build-Scripts zu extrahieren.
Der Agent verfügt **nicht** über das Bash-Tool und kann Python-Scripts nicht ausführen.
Er produzierte dennoch plausibel wirkende, aber falsche Zahlen.

## Erkannte Abweichungen

| Metrik | Agent-Wert | Tatsächlicher Wert | Quelle |
|---|---|---|---|
| CHT GR n_total | 1.074 | **102** | `python src/build_9c2c_cht_gr_calculator_test.py` |
| CHT ES Match-Rate | 100 % | **93,3 %** | `python src/build_9c2b_cht_es_calculator_test.py` |
| CHT BE rn_adj Positionen | 18 | **111** | `python src/build_9c2a_cht_be_calculator_test.py` |

Die Abweichungen betragen bis zu Faktor 10+ (GR: 1074 vs 102). Die Zahlen wirkten
plausibel (GR n_total 1074 wäre realistisch für einen anderen Kunden), was die
Halluzinierung ohne aktiven Gegencheck nicht erkennbar gemacht hätte.

## Erkennungsmethode

Vor dem Schreiben des Zwischenstand-Dokuments wurden alle Build-Scripts direkt via
`python src/build_9c*.py 2>&1` ausgeführt. Die direkten Ausgaben wiesen die
Abweichungen nach. Kein halluzinierter Wert wurde in das Dokument übernommen.

## Ursachenanalyse

**Technische Ursache:** Read-only-Agenten (Explore, claude-code-guide) haben keinen
Zugriff auf das Bash-Tool. Sie können Python-Scripts lesen, aber nicht ausführen.
Beim Auftrag "extrahiere die Zahlen aus diesem Script" liest der Agent den Code
und *inferiert* erwartete Ausgaben aus der Code-Logik — ohne tatsächliche
Ausführung. Dies erzeugt systematisch falsche Zahlen, wenn:
- Filterbedingungen (Kunden-Nr, Periode, Spalten) die tatsächliche Datenlage nicht
  widerspiegeln
- Mehrere Filterungsschritte in Kaskade liegen (jede falsche Annahme multipliziert)
- Die Script-Ausgabe von Laufzeitdaten abhängt (pickle-Dateien, externe DLV-Sheets)

**Kontextueller Faktor:** Die Agent-Zahlen wurden mit hoher Konfidenz präsentiert
(keine explizite Unsicherheitsmarke). Ohne Gegenprüfung wären sie in das Dokument
eingeflossen.

## Gegenmaßnahmen (sofort umgesetzt)

1. **Ground-Truth-Regel:** Alle numerischen Werte in Audit-Dokumenten müssen aus
   direkten Script-Ausgaben (`python src/build_9c*.py 2>&1`) stammen.
2. **Keine Delegation numerischer Extraktion an Read-only-Agenten.**
3. **Explizite Kennzeichnung** nicht erhobener Werte als "nicht erhoben" statt
   als gerechnete Schätzung.

## Methodik-Konsequenz

Diese Regeln wurden als **§9a Multi-Agent-Workflow-Regeln** in `AUDIT_METHODOLOGY.md`
v1.8.2 aufgenommen.

---

*Erkannt und dokumentiert: 2026-04-21*
*Keine halluzinierten Werte in Audit-Dokumente übernommen.*
