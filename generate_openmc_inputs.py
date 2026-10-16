"""
generate_openmc_inputs.py - Sinh toan bo file XML cho OpenMC theo bang be day
Ho hoan toan mo hinh Paper 1 (Paper 10.1 - PNE 2022):
- Nguon photon don nang tu 15 keV den 15000 keV (23 muc nang luong)
- 8 mau thuy tinh S1 -> S8 + Blank
- Banh be day day du 9-10 muc: 0.005 cm (cho 15-40 keV) va 0.1 -> 3.0 cm

Cach chay:
    python generate_openmc_inputs.py thickness_table_all9.xlsx inputs/ 1000000 10
"""
import re
import sys
import pandas as pd
from pathlib import Path

# Import model builder
from openmc_model import export_openmc_model, COMPOSITION


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


def main(excel_path: str = "thickness_table_all9.xlsx", output_dir: str = "inputs",
         n_particles: int = 1000000, n_batches: int = 10):
    df = pd.read_excel(excel_path)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    materials = [col for col in df.columns if col.lower() != "energy"]
    count_jobs = 0
    blank_generated = set()

    print("=" * 70)
    print("🚀 DANG SINH CAC FILE MO HINH XML CHO OPENMC...")
    print(f"File be day: {excel_path}")
    print(f"Thu muc xuat: {output_path}")
    print(f"So hat moi job: {n_particles} particles ({n_batches} batches)")
    print("=" * 70)

    for _, row in df.iterrows():
        energy_kev = int(round(row["Energy"]))

        # 1. Tao file Blank cho muc nang luong nay (chi can 1 blank cho moi energy)
        if energy_kev not in blank_generated:
            th_blank = 0.5  # Bề dày ô trống cho Blank
            blank_job_name = f"blank_{energy_kev}keV"
            blank_dir = output_path / blank_job_name
            export_openmc_model(
                output_dir=str(blank_dir),
                mat_key="blank",
                energy_kev=energy_kev,
                thickness_cm=th_blank,
                n_particles=n_particles,
                n_batches=n_batches,
            )
            blank_generated.add(energy_kev)
            count_jobs += 1

        # 2. Tao file cho tung mau thuy tinh S1 -> S8
        for mat in materials:
            mat_key = mat.lower()
            if mat_key not in COMPOSITION:
                continue

            th_list = _parse_thickness_list(row[mat])
            for th in th_list:
                th_str = _fmt_thickness(th)
                job_name = f"{mat_key}_{energy_kev}keV_th{th_str}cm"
                job_dir = output_path / job_name

                export_openmc_model(
                    output_dir=str(job_dir),
                    mat_key=mat_key,
                    energy_kev=energy_kev,
                    thickness_cm=th,
                    n_particles=n_particles,
                    n_batches=n_batches,
                )
                count_jobs += 1

    print("\n" + "=" * 70)
    print(f"✅ DA SINH THANH CONG {count_jobs} JOB MO HINH OPENMC VAO: {output_path}")
    print("=" * 70)


if __name__ == "__main__":
    ex_p = sys.argv[1] if len(sys.argv) > 1 else "thickness_table_all9.xlsx"
    out_d = sys.argv[2] if len(sys.argv) > 2 else "inputs"
    n_part = int(sys.argv[3]) if len(sys.argv) > 3 else 1000000
    n_bat = int(sys.argv[4]) if len(sys.argv) > 4 else 10
    main(ex_p, out_d, n_part, n_bat)
