"""
run_all.py -- Chay tu dong toan bo 8 mau (S1..S8) x 23 muc nang luong cho Paper 10
Goi lan luot: Run_nosample.py -> Run_sample.py (x8 mau) -> ghi openmc_results.csv
1 lenh duy nhat: python run_all.py --config-excel Config_Simulation.xlsx

Ho tro cac tuy chon manh me:
  --resume   : Bo qua cac dong da co trong CSV
  --dry-run  : In danh sach cac job can chay ma khong thuc hien
  --emin/--emax : Gioi han dai nang luong can chay (keV)
  --particles/--batches : Chinh so hat va so batch chay OpenMC
"""
import subprocess
import sys
import os
import csv
import json
import argparse
import time
import math
import datetime
import glob
import sim_config

SAMPLES = sim_config.SAMPLES   # S1..S8

CSV_FILE      = 'openmc_results.csv'
NOSAMPLE_DIR  = 'run_nosample'
TIMING_FILE   = 'run_all_timing.json'

TIME_FMT = '%H:%M:%S %d/%m/%Y'

parser = argparse.ArgumentParser()
parser.add_argument('--config-excel', type=str, default='Config_Simulation.xlsx',
                    help='File Excel chua sheet Energy_Thickness va Sample_Composition.')
parser.add_argument('--particles', type=int, default=1_000_000,
                    help='So particles/batch (mac dinh 1,000,000 cho tong 10^8 hat).')
parser.add_argument('--batches',   type=int, default=100,
                    help='So batches (mac dinh 100 cho tong 10^8 hat).')
parser.add_argument('--resume',    action='store_true', help='Bo qua cac diem da co trong CSV.')
parser.add_argument('--dry-run',   action='store_true', help='In danh sach job ma khong chay.')
parser.add_argument('--emin', type=float, default=None,
                    help='Chi chay cac muc nang luong >= EMIN (keV).')
parser.add_argument('--emax', type=float, default=None,
                    help='Chi chay cac muc nang luong <= EMAX (keV).')
args = parser.parse_args()

RESUME  = args.resume
DRY_RUN = args.dry_run

CONFIG_EXCEL = os.path.abspath(args.config_excel)
if not os.path.isfile(CONFIG_EXCEL):
    print(f"  [LOI] Khong tim thay file config Excel: {CONFIG_EXCEL}")
    sys.exit(1)
os.environ['CONFIG_EXCEL'] = CONFIG_EXCEL

N_PARTICLES = args.particles
N_BATCHES   = args.batches

# Nap sheet Energy_Thickness
THICKNESS_EXCEL = sim_config.load_energy_thickness(CONFIG_EXCEL)
if not THICKNESS_EXCEL:
    print(f"  [LOI] Sheet Energy_Thickness trong {CONFIG_EXCEL} rong hoac khong ton tai.")
    sys.exit(1)

ENERGY_LIST = sorted(THICKNESS_EXCEL.keys())

if args.emin is not None:
    ENERGY_LIST = [e for e in ENERGY_LIST if e >= args.emin]
if args.emax is not None:
    ENERGY_LIST = [e for e in ENERGY_LIST if e <= args.emax]
if args.emin is not None or args.emax is not None:
    print(f"  [OK] --emin/--emax: gioi han lai con {len(ENERGY_LIST)} muc nang luong: {ENERGY_LIST}")

# Doc cap da chay neu --resume
done_keys = set()
if RESUME and os.path.isfile(CSV_FILE):
    with open(CSV_FILE, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            try:
                variant_idx = int(row.get('Bo_be_day') or 1)
                done_keys.add((row['Mau'], float(row['E_keV']), variant_idx, float(row['Be_day_cm'])))
            except Exception:
                pass
    print(f"[RESUME] Bo qua {len(done_keys)} dong da co trong CSV.")


def run_cmd(cmd, label, output_dir=None, poll_interval=0.2):
    t_launch_dt = datetime.datetime.now()
    print(f"\n  >> {label}")
    print(f"     Bat dau: {t_launch_dt.strftime(TIME_FMT)}")

    def _h5_mtimes():
        m = {}
        if output_dir and os.path.isdir(output_dir):
            for p in glob.glob(os.path.join(output_dir, '*.h5')):
                try:
                    m[p] = os.path.getmtime(p)
                except OSError:
                    pass
        return m

    before_mtimes = _h5_mtimes()

    def _first_touched_dt(before):
        for p, m_now in _h5_mtimes().items():
            m_before = before.get(p)
            if m_before is None or m_now > m_before:
                return datetime.datetime.now()
        return None

    proc = subprocess.Popen(cmd, text=True)
    first_h5_dt = None
    if output_dir:
        while proc.poll() is None:
            first_h5_dt = _first_touched_dt(before_mtimes)
            if first_h5_dt is not None:
                break
            time.sleep(poll_interval)
    proc.wait()
    t_end_dt = datetime.datetime.now()

    if first_h5_dt is None and output_dir:
        after_mtimes = _h5_mtimes()
        touched_mtimes = [m for p, m in after_mtimes.items()
                           if before_mtimes.get(p) is None or m > before_mtimes[p]]
        if touched_mtimes:
            first_h5_dt = datetime.datetime.fromtimestamp(min(touched_mtimes))

    t_start_dt = first_h5_dt if first_h5_dt is not None else t_launch_dt
    elapsed = (t_end_dt - t_start_dt).total_seconds()

    if proc.returncode != 0:
        print(f"  [LOI] {label} that bai")
        return False, t_start_dt, t_end_dt, elapsed
    print(f"     Ket thuc: {t_end_dt.strftime(TIME_FMT)}  (Hoan thanh trong {elapsed:.1f}s)")
    return True, t_start_dt, t_end_dt, elapsed


def calc_and_write(energy_keV, thickness_cm, sample_name, n_total, variant_idx,
                   t_start_dt=None, t_end_dt=None, elapsed_s=None):
    nosample_json = os.path.join(NOSAMPLE_DIR, 'run_info.json')
    sample_dir    = f'run_sample_{sample_name.lower()}'
    sample_json   = os.path.join(sample_dir, 'run_info.json')

    with open(nosample_json, encoding='utf-8') as f: info0 = json.load(f)
    with open(sample_json,   encoding='utf-8') as f: info1 = json.load(f)

    I0 = info0['I0']; I0_std = info0['I0_stddev']
    I  = info1['I'];  I_std  = info1['I_stddev']

    R_sample = info1.get('R_sample_no_coherent', None)
    R_sample_std = info1.get('R_sample_no_coherent_stddev', None)
    has_R = (R_sample is not None) and (R_sample > 0)
    density = info1['sample_density_gcm3']
    thick   = info1['sample_thickness_cm']

    I0_hat = round(I0 * n_total)
    I_hat  = round(I  * n_total)

    T = I / I0 if I0 > 0 else 0.0
    rel_err_I = (I_std / I) if I > 0 else float('inf')
    canh_bao = ""
    if T < 0.02 or T > 0.9:
        canh_bao = "NGOAI_VUNG_AN_TOAN"

    mu = MAC = RPE = None
    has_I = (I is not None) and (I > 0) and (I0 is not None) and (I0 > 0)
    if has_I:
        mu  = (1/thick) * math.log(I0/I)
        MAC = mu / density
        RPE = (1 - I/I0) * 100

    gio_bat_dau  = t_start_dt.strftime(TIME_FMT) if t_start_dt else ""
    gio_ket_thuc = t_end_dt.strftime(TIME_FMT)   if t_end_dt   else ""
    thoi_gian_s  = f"{elapsed_s:.1f}" if elapsed_s is not None else ""

    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, 'a', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow([
                'Mau', 'E_keV', 'Bo_be_day', 'Be_day_cm', 'Density_g_cm3',
                'I0 (hat)', 'I (hat)',
                'R_Compton_mau', 'R_Compton_mau_stddev',
                'mu (cm-1)', 'MAC (cm2/g)', 'RPE (%)',
                'T (I/I0)', 'RelErr_I (%)', 'Canh_bao',
                'Gio_bat_dau', 'Gio_ket_thuc', 'Thoi_gian_chay_s',
            ])
        w.writerow([
            sample_name, energy_keV, variant_idx, thickness_cm, f"{density:.5f}",
            I0_hat, I_hat,
            f"{R_sample:.6f}" if has_R else "",
            f"{R_sample_std:.6f}" if (has_R and R_sample_std is not None) else "",
            f"{mu:.4f}"  if mu  is not None else "",
            f"{MAC:.4f}" if MAC is not None else "",
            f"{RPE:.4f}" if RPE is not None else "",
            f"{T:.4f}", f"{rel_err_I*100:.2f}", canh_bao,
            gio_bat_dau, gio_ket_thuc, thoi_gian_s,
        ])
    mac = f"{MAC:.5f}" if MAC is not None else "N/A(I=0)"
    r_disp = f"{R_sample:.6f}" if has_R else "N/A"
    print(f"     -> {sample_name} | MAC={mac} cm2/g | R={r_disp} | T={T:.4f} | I0={I0_hat} I={I_hat} | Thoi gian: {thoi_gian_s}s")


# =====================================================================
python_exe = sys.executable
n_total    = N_PARTICLES * N_BATCHES
total_thickness_rows = sum(len(THICKNESS_EXCEL[e]) for e in ENERGY_LIST)
total_runs = total_thickness_rows * len(SAMPLES)

print("=" * 70)
print(f"  run_all.py -- {len(ENERGY_LIST)} muc nang luong ({total_thickness_rows} dong be day) "
      f"x {len(SAMPLES)} mau = {total_runs} luot chay")
print(f"  Particles/batch: {N_PARTICLES:,}  x  Batches: {N_BATCHES}  =  {n_total:,} hat/chay")
print(f"  Config: {CONFIG_EXCEL}")
if RESUME:  print(f"  Mode: RESUME")
if DRY_RUN: print(f"  Mode: DRY-RUN")
print("=" * 70)

success = 0; fail_list = []; skip = 0
t_start = time.time()
t_start_all_dt = datetime.datetime.now()

for idx, energy_keV in enumerate(ENERGY_LIST, 1):
    print(f"\n{'='*70}")
    print(f"  [{idx}/{len(ENERGY_LIST)}]  E = {energy_keV} keV")
    print(f"{'='*70}")

    thickness_variants = THICKNESS_EXCEL[energy_keV]
    n_variants = len(thickness_variants)

    if DRY_RUN:
        for v_idx, thickness_set in enumerate(thickness_variants, 1):
            for s in SAMPLES:
                print(f"  [DRY-RUN] bo be day {v_idx}/{n_variants}: {s}: day = {thickness_set[s]} cm")
        continue

    # Chay nosample 1 lan cho muc nang luong nay
    nosample_done = False
    nosample_json = os.path.join(NOSAMPLE_DIR, 'run_info.json')
    if RESUME and os.path.isfile(nosample_json):
        try:
            with open(nosample_json) as f:
                info = json.load(f)
            if info.get('energy_keV') == energy_keV:
                nosample_done = True
                print(f"  [SKIP nosample] Da co ket qua nosample cho E={energy_keV} keV")
        except Exception:
            pass

    if not nosample_done:
        ok, _ns_start, _ns_end, _ns_elapsed = run_cmd(
            [python_exe, 'Run_nosample.py',
             str(energy_keV), str(N_PARTICLES), str(N_BATCHES)],
            f"Run_nosample E={energy_keV} keV",
            output_dir=NOSAMPLE_DIR
        )
        if not ok:
            for thickness_set in thickness_variants:
                for s in SAMPLES:
                    fail_list.append((s, energy_keV, thickness_set[s], 'nosample'))
            continue

    # Chay sample cho tung bo be day va tung mau S1..S8
    for v_idx, thickness_set in enumerate(thickness_variants, 1):
        for sample_name in SAMPLES:
            thickness_cm = thickness_set[sample_name]

            key = (sample_name, float(energy_keV), v_idx, float(thickness_cm))
            if RESUME and key in done_keys:
                print(f"  [SKIP] {sample_name} E={energy_keV} keV bo be day {v_idx} day={thickness_cm}cm da co trong CSV")
                skip += 1
                continue

            ok, s_start_dt, s_end_dt, s_elapsed = run_cmd(
                [python_exe, 'Run_sample.py',
                 str(energy_keV), str(thickness_cm),
                 str(N_PARTICLES), str(N_BATCHES), sample_name],
                f"Run_sample {sample_name} E={energy_keV} keV (day={thickness_cm} cm)",
                output_dir=f'run_sample_{sample_name.lower()}'
            )
            if not ok:
                fail_list.append((sample_name, energy_keV, thickness_cm, 'sample'))
                continue

            try:
                calc_and_write(energy_keV, thickness_cm, sample_name, n_total, v_idx,
                               t_start_dt=s_start_dt, t_end_dt=s_end_dt, elapsed_s=s_elapsed)
                success += 1
            except Exception as e:
                print(f"  [LOI CSV] {e}")
                fail_list.append((sample_name, energy_keV, thickness_cm, 'csv'))

elapsed = time.time() - t_start
t_end_all_dt = datetime.datetime.now()

timing_summary = {
    "gio_bat_dau_toan_bo":  t_start_all_dt.strftime(TIME_FMT),
    "gio_ket_thuc_toan_bo": t_end_all_dt.strftime(TIME_FMT),
    "tong_thoi_gian_giay":  round(elapsed, 1),
    "tong_thoi_gian_phut":  round(elapsed / 60, 2),
}
with open(TIMING_FILE, 'w', encoding='utf-8') as f:
    json.dump(timing_summary, f, indent=2, ensure_ascii=False)

print(f"\n{'='*70}")
print(f"  HOAN THANH")
print(f"  Thanh cong : {success} / {total_runs - skip} luot chay")
print(f"  Bo qua     : {skip}")
print(f"  That bai   : {len(fail_list)}")
print(f"  Tong thoi gian : {elapsed:.1f} giay (~{elapsed/60:.1f} phut)")
print(f"  Ket qua CSV    : {CSV_FILE}")
print(f"  Timing JSON    : {TIMING_FILE}")
print(f"{'='*70}")
