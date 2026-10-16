"""
Export_excel.py -- Doc openmc_results.csv va xuat ra openmc_export.xlsx cho Paper 10 (S1..S8)
Gom cac Sheet:
  - Sheet 1: MAC (cm2/g) - Ma tran MAC he so suy giam khoi luong
  - Sheet 2: T_Transmittance - Do truyen qua T = I/I0 (to mau canh bao ngoai vung 2% - 90%)
  - Sheet 3: R_Compton - Ty le R = mu_Compton / (mu_Total - mu_Rayleigh) trong mau
  - Sheet 4: Do_day_mau - Do day da dung trong tung luot chay
  - Sheet 5: QA_Transmittance - Chi tiet kiem dinh chat luong so dem va do truyen qua
  - Sheet 6: Thoi_gian_chay - Thoi gian bat dau, ket thuc va tong thoi gian chay
  - Sheet 7: Benchmark_Table2 - So sanh doi chieu truc tiep voi Table 2 Paper 1 (XCOM & MCNPX)
"""
import csv
import os
import json
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

CSV_FILE     = 'openmc_results.csv'
OUTPUT_FILE  = 'openmc_export.xlsx'
TIMING_FILE  = 'run_all_timing.json'
SAMPLES      = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8']

# Table 2 Paper 1 (PNE 2022) - Du lieu chuan doi chieu
PAPER1_TABLE2 = {
    0.015: {"s1": {"XCOM": 9.479, "MCNPX": 9.387}, "s2": {"XCOM": 14.88, "MCNPX": 14.67}, "s3": {"XCOM": 20.25, "MCNPX": 19.98}, "s4": {"XCOM": 25.59, "MCNPX": 25.29}, "s5": {"XCOM": 34.61, "MCNPX": 34.22}, "s6": {"XCOM": 40.59, "MCNPX": 40.16}, "s7": {"XCOM": 46.54, "MCNPX": 46.06}, "s8": {"XCOM": 52.47, "MCNPX": 51.95}},
    0.020: {"s1": {"XCOM": 4.095, "MCNPX": 4.072}, "s2": {"XCOM": 6.848, "MCNPX": 6.786}, "s3": {"XCOM": 9.587, "MCNPX": 9.489}, "s4": {"XCOM": 12.31, "MCNPX": 12.18}, "s5": {"XCOM": 16.92, "MCNPX": 16.76}, "s6": {"XCOM": 19.98, "MCNPX": 19.81}, "s7": {"XCOM": 23.03, "MCNPX": 22.84}, "s8": {"XCOM": 26.07, "MCNPX": 25.86}},
    0.030: {"s1": {"XCOM": 1.288, "MCNPX": 1.288}, "s2": {"XCOM": 2.378, "MCNPX": 2.368}, "s3": {"XCOM": 3.461, "MCNPX": 3.444}, "s4": {"XCOM": 4.540, "MCNPX": 4.515}, "s5": {"XCOM": 6.368, "MCNPX": 6.335}, "s6": {"XCOM": 7.576, "MCNPX": 7.538}, "s7": {"XCOM": 8.780, "MCNPX": 8.736}, "s8": {"XCOM": 9.979, "MCNPX": 9.932}},
    0.040: {"s1": {"XCOM": 0.5898, "MCNPX": 0.5925}, "s2": {"XCOM": 1.171, "MCNPX": 1.172}, "s3": {"XCOM": 1.748, "MCNPX": 1.749}, "s4": {"XCOM": 2.323, "MCNPX": 2.323}, "s5": {"XCOM": 3.292, "MCNPX": 3.293}, "s6": {"XCOM": 3.935, "MCNPX": 3.936}, "s7": {"XCOM": 4.576, "MCNPX": 4.577}, "s8": {"XCOM": 5.215, "MCNPX": 5.217}},
    0.050: {"s1": {"XCOM": 0.3340, "MCNPX": 0.3364}, "s2": {"XCOM": 1.742, "MCNPX": 1.742}, "s3": {"XCOM": 3.143, "MCNPX": 3.142}, "s4": {"XCOM": 4.536, "MCNPX": 4.534}, "s5": {"XCOM": 6.901, "MCNPX": 6.899}, "s6": {"XCOM": 8.469, "MCNPX": 8.466}, "s7": {"XCOM": 10.03, "MCNPX": 10.03}, "s8": {"XCOM": 11.59, "MCNPX": 11.58}},
    0.060: {"s1": {"XCOM": 0.1859, "MCNPX": 0.1873}, "s2": {"XCOM": 0.6878, "MCNPX": 0.6896}, "s3": {"XCOM": 1.1897, "MCNPX": 1.189}, "s4": {"XCOM": 1.6917, "MCNPX": 1.688}, "s5": {"XCOM": 2.2299, "MCNPX": 2.229}, "s6": {"XCOM": 2.7319, "MCNPX": 2.731}, "s7": {"XCOM": 3.2338, "MCNPX": 3.232}, "s8": {"XCOM": 3.7357, "MCNPX": 3.732}},
    0.080: {"s1": {"XCOM": 0.1706, "MCNPX": 0.1724}, "s2": {"XCOM": 0.4497, "MCNPX": 0.4533}, "s3": {"XCOM": 0.7274, "MCNPX": 0.7325}, "s4": {"XCOM": 1.004, "MCNPX": 1.010}, "s5": {"XCOM": 1.346, "MCNPX": 1.353}, "s6": {"XCOM": 1.624, "MCNPX": 1.632}, "s7": {"XCOM": 1.902, "MCNPX": 1.910}, "s8": {"XCOM": 2.179, "MCNPX": 2.188}},
    0.100: {"s1": {"XCOM": 0.1601, "MCNPX": 0.1618}, "s2": {"XCOM": 0.3207, "MCNPX": 0.3235}, "s3": {"XCOM": 0.4805, "MCNPX": 0.4842}, "s4": {"XCOM": 0.6394, "MCNPX": 0.6437}, "s5": {"XCOM": 0.8548, "MCNPX": 0.8596}, "s6": {"XCOM": 1.015, "MCNPX": 1.020}, "s7": {"XCOM": 1.174, "MCNPX": 1.180}, "s8": {"XCOM": 1.332, "MCNPX": 1.339}},
    0.150: {"s1": {"XCOM": 0.1417, "MCNPX": 0.1428}, "s2": {"XCOM": 0.2081, "MCNPX": 0.2096}, "s3": {"XCOM": 0.2742, "MCNPX": 0.2759}, "s4": {"XCOM": 0.3399, "MCNPX": 0.3418}, "s5": {"XCOM": 0.4449, "MCNPX": 0.4468}, "s6": {"XCOM": 0.5109, "MCNPX": 0.5130}, "s7": {"XCOM": 0.5766, "MCNPX": 0.5788}, "s8": {"XCOM": 0.6420, "MCNPX": 0.6444}},
    0.200: {"s1": {"XCOM": 0.1293, "MCNPX": 0.1299}, "s2": {"XCOM": 0.1661, "MCNPX": 0.1669}, "s3": {"XCOM": 0.2026, "MCNPX": 0.2036}, "s4": {"XCOM": 0.2389, "MCNPX": 0.2399}, "s5": {"XCOM": 0.3032, "MCNPX": 0.3040}, "s6": {"XCOM": 0.3399, "MCNPX": 0.3408}, "s7": {"XCOM": 0.3764, "MCNPX": 0.3773}, "s8": {"XCOM": 0.4127, "MCNPX": 0.4137}},
    0.300: {"s1": {"XCOM": 0.1121, "MCNPX": 0.1123}, "s2": {"XCOM": 0.1303, "MCNPX": 0.1306}, "s3": {"XCOM": 0.1484, "MCNPX": 0.1486}, "s4": {"XCOM": 0.1663, "MCNPX": 0.1666}, "s5": {"XCOM": 0.2009, "MCNPX": 0.2008}, "s6": {"XCOM": 0.2189, "MCNPX": 0.2188}, "s7": {"XCOM": 0.2368, "MCNPX": 0.2366}, "s8": {"XCOM": 0.2546, "MCNPX": 0.2544}},
    0.400: {"s1": {"XCOM": 0.1005, "MCNPX": 0.1006}, "s2": {"XCOM": 0.1118, "MCNPX": 0.1118}, "s3": {"XCOM": 0.1229, "MCNPX": 0.1229}, "s4": {"XCOM": 0.1340, "MCNPX": 0.1340}, "s5": {"XCOM": 0.1565, "MCNPX": 0.1561}, "s6": {"XCOM": 0.1675, "MCNPX": 0.1670}, "s7": {"XCOM": 0.1784, "MCNPX": 0.1778}, "s8": {"XCOM": 0.1892, "MCNPX": 0.1886}},
    0.500: {"s1": {"XCOM": 0.0917, "MCNPX": 0.0917}, "s2": {"XCOM": 0.0995, "MCNPX": 0.0994}, "s3": {"XCOM": 0.1072, "MCNPX": 0.1070}, "s4": {"XCOM": 0.1148, "MCNPX": 0.1146}, "s5": {"XCOM": 0.1308, "MCNPX": 0.1302}, "s6": {"XCOM": 0.1383, "MCNPX": 0.1377}, "s7": {"XCOM": 0.1458, "MCNPX": 0.1451}, "s8": {"XCOM": 0.1533, "MCNPX": 0.1524}},
    0.600: {"s1": {"XCOM": 0.0847, "MCNPX": 0.0847}, "s2": {"XCOM": 0.0906, "MCNPX": 0.0905}, "s3": {"XCOM": 0.0964, "MCNPX": 0.0962}, "s4": {"XCOM": 0.1022, "MCNPX": 0.1019}, "s5": {"XCOM": 0.1145, "MCNPX": 0.1139}, "s6": {"XCOM": 0.1202, "MCNPX": 0.1195}, "s7": {"XCOM": 0.1258, "MCNPX": 0.1250}, "s8": {"XCOM": 0.1314, "MCNPX": 0.1305}},
    0.662: {"s1": {"XCOM": 0.0810, "MCNPX": 0.0810}, "s2": {"XCOM": 0.0862, "MCNPX": 0.0861}, "s3": {"XCOM": 0.0913, "MCNPX": 0.0911}, "s4": {"XCOM": 0.0963, "MCNPX": 0.0961}, "s5": {"XCOM": 0.1071, "MCNPX": 0.1065}, "s6": {"XCOM": 0.1121, "MCNPX": 0.1114}, "s7": {"XCOM": 0.1170, "MCNPX": 0.1163}, "s8": {"XCOM": 0.1219, "MCNPX": 0.1211}},
    0.800: {"s1": {"XCOM": 0.0743, "MCNPX": 0.0743}, "s2": {"XCOM": 0.0782, "MCNPX": 0.0781}, "s3": {"XCOM": 0.0821, "MCNPX": 0.0819}, "s4": {"XCOM": 0.0859, "MCNPX": 0.0856}, "s5": {"XCOM": 0.0943, "MCNPX": 0.0937}, "s6": {"XCOM": 0.0980, "MCNPX": 0.0974}, "s7": {"XCOM": 0.1017, "MCNPX": 0.1010}, "s8": {"XCOM": 0.1054, "MCNPX": 0.1046}},
    1.000: {"s1": {"XCOM": 0.0667, "MCNPX": 0.0667}, "s2": {"XCOM": 0.0695, "MCNPX": 0.0694}, "s3": {"XCOM": 0.0723, "MCNPX": 0.0721}, "s4": {"XCOM": 0.0750, "MCNPX": 0.0748}, "s5": {"XCOM": 0.0810, "MCNPX": 0.0805}, "s6": {"XCOM": 0.0837, "MCNPX": 0.0831}, "s7": {"XCOM": 0.0863, "MCNPX": 0.0857}, "s8": {"XCOM": 0.0889, "MCNPX": 0.0882}},
    1.173: {"s1": {"XCOM": 0.0617, "MCNPX": 0.0617}, "s2": {"XCOM": 0.0639, "MCNPX": 0.0638}, "s3": {"XCOM": 0.0661, "MCNPX": 0.0660}, "s4": {"XCOM": 0.0683, "MCNPX": 0.0681}, "s5": {"XCOM": 0.0731, "MCNPX": 0.0726}, "s6": {"XCOM": 0.0752, "MCNPX": 0.0747}, "s7": {"XCOM": 0.0772, "MCNPX": 0.0767}, "s8": {"XCOM": 0.0792, "MCNPX": 0.0786}},
    1.250: {"s1": {"XCOM": 0.0598, "MCNPX": 0.0598}, "s2": {"XCOM": 0.0618, "MCNPX": 0.0617}, "s3": {"XCOM": 0.0638, "MCNPX": 0.0636}, "s4": {"XCOM": 0.0658, "MCNPX": 0.0656}, "s5": {"XCOM": 0.0702, "MCNPX": 0.0698}, "s6": {"XCOM": 0.0721, "MCNPX": 0.0716}, "s7": {"XCOM": 0.0739, "MCNPX": 0.0734}, "s8": {"XCOM": 0.0758, "MCNPX": 0.0752}},
    1.332: {"s1": {"XCOM": 0.0579, "MCNPX": 0.0579}, "s2": {"XCOM": 0.0598, "MCNPX": 0.0597}, "s3": {"XCOM": 0.0616, "MCNPX": 0.0615}, "s4": {"XCOM": 0.0634, "MCNPX": 0.0632}, "s5": {"XCOM": 0.0674, "MCNPX": 0.0670}, "s6": {"XCOM": 0.0691, "MCNPX": 0.0687}, "s7": {"XCOM": 0.0708, "MCNPX": 0.0703}, "s8": {"XCOM": 0.0725, "MCNPX": 0.0719}},
    1.500: {"s1": {"XCOM": 0.0545, "MCNPX": 0.0545}, "s2": {"XCOM": 0.0560, "MCNPX": 0.0559}, "s3": {"XCOM": 0.0575, "MCNPX": 0.0574}, "s4": {"XCOM": 0.0590, "MCNPX": 0.0588}, "s5": {"XCOM": 0.0624, "MCNPX": 0.0620}, "s6": {"XCOM": 0.0638, "MCNPX": 0.0634}, "s7": {"XCOM": 0.0652, "MCNPX": 0.0647}, "s8": {"XCOM": 0.0666, "MCNPX": 0.0661}},
    2.000: {"s1": {"XCOM": 0.0469, "MCNPX": 0.0469}, "s2": {"XCOM": 0.0478, "MCNPX": 0.0477}, "s3": {"XCOM": 0.0487, "MCNPX": 0.0485}, "s4": {"XCOM": 0.0495, "MCNPX": 0.0494}, "s5": {"XCOM": 0.0516, "MCNPX": 0.0513}, "s6": {"XCOM": 0.0524, "MCNPX": 0.0520}, "s7": {"XCOM": 0.0532, "MCNPX": 0.0527}, "s8": {"XCOM": 0.0540, "MCNPX": 0.0535}},
    15.000: {"s1": {"XCOM": 0.0210, "MCNPX": 0.0211}, "s2": {"XCOM": 0.0223, "MCNPX": 0.0224}, "s3": {"XCOM": 0.0236, "MCNPX": 0.0237}, "s4": {"XCOM": 0.0249, "MCNPX": 0.0250}, "s5": {"XCOM": 0.0275, "MCNPX": 0.0276}, "s6": {"XCOM": 0.0287, "MCNPX": 0.0288}, "s7": {"XCOM": 0.0298, "MCNPX": 0.0300}, "s8": {"XCOM": 0.0310, "MCNPX": 0.0311}},
}

data = defaultdict(dict)
thickness_by_sample_energy = {}

if not os.path.isfile(CSV_FILE):
    print(f"Khong tim thay file {CSV_FILE}!")
    exit(1)

with open(CSV_FILE, 'r', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        mau = row['Mau'].upper()
        e   = float(row['E_keV'])
        v_idx = int(row.get('Bo_be_day') or 1)
        key = (e, v_idx)
        thickness_by_sample_energy[(mau, key)] = float(row['Be_day_cm'])
        data[mau][key] = row

row_keys = sorted({key for (_, key) in thickness_by_sample_energy.keys()},
                   key=lambda k: (k[0], k[1]))
energies = row_keys

def get_sample_density(sample_name):
    for e, row in data.get(sample_name, {}).items():
        raw = row.get('Density_g_cm3', '')
        try: return float(raw)
        except: continue
    return None

SAMPLE_DENSITY = {s: get_sample_density(s) for s in SAMPLES}

timing_summary = None
if os.path.isfile(TIMING_FILE):
    with open(TIMING_FILE, encoding='utf-8') as f:
        timing_summary = json.load(f)

def thickness_display(key):
    vals = {thickness_by_sample_energy[(s, key)]
            for s in SAMPLES if (s, key) in thickness_by_sample_energy}
    if len(vals) == 0: return ''
    if len(vals) == 1: return next(iter(vals))
    return 'xem sheet Do_day_mau'

def energy_label(key):
    e, v_idx = key
    e_disp = int(e) if e == int(e) else e
    n_variants = sum(1 for (ee, _vv) in row_keys if ee == e)
    if n_variants > 1:
        return f"{e_disp} (v{v_idx})"
    return e_disp

def thin_border():
    t = Side(style='thin')
    return Border(left=t, right=t, top=t, bottom=t)

def set_hdr(cell, value, bg='4472C4', fg='FFFFFF'):
    cell.value = value
    cell.font  = Font(name='Arial', bold=True, color=fg, size=10)
    cell.fill  = PatternFill('solid', start_color=bg, fgColor=bg)
    cell.border = thin_border()
    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

def set_val(cell, value, fmt=None):
    cell.value  = value
    cell.font   = Font(name='Arial', size=10)
    cell.border = thin_border()
    cell.alignment = Alignment(horizontal='center', vertical='center')
    if fmt:
        cell.number_format = fmt

def alt_row(ws, row_idx, n_cols):
    if row_idx % 2 == 0:
        for c in range(1, n_cols+1):
            ws.cell(row_idx, c).fill = PatternFill('solid', start_color='EBF3FB', fgColor='EBF3FB')

COL_COLORS = ['70AD47','5B9BD5','ED7D31','A9D18E','FFC000','FF0000','7030A0','2F5597']

wb = Workbook()

# =====================================================================
# SHEET 1: MAC (cm2/g)
# =====================================================================
ws_mac = wb.active
ws_mac.title = 'MAC'
ws_mac.merge_cells('A1:J1')
ws_mac['A1'] = 'He so suy giam khoi luong MAC (cm2/g) - OpenMC Fast Pipeline'
ws_mac['A1'].font = Font(name='Arial', bold=True, size=13)
ws_mac['A1'].alignment = Alignment(horizontal='center', vertical='center')
ws_mac.row_dimensions[1].height = 25

hdrs_mac = ['Energy (keV)', 'Be day (cm)'] + [f'{s}\n({SAMPLE_DENSITY.get(s, 0):.3f})' for s in SAMPLES]
for col, (hdr, bg) in enumerate(zip(hdrs_mac, ['4472C4','4472C4']+COL_COLORS), 1):
    set_hdr(ws_mac.cell(2, col), hdr, bg=bg)
ws_mac.row_dimensions[2].height = 30

for ri, key in enumerate(energies, 3):
    set_val(ws_mac.cell(ri, 1), energy_label(key))
    set_val(ws_mac.cell(ri, 2), thickness_display(key))
    for ci, s in enumerate(SAMPLES, 3):
        val = ''
        if key in data[s]:
            try: val = float(data[s][key].get('MAC (cm2/g)', ''))
            except: val = ''
        set_val(ws_mac.cell(ri, ci), val, fmt='0.00000')
    alt_row(ws_mac, ri, 10)

for i in range(1, 11):
    ws_mac.column_dimensions[get_column_letter(i)].width = 13
ws_mac.freeze_panes = 'A3'

# =====================================================================
# SHEET 2: T_Transmittance
# =====================================================================
ws_t = wb.create_sheet('T_Transmittance')
ws_t.merge_cells('A1:J1')
ws_t['A1'] = 'Do truyen qua T = I/I0 - OpenMC (To mau do neu < 2% hoac > 90%)'
ws_t['A1'].font = Font(name='Arial', bold=True, size=13)
ws_t['A1'].alignment = Alignment(horizontal='center', vertical='center')
ws_t.row_dimensions[1].height = 25

hdrs_t = ['Energy (keV)', 'Be day (cm)'] + [f'{s}\nT' for s in SAMPLES]
for col, (hdr, bg) in enumerate(zip(hdrs_t, ['4472C4','4472C4']+COL_COLORS), 1):
    set_hdr(ws_t.cell(2, col), hdr, bg=bg)
ws_t.row_dimensions[2].height = 30

warn_fill = PatternFill('solid', start_color='FFC7CE', fgColor='FFC7CE')
for ri, key in enumerate(energies, 3):
    set_val(ws_t.cell(ri, 1), energy_label(key))
    set_val(ws_t.cell(ri, 2), thickness_display(key))
    alt_row(ws_t, ri, 10)
    for ci, s in enumerate(SAMPLES, 3):
        val = ''
        warn = ''
        if key in data[s]:
            try: val = float(data[s][key].get('T (I/I0)', ''))
            except: val = ''
            warn = data[s][key].get('Canh_bao', '')
        set_val(ws_t.cell(ri, ci), val, fmt='0.0000')
        if warn:
            ws_t.cell(ri, ci).fill = warn_fill

for i in range(1, 11):
    ws_t.column_dimensions[get_column_letter(i)].width = 13
ws_t.freeze_panes = 'A3'

# =====================================================================
# SHEET 3: R_Compton
# =====================================================================
ws_r = wb.create_sheet('R_Compton')
ws_r.merge_cells('A1:J1')
ws_r['A1'] = 'Ty le R = mu_Compton / (mu_Total - mu_Rayleigh) trong vat lieu mau'
ws_r['A1'].font = Font(name='Arial', bold=True, size=13)
ws_r['A1'].alignment = Alignment(horizontal='center', vertical='center')
ws_r.row_dimensions[1].height = 25

hdrs_r = ['Energy (keV)', 'Be day (cm)'] + [f'{s}\nR' for s in SAMPLES]
for col, (hdr, bg) in enumerate(zip(hdrs_r, ['4472C4','4472C4']+COL_COLORS), 1):
    set_hdr(ws_r.cell(2, col), hdr, bg=bg)
ws_r.row_dimensions[2].height = 30

for ri, key in enumerate(energies, 3):
    set_val(ws_r.cell(ri, 1), energy_label(key))
    set_val(ws_r.cell(ri, 2), thickness_display(key))
    for ci, s in enumerate(SAMPLES, 3):
        val = ''
        if key in data[s]:
            try: val = float(data[s][key].get('R_Compton_mau', ''))
            except: val = ''
        set_val(ws_r.cell(ri, ci), val, fmt='0.000000')
    alt_row(ws_r, ri, 10)

for i in range(1, 11):
    ws_r.column_dimensions[get_column_letter(i)].width = 13
ws_r.freeze_panes = 'A3'

# =====================================================================
# SHEET 4: Do_day_mau
# =====================================================================
ws_th = wb.create_sheet('Do_day_mau')
ws_th.merge_cells('A1:J1')
ws_th['A1'] = 'Do day thuc te da dung trong tung luot chay (cm)'
ws_th['A1'].font = Font(name='Arial', bold=True, size=13)
ws_th['A1'].alignment = Alignment(horizontal='center', vertical='center')
ws_th.row_dimensions[1].height = 25

hdrs_th = ['Energy (keV)', ''] + [f'{s}\nBe day (cm)' for s in SAMPLES]
for col, (hdr, bg) in enumerate(zip(hdrs_th, ['4472C4','4472C4']+COL_COLORS), 1):
    set_hdr(ws_th.cell(2, col), hdr, bg=bg)
ws_th.row_dimensions[2].height = 30

for ri, key in enumerate(energies, 3):
    set_val(ws_th.cell(ri, 1), energy_label(key))
    set_val(ws_th.cell(ri, 2), '')
    for ci, s in enumerate(SAMPLES, 3):
        val = thickness_by_sample_energy.get((s, key), '')
        set_val(ws_th.cell(ri, ci), val, fmt='0.00000')
    alt_row(ws_th, ri, 10)

for i in range(1, 11):
    ws_th.column_dimensions[get_column_letter(i)].width = 13
ws_th.freeze_panes = 'A3'

# =====================================================================
# SHEET 5: QA_Transmittance
# =====================================================================
ws_qa = wb.create_sheet('QA_Transmittance')
ws_qa.merge_cells('A1:F1')
ws_qa['A1'] = 'QA: Kiem tra Transmittance T=I/I0 va sai so tuong doi'
ws_qa['A1'].font = Font(name='Arial', bold=True, size=13)
ws_qa['A1'].alignment = Alignment(horizontal='center', vertical='center')
ws_qa.row_dimensions[1].height = 25

hdrs_qa = ['Mau', 'Energy (keV)', 'Be day (cm)', 'T (I/I0)', 'RelErr_I (%)', 'Canh bao']
for col, hdr in enumerate(hdrs_qa, 1):
    set_hdr(ws_qa.cell(2, col), hdr)
ws_qa.row_dimensions[2].height = 28

ri = 3
for s in SAMPLES:
    for key in energies:
        if key not in data[s]:
            continue
        row = data[s][key]
        set_val(ws_qa.cell(ri, 1), s)
        set_val(ws_qa.cell(ri, 2), energy_label(key))
        set_val(ws_qa.cell(ri, 3), thickness_by_sample_energy.get((s, key), ''), fmt='0.00000')
        try: t_val = float(row.get('T (I/I0)', ''))
        except: t_val = ''
        set_val(ws_qa.cell(ri, 4), t_val, fmt='0.0000')
        try: rel_val = float(row.get('RelErr_I (%)', ''))
        except: rel_val = ''
        set_val(ws_qa.cell(ri, 5), rel_val, fmt='0.00')
        warn = row.get('Canh_bao', '')
        set_val(ws_qa.cell(ri, 6), warn)
        if warn:
            for c in range(1, 7):
                ws_qa.cell(ri, c).fill = warn_fill
        else:
            alt_row(ws_qa, ri, 6)
        ri += 1

for i, w in enumerate([8, 14, 14, 12, 14, 22], 1):
    ws_qa.column_dimensions[get_column_letter(i)].width = w
ws_qa.freeze_panes = 'A3'

# =====================================================================
# SHEET 6: Thoi_gian_chay
# =====================================================================
ws_time = wb.create_sheet('Thoi_gian_chay')
ws_time.merge_cells('A1:F1')
ws_time['A1'] = 'Thong ke thoi gian chay OpenMC'
ws_time['A1'].font = Font(name='Arial', bold=True, size=13)
ws_time['A1'].alignment = Alignment(horizontal='center', vertical='center')
ws_time.row_dimensions[1].height = 25

row_ptr = 2
if timing_summary:
    for label, val in [
        ('Gio bat dau toan bo:', timing_summary.get('gio_bat_dau_toan_bo', '')),
        ('Gio ket thuc toan bo:', timing_summary.get('gio_ket_thuc_toan_bo', '')),
        ('Tong thoi gian (giay):', timing_summary.get('tong_thoi_gian_giay', '')),
        ('Tong thoi gian (phut):', timing_summary.get('tong_thoi_gian_phut', '')),
    ]:
        ws_time.cell(row_ptr, 1).value = label
        ws_time.cell(row_ptr, 1).font  = Font(name='Arial', bold=True, size=10)
        ws_time.cell(row_ptr, 2).value = val
        ws_time.cell(row_ptr, 2).font  = Font(name='Arial', size=10)
        row_ptr += 1
    row_ptr += 1

hdr_row = row_ptr
hdrs_time = ['Mau', 'Energy (keV)', 'Be day (cm)', 'Gio bat dau', 'Gio ket thuc', 'Thoi gian (s)']
for col, hdr in enumerate(hdrs_time, 1):
    set_hdr(ws_time.cell(hdr_row, col), hdr)
ws_time.row_dimensions[hdr_row].height = 28

ri = hdr_row + 1
for s in SAMPLES:
    for key in energies:
        if key not in data[s]:
            continue
        row = data[s][key]
        set_val(ws_time.cell(ri, 1), s)
        set_val(ws_time.cell(ri, 2), energy_label(key))
        set_val(ws_time.cell(ri, 3), thickness_by_sample_energy.get((s, key), ''), fmt='0.00000')
        set_val(ws_time.cell(ri, 4), row.get('Gio_bat_dau', ''))
        set_val(ws_time.cell(ri, 5), row.get('Gio_ket_thuc', ''))
        try: dur_val = float(row.get('Thoi_gian_chay_s', ''))
        except: dur_val = ''
        set_val(ws_time.cell(ri, 6), dur_val, fmt='0.0')
        alt_row(ws_time, ri, 6)
        ri += 1

for i, w in enumerate([8, 14, 14, 20, 20, 16], 1):
    ws_time.column_dimensions[get_column_letter(i)].width = w
ws_time.freeze_panes = f'A{hdr_row + 1}'

# =====================================================================
# SHEET 7: Benchmark_Table2 (Doi chieu Paper 1 Table 2)
# =====================================================================
ws_bench = wb.create_sheet('Benchmark_Table2')
ws_bench.merge_cells('A1:G1')
ws_bench['A1'] = 'Doi chieu ket qua OpenMC voi Table 2 Paper 1 (XCOM & MCNPX)'
ws_bench['A1'].font = Font(name='Arial', bold=True, size=13)
ws_bench['A1'].alignment = Alignment(horizontal='center', vertical='center')
ws_bench.row_dimensions[1].height = 25

hdrs_bench = ['Mau', 'Energy (MeV)', 'Be day (cm)', 'OpenMC MAC', 'Paper1 XCOM', 'Paper1 MCNPX', 'RD% vs XCOM']
for col, hdr in enumerate(hdrs_bench, 1):
    set_hdr(ws_bench.cell(2, col), hdr)
ws_bench.row_dimensions[2].height = 28

ri = 3
for key in energies:
    e_kev, v_idx = key
    e_mev = round(e_kev / 1000.0, 4)
    ref_e = PAPER1_TABLE2.get(e_mev, {})
    for s in SAMPLES:
        if key not in data[s]:
            continue
        s_lower = s.lower()
        row = data[s][key]
        try: mac_val = float(row.get('MAC (cm2/g)', ''))
        except: mac_val = None

        ref_xcom = ref_e.get(s_lower, {}).get("XCOM", None)
        ref_mcnpx = ref_e.get(s_lower, {}).get("MCNPX", None)

        rd_xcom = ""
        if mac_val is not None and ref_xcom is not None:
            rd_xcom = (mac_val - ref_xcom) / ref_xcom * 100.0

        set_val(ws_bench.cell(ri, 1), s)
        set_val(ws_bench.cell(ri, 2), e_mev, fmt='0.000')
        set_val(ws_bench.cell(ri, 3), thickness_by_sample_energy.get((s, key), ''), fmt='0.00000')
        set_val(ws_bench.cell(ri, 4), mac_val if mac_val is not None else '', fmt='0.00000')
        set_val(ws_bench.cell(ri, 5), ref_xcom if ref_xcom is not None else '', fmt='0.00000')
        set_val(ws_bench.cell(ri, 6), ref_mcnpx if ref_mcnpx is not None else '', fmt='0.00000')
        set_val(ws_bench.cell(ri, 7), rd_xcom if rd_xcom != "" else '', fmt='+0.00%')
        alt_row(ws_bench, ri, 7)
        ri += 1

for i, w in enumerate([8, 14, 14, 15, 15, 15, 15], 1):
    ws_bench.column_dimensions[get_column_letter(i)].width = w
ws_bench.freeze_panes = 'A3'

wb.save(OUTPUT_FILE)
print(f"Da xuat thanh cong: {OUTPUT_FILE} voi 7 Sheet chi tiet!")
