#!/usr/bin/env python3
"""
apply_rollout.py
================
Applies flag_multi_rn_dinas rollout + DQ coverage block to 7 report builders.
Safe to re-run: checks for marker strings before applying each patch.

Run from /home/user/TMS: python src/apply_rollout.py
"""
import re
from pathlib import Path

# ── Shared code snippets ────────────────────────────────────────────────────

IMPORT_SNIPPET = "from dinas_bi_enrichment import enrich_customer_bi\n"

ENRICHMENT_BLOCK = '''
# ── BI-Enrichment: Komplettpreis / Sammelposten / Gutschrift-Netting ──────
print('\\n── BI-Enrichment ────────────────────────────────────────────────────')
_bi_raw  = pd.read_pickle(Path('output/bi_top20_data.pkl'))['df']
_cust_bi = _bi_raw[_bi_raw['Kunden Nr BK'] == KNR].copy()
_bi_enriched, _dinas_net, _enrich_stats = enrich_customer_bi(_cust_bi, dinas_cache)
s = _enrich_stats
_tmp = _bi_enriched.drop_duplicates('_snr').set_index('_snr')
_flag_kp  = _tmp['flag_komplettpreis'].to_dict()
_flag_sp  = _tmp['flag_bi_split'].to_dict()
_flag_dvp = _tmp['dinas_vs_bi_diff_pct'].to_dict()
_flag_mr  = _tmp['flag_multi_rn_dinas'].fillna(False).to_dict()
del _tmp
'''

HDR_COLS_EXTRA = "            'Komplettpreis','BI-Split','DINAS vs BI %','DINAS Multi-Row']"

DQ_BLOCK = '''
    # ── DQ block + PDF-Coverage ───────────────────────────────────────────
    n_pre_bi   = len(_cust_bi[_cust_bi['periode'] == 'PRE'])
    n_post_bi  = len(_cust_bi[_cust_bi['periode'] == 'POST'])
    n_matched  = s['n_dinas_matched']
    n_multi_rn = s.get('n_multi_rn_dinas', 0)
    n_acc_base = s.get('n_acc_base', n_matched)
    n_ok       = s['n_within_5pct']
    n_sp       = s['n_split_snrs']
    n_gus      = s['n_gutschrift_solo']
    cov_pct    = n_matched / n_pre_bi * 100 if n_pre_bi else 0
    cov_warn   = '  ⚠ Coverage < 50%% — Accuracy auf Stichprobe!' if cov_pct < 50 else ''
    FILL_DQ  = fill('F2F2F2')
    FILL_DQH = fill('D9D9D9')
    FILL_DQW = fill('FFF2CC')
    dq_rows = [
        ('Datenqualität — PDF-Coverage + Accuracy-Basis', None, True),
        ('PRE-Sendungen gesamt (aus bi_raw)', f'{n_pre_bi}  (POST: {n_post_bi})', False),
        ('davon mit DINAS-PDF-Match',
         f'{n_matched} / {n_pre_bi} ({cov_pct:.0f}%%){cov_warn}', False),
        ('davon nach Multi-Row-Ausschluss vergleichbar', f'{n_acc_base}', False),
        ('davon im \\u00b15%%-Band',
         (f'{n_ok} / {n_acc_base} ({n_ok/n_acc_base*100:.0f}%% der Acc.-Basis)  \\u2190 Basis-Accuracy'
          if n_acc_base else '\\u2013'), False),
        ('Ausschluss-Gründe',
         f'A) Kein DINAS-Match: {n_pre_bi - n_matched}  |  '
         f'B) Sammelposten (nicht ausgeschl.): {n_sp} ({s["pct_split"]:.0f}%%)  |  '
         f'C) Solo-Gutschriften: {n_gus}  |  '
         f'D) DINAS Multi-Row: {n_multi_rn} (aus \\u00b15%%-Basis ausgeschl.)', False),
        ('Vergleich-Methode',
         'Komplettpreis \\u2192 DINAS total_items vs BI Erloese  |  '
         'Standard \\u2192 DINAS fracht vs BI Erl\\u00f6se Fracht', False),
    ]
    for ri, (label, val, is_hdr) in enumerate(dq_rows, 2):
        rf   = FILL_DQH if is_hdr else (FILL_DQW if '\\u26a0' in (val or '') else FILL_DQ)
        fn_l = fnt(bold=is_hdr, size=9)
        fn_v = fnt(bold=False, size=9, italic=True)
        ws.merge_cells(start_row=ri, start_column=1, end_row=ri, end_column=N//2)
        wc(ws, ri, 1, label, rf, fn_l, 'left')
        if val:
            ws.merge_cells(start_row=ri, start_column=N//2+1, end_row=ri, end_column=N)
            wc(ws, ri, N//2+1, val, rf, fn_v, 'left')
    DQ_ROWS = len(dq_rows) + 1
    ws.freeze_panes = f'A{DQ_ROWS + 2}'
    HDR_ROW = DQ_ROWS + 1
'''

ACC_SHEET_FN = '''
def build_accuracy_sheet(ws):
    ws.title = 'Accuracy_PRE'
    ws.freeze_panes = 'A3'
    _pre = _bi_enriched[_bi_enriched['periode'] == 'PRE'].copy()
    _rn_lkp = _dinas_net.set_index('_snr')[['rechnung_nr', 'n_rows']].to_dict('index')
    _pre['rechnung_nr_dinas'] = _pre['_snr'].map(
        lambda s_: _rn_lkp.get(s_, {}).get('rechnung_nr', ''))
    _pre['n_dinas_rows'] = _pre['_snr'].map(
        lambda s_: _rn_lkp.get(s_, {}).get('n_rows', None))
    acc = _pre[_pre['dinas_netto_compare'].notna()].copy()
    acc['diff_eur'] = acc['dinas_vs_bi_diff_eur'].round(2)
    acc['diff_pct'] = acc['dinas_vs_bi_diff_pct'].round(1)
    acc = acc.sort_values('diff_pct', key=abs, ascending=False).reset_index(drop=True)
    n_tot     = len(acc)
    _is_multi = acc['flag_multi_rn_dinas'].fillna(False).astype(bool)
    n_multi   = int(_is_multi.sum())
    n_acc     = n_tot - n_multi
    n_ok_a    = int((acc.loc[~_is_multi, 'diff_pct'].abs() <= 5).sum()) if n_acc else 0
    n_big_a   = int((acc.loc[~_is_multi, 'diff_pct'].abs() > 10).sum()) if n_acc else 0
    n_kp      = int(acc['flag_komplettpreis'].sum())
    n_sp_a    = int(acc['flag_bi_split'].sum())
    n_gus_a   = int(acc['flag_gutschrift_solo'].fillna(False).sum())
    summary = (f'{KUNDE} ({KNR}) \u2014 PRE Accuracy: DINAS Total vs BI Erloese_effektiv  |  '
               f'Rows: {n_tot}  |  Multi-Row (ausgeschl.): {n_multi}  |  Acc.-Basis: {n_acc}  |  '
               f'\u00b15%%: {n_ok_a} ({n_ok_a/n_acc*100:.0f}%% der Basis)  |  >10%% Abw.: {n_big_a}  |  '
               f'Komplettpreis: {n_kp}  |  Sammelposten: {n_sp_a}  |  Solo-Gutschrift: {n_gus_a}')
    ACC_COLS = ['Auftrags-Nr','Rech.-Nr DINAS','Rech.-Nr BI','Datum',
                'Land','Empf.PLZ','Tonnage kg',
                'DINAS Total/Fracht','BI Erloese_eff','Diff EUR','Diff %%',
                'Komplettpreis','BI-Split','Solo-Gutschrift','Multi-Row DINAS','Abw. Klasse']
    NA = len(ACC_COLS)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=NA)
    wc(ws, 1, 1, summary, FILL_HDR, fnt(bold=True, color='FFFFFF', size=10), 'left')
    for ci, h in enumerate(ACC_COLS, 1):
        wc(ws, 2, ci, h, FILL_HDR, fnt(bold=True, color='FFFFFF', size=9), 'center', brd=BRD)
    FILL_OK   = fill('E2EFDA')
    FILL_WARN = fill('FFEB9C')
    FILL_BAD  = fill('FFC7CE')
    FILL_MROW = fill('FFCC99')
    EUR_ACC = {8, 9, 10}; PCT_ACC = {11}
    def abw_klasse(pct):
        if pd.isna(pct): return 'n/a'
        a = abs(pct)
        if a <= 5:  return '\u00b15%%'
        if a <= 10: return '5-10%%'
        return '>10%%'
    rnum = 2
    for _, r in acc.iterrows():
        rnum += 1
        pct   = r['diff_pct']
        is_mr = bool(r.get('flag_multi_rn_dinas', False))
        rf    = FILL_MROW if is_mr else (
                FILL_OK   if pd.notna(pct) and abs(pct) <= 5 else (
                FILL_WARN if pd.notna(pct) and abs(pct) <= 10 else FILL_BAD))
        vals = [
            r.get('Auftragsnummer'), r.get('rechnung_nr_dinas') or '',
            r.get('Rechnungsnummer') or '', r.get('Leistungsdatum') or '',
            r.get('Empf\u00e4nger Land') or '', r.get('Empf\u00e4nger PLZ') or '',
            r.get('Tonnage (eff.)'), r.get('dinas_netto_compare'),
            r.get('erloese_fracht_effektiv'), r.get('diff_eur'), pct,
            'JA' if r.get('flag_komplettpreis') else '',
            'JA' if r.get('flag_bi_split') else '',
            'JA' if r.get('flag_gutschrift_solo') else '',
            'JA' if is_mr else '',
            abw_klasse(pct) if not is_mr else 'Multi-Row',
        ]
        for ci, v in enumerate(vals, 1):
            if isinstance(v, float) and math.isnan(v): v = None
            fmt = EUR_FMT if ci in EUR_ACC else ('#,##0.0"%%"' if ci in PCT_ACC else None)
            al  = 'right' if ci in EUR_ACC or ci in PCT_ACC else 'left'
            if ci in {1, 2, 3} and v is not None:
                try: v = str(int(float(str(v))))
                except: v = str(v)
            wc(ws, rnum, ci, v, rf, fnt(size=9), al, fmt, BRD)
    col_widths = [15, 14, 14, 12, 6, 8, 10, 12, 12, 10, 8, 10, 8, 12, 12, 10]
    for ci, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[1].height = 18
    ws.row_dimensions[2].height = 16
    return rnum

'''


def patch_file(path: Path, dry_run=False) -> bool:
    src = path.read_text(encoding='utf-8')
    original = src
    name = path.name

    # Guard: already patched?
    if 'build_accuracy_sheet' in src and '_cust_bi' in src:
        print(f'  SKIP {name}: already patched')
        return False

    # ── 1. Add import ──────────────────────────────────────────────────────
    IMPORT_ANCHOR = 'from dinas_pdf_parser import parse_one, flatten'
    if IMPORT_SNIPPET.strip() not in src:
        if IMPORT_ANCHOR in src:
            src = src.replace(IMPORT_ANCHOR,
                              IMPORT_ANCHOR + '\n' + IMPORT_SNIPPET.strip())
        else:
            print(f'  WARN {name}: import anchor not found')

    # ── 2. Enrichment block ────────────────────────────────────────────────
    if '_cust_bi' not in src:
        # Insert after the Fracht>0 filter line
        anchor_enrich = "pre = pre[pre['Dinas Fracht'].fillna(0) > 0].copy()"
        if anchor_enrich in src:
            src = src.replace(anchor_enrich,
                              anchor_enrich + '\n' + ENRICHMENT_BLOCK)
        else:
            print(f'  WARN {name}: enrichment anchor not found')

    # ── 3. Extend HDR_COLS ─────────────────────────────────────────────────
    if 'DINAS Multi-Row' not in src:
        old_hdr_end = "'Erlöse','Abw. Grund']"
        new_hdr_end = ("'Erlöse','Abw. Grund',\n" +
                       "            'Komplettpreis','BI-Split','DINAS vs BI %','DINAS Multi-Row']")
        if old_hdr_end in src:
            src = src.replace(old_hdr_end, new_hdr_end)
        else:
            print(f'  WARN {name}: HDR_COLS anchor not found')

    # ── 4. Update NUM_RIGHT (add col 36) ──────────────────────────────────
    if '36' not in src.split('NUM_RIGHT')[1][:60] if 'NUM_RIGHT' in src else True:
        # Replace set: add 36
        src = re.sub(
            r'NUM_RIGHT\s*=\s*\{(5,\s*16,\s*19,\s*20,\s*21,\s*22)\}',
            r'NUM_RIGHT = {\1, 36}',
            src
        )

    # ── 5. Modify build_main_sheet: remove freeze_panes, add DQ block ──────
    if 'DQ block + PDF-Coverage' not in src:
        # Pattern varies by file; match the freeze_panes + title block
        # Remove ws.freeze_panes = 'A3' from build_main_sheet
        src = re.sub(
            r"(def build_main_sheet\(ws\):.*?ws\.title = '[^']+'\n)\s*ws\.freeze_panes = 'A3'\n",
            r'\1',
            src, flags=re.DOTALL
        )
        # Add DQ block after the title wc(...) call and before the column header loop
        # Try both spaced and compact (no-space) variants
        for _a, _r in [
            ("    for ci, h in enumerate(HDR_COLS, 1):\n        wc(ws, 2, ci,",
             DQ_BLOCK + "    for ci, h in enumerate(HDR_COLS, 1):\n        wc(ws, HDR_ROW, ci,"),
            ("    for ci, h in enumerate(HDR_COLS, 1):\n        wc(ws,2,ci,",
             DQ_BLOCK + "    for ci, h in enumerate(HDR_COLS, 1):\n        wc(ws,HDR_ROW,ci,"),
        ]:
            if _a in src:
                src = src.replace(_a, _r)
                break
        else:
            print(f'  WARN {name}: HDR_COLS loop anchor not found')

        # Update row = 2 → row = HDR_ROW (inside build_main_sheet)
        src = re.sub(r'(\n    row = )2(\n\n    for _, cl in stats)', r'\1HDR_ROW\2', src)

    # ── 6. Extend alt-row vals ─────────────────────────────────────────────
    if '_sk = _norm' not in src:
        old_alt = (
            "            vals = ['alt', r.get('Auftragsnummer'),\n"
            "                    r.get('_master_nr'), r.get('_sub_nrs'), int(r.get('_n_subs') or 0), r.get('_ist_master') or '',\n"
            "                    r.get('Rechnungsnummer'), r.get('Leistungsdatum'), KUNDE,\n"
            "                    r.get('Empfänger Land'), r.get('Empfänger PLZ'), r.get('Versender PLZ'),\n"
            "                    gwband, zone, BASIS, billing_kg, bp, eff,\n"
            "                    kg, r.get('Stellplätze'), r.get('Lademeter'), r.get('Volumen'), soll,\n"
            "                    *nk,\n"
            "                    erloese, abw_grund_row(nk, soll, erloese)]\n"
            "            write_row(ws, row, vals, FILL_ALT, is_ctrl)"
        )
        new_alt = (
            "            _sk = _norm(str(r.get('Auftragsnummer', '')))\n"
            "            vals = ['alt', r.get('Auftragsnummer'),\n"
            "                    r.get('_master_nr'), r.get('_sub_nrs'), int(r.get('_n_subs') or 0), r.get('_ist_master') or '',\n"
            "                    r.get('Rechnungsnummer'), r.get('Leistungsdatum'), KUNDE,\n"
            "                    r.get('Empfänger Land'), r.get('Empfänger PLZ'), r.get('Versender PLZ'),\n"
            "                    gwband, zone, BASIS, billing_kg, bp, eff,\n"
            "                    kg, r.get('Stellplätze'), r.get('Lademeter'), r.get('Volumen'), soll,\n"
            "                    *nk,\n"
            "                    erloese, abw_grund_row(nk, soll, erloese),\n"
            "                    'JA' if _flag_kp.get(_sk, False) else '',\n"
            "                    'JA' if _flag_sp.get(_sk, False) else '',\n"
            "                    _flag_dvp.get(_sk, None),\n"
            "                    'JA' if _flag_mr.get(_sk, False) else '']\n"
            "            write_row(ws, row, vals, FILL_ALT, is_ctrl)"
        )
        if old_alt in src:
            src = src.replace(old_alt, new_alt)
        else:
            # Try GEZE/Sika compact variant ('n/a' zone, r.name==ctrl_pi, no *nk linebreak)
            for _zone_fld, _billing_fld in [
                ("gwband, 'n/a', BASIS, billing_kg, bp, eff,\n"
                 "                    kg, r.get('Stellplätze'), r.get('Lademeter'), r.get('Volumen'), soll,\n"
                 "                    *nk, erloese, abw_grund_row(nk, soll, erloese)]\n"
                 "            write_row(ws, row, vals, FILL_ALT, r.name==ctrl_pi)",
                 "gwband, 'n/a', BASIS, billing_kg, bp, eff,\n"
                 "                    kg, r.get('Stellplätze'), r.get('Lademeter'), r.get('Volumen'), soll,\n"
                 "                    *nk, erloese, abw_grund_row(nk, soll, erloese),\n"
                 "                    'JA' if _flag_kp.get(_sk, False) else '',\n"
                 "                    'JA' if _flag_sp.get(_sk, False) else '',\n"
                 "                    _flag_dvp.get(_sk, None),\n"
                 "                    'JA' if _flag_mr.get(_sk, False) else '']\n"
                 "            write_row(ws, row, vals, FILL_ALT, r.name==ctrl_pi)"),
                ("sb, 'n/a', BASIS, stpl, bp, eff,\n"
                 "                    r.get('Tonnage (eff.)'), r.get('Stellplätze'), r.get('Lademeter'), r.get('Volumen'), soll,\n"
                 "                    *nk, erloese, abw_grund_row(nk, soll, erloese)]\n"
                 "            write_row(ws, row, vals, FILL_ALT, r.name==ctrl_pi)",
                 "sb, 'n/a', BASIS, stpl, bp, eff,\n"
                 "                    r.get('Tonnage (eff.)'), r.get('Stellplätze'), r.get('Lademeter'), r.get('Volumen'), soll,\n"
                 "                    *nk, erloese, abw_grund_row(nk, soll, erloese),\n"
                 "                    'JA' if _flag_kp.get(_sk, False) else '',\n"
                 "                    'JA' if _flag_sp.get(_sk, False) else '',\n"
                 "                    _flag_dvp.get(_sk, None),\n"
                 "                    'JA' if _flag_mr.get(_sk, False) else '']\n"
                 "            write_row(ws, row, vals, FILL_ALT, r.name==ctrl_pi)"),
            ]:
                _old_part, _new_part = _zone_fld, _billing_fld
                _old_full = (
                    "            vals = ['alt', r.get('Auftragsnummer'),\n"
                    "                    r.get('_master_nr'), r.get('_sub_nrs'), int(r.get('_n_subs') or 0), r.get('_ist_master') or '',\n"
                    "                    r.get('Rechnungsnummer'), r.get('Leistungsdatum'), KUNDE,\n"
                    "                    r.get('Empfänger Land'), r.get('Empfänger PLZ'), r.get('Versender PLZ'),\n"
                    "                    " + _old_part
                )
                _new_full = (
                    "            _sk = _norm(str(r.get('Auftragsnummer', '')))\n"
                    "            vals = ['alt', r.get('Auftragsnummer'),\n"
                    "                    r.get('_master_nr'), r.get('_sub_nrs'), int(r.get('_n_subs') or 0), r.get('_ist_master') or '',\n"
                    "                    r.get('Rechnungsnummer'), r.get('Leistungsdatum'), KUNDE,\n"
                    "                    r.get('Empfänger Land'), r.get('Empfänger PLZ'), r.get('Versender PLZ'),\n"
                    "                    " + _new_part
                )
                if _old_full in src:
                    src = src.replace(_old_full, _new_full)
                    break
            else:
                print(f'  WARN {name}: alt-row vals anchor not found')

        # neu-row
        old_neu = (
            "            vals = ['neu', r.get('Auftragsnummer'),\n"
            "                    r.get('_master_nr'), r.get('_sub_nrs'), int(r.get('_n_subs') or 0), r.get('_ist_master') or '',\n"
            "                    r.get('Rechnungsnummer'), r.get('Leistungsdatum'), KUNDE,\n"
            "                    r.get('Empfänger Land'), r.get('Empfänger PLZ'), r.get('Versender PLZ'),\n"
            "                    gwband, zone, BASIS, billing_kg, bp, eff,\n"
            "                    kg, r.get('Stellplätze'), r.get('Lademeter'), r.get('Volumen'), soll,\n"
            "                    *nk,\n"
            "                    erloese, abw_grund_row(nk, soll, erloese)]\n"
            "            write_row(ws, row, vals, FILL_NEU, is_ctrl)"
        )
        new_neu = (
            "            _sk = _norm(str(r.get('Auftragsnummer', '')))\n"
            "            vals = ['neu', r.get('Auftragsnummer'),\n"
            "                    r.get('_master_nr'), r.get('_sub_nrs'), int(r.get('_n_subs') or 0), r.get('_ist_master') or '',\n"
            "                    r.get('Rechnungsnummer'), r.get('Leistungsdatum'), KUNDE,\n"
            "                    r.get('Empfänger Land'), r.get('Empfänger PLZ'), r.get('Versender PLZ'),\n"
            "                    gwband, zone, BASIS, billing_kg, bp, eff,\n"
            "                    kg, r.get('Stellplätze'), r.get('Lademeter'), r.get('Volumen'), soll,\n"
            "                    *nk,\n"
            "                    erloese, abw_grund_row(nk, soll, erloese),\n"
            "                    '', 'JA' if _flag_sp.get(_sk, False) else '', None, None]\n"
            "            write_row(ws, row, vals, FILL_NEU, is_ctrl)"
        )
        if old_neu in src:
            src = src.replace(old_neu, new_neu)
        else:
            for _zone_fld, _billing_fld in [
                ("gwband, 'n/a', BASIS, billing_kg, bp, eff,\n"
                 "                    kg, r.get('Stellplätze'), r.get('Lademeter'), r.get('Volumen'), soll,\n"
                 "                    *nk, erloese, abw_grund_row(nk, soll, erloese)]\n"
                 "            write_row(ws, row, vals, FILL_NEU, r.name==ctrl_oi)",
                 "gwband, 'n/a', BASIS, billing_kg, bp, eff,\n"
                 "                    kg, r.get('Stellplätze'), r.get('Lademeter'), r.get('Volumen'), soll,\n"
                 "                    *nk, erloese, abw_grund_row(nk, soll, erloese),\n"
                 "                    '', 'JA' if _flag_sp.get(_sk, False) else '', None, None]\n"
                 "            write_row(ws, row, vals, FILL_NEU, r.name==ctrl_oi)"),
                ("sb, 'n/a', BASIS, stpl, bp, eff,\n"
                 "                    r.get('Tonnage (eff.)'), r.get('Stellplätze'), r.get('Lademeter'), r.get('Volumen'), soll,\n"
                 "                    *nk, erloese, abw_grund_row(nk, soll, erloese)]\n"
                 "            write_row(ws, row, vals, FILL_NEU, r.name==ctrl_oi)",
                 "sb, 'n/a', BASIS, stpl, bp, eff,\n"
                 "                    r.get('Tonnage (eff.)'), r.get('Stellplätze'), r.get('Lademeter'), r.get('Volumen'), soll,\n"
                 "                    *nk, erloese, abw_grund_row(nk, soll, erloese),\n"
                 "                    '', 'JA' if _flag_sp.get(_sk, False) else '', None, None]\n"
                 "            write_row(ws, row, vals, FILL_NEU, r.name==ctrl_oi)"),
            ]:
                _old_part, _new_part = _zone_fld, _billing_fld
                _old_full = (
                    "            vals = ['neu', r.get('Auftragsnummer'),\n"
                    "                    r.get('_master_nr'), r.get('_sub_nrs'), int(r.get('_n_subs') or 0), r.get('_ist_master') or '',\n"
                    "                    r.get('Rechnungsnummer'), r.get('Leistungsdatum'), KUNDE,\n"
                    "                    r.get('Empfänger Land'), r.get('Empfänger PLZ'), r.get('Versender PLZ'),\n"
                    "                    " + _old_part
                )
                _new_full = (
                    "            _sk = _norm(str(r.get('Auftragsnummer', '')))\n"
                    "            vals = ['neu', r.get('Auftragsnummer'),\n"
                    "                    r.get('_master_nr'), r.get('_sub_nrs'), int(r.get('_n_subs') or 0), r.get('_ist_master') or '',\n"
                    "                    r.get('Rechnungsnummer'), r.get('Leistungsdatum'), KUNDE,\n"
                    "                    r.get('Empfänger Land'), r.get('Empfänger PLZ'), r.get('Versender PLZ'),\n"
                    "                    " + _new_part
                )
                if _old_full in src:
                    src = src.replace(_old_full, _new_full)
                    break
            else:
                print(f'  WARN {name}: neu-row vals anchor not found')

    # ── 7. Extend widths ──────────────────────────────────────────────────
    old_widths = "    widths = [8,15,16,30,8,9, 13,12,18,5,8,8, 11,8,10, 9,10,10, 9,9,9,9, 10, 10,9,9,9,9,9,9,9, 11,22]"
    new_widths = "    widths = [8,15,16,30,8,9, 13,12,18,5,8,8, 11,8,10, 9,10,10, 9,9,9,9, 10, 10,9,9,9,9,9,9,9, 11,22, 12,12,10,12]"
    if old_widths in src:
        src = src.replace(old_widths, new_widths)

    # ── 8. Update row_dimensions[2] → HDR_ROW ─────────────────────────────
    src = src.replace(
        '    ws.row_dimensions[2].height = 18\n    return row',
        '    ws.row_dimensions[HDR_ROW].height = 18\n    return row'
    )
    # GEZE/Sika: combined line format
    src = src.replace(
        '    ws.row_dimensions[1].height = 20; ws.row_dimensions[2].height = 18\n    return row',
        '    ws.row_dimensions[1].height = 20; ws.row_dimensions[HDR_ROW].height = 18\n    return row'
    )

    # ── 9. Add build_accuracy_sheet function before # ── Schreiben ─────────
    if 'build_accuracy_sheet' not in src:
        anchor_write = '# ── Schreiben ─'
        if anchor_write in src:
            src = src.replace(anchor_write, ACC_SHEET_FN + anchor_write)
        else:
            print(f'  WARN {name}: Schreiben anchor not found')

    # ── 10. Update save section ────────────────────────────────────────────
    if 'acc_rows' not in src:
        src = re.sub(
            r"(build_nk_sheet\(wb\.create_sheet\('NK_Konditionen'\)\))\n(wb\.save)",
            lambda m: m.group(1) + "\nacc_rows = build_accuracy_sheet(wb.create_sheet('Accuracy_PRE'))\n" + m.group(2),
            src
        )
        src = re.sub(
            r"(print\(f'  Sheet \"NK_Konditionen\":.*\n)",
            lambda m: m.group(1) + 'print(f\'  Sheet "Accuracy_PRE":      {acc_rows-2} Rows\')\n',
            src
        )

    if src == original:
        print(f'  NOOP {name}: no changes made')
        return False

    if not dry_run:
        path.write_text(src, encoding='utf-8')
        print(f'  PATCHED {name}')
    else:
        print(f'  DRY-RUN {name}: changes would be applied')
    return True


# ── Files to patch ───────────────────────────────────────────────────────────
TARGETS = [
    Path('src/build_fischer_report.py'),
    Path('src/build_bitzer_report.py'),
    Path('src/build_ebm_report.py'),
    Path('src/build_helu_report_v2.py'),
    Path('src/build_geze_report.py'),
    Path('src/build_sika_report.py'),
]

if __name__ == '__main__':
    import sys
    dry = '--dry' in sys.argv
    print('=== Rollout Patch ===')
    for p in TARGETS:
        print(f'\n[{p.name}]')
        patch_file(p, dry_run=dry)
    print('\nDone.')
