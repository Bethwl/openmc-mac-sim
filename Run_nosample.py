"""
Run_nosample.py -- CHAY MO PHONG KHONG MAU (NOSAMPLE) -> xuat I0
Hinh hoc Narrow-Beam chuan 1:1 voi PHITS:
- Nguon photon diem tai z = 1.0 cm chieu doc truc +z
- Collimator 1 chi tu z = 1.0 den 7.0 cm (lo r = 0.5 cm, vo r = 3.5 cm)
- Vung mau: tu z = 7.0 den 7.0 cm (be day = 0, void)
- Collimator 2 chi tu z = 7.0 den 10.0 cm (lo r = 0.5 cm, vo r = 2.5 cm)
- Dau do NaI(Tl) tu z = 10.0 den 15.0 cm (r = 2.5 cm)
- Vo chi boc ngoai Pb bao quanh toan bo he
- Tally toi uu: Surface current photon di qua mat truoc dau do (z13) voi EnergyFilter [E0 - 1 eV, E0 + 1 eV]
"""
import math
import os
import sys
import json
import openmc

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
ENERGY_KEV  = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
N_PARTICLES = int(sys.argv[2])   if len(sys.argv) > 2 else 1_000_000
N_BATCHES   = int(sys.argv[3])   if len(sys.argv) > 3 else 100
OUTPUT_DIR  = 'run_nosample'

CUTOFF_ENERGY_PHOTON_EV = 1000.0   # nguong cutoff photon 1 keV

# =====================================================================
# 1. VAT LIEU
# =====================================================================
mat_pb = openmc.Material(material_id=1, name="Pb (collimators + shield)")
mat_pb.add_element('Pb', 1.0, 'ao')
mat_pb.set_density('g/cm3', 11.34)

mat_nai = openmc.Material(material_id=2, name="NaI(Tl) - detector")
mat_nai.add_element('Na', 0.15337, 'wo')
mat_nai.add_element('I',  0.84663, 'wo')
mat_nai.set_density('g/cm3', 3.67)

materials = openmc.Materials([mat_pb, mat_nai])
materials.export_to_xml()

# =====================================================================
# 2. BE MAT
# =====================================================================
Z_PRE_FRONT        = 0.0
Z_SOURCE_FRONT     = 0.5
Z_SOURCE           = 1.0     # Nguon tai z = 1.0 cm
Z_COLLIM1_BACK     = 7.0
GAP_COLLIM1_SAMPLE = 0.0
GAP_SAMPLE_COLLIM2 = 0.0
COLLIM2_LEN        = 3.0
DET_LEN            = 5.0
AIR_MARGIN         = 0.0
SHIELD_MARGIN      = 5.0
SHIELD_MARGIN_BACK = 0.0
WORLD_R            = 100.0

SAMPLE_THICKNESS_CM = 0.0

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
    name="Vung mau [KHONG MAU - VOID]",
    fill=None,
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
# 6. TALLY TOI UU: Surface current tai z13 voi EnergyFilter [E0 - 1 eV, E0 + 1 eV]
# =====================================================================
surf_filter   = openmc.SurfaceFilter(z13)
energy_filter = openmc.EnergyFilter([ENERGY_KEV*1e3 - 1.0, ENERGY_KEV*1e3 + 1.0])

tally_bdx = openmc.Tally(name="USRBDX equivalent: photon current vao detector")
tally_bdx.filters = [surf_filter, energy_filter]
tally_bdx.scores  = ['current']

tallies = openmc.Tallies([tally_bdx])
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

I0_value   = float(t_bdx.mean.sum())
I0_stddev  = float(t_bdx.std_dev.sum())

run_info = {
    "role": "nosample",
    "energy_keV": ENERGY_KEV,
    "n_particles_total": N_PARTICLES * N_BATCHES,
    "n_batches": N_BATCHES,
    "statepoint_path": statepoint_path,
    "tally_name": "USRBDX equivalent: photon current vao detector",
    "I0": I0_value,
    "I0_stddev": I0_stddev,
}

with open(os.path.join(OUTPUT_DIR, 'run_info.json'), 'w', encoding='utf-8') as f:
    json.dump(run_info, f, indent=2, ensure_ascii=False)

print("\n" + "=" * 60)
print(f"  [NOSAMPLE] Energy = {ENERGY_KEV} keV")
print(f"  I0      = {I0_value:.6e} +/- {I0_stddev:.2e} photon/source (surface current)")
print(f"  -> Da ghi: {os.path.join(OUTPUT_DIR, 'run_info.json')}")
print(f"  -> Da ghi: {statepoint_path}")
print("=" * 60)
