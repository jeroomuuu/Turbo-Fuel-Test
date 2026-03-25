import openmc
import openmc.deplete
import numpy as np
import math

# dont forget to download and extract the endf file and point to the right location
# export OPENMC_CROSS_SECTIONS=/path-to-file/cross_sections.xml
# echo 'export OPENMC_CROSS_SECTIONS="/path-to-file/cross_sections.xml"' >> ~/.bashrc
# source ~./bashrc

# --- MATERIALS ---
fuel = openmc.Material(name="UO2 Fuel")
fuel.set_density('g/cm3', 10.5)
fuel.add_element('U', 1.0, enrichment=5.0)
fuel.add_element('O', 2.0)

indium = openmc.Material(name="Indium Moderator")
indium.set_density('g/cm3', 7.31)
indium.add_element('In', 1.0)

materials = openmc.Materials([fuel, indium])

# --- ASSIGN VOLUMES (required for depletion) ---
fuel_volume = (4.0 / 3.0) * math.pi * (50.0 ** 3)
indium_volume = (4.0 / 3.0) * math.pi * (60.0 ** 3 - 50.0 ** 3)

fuel.volume = fuel_volume
indium.volume = indium_volume

print(f"Fuel volume   = {fuel.volume:.2f} cm³")
print(f"Indium volume = {indium.volume:.2f} cm³")

# --- GEOMETRY ---
fuel_sphere = openmc.Sphere(r=50.0)
mod_sphere = openmc.Sphere(r=60.0, boundary_type='vacuum')

fuel_cell = openmc.Cell(region=-fuel_sphere, fill=fuel)
mod_cell = openmc.Cell(region=+fuel_sphere & -mod_sphere, fill=indium)

universe = openmc.Universe(cells=[fuel_cell, mod_cell])
geometry = openmc.Geometry(universe)

# --- SETTINGS ---
settings = openmc.Settings()
settings.batches = 50
settings.inactive = 10
settings.particles = 5000
settings.run_mode = 'eigenvalue'

# Uniform fissionable source (current API — no deprecation warning)
bounds = [-50, -50, -50, 50, 50, 50]
# Newer setting for future versions:
# uniform_dist = openmc.stats.Box(bounds[:3], bounds[3:], constraints=['fissionable'])
# Old currurent setting:
uniform_dist = openmc.stats.Box(bounds[:3], bounds[3:], only_fissionable=True)
settings.source = openmc.IndependentSource(space=uniform_dist)

# --- MODEL ---
model = openmc.Model(geometry=geometry, materials=materials, settings=settings)

# --- DEPLETION CHAIN FILE ---
# --- Download the appropiate one from openmc.org/data ---
chain_file = "/workspace/thermal.xml"

# --- COUPLED OPERATOR ---
operator = openmc.deplete.CoupledOperator(model, chain_file=chain_file)

# --- TRANSIENT DRIVER ---
timesteps = [1.0] * 20
power = 1e6  # W

# Avoid exactly zero density (OpenMC requirement)
EPS = 1e-10
absorber_densities = np.linspace(EPS, 1.0, 10).tolist() + np.linspace(1.0, EPS, 10).tolist()

results = []
statepoint_filename = ""

for step, density_factor in enumerate(absorber_densities, start=1):
    current_density = 7.31 * density_factor
    indium.set_density('g/cm3', current_density)
    
    print(f"\n{'='*40}")
    print(f"Step {step}: Indium density = {indium.density:.10f} g/cm³")
    print(f"{'='*40}")

    # Run OpenMC natively (no MPI required)
    statepoint_filename = model.run(output=False)

    with openmc.StatePoint(statepoint_filename) as sp:
        results.append({
            'step': step,
            'density': current_density,
            'keff': sp.keff.nominal_value,
            'error': sp.keff.std_dev
        })

# --- POST-PROCESSING ---
results = openmc.deplete.Results("depletion_results.h5")

keff = results.get_keff()
print("\nKeff over time:")
for i, (val, err) in enumerate(keff, start=1):
    print(f" Step {i:02d}: keff = {val:.5f} ± {err:.5f}")

tracked_isotopes = ['U235', 'U238', 'In115', 'Sn116']
for iso in tracked_isotopes:
    try:
        atom_dens = results.get_atoms(material=fuel, nuc=iso)
    except KeyError:
        atom_dens = results.get_atoms(material=indium, nuc=iso)
    print(f"\nIsotope {iso} atom densities over time:")
    for t, dens in zip(results.get_times(), atom_dens[1]):
        print(f"  Time {t:.1f} days: {dens:.6e} atoms/b-cm")
