# Operatives Follow-up: EBM SK — Sender-PLZ 1380

**Stand:** 2026-04-26 | **Erstellt durch:** Audit-Analyse v1.9.4
**Kunde:** EBM-Papst Mulfingen GmbH & Co. KG (KNR 410844)
**An:** ERKA Operations
**Status:** offen

---

## Befund

In den AX-Abrechnungen für EBM-Papst (Periode 2025-10 bis 2026-03) erscheinen
**12 Sendungen nach Slovakei (PLZ 905 01)** mit einem Absender-PLZ **1380** —
nicht dem bekannten EBM-Hauptstandort Mulfingen 74673.

| Merkmal | Wert |
|---------|------|
| Sender-PLZ in AX | 1380 |
| Empfänger-PLZ | SK 905 01 |
| Anzahl Sendungen | 12 |
| Zeitraum | 2026-02-10 bis 2026-03-24 |
| AX-fakturierter Preis (stp33) | 1.100,00 EUR/Sendung |
| Referenzpreis Mulfingen-DLV (stp33) | 960,00 EUR/Sendung |
| Differenz | +140,00 EUR/Sendung |
| Gesamt-Überschuss (vs. Mulfingen-DLV) | +2.021,00 EUR |

---

## Details

### stp33–34 Sendungen (11 Zeilen)

AX fakturiert **1.100 EUR** pro Sendung im Cap-Band (stp ≥ 31).
Die Noerpel-DLV für Mulfingen 74673 zeigt **960 EUR** für dieses Band.

Die Differenz entspricht exakt einem zweiten SK-905-Eintrag in der
2026-DLV-Datei (`20260227_...Export Europa.xlsx`), der möglicherweise
als Override für einen anderen Absenderstandort vorgesehen ist.

### stp6 Sondersendung (1 Zeile, +481 EUR)

Eine Sendung mit stp=6 wurde mit **975 EUR** fakturiert.
Der LTL-Band-Preis (stp=6) laut Mulfingen-DLV beträgt **494 EUR**.
Eine Abweichung von +97 % ist mit keiner tariflichen Bandbreiten-Toleranz
erklärbar und verstärkt den Verdacht einer anderen Tarif-Grundlage.

---

## Klärungsbedarf

**Frage 1:** Welchem EBM-Standort gehört PLZ 1380?
*(Mögliche EBM-Niederlassungen oder Zulieferer mit eigenem Noerpel-Vertrag?)*

**Frage 2:** Existiert für PLZ 1380 eine separate Noerpel-DLV-Vereinbarung
mit anderen Sätzen (z.B. stp33 = 1.100 EUR, LTL-Sätze abweichend)?

**Frage 3:** Falls kein eigener DLV: Handelt es sich um einen AX-Konfigurationsfehler
(falscher Tarifeintrag für diesen Absenderstandort)?

---

## Empfohlene Schritte

1. **Noerpel anfragen:** DLV-Dokument für Absenderstandort PLZ 1380 anfordern.
2. **EBM-Ansprechpartner:** Identität des PLZ-1380-Standorts mit EBM klären.
3. **AX prüfen:** Wenn kein separater DLV → AX-Tarifeintrag für 1380 auf Korrektheit
   prüfen; ggf. auf Mulfingen-Sätze angleichen.
4. **Rückforderung bewerten:** Falls 1.100 EUR nicht durch DLV gedeckt →
   +2.021 EUR Rückforderungsgrundlage gegenüber Noerpel.

---

## Abgrenzung

Dieser Befund ist **kein Migrations-Schaden** und **kein EBM-Audit-Befund** im Sinne
des v1.9.4-Reports. Die IE-Lanes (60 % der beurteilbaren Erlöse) sind exakt DLV-konform.
Sender-1380-Sendungen wurden im Cluster-Report als `Mx-DQ` markiert (strukturell
inkompatibler DLV-Vergleich) und nicht in die Netto-Bewertung einbezogen.

Dies ist ein operatives Klärungsthema, das unabhängig vom Migrations-Audit abgehandelt
werden sollte.
