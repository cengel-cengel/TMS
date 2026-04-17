# AX-Cluster-Konsolidierung — Implementierungslogik

## Hintergrund

AX (Abrechnung) fasst physische Einzelsendungen in Abrechnungscluster zusammen.
Jeder Cluster wird durch die Spalte **`Zusammengefasst in`** identifiziert und hat
genau eine Masterzeile (`Hauptabrechnungsstrecke == 'Ja'`). Alle anderen Zeilen
im selben Cluster sind Subzeilen (`Hauptabrechnungsstrecke == 'Nein'`).

Quelle: `Abrechnungsstrecken.xlsx` (Kontonummer-gefiltert pro Kunde).

---

## Regel A — Abrechnungsgewicht

**ERKA-UI-verifiziert** (Cluster 00194384):

> `Master.Abrechnungsgewicht` (Spalte V) enthält bereits die Summe aller
> physischen Gewichte im Cluster.
> `Master.Gewicht` (Spalte U) ist nur das physische Gewicht der Mastersendung.
>
> Beispiel: Sub (213 kg) + Master (9.952 kg) = Master.AbrGew (10.165 kg).

**Validierung (1.233 Multi-Cluster, alle Kunden):**

| Kategorie | Anzahl | % |
|-----------|-------:|---:|
| \|Δ\| < 0.01 kg | 1.230 | 99,76% |
| \|Δ\| 0.01–1 kg (Rundung) | 1 | 0,08% |
| \|Δ\| ≥ 1 kg (CY-Mindestgewicht) | 2 | 0,16% |

Die 2 Ausreißer (Cluster 141421 und 288976, beide GEZE/Zypern) sind valide
Mindestgewicht-Vereinbarungen, keine Datenfehler.

→ **Für Tariflookups: `tonnage_ax = master_row['Abrechnungsgewicht']`**

---

## Akkumulations-Muster

### Symmetrisches Standard-Muster

Für alle Cluster ohne Duplikate gilt:

```python
master[col] = cluster_df[col].sum(min_count=1)
```

`cluster_df` = Masterzeile + alle Subzeilen im Cluster.  
`min_count=1`: gibt NaN zurück wenn alle Werte NaN sind (vermeidet falsche Null-Interpretation
bei Kunden, die physikalische Felder nicht befüllen).

**Akkumulierte Spalten:**

- `_AX_FIN_COLS`: AX Fracht, AX Diesel, AX Maut, AX Nebengebühr, AX Lademittel,
  AX Peak, AX EUST/Zoll, AX Versicherung, AX Gesamt
- `_BI_ERLOES_COLS`: Erlöse Fracht, Erlöse Diesel, Erlöse Maut, Erlöse Nebengebühr,
  Erlöse Lademittel, Erlöse Peak, Erlöse EUST Zoll, Erlöse Transportversicherung, Erloese
- `_BI_PHYS_COLS`: Lademeter, Stellplätze, Volumen

**Nicht akkumuliert:** `Gewicht` — wegen Regel A (Master.AbrGew ist ERKA-autoritativ).

---

## Fallstricke und Lösungen

### Trap 1 — Doppelte Master-BI-Zeilen (Dup-Master-Cluster)

**Ursache:** Das Quellsystem weist gelegentlich dieselbe `Auftragsnummer` an
unterschiedliche reale Sendungen zu (Datenqualitäts-Artefakt, kein Bug in dieser Pipeline).
Beide Zeilen erscheinen im BI-POST-Dataset unter derselben Nummer.

**Symptom:** Ein Cluster hat >1 BI-Zeile mit `_ax_mstr == True`. Mit dem symmetrischen
Muster würde `cluster_df[col].sum()` beide Masterzeilen einschließen — beide erhielten
dann denselben (aufgeblähten) Cluster-Sum, was zu Doppelzählung führt.  
Der globale Summen-Erhalt-Test würde diesen Fehler **nicht** erkennen, weil er eine
intra-Cluster-Umverteilung ist.

**Lösung — Additives Fallback:**  
Für Cluster mit >1 Master-BI-Zeile gilt:

```python
master[col] = master[col].fillna(0) + subs.sum()
```

Jede Duplikatzeile behält ihren eigenen Wert und trägt separat zur Cluster-Summe bei.

**Invariante (Runtime-Guard):**  
Dup-Master-Cluster müssen `n_subs == 0` haben. Falls je ein Dup-Master-Cluster
Subzeilen enthält, löst die Pipeline einen `AssertionError` aus:

```
STOP: dup-master cluster(s) have subs > 0 — additive fallback would
double-count sub contributions. Clusters: {cluster_id: n_subs}
```

Begründung: Additiv würde den Sub-Sum zu JEDER Duplikatzeile addieren.
Da der globale Summen-Test das nicht fängt (intra-Cluster-Fehler), muss hier
explizit gestoppt werden.

**Beobachtung bei Implementierung:**

| Kunde | Dup-Master-Cluster | Sub-Zeilen in Dup-Clustern |
|-------|-----------------:|------------------:|
| GEZE  | 1 (Cluster 351971) | 0 ✓ |
| CHT   | 0 | 0 ✓ |
| EBM   | 0 | 0 ✓ |

GEZE Cluster 351971: `Auftragsnummer` `7091200283960003` taucht zweimal auf
(Erlöse Fracht 262,53 € und 813,36 €). Beide Zeilen bleiben im Output mit
ihren eigenen Werten; Σ = 1.075,89 €.

---

### Trap 2 — Orphan-Subs (Master nicht im BI-Subset)

**Ursache:** Nach Rechnungsnummer-Filter (`RN > 5`) kann der Master einer Sendung
aus dem BI-POST-Subset herausfallen, während die Subzeilen noch enthalten sind.

**Lösung:** Subzeilen werden nur dann gedroppt, wenn ihr Cluster-Master **ebenfalls**
im gefilterten BI-Subset vorhanden ist. Orphan-Subs (`_ax_sub == False`) bleiben als
eigenständige Zeilen erhalten.

**Beobachtung:** GEZE 10 Orphan-Subs (Σ Erlöse Fracht 1.074,51 €), CHT 10, EBM 0.

---

### Trap 3 — dict(zip()) Last-Value-Wins bei Duplikat-Auftragsnummern

Wenn dieselbe `Auftragsnummer` in mehreren AX-Zeilen vorkommt (1.127 Fälle bei GEZE),
überschreibt ein späteres `Nein` in `Hauptabrechnungsstrecke` ein früheres `Ja` im Dict.

**Lösung:** Set-basierte Master-Erkennung:

```python
master_auftrs = set(mstr_rows['_auftr'])  # True wenn JE EINMAL Haupt=Ja
post['_ax_mstr'] = post['_auftr_s'].isin(master_auftrs)
```

---

## Summen-Erhalt-Garantie

Nach Konsolidierung müssen für alle akkumulierten Spalten gelten:

```
Σ(Spalte, alle POST-Rows vorher) == Σ(Spalte, konsolidierte Rows nachher)
```

Validiert über 21 Checks (3 Kunden × 7 Spalten): **alle ±0,0000 €**.

---

## Strenge PRE/POST-Trennung

AX-Cluster-Konsolidierung (`enrich_post_ax_clusters`) betrifft **ausschließlich POST**.

DINAS-seitige Mastersendung-Logik (`consolidate_master_shipments_dinas`) betrifft
ausschließlich PRE und verwendet eine vollständig andere Schlüsselsemantik
(`Mastersendung`, 16-stellige DINAS-IDs vs. AX `Zusammengefasst in` 4–6-stellige
Integer). Diese Systeme dürfen **nicht vermischt** werden.
