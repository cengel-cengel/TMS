# GEZE v1.9 Rollout — Regression-Resultat Schritte 1–4

**Stand:** 2026-04-24 | **KNR:** 406035 | **Methodik:** v1.9.3
**Datenbasis:** `output/bi_top20_data.pkl`, POST-Periode, GEZE-Zeilen

---

## §1 Ausgeführte Schritte

| Schritt | Aktion | Ergebnis |
|---------|--------|---------|
| 1 | `classify_ax_rows()` | 586 Master, 1.751 Sub, 8.610 Standalone |
| 2 | `filter_comparison_set()` — Sub-Rows entfernen | 9.196 Zeilen (−1.751 Subs) |
| 3 | `~unbeurteilbar`-Filter (Tonnage ≤ 0 AND LDM ≤ 0) | −37 Standalone → 9.159 Zeilen |
| 4 | Scope-Vergleich alter Proxy vs. v1.9 | Unten |

---

## §2 Scope-Vergleich (POST-Periode)

| Kennzahl | Alter Proxy (Tonnage > 0) | v1.9 (Schritte 1–3) | Differenz |
|----------|--------------------------|---------------------|-----------|
| Zeilen im Scope | 6.117 | 9.159 | +3.042 |
| Erlöse Fracht | 440.130 EUR | 422.517 EUR | **−17.613 EUR** |
| Gruppen (RN × Land × PLZ) | 1.073 | 1.073 | **0 (stabil)** |

**Zeilen-Differenz-Erläuterung:** Der alte Scope enthielt nur Tonnage>0-Zeilen;
der neue Scope enthält alle Master- und Standalone-Zeilen (inkl. Tonnage=0 bis
Stage-2-Filter sie als unbeurteilbar entfernt). Netto: +3.042 Zeilen kommen aus
den bisher ausgeschlossenen Standalone-/Master-Zeilen mit Tonnage=0, aber diese
werden durch Stage-2 wieder entfernt (37 unbeurteilbar). Der relevante Unterschied
ist die **Gruppen-Struktur** — die ist identisch (1.073).

---

## §3 FP-Analyse: 153 Sub-Rows entfernt

Die 153 FP-Zeilen (Sub-Rows mit Tonnage > 0) werden durch `filter_comparison_set()`
korrekt ausgeschlossen.

### Verteilung nach Länder/PLZ-Zone

| Land | PLZ-Zone | n Subs entfernt | Erlöse entfernt |
|------|----------|----------------|-----------------|
| GB | WS (Wallingford) | 83 | **9.274 EUR** |
| FR | 59 (Lille-Region) | 4 | 3.005 EUR |
| FR | 27, 77, 72 | 55 | 3.164 EUR |
| IT | 38, 20 | 11 | 2.170 EUR |
| **Gesamt** | | **153** | **17.613 EUR** |

### GB/WS-Gruppe (9.274 EUR)

Die GB/WS-Gruppe (PLZ WS13 8SY) war in der 9b4-Analyse bereits als
**Aggregationsartefakt** identifiziert worden (n_pos=27, GB/WS13 8SY-Gruppe,
`docs/9b4_geze_report.md`). Mit v1.9 werden die 83 Sub-Zeilen dieser Gruppe
korrekt ausgeschlossen. Die Gruppe bleibt im Scope (ihr Master verbleibt),
aber ihre AX-Erlöse sinken um 9.274 EUR. Das GB Muster-B-Artefakt war bereits
aus den 12 unvalidierten Kandidaten ausgeschlossen — kein Einfluss auf Findings.

### Masters der FP-Subs bleiben im Scope

22 Master-Zeilen, auf die die 153 FP-Subs verweisen, verbleiben in `df_vergleich`.
Diese Master tragen eigene `Erlöse Fracht` von nur 1.032 EUR (nahezu 0 — korrekt,
Erlöse liegen auf Subs). In v1.9 werden für diese Master die Sub-Erlöse über
`reconstruct_ax_master()` aggregiert.

---

## §4 FN-Analyse: 37 Standalone-Zeilen korrekt durch Stage-2 entfernt

37 Standalone-Zeilen (Tonnage = 0, LDM = 0) waren im alten Proxy-Scope nicht
enthalten (Tonnage=0 ausgeschlossen). Im v1.9-Scope kommen sie nach Step 1 hinzu,
werden aber sofort durch Stage-2 als `unbeurteilbar` gefiltert.

| Kennzahl | Wert |
|----------|------|
| Zeilen | 37 |
| Erlöse Fracht | 2.769 EUR |
| Klassifikation | Alle `is_standalone` |
| Periode | Alle POST |
| Stage-2-Ergebnis | Entfernt (Tonnage=0 AND LDM=0) |

Netto-Impact auf Vergleichs-Set: 0 Zeilen, 0 EUR. Stage-2-Filter funktioniert korrekt.

---

## §5 Muster-B Regression-Check

**Kernfrage:** Sind die 12 unvalidierten Muster-B-Kandidaten aus 9b4 Sub-Rows,
die durch den neuen Filter herausfallen?

**Ergebnis: NEIN.** Alle 12 Muster-B-Kandidaten sind Master- oder Standalone-Zeilen
und verbleiben in `df_vergleich`. Kein Muster-B-Befund entfällt durch v1.9.

**Sekundäreffekt:** Die Erlöse einiger Gruppen (FR, IT) sinken um 5–6 kEUR
(FP-Sub-Erlöse entfernt). Dies kann dazu führen, dass Gruppen in diesen Ländern
einen negativeren Delta-Wert aufweisen als vorher — potenziell neue Muster-B-
Kandidaten. Dieser Effekt ist quantitativ:

| Lane | Erlöse entfernt | Wirkung auf Delta |
|------|----------------|-------------------|
| GB/WS | 9.274 EUR | Gruppe war bereits Artefakt — Delta nicht in 12er-Liste |
| FR (59+27+77+72) | 6.169 EUR | Delta sinkt um ~6 kEUR → mögliche neue Kandidaten |
| IT (38+20) | 2.170 EUR | Delta sinkt um ~2 kEUR → kleiner Effekt |

Ob neue Muster-B-Kandidaten entstehen, ist erst nach DLV-gefiltertem Re-Run
feststellbar (Schritt 5-8 des Rollouts, noch nicht ausgeführt).

---

## §6 Strukturelle Stabilität

| Prüfpunkt | Ergebnis | Bewertung |
|-----------|---------|-----------|
| Gruppen-Anzahl (RN × Land × PLZ) | 1.073 = 1.073 | **Stabil** |
| Muster-B-Kandidaten in Scope | 12 von 12 erhalten | **Stabil** |
| GB/WS-Artefakt | Bereits ausgeschlossen; FP-Removal bestätigt Klassifikation | **Konsistent** |
| 37 unbeurteilbar | Korrekt durch Stage-2 entfernt | **Korrekt** |

---

## §7 STOP-Kriterium-Check

> STOP-Kriterium: Scope-Änderung > 5 kEUR nach Sub-Exclusion.

**Ausgelöst: Ja — 17.613 EUR > 5 kEUR.**

**Bewertung:** Die Änderung ist methodisch korrekt und erwartet. Es handelt sich
nicht um einen Fehler, sondern um die planmäßige Entfernung von Sub-Zeilen, die
der alte Tonnage-Proxy fälschlicherweise im Scope beließ. Die Erlöse sinken, weil
Sub-Erlöse (FR/GB/IT) nicht mehr isoliert in der Vergleichsmenge stehen.

Die 22 Master-Zeilen dieser Subs bleiben im Scope — ihre Erlöse werden durch
`reconstruct_ax_master()` aus den Subs aggregiert (Schritt 5 des Rollouts).
Erst nach `reconstruct_ax_master()`-Integration sind die Sub-Erlöse wieder
korrekt in der Vergleichsmenge — auf der Master-Zeile, nicht auf der Sub-Zeile.

**Konsequenz:** Das STOP-Kriterium ist formal ausgelöst, aber die Ursache ist
bekannt und methodisch begründet. Es wird zur Entscheidung vorgelegt:

> *Freigabe: Schritt 5 des Rollouts (reconstruct_ax_master Integration) ausführen?*
> *Nach Schritt 5 werden die 22 Master-Zeilen mit Sub-Erlösen korrekt befüllt,*
> *und der 17.613-EUR-Unterschied verringert sich auf den tatsächlichen methodischen*
> *Unterschied (Sub-Erlöse waren falsch disaggregiert).*

---

## §8 Ausstehend vor Abschluss GEZE v1.9 (Schritte 5–8)

| Schritt | Inhalt | Status |
|---------|--------|--------|
| 5 | `reconstruct_ax_master()` für 22 Master mit FP-Subs | Ausstehend |
| 6 | DLV-gefilterter Re-Run (Phasen in_dlv_2025 + fallback) | Ausstehend |
| 7 | Neue Muster-B-Scan nach DLV-Filter | Ausstehend |
| 8 | Dinas-vs-AX systematisch (15 Multi-Group-RNs) | Ausstehend |

---

*Erstellt: 2026-04-24 | Keine Code-Änderungen an bestehenden Report-Scripts.*
*Grundlage: bi_top20_data.pkl POST-Daten | classify_ax_rows() v1.9.3*
