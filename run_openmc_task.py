"""
run_openmc_task.py - Parallel worker for OpenMC Simulation (2026.10.16_Paper10.1_MAC_OpenMC)
Runs on GitHub Actions Swarm (18 accounts x 10 runners = 180 concurrent runners).
Uploads raw 1-to-1 CSV results directly to Flat Common Pool (02_Flux_Data).
Uploads output tallies/statepoints to Flat Common Pool (03_Simulation_Outputs).
"""

import argparse
import os
import sys
import time
import json
import shutil
import zipfile
import subprocess
from pathlib import Path
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import gdrive_helper
import openmc
import openmc_model

DET_VOLUME_CM3 = 157.07963268  # pi * r^2 * h = pi * 5^2 * 2 cm3


def parse_args():
    parser = argparse.ArgumentParser(description="OpenMC Parallel Worker for MAC Simulation")
    parser.add_argument("--runner-id", type=int, required=True, help="ID runner (1..10)")
    parser.add_argument("--num-runners", type=int, default=10, help="Tong so runner tren account nay")
    parser.add_argument("--primaries", type=int, default=100000000, help="So hat moi job (10^8)")
    parser.add_argument("--gdrive-folder", type=str, default="1FVMmlEQWDki_8A4fU8515zy_EcnM9yM5")
    parser.add_argument("--plan-file", type=str, default="openmc_plan_18acc.json")
    parser.add_argument("--github-user", type=str, default=None)
    parser.add_argument("--timeout-hours", type=float, default=5.0)
    return parser.parse_args()


def get_existing_drive_files(drive_service, flux_folder_id):
    existing = set()
    page_token = None
    while True:
        try:
            q = f"'{flux_folder_id}' in parents and trashed = false"
            res = drive_service.files().list(
                q=q, supportsAllDrives=True, includeItemsFromAllDrives=True,
                fields="nextPageToken, files(name)",
                pageSize=1000, pageToken=page_token
            ).execute()
            for f in res.get("files", []):
                existing.add(f["name"].lower().strip())
            page_token = res.get("nextPageToken")
            if not page_token:
                break
        except Exception as e:
            print(f">>> [WARNING] Loi doc danh sach drive: {e}")
            break
    return existing


def main():
    args = parse_args()
    acc_name = args.github_user or os.environ.get("GITHUB_REPOSITORY_OWNER") or "runner"

    print("=" * 80)
    print("OPENMC PARALLEL WORKER - 2026.10.16_Paper10.1_MAC_OpenMC")
    print(f"Account:       {acc_name}")
    print(f"Runner ID:     {args.runner_id}/{args.num_runners}")
    print(f"Primaries:     {args.primaries:,} (10^8)")
    print(f"GDrive Folder: {args.gdrive_folder}")
    print("=" * 80)

    # 1. Connect Google Drive
    print(">>> [AUTH] Dang khoi tao Google Drive API...")
    try:
        drive_service = gdrive_helper.get_drive_service()
        subfolders = gdrive_helper.get_or_create_subfolders(drive_service, parent_id=args.gdrive_folder)
        flux_folder_id = subfolders.get("02_Flux_Data")
        outputs_folder_id = subfolders.get("03_Simulation_Outputs")
        print(f">>> [GDRIVE] 02_Flux_Data ID:          {flux_folder_id}")
        print(f">>> [GDRIVE] 03_Simulation_Outputs ID:  {outputs_folder_id}")
    except Exception as e:
        print(f">>> [GDRIVE FATAL] Khong the ket noi Google Drive: {e}")
        sys.exit(1)

    # 2. Load execution plan
    plan_path = Path(args.plan_file)
    if not plan_path.exists():
        print(f">>> [FATAL] Khong tim thay plan file: {plan_path}")
        sys.exit(1)

    with open(plan_path, "r", encoding="utf-8") as pf:
        full_plan = json.load(pf)

    acc_plan = full_plan.get(acc_name)
    if not acc_plan:
        print(f">>> [PLAN] Account '{acc_name}' khong co trong plan JSON. Su dung round-robin...")
        all_jobs = []
        for a_k, a_v in full_plan.items():
            for r_k, r_jobs in a_v.items():
                all_jobs.extend(r_jobs)
        assigned_jobs = [j for i, j in enumerate(all_jobs) if (i % args.num_runners) == (args.runner_id - 1)]
    else:
        assigned_jobs = acc_plan.get(str(args.runner_id), [])

    total_jobs = len(assigned_jobs)
    print(f">>> [PLAN] Runner #{args.runner_id} duoc giao {total_jobs} jobs.")

    if total_jobs == 0:
        print(">>> [INFO] Khong co job nao can chay. Ket thuc.")
        sys.exit(0)

    # 3. Scan existing files in Drive 02_Flux_Data to resume / skip
    print(">>> [GDRIVE] Dang quet cac file da hoan thanh tren Drive...")
    existing_files = get_existing_drive_files(drive_service, flux_folder_id)
    print(f">>> [GDRIVE] Da tim thay {len(existing_files)} file tren 02_Flux_Data.")

    completed_count = 0
    skipped_count = 0
    error_count = 0
    start_time = time.time()
    max_duration = args.timeout_hours * 3600.0

    runs_base_dir = Path("/tmp/openmc_runs")
    runs_base_dir.mkdir(parents=True, exist_ok=True)

    for idx, job in enumerate(assigned_jobs, 1):
        if time.time() - start_time > max_duration:
            print(f">>> [TIMEOUT] Da dat gioi han {args.timeout_hours}h. Dung lai de runner tiep theo cuu ho.")
            break

        jname = job["job_name"]
        sample = job["sample"]
        thickness_cm = float(job["thickness_cm"])
        energy_kev = float(job["energy_kev"])
        output_csv_name = f"{jname}.csv"

        if output_csv_name.lower().strip() in existing_files:
            print(f"[{idx}/{total_jobs}] SKIP: {output_csv_name} da ton tai tren Drive.")
            skipped_count += 1
            continue

        print(f"\n--- [{idx}/{total_jobs}] RUNNING: {jname} ---")
        print(f"    Sample: {sample} | Thickness: {thickness_cm} cm | Energy: {energy_kev} keV | Primaries: {args.primaries:,}")

        job_dir = runs_base_dir / jname
        if job_dir.exists():
            shutil.rmtree(job_dir)
        job_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Generate XML model
            t0 = time.time()
            openmc_model.export_openmc_model(
                output_dir=str(job_dir),
                mat_key=sample,
                energy_kev=energy_kev,
                thickness_cm=thickness_cm,
                n_particles=args.primaries,
                n_batches=10
            )

            # 2. Run OpenMC
            cmd = ["openmc"]
            res = subprocess.run(cmd, cwd=str(job_dir), capture_output=True, text=True)
            elapsed = time.time() - t0

            if res.returncode != 0:
                print(f"    [SIM ERROR] code {res.returncode}: {(res.stderr or res.stdout)[-400:]}")
                error_count += 1
                continue

            print(f"    [SIM OK] Thoi gian chay: {elapsed:.2f}s")

            # 3. Read tallies from statepoint.10.h5
            sp_file = job_dir / "statepoint.10.h5"
            if not sp_file.exists():
                print(f"    [ERR] Khong tim thay {sp_file}!")
                error_count += 1
                continue

            sp = openmc.StatePoint(str(sp_file))
            tally_tot = sp.get_tally(name="total_flux")
            tally_peak = sp.get_tally(name="peak_flux")

            flux_tot_val = float(tally_tot.mean.flatten()[0]) / DET_VOLUME_CM3
            flux_tot_err = float(tally_tot.std_dev.flatten()[0]) / DET_VOLUME_CM3
            flux_peak_val = float(tally_peak.mean.flatten()[0]) / DET_VOLUME_CM3
            flux_peak_err = float(tally_peak.std_dev.flatten()[0]) / DET_VOLUME_CM3

            print(f"    Total Flux:      {flux_tot_val:.6e} +/- {flux_tot_err:.4e}")
            print(f"    Uncollided Flux: {flux_peak_val:.6e} +/- {flux_peak_err:.4e}")

            # 4. Write 1-to-1 CSV
            csv_path = job_dir / output_csv_name
            df_row = pd.DataFrame([{
                "job_name": jname,
                "sample": sample,
                "thickness_cm": thickness_cm,
                "energy_kev": energy_kev,
                "primaries": args.primaries,
                "det_volume_cm3": DET_VOLUME_CM3,
                "flux_total": flux_tot_val,
                "flux_uncollided": flux_peak_val,
                "flux_total_err": flux_tot_err,
                "flux_uncollided_err": flux_peak_err,
                "sim_seconds": round(elapsed, 2)
            }])
            df_row.to_csv(csv_path, index=False)

            # 5. Upload CSV to Drive 02_Flux_Data
            gdrive_helper.upload_file_to_folder(drive_service, str(csv_path), flux_folder_id)
            existing_files.add(output_csv_name.lower().strip())
            print(f"    [UPLOAD] -> 02_Flux_Data/{output_csv_name} (DONE)")

            # 6. Package and upload simulation outputs (.out and .h5)
            out_zip_name = f"{jname}_outputs.zip"
            out_zip_path = job_dir / out_zip_name
            with zipfile.ZipFile(out_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                if (job_dir / "tallies.out").exists():
                    zf.write(job_dir / "tallies.out", f"{jname}_tallies.out")
                if sp_file.exists():
                    zf.write(sp_file, f"{jname}_statepoint.10.h5")
            
            gdrive_helper.upload_file_to_folder(drive_service, str(out_zip_path), outputs_folder_id)
            print(f"    [UPLOAD] -> 03_Simulation_Outputs/{out_zip_name} (DONE)")

            completed_count += 1

        except Exception as e:
            print(f"    [EXCEPTION] {jname}: {e}")
            error_count += 1
        finally:
            if job_dir.exists():
                try:
                    shutil.rmtree(job_dir)
                except Exception:
                    pass

    total_time = time.time() - start_time
    print("\n" + "=" * 80)
    print(f"RUNNER #{args.runner_id} HOAN TAT: {completed_count} thanh cong, {skipped_count} da co, {error_count} loi")
    print(f"Tong thoi gian: {total_time/60:.2f} phut")
    print("=" * 80)


if __name__ == "__main__":
    main()
