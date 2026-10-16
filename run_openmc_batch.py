"""
run_openmc_batch.py - Dieu khien chay song song toan bo cac job OpenMC
Tu dong chay da luong bang WSL, theo doi tien do va thoi gian.

Cach chay (tu Windows):
    python run_openmc_batch.py inputs/ 4

Cach chay (trong WSL):
    python run_openmc_batch.py inputs/ 4
"""
import os
import sys
import time
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

OPENMC_CROSS_SECTIONS_PATH = "/home/ht/nuclear_data/endfb-viii.0-hdf5/endfb-viii.0-hdf5/cross_sections.xml"
OPENMC_BIN_PATH = "/home/ht/miniconda3/envs/openmc/bin"


def is_running_in_wsl() -> bool:
    """Kiem tra xem dang chay truc tiep trong WSL hay tren Windows."""
    return sys.platform.startswith("linux")


def to_wsl_path(win_path: Path) -> str:
    """Chuyen doi duong dan Windows (C:\\...) sang WSL (/mnt/c/...)."""
    p_str = str(win_path.resolve()).replace("\\", "/")
    if len(p_str) > 1 and p_str[1] == ":":
        drive = p_str[0].lower()
        return f"/mnt/{drive}{p_str[2:]}"
    return p_str


def run_single_job(job_dir: Path) -> tuple[str, bool, float]:
    """Chay 1 job OpenMC tai thu muc job_dir."""
    t0 = time.time()
    job_name = job_dir.name

    # Kiem tra neu da chay xong roi (co file statepoint)
    sp_files = list(job_dir.glob("statepoint.*.h5"))
    if sp_files:
        return job_name, True, 0.0

    if is_running_in_wsl():
        # Chay truc tiep trong Linux / WSL
        env = os.environ.copy()
        env["PATH"] = f"{OPENMC_BIN_PATH}:{env.get('PATH', '')}"
        env["OPENMC_CROSS_SECTIONS"] = OPENMC_CROSS_SECTIONS_PATH

        cmd = [f"{OPENMC_BIN_PATH}/openmc"]
        p = subprocess.run(cmd, cwd=str(job_dir), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        success = (p.returncode == 0)
    else:
        # Chay tu Windows goi WSL
        wsl_job_dir = to_wsl_path(job_dir)
        bash_cmd = (
            f"export PATH={OPENMC_BIN_PATH}:$PATH && "
            f"export OPENMC_CROSS_SECTIONS={OPENMC_CROSS_SECTIONS_PATH} && "
            f"cd '{wsl_job_dir}' && openmc"
        )
        cmd = ["wsl", "-d", "Ubuntu-24.04", "bash", "-c", bash_cmd]
        p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        success = (p.returncode == 0)

    elapsed = time.time() - t0
    return job_name, success, elapsed


def main(inputs_dir: str = "inputs", max_workers: int = 4):
    in_path = Path(inputs_dir)
    if not in_path.exists():
        print(f"Loi: Thu muc '{inputs_dir}' khong ton tai!")
        sys.exit(1)

    # Tim tat ca cac thu muc con chua settings.xml va geometry.xml
    all_job_dirs = sorted([
        d for d in in_path.iterdir()
        if d.is_dir() and (d / "settings.xml").exists() and (d / "geometry.xml").exists()
    ])

    total_jobs = len(all_job_dirs)
    if total_jobs == 0:
        print(f"Khong tim thay job OpenMC hop le nao trong '{inputs_dir}'!")
        sys.exit(0)

    print("=" * 70)
    print("🚀 BAT DAU CHAY BATCH MO PHONG OPENMC")
    print(f"Thu muc jobs: {in_path.resolve()}")
    print(f"Tong so jobs: {total_jobs}")
    print(f"So luong tien trinh song song: {max_workers}")
    print(f"Moi truong chay: {'Linux (WSL)' if is_running_in_wsl() else 'Windows (Goi WSL)'}")
    print("=" * 70)

    start_total = time.time()
    completed = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_single_job, j_dir): j_dir for j_dir in all_job_dirs}

        for future in as_completed(futures):
            job_name, ok, elapsed = future.result()
            if ok:
                completed += 1
                status = f"✅ DONE ({elapsed:.1f}s)" if elapsed > 0 else "⏭️ SKIPPED (Da co san)"
            else:
                failed += 1
                status = f"❌ FAILED ({elapsed:.1f}s)"

            pct = (completed + failed) / total_jobs * 100.0
            print(f"[{completed + failed:4d}/{total_jobs:4d} - {pct:5.1f}%] {job_name:<35s} {status}")

    total_time = time.time() - start_total
    print("\n" + "=" * 70)
    print(f"🏁 HOAN THANH BATCH OPENMC!")
    print(f"Thanh cong: {completed} / {total_jobs}")
    print(f"That bai:   {failed} / {total_jobs}")
    print(f"Tong thoi gian: {total_time / 60.0:.2f} phut ({total_time:.1f} giay)")
    print("=" * 70)


if __name__ == "__main__":
    in_d = sys.argv[1] if len(sys.argv) > 1 else "inputs"
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    main(in_d, workers)
