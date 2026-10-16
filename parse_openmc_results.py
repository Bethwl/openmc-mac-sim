"""
parse_openmc_results.py - Doc ket qua tu cac file statepoint.*.h5 cua OpenMC
Trich xuat:
- Thong luong dinh (Uncollided peak flux) va sai so
- Tong thong luong (Total flux) va sai so
- Tinh LAC (mu) va MAC (mu/rho) theo dinh luat Beer-Lambert
- Xuat ra file Excel flux_results.xlsx voi cac Sheet:
  + Peak_Flux_Uncollided
  + Total_Flux
  + Summary_MAC
  + Raw_Flux_Merged

Cach chay:
    python parse_openmc_results.py thickness_table_all9.xlsx inputs/ flux_results.xlsx
"""
import os
import re
import sys
import math
from pathlib import Path
import pandas as pd
import numpy as np
import openmc

from openmc_model import COMPOSITION, DENSITY


def _fmt_thickness(th: float) -> str:
    s = f"{th:.4f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _parse_thickness_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, float) and pd.isna(value):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    s = str(value).strip()
    if not s:
        return []
    parts = [p for p in re.split(r"[,;\s]+", s) if p]
    return [float(p) for p in parts]


def read_job_statepoint(job_dir: Path) -> tuple[float, float, float, float]:
    """
    Doc file statepoint.*.h5 trong thu muc job.
    Tra ve: (peak_flux, peak_err, tot_flux, tot_err)
    """
    sp_files = list(job_dir.glob("statepoint.*.h5"))
    if not sp_files:
        return np.nan, np.nan, np.nan, np.nan

    # Lay file statepoint cuoi cung (so batch cao nhat)
    def _sp_batch(p: Path):
        m = re.search(r"statepoint\.(\d+)\.h5", p.name)
        return int(m.group(1)) if m else 0

    sp_file = max(sp_files, key=_sp_batch)

    try:
        sp = openmc.StatePoint(str(sp_file))
        t_peak = sp.get_tally(name="peak_flux")
        t_tot = sp.get_tally(name="total_flux")

        peak_m = float(t_peak.mean.flatten()[0])
        peak_s = float(t_peak.std_dev.flatten()[0])
        peak_err = (peak_s / peak_m) if peak_m > 0 else 0.0

        tot_m = float(t_tot.mean.flatten()[0])
        tot_s = float(t_tot.std_dev.flatten()[0])
        tot_err = (tot_s / tot_m) if tot_m > 0 else 0.0

        return peak_m, peak_err, tot_m, tot_err
    except Exception as ex:
        print(f"Loi khi doc {sp_file}: {ex}")
        return np.nan, np.nan, np.nan, np.nan


def main(excel_path: str = "thickness_table_all9.xlsx", jobs_dir: str = "inputs",
         output_excel: str = "flux_results.xlsx"):
    df_th = pd.read_excel(excel_path)
    jobs_path = Path(jobs_dir)

    print("=" * 70)
    print(f"📊 DANG DOC KET QUA TU THU MUC: {jobs_path}")
    print(f"Bang be day: {excel_path}")
    print(f"File xuat: {output_excel}")
    print("=" * 70)

    # 1. Quet thong luong Blank I0 cho tung muc nang luong
    blank_dict = {}  # {energy_kev: (peak_flux, peak_err, tot_flux, tot_err)}
    for b_dir in jobs_path.glob("blank_*keV"):
        m = re.search(r"blank_(\d+)keV", b_dir.name)
        if m:
            e_kev = int(m.group(1))
            res = read_job_statepoint(b_dir)
            blank_dict[e_kev] = res

    print(f"Da tim thay du lieu Blank cho {len(blank_dict)} muc nang luong.")

    # 2. Quet thong luong cua cac mau
    materials = [c for c in df_th.columns if c.lower() != "energy"]
    raw_records = []

    for _, row in df_th.iterrows():
        energy_kev = int(round(row["Energy"]))
        e0_mev = energy_kev / 1000.0

        # Lay thong tin blank
        b_res = blank_dict.get(energy_kev, (np.nan, np.nan, np.nan, np.nan))
        b_peak, b_peak_err, b_tot, b_tot_err = b_res

        # Ghi ban ghi Blank
        raw_records.append({
            "energy_mev": e0_mev,
            "energy_kev": energy_kev,
            "sample": "BLANK",
            "thickness_cm": 0.0,
            "peak_flux": b_peak,
            "peak_err": b_peak_err,
            "total_flux": b_tot,
            "total_err": b_tot_err,
            "I0_peak": b_peak,
            "lac_cm-1": np.nan,
            "mac_cm2_g": np.nan,
        })

        for mat in materials:
            mat_key = mat.lower()
            if mat_key not in COMPOSITION:
                continue

            rho = DENSITY[mat_key]
            th_list = _parse_thickness_list(row[mat])

            for th in th_list:
                th_str = _fmt_thickness(th)
                job_dir = jobs_path / f"{mat_key}_{energy_kev}keV_th{th_str}cm"
                peak_m, peak_err, tot_m, tot_err = read_job_statepoint(job_dir)

                # Tinh LAC va MAC neu co Blank va Sample > 0
                if pd.notna(b_peak) and b_peak > 0 and pd.notna(peak_m) and peak_m > 0 and th > 0:
                    lac = math.log(b_peak / peak_m) / th
                    mac = lac / rho
                else:
                    lac = np.nan
                    mac = np.nan

                raw_records.append({
                    "energy_mev": e0_mev,
                    "energy_kev": energy_kev,
                    "sample": mat_key.upper(),
                    "thickness_cm": th,
                    "peak_flux": peak_m,
                    "peak_err": peak_err,
                    "total_flux": tot_m,
                    "total_err": tot_err,
                    "I0_peak": b_peak,
                    "lac_cm-1": lac,
                    "mac_cm2_g": mac,
                })

    df_raw = pd.DataFrame(raw_records)

    # 3. Tao bang ma tran Pivot cho Peak Flux va Total Flux
    # Pivot: Energy_MeV lam Index, cac cot Sample_thX.XXcm lam Values
    df_samples = df_raw[df_raw["sample"] != "BLANK"].copy()

    df_samples["col_name"] = df_samples.apply(
        lambda r: f"{r['sample']}_th{_fmt_thickness(r['thickness_cm'])}cm", axis=1
    )

    pivot_peak = df_samples.pivot(index="energy_mev", columns="col_name", values="peak_flux").reset_index()
    pivot_peak.insert(1, "Blank", pivot_peak["energy_mev"].map(
        lambda e: df_raw[(df_raw["energy_mev"] == e) & (df_raw["sample"] == "BLANK")]["peak_flux"].values[0]
        if len(df_raw[(df_raw["energy_mev"] == e) & (df_raw["sample"] == "BLANK")]) > 0 else np.nan
    ))

    pivot_tot = df_samples.pivot(index="energy_mev", columns="col_name", values="total_flux").reset_index()
    pivot_tot.insert(1, "Blank", pivot_tot["energy_mev"].map(
        lambda e: df_raw[(df_raw["energy_mev"] == e) & (df_raw["sample"] == "BLANK")]["total_flux"].values[0]
        if len(df_raw[(df_raw["energy_mev"] == e) & (df_raw["sample"] == "BLANK")]) > 0 else np.nan
    ))

    pivot_mac = df_samples.pivot(index="energy_mev", columns="col_name", values="mac_cm2_g").reset_index()

    # Xuat file Excel
    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        df_raw.to_excel(writer, sheet_name="Raw_Flux_Merged", index=False)
        pivot_peak.to_excel(writer, sheet_name="Peak_Flux_Uncollided", index=False)
        pivot_tot.to_excel(writer, sheet_name="Total_Flux", index=False)
        pivot_mac.to_excel(writer, sheet_name="Summary_MAC", index=False)

    print("\n" + "=" * 70)
    print(f"✅ DA TRICH XUAT VA LUU THANH CONG FILE KET QUA: {output_excel}")
    print(f"Tong so ban ghi: {len(df_raw)}")
    print("=" * 70)


if __name__ == "__main__":
    ex_p = sys.argv[1] if len(sys.argv) > 1 else "thickness_table_all9.xlsx"
    j_dir = sys.argv[2] if len(sys.argv) > 2 else "inputs"
    out_e = sys.argv[3] if len(sys.argv) > 3 else "flux_results.xlsx"
    main(ex_p, j_dir, out_e)
