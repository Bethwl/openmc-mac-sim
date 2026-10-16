"""
run_local_test_openmc.py - Chay test nhanh OpenMC cho 8 mau S1 -> S8 va Blank
Kiem tra truc tiep do khop voi Table 2 Paper 1 (XCOM / MCNPX) va EpiXS.

Cach chay:
    python run_local_test_openmc.py 60 0.5 100000 4
    (Tham so: [energy_kev=60] [thickness_cm=0.5] [particles=100000] [threads=4])
"""
import os
import sys
import time
import math
import subprocess
from pathlib import Path
import pandas as pd
import numpy as np
import openmc

from openmc_model import export_openmc_model, COMPOSITION, DENSITY
from calculate_paper1_quantities_openmc import PAPER1_TABLE2

OPENMC_CROSS_SECTIONS_PATH = "/home/ht/nuclear_data/endfb-viii.0-hdf5/endfb-viii.0-hdf5/cross_sections.xml"
OPENMC_BIN_PATH = "/home/ht/miniconda3/envs/openmc/bin"


def to_wsl_path(win_path: Path) -> str:
    p_str = str(win_path.resolve()).replace("\\", "/")
    if len(p_str) > 1 and p_str[1] == ":":
        drive = p_str[0].lower()
        return f"/mnt/{drive}{p_str[2:]}"
    return p_str


def run_job(job_dir: Path):
    if sys.platform.startswith("linux"):
        env = os.environ.copy()
        env["PATH"] = f"{OPENMC_BIN_PATH}:{env.get('PATH', '')}"
        env["OPENMC_CROSS_SECTIONS"] = OPENMC_CROSS_SECTIONS_PATH
        subprocess.run([f"{OPENMC_BIN_PATH}/openmc"], cwd=str(job_dir), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    else:
        wsl_dir = to_wsl_path(job_dir)
        cmd_str = f"export PATH={OPENMC_BIN_PATH}:$PATH && export OPENMC_CROSS_SECTIONS={OPENMC_CROSS_SECTIONS_PATH} && cd '{wsl_dir}' && openmc"
        subprocess.run(["wsl", "-d", "Ubuntu-24.04", "bash", "-c", cmd_str], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def main():
    energy_kev = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    thickness_cm = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
    particles = int(sys.argv[3]) if len(sys.argv) > 3 else 100000
    batches = 10

    test_base = Path("quick_test")
    test_base.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("🚀 CHAY TEST NHANH OPENMC CHO 8 MAU S1 -> S8 + BLANK")
    print(f"Nang luong:    {energy_kev} keV ({energy_kev/1000.0:.3f} MeV)")
    print(f"Be day:        {thickness_cm} cm")
    print(f"So hat:        {particles} particles ({batches} batches)")
    print("=" * 80)

    # 1. Sinh va chay Blank
    blank_dir = test_base / f"blank_{int(energy_kev)}keV"
    print(f"\n[1/9] Dang tao va chay Blank...")
    export_openmc_model(str(blank_dir), "blank", energy_kev, thickness_cm, particles, batches)
    t0 = time.time()
    run_job(blank_dir)
    print(f"  -> Blank xong trong {time.time() - t0:.1f}s")

    sp_b = openmc.StatePoint(str(blank_dir / f"statepoint.{batches}.h5"))
    t_peak_b = sp_b.get_tally(name="peak_flux")
    I0 = float(t_peak_b.mean.flatten()[0])
    I0_err = float(t_peak_b.std_dev.flatten()[0]) / I0 if I0 > 0 else 0.0
    print(f"  -> I0 (Peak Flux) = {I0:.6E} +/- {I0_err*100:.2f}%")

    # 2. Sinh va chay tung mau S1 -> S8
    results = []
    e_mev = round(energy_kev / 1000.0, 4)
    ref_table = PAPER1_TABLE2.get(e_mev, {})

    for idx, s_key in enumerate(["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"]):
        s_upper = s_key.upper()
        s_dir = test_base / f"{s_key}_{int(energy_kev)}keV_th{thickness_cm}cm"
        print(f"[{idx+2}/9] Dang chay {s_upper}...")

        export_openmc_model(str(s_dir), s_key, energy_kev, thickness_cm, particles, batches)
        t_start = time.time()
        run_job(s_dir)
        elapsed = time.time() - t_start

        sp_s = openmc.StatePoint(str(s_dir / f"statepoint.{batches}.h5"))
        t_peak_s = sp_s.get_tally(name="peak_flux")
        I = float(t_peak_s.mean.flatten()[0])
        I_err = float(t_peak_s.std_dev.flatten()[0]) / I if I > 0 else 0.0

        rho = DENSITY[s_key]
        if I0 > 0 and I > 0:
            lac = math.log(I0 / I) / thickness_cm
            mac = lac / rho
        else:
            lac = np.nan
            mac = np.nan

        ref_xcom = ref_table.get(s_key, {}).get("XCOM", np.nan)
        ref_mcnpx = ref_table.get(s_key, {}).get("MCNPX", np.nan)
        dev_xcom = (mac - ref_xcom) / ref_xcom * 100.0 if pd.notna(mac) and pd.notna(ref_xcom) else np.nan

        print(f"  -> {s_upper}: I={I:.4E}, MAC={mac:.4f} cm2/g | Ref XCOM={ref_xcom:.4f} (Dev: {dev_xcom:+.2f}%) [{elapsed:.1f}s]")

        results.append({
            "Sample": s_upper,
            "Density": rho,
            "Thickness_cm": thickness_cm,
            "I0_peak": I0,
            "I_peak": I,
            "I_err_%": I_err * 100.0,
            "LAC_OpenMC": lac,
            "MAC_OpenMC": mac,
            "XCOM_Paper1": ref_xcom,
            "MCNPX_Paper1": ref_mcnpx,
            "Dev_vs_XCOM_%": dev_xcom,
        })

    df_res = pd.DataFrame(results)
    out_excel = test_base / f"Quick_Test_Results_{int(energy_kev)}keV.xlsx"
    df_res.to_excel(out_excel, index=False)

    print("\n" + "=" * 80)
    print("📊 BANG KET QUA TEST DOI CHIEU VOI PAPER 1 TABLE 2:")
    print("=" * 80)
    print(df_res[["Sample", "Density", "MAC_OpenMC", "XCOM_Paper1", "Dev_vs_XCOM_%"]].to_string(index=False))
    print(f"\nDa luu ket qua vao: {out_excel.resolve()}")
    print("=" * 80)


if __name__ == "__main__":
    main()
