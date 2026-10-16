"""
Run_sample.py -- CHAY MO PHONG CO MAU (SAMPLE) -> xuat I va R_Compton
Hinh hoc Narrow-Beam chuan 1:1 voi PHITS cho 8 mau S1..S8 Paper 10:
- Doc thanh phan (Li/B/O/Al/Si/Ca/Gd) va mat do tu Config_Simulation.xlsx qua sim_config.py
- Nguon photon diem tai z = 1.0 cm chieu doc truc +z
- Collimator 1 Pb: z = 1.0 den 7.0 cm (lo r = 0.5 cm, vo r = 3.5 cm)
- Mau Glass S1..S8: z = 7.0 den 7.0 + SAMPLE_THICKNESS_CM (r = 1.0 cm)
- Collimator 2 Pb: z = 7.0 + th den 10.0 + th (lo r = 0.5 cm, vo r = 2.5 cm)
- Dau do NaI(Tl): z = 10.0 + th den 15.0 + th (r = 2.5 cm)
- Vo chi boc ngoai Pb bao quanh toan bo he
- Tally:
  + Surface current vao detector tai z13 voi EnergyFilter [E0 - 1 eV, E0 + 1 eV]
  + 3 tally trong mau de tinh R_Compton (chuan Zeq)
"""
import math
import os
import sys
import json
import openmc
import sim_config

# Tu dong dat OPENMC_CROSS_SECTIONS va PATH neu chua co
OPENMC_BIN = "/home/ht/miniconda3/envs/openmc/bin"
if OPENMC_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{OPENMC_BIN}:{os.environ.get('PATH', '')}"

DEFAULT_XS = "/home/ht/nuclear_data/endfb-viii.0-hdf5/endfb-viii.0-hdf5/cross_sections.xml"
if "OPENMC_CROSS_SECTIONS" not in os.environ and os.path.exists(DEFAULT_XS):
    os.environ["OPENMC_CROSS_SECTIONS"] = DEFAULT_XS


# =====================================================================
# 0. CAU HINH CHAY
# =====================================================================
ENERGY_KEV           = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
SAMPLE_THICKNESS_CM  = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
N_PARTICLES          = int(sys.argv[3])   if len(sys.argv) > 3 else 1_000_000
N_BATCHES            = int(sys.argv[4])   if len(sys.argv) > 4 else 100
SAMPLE_NAME          = sys.argv[5].upper() if len(sys.argv) > 5 else 'S1'
OUTPUT_DIR           = f'run_sample_{SAMPLE_NAME.lower()}'

CONFIG_EXCEL = os.environ.get('CONFIG_EXCEL', 'Config_Simulation.xlsx')
SAMPLE_CONFIGS = sim_config.load_sample_composition(CONFIG_EXCEL)

CUTOFF_ENERGY_PHOTON_EV = 1000.0   # nguong cutoff photon 1 keV
PEAK_WINDOW_FRAC        = 0.0005   # do rong +-frac quanh E0 dung cho tally R trong mau

cfg = SAMPLE_CONFIGS[SAMPLE_NAME]
SAMPLE_DENSITY_GCM3 = cfg['density']

# =====================================================================
# 1. VAT LIEU
# =====================================================================
mat_pb = openmc.Material(material_id=1, name="Pb (collimators + shield)")
mat_pb.add_element('Pb', 1.0, 'ao')
mat_pb.set_density('g/cm3', 11.34)

# Mau thuy tinh (S1 -> S8): nap dong cac nguyen to co ti le > 0
mat_sam = openmc.Material(material_id=2, name=f"Mau ({SAMPLE_NAME})")
for _el in sim_config.ALL_ELEMENT_KEYS:
    _frac = cfg.get(_el, 0.0)
    if _frac > 0:
        mat_sam.add_element(_el, _frac, 'wo')
mat_sam.set_density('g/cm3', SAMPLE_DENSITY_GCM3)

mat_nai = openmc.Material(material_id=3, name="NaI(Tl) - detector")
mat_nai.add_element('Na', 0.15337, 'wo')
mat_nai.add_element('I',  0.84663, 'wo')
mat_nai.set_density('g/cm3', 3.67)

materials = openmc.Materials([mat_pb, mat_sam, mat_nai])
materials.export_to_xml()

# =====================================================================
# 2. BE MAT
# =====================================================================
Z_PRE_FRONT        = 0.0
Z_SOURCE_FRONT     = 0.5
Z_SOURCE           = 1.0
Z_COLLIM1_BACK     = 7.0
GAP_COLLIM1_SAMPLE = 0.0
GAP_SAMPLE_COLLIM2 = 0.0
COLLIM2_LEN        = 3.0
DET_LEN            = 5.0
AIR_MARGIN         = 0.0
SHIELD_MARGIN      = 5.0
SHIELD_MARGIN_BACK = 0.0
WORLD_R            = 100.0

Z_SAMPLE_FRONT       = Z_COLLIM1_BACK + GAP_COLLIM1_SAMPLE
z_sample_back_val    = Z_SAMPLE_FRONT + SAMPLE_THICKNESS_CM
z_collim2_front_val  = z_sample_back_val + GAP_SAMPLE_COLLIM2
z_collim2_back_val   = z_collim2_front_val + COLLIM2_LEN
z_det_back_val       = z_collim2_back_val + DET_LEN
z_40_val = Z_PRE_FRONT - AIR_MARGIN
z_41_val = z_det_back_val + AIR_MARGIN
z_30_val = z_40_val - SHIELD_MARGIN
z_31_val = z_41_val + SHIELD_MARGIN_BACK

z10 = openmc.ZPlane(z0=Z_PRE_FRONT)
z16 = openmc.ZPlane(z0=Z_SOURCE_FRONT)
z19 = openmc.ZPlane(z0=Z_SOURCE)
z11 = openmc.ZPlane(z0=Z_COLLIM1_BACK)
z17 = z11
z12 = z17 if SAMPLE_THICKNESS_CM <= 0 else openmc.ZPlane(z0=z_sample_back_val)
z18 = z12
z13 = openmc.ZPlane(z0=z_collim2_back_val)
z14 = openmc.ZPlane(z0=z_det_back_val)
z40 = z10
z41 = z14
z30 = openmc.ZPlane(z0=z_30_val)
z31 = z41

cz20 = openmc.ZCylinder(r=0.5)                      # r_channel
cz21 = openmc.ZCylinder(r=1.0)                      # r_pre_hole
cz22 = openmc.ZCylinder(r=1.0)                      # r_sample
cz23 = openmc.ZCylinder(r=2.5)                      # r_det
cz33 = openmc.ZCylinder(r=3.5)                      # r_airbore
cz26 = openmc.ZCylinder(r=3.5)                      # r_pre_outer
cz28 = openmc.ZCylinder(r=3.5)                      # r_collim1_outer
cz27 = openmc.ZCylinder(r=2.5)                      # r_collim2_outer
cz32 = openmc.ZCylinder(r=8.5)                      # r_shield_outer

sph99 = openmc.Sphere(r=WORLD_R, boundary_type='vacuum')

# =====================================================================
# 3. CELLS
# =====================================================================
cell_pre = openmc.Cell(
    name="Pre-collimator Pb",
    fill=mat_pb,
    region=+z10 & -z19 & +cz21 & -cz26,
)
cell_pre_hole_a = openmc.Cell(
    name="Lo pre-collimator (truoc nguon) [VOID]",
    fill=None,
    region=+z10 & -z16 & -cz21,
)
cell_pre_hole_b = openmc.Cell(
    name="Lo pre-collimator (sau nguon, chua nguon) [VOID]",
    fill=None,
    region=+z16 & -z19 & -cz21,
)
cell_col1 = openmc.Cell(
    name="Collimator 1 Pb",
    fill=mat_pb,
    region=+z19 & -z11 & +cz20 & -cz28,
)
cell_col1_bore = openmc.Cell(
    name="Lo chuan truc collimator 1 [VOID]",
    fill=None,
    region=+z19 & -z11 & -cz20,
)
cell_sam = openmc.Cell(
    name=f"Mau {SAMPLE_NAME} day {SAMPLE_THICKNESS_CM}cm",
    fill=mat_sam,
    region=+z17 & -z12 & -cz22,
)
cell_col2 = openmc.Cell(
    name="Collimator 2 Pb",
    fill=mat_pb,
    region=+z18 & -z13 & +cz20 & -cz27,
)
cell_col2_bore = openmc.Cell(
    name="Lo chuan truc collimator 2 [VOID]",
    fill=None,
    region=+z18 & -z13 & -cz20,
)
cell_det = openmc.Cell(
    name="Dau do NaI(Tl)",
    fill=mat_nai,
    region=+z13 & -z14 & -cz23,
)

term_A_120 = +z13 & -z14 & +cz23 & -cz33
term_B_120 = +z30 & -z31 & -cz32 & (-z40 | +z41 | +cz33)
cell_shield = openmc.Cell(
    name="Vo chi boc ngoai",
    fill=mat_pb,
    region=term_A_120 | term_B_120,
)

region_all_inner = (
    cell_pre.region | cell_pre_hole_a.region | cell_pre_hole_b.region |
    cell_col1.region | cell_col1_bore.region | cell_sam.region |
    cell_col2.region | cell_col2_bore.region | cell_det.region |
    cell_shield.region
)
cell_inner_void = openmc.Cell(
    name="Chan khong con lai trong airbore [VOID]",
    fill=None,
    region=+z40 & -z41 & -cz33 & ~region_all_inner,
)
cell_outer_vac = openmc.Cell(
    name="Chan khong ngoai vo chi, trong world [VOID]",
    fill=None,
    region=-sph99 & (-z30 | +z31 | +cz32),
)

universe = openmc.Universe(cells=[
    cell_pre, cell_pre_hole_a, cell_pre_hole_b,
    cell_col1, cell_col1_bore,
    cell_sam,
    cell_col2, cell_col2_bore,
    cell_det,
    cell_shield,
    cell_inner_void,
    cell_outer_vac,
])

geometry = openmc.Geometry(universe)
geometry.export_to_xml()

# =====================================================================
# 4. NGUON PHOTON
# =====================================================================
source = openmc.IndependentSource()
source.particle = 'photon'
source.space = openmc.stats.Point((0.0, 0.0, Z_SOURCE))
source.energy = openmc.stats.Discrete([ENERGY_KEV * 1.0e3], [1.0])  # keV -> eV
source.angle = openmc.stats.Monodirectional((0.0, 0.0, 1.0))

# =====================================================================
# 5. SETTINGS
# =====================================================================
settings = openmc.Settings()
settings.run_mode = 'fixed source'
settings.source = [source]
settings.batches = N_BATCHES
settings.particles = N_PARTICLES
settings.photon_transport = True
settings.electron_treatment = 'ttb'
settings.cutoff = {'energy_photon': CUTOFF_ENERGY_PHOTON_EV}
settings.output = {'path': OUTPUT_DIR}

os.makedirs(OUTPUT_DIR, exist_ok=True)
settings.export_to_xml()

# =====================================================================
# 6. TALLIES: 1 Surface current detector + 3 Tally R trong mau
# =====================================================================
surf_filter   = openmc.SurfaceFilter(z13)
energy_filter = openmc.EnergyFilter([ENERGY_KEV*1e3 - 1.0, ENERGY_KEV*1e3 + 1.0])

tally_bdx = openmc.Tally(name="USRBDX equivalent: photon current vao detector")
tally_bdx.filters = [surf_filter, energy_filter]
tally_bdx.scores  = ['current']

# 3 tally tinh R = mu_Compton / (mu_total - mu_Rayleigh) trong mau
cell_sam_filter = openmc.CellFilter([cell_sam])
peak_frac = PEAK_WINDOW_FRAC
energy_filter_R = openmc.EnergyFilter([ENERGY_KEV*1e3*(1-peak_frac), ENERGY_KEV*1e3*(1+peak_frac)])

tally_scatter_sam = openmc.Tally(name="Compton scatter trong mau")
tally_scatter_sam.filters = [cell_sam_filter, energy_filter_R]
tally_scatter_sam.scores  = ['incoherent-scatter']

tally_total_sam = openmc.Tally(name="Total reaction trong mau")
tally_total_sam.filters = [cell_sam_filter, energy_filter_R]
tally_total_sam.scores  = ['total']

tally_coherent_sam = openmc.Tally(name="Coherent scatter trong mau")
tally_coherent_sam.filters = [cell_sam_filter, energy_filter_R]
tally_coherent_sam.scores  = ['coherent-scatter']

tallies = openmc.Tallies([tally_bdx, tally_scatter_sam, tally_total_sam, tally_coherent_sam])
tallies.export_to_xml()

# =====================================================================
# 7. CHAY SIMULATION
# =====================================================================
openmc.run()

# =====================================================================
# 8. GHI METADATA
# =====================================================================
statepoint_path = os.path.join(OUTPUT_DIR, f'statepoint.{N_BATCHES}.h5')
sp = openmc.StatePoint(statepoint_path)
t_bdx = sp.get_tally(name="USRBDX equivalent: photon current vao detector")

I_value  = float(t_bdx.mean.sum())
I_stddev = float(t_bdx.std_dev.sum())

t_scatter_sam  = sp.get_tally(name="Compton scatter trong mau")
t_total_sam    = sp.get_tally(name="Total reaction trong mau")
t_coherent_sam = sp.get_tally(name="Coherent scatter trong mau")

scatter_sam_mean   = float(t_scatter_sam.mean.sum())
total_sam_mean     = float(t_total_sam.mean.sum())
coherent_sam_mean  = float(t_coherent_sam.mean.sum())
denom_no_coherent  = total_sam_mean - coherent_sam_mean


def _ratio_stddev(numer_tally, denom_tally, denom_mean):
    if denom_mean is None or denom_mean <= 0:
        return None
    try:
        derived = numer_tally / denom_tally
        return float(derived.std_dev.sum())
    except Exception:
        return None


R_sample_with_coherent_value = (scatter_sam_mean / total_sam_mean if total_sam_mean > 0 else 0.0)
_std_wc = _ratio_stddev(t_scatter_sam, t_total_sam, total_sam_mean)
R_sample_with_coherent_stddev = _std_wc if _std_wc is not None else 0.0

t_denom_no_coherent = t_total_sam - t_coherent_sam
R_sample_no_coherent_value = (scatter_sam_mean / denom_no_coherent if denom_no_coherent > 0 else 0.0)
_std_noc = _ratio_stddev(t_scatter_sam, t_denom_no_coherent, denom_no_coherent)
R_sample_no_coherent_stddev = _std_noc if _std_noc is not None else 0.0

run_info = {
    "role": "sample",
    "sample_name": SAMPLE_NAME,
    "energy_keV": ENERGY_KEV,
    "sample_thickness_cm": SAMPLE_THICKNESS_CM,
    "sample_density_gcm3": SAMPLE_DENSITY_GCM3,
    "n_particles_total": N_PARTICLES * N_BATCHES,
    "n_batches": N_BATCHES,
    "statepoint_path": statepoint_path,
    "tally_name": "USRBDX equivalent: photon current vao detector",
    "I": I_value,
    "I_stddev": I_stddev,
    "R_sample_with_coherent": R_sample_with_coherent_value,
    "R_sample_with_coherent_stddev": R_sample_with_coherent_stddev,
    "R_sample_no_coherent": R_sample_no_coherent_value,
    "R_sample_no_coherent_stddev": R_sample_no_coherent_stddev,
}

with open(os.path.join(OUTPUT_DIR, 'run_info.json'), 'w', encoding='utf-8') as f:
    json.dump(run_info, f, indent=2, ensure_ascii=False)

print("\n" + "=" * 60)
print(f"  [SAMPLE: {SAMPLE_NAME}] Energy = {ENERGY_KEV} keV, day = {SAMPLE_THICKNESS_CM} cm")
print(f"  I       = {I_value:.6e} +/- {I_stddev:.2e} photon/source (surface current)")
print(f"  R_mau (CHUAN Zeq, KHONG coherent) = {R_sample_no_coherent_value:.6f}")
print(f"  -> Da ghi: {os.path.join(OUTPUT_DIR, 'run_info.json')}")
print(f"  -> Da ghi: {statepoint_path}")
print("=" * 60)
