import openmc
import openmc.deplete
import numpy as np
import math

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
fuel_volume = (4.0 / 3.0) * math.pi * (50.0 ** 3)          # inner sphere r = 50 cm
indium_volume = (4.0 / 3.0) * math.pi * (60.0 ** 3 - 50.0 ** 3)  # shell between 50 cm and 60 cm

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

# Uniform source in fuel (current API)
bounds = [-50, -50, -50, 50, 50, 50]
# uniform_dist = openmc.stats.Box(bounds[:3], bounds[3:], constraints=['fissionable'])
uniform_dist = openmc.stats.Box(bounds[:3], bounds[3:], only_fissionable=True)
settings.source = openmc.IndependentSource(space=uniform_dist)

# --- MODEL ---
model = openmc.Model(geometry=geometry, materials=materials, settings=settings)

# --- DOWNLOAD THE SAME NUCLEAR DATA FILE AND SET THE ENV TO THE XML FILE ---
# --- export OPENMC_CROSS_SECTIONS="/PATH_TO/chain_endfb/cross_sections.xml"
# --- set that in your bash script at the bottom and reload with source ~/.bashrc

# --- DEPLETION CHAIN FILE ---
# --- YOU CAN DOWNLOAD THE DEPLETION CHAIN FILES HERE: https://openmc.org/data/ ---
chain_file = "/PATH_TO/chain_endfb/xx_thermal-or-and-fast.xml"

# --- COUPLED OPERATOR ---
operator = openmc.deplete.CoupledOperator(
    model,
    chain_file=chain_file
)

# --- TRANSIENT DRIVER ---
timesteps = [1.0] * 10 + [1.0] * 10  # 1 day per step
power = 1e6  # W

absorber_densities = np.linspace(0.0, 1.0, 10).tolist() + np.linspace(1.0, 0.0, 10).tolist()

for step, density_factor in enumerate(absorber_densities, start=1):
    indium.set_density('g/cm3', 7.31 * density_factor)
    print(f"Step {step}: Indium density = {indium.density:.3f} g/cm³")

    integrator = openmc.deplete.PredictorIntegrator(
        operator, timesteps=[timesteps[step-1]], power=power
    )
    integrator.integrate()

print("Transient depletion simulation complete.")

# --- POST-PROCESSING ---
results = openmc.deplete.Results("depletion_results.h5")

# Track keff
keff = results.get_keff()
print("\nKeff over time:")
for i, (val, err) in enumerate(keff, start=1):
    print(f" Step {i:02d}: keff = {val:.5f} ± {err:.5f}")

# Track isotope evolution
tracked_isotopes = ['U235', 'U238', 'In115', 'Sn116']
for iso in tracked_isotopes:
    try:
        atom_dens = results.get_atoms(material=fuel, nuc=iso)
    except KeyError:
        atom_dens = results.get_atoms(material=indium, nuc=iso)
    print(f"\nIsotope {iso} atom densities over time:")
    for t, dens in zip(results.get_times(), atom_dens[1]):
        print(f"  Time {t:.1f} days: {dens:.6e} atoms/b-cm")
