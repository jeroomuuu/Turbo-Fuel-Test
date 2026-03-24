import openmc
import numpy as np
import math
import matplotlib.pyplot as plt

# --- MATERIALS ---
fuel = openmc.Material(name="UO2 Fuel")
fuel.set_density('g/cm3', 10.5)
fuel.add_element('U', 1.0, enrichment=5.0)
fuel.add_element('O', 2.0)

indium = openmc.Material(name="Indium Reflector")
indium.set_density('g/cm3', 7.31)
indium.add_element('In', 1.0)

materials = openmc.Materials([fuel, indium])

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
settings.run_mode = 'eigenvalue'

# Hardware Optimizations for 384-core (192 physical) machine
settings.threads = 240 
settings.particles = 1_000_000 

# Uniform fissionable source
bounds = [-50, -50, -50, 50, 50, 50]
uniform_dist = openmc.stats.Box(bounds[:3], bounds[3:], only_fissionable=True)
settings.source = openmc.IndependentSource(space=uniform_dist)

# --- TALLIES (For Flux Heatmap) ---
mesh = openmc.RegularMesh()
mesh.dimension = [100, 100, 100]  # 100x100x100 grid of voxels
mesh.lower_left = [-60.0, -60.0, -60.0]
mesh.upper_right = [60.0, 60.0, 60.0]

mesh_filter = openmc.MeshFilter(mesh)
flux_tally = openmc.Tally(name='flux_tally')
flux_tally.filters = [mesh_filter]
flux_tally.scores = ['flux']

tallies = openmc.Tallies([flux_tally])

# --- MODEL ---
model = openmc.Model(geometry=geometry, materials=materials, settings=settings, tallies=tallies)

# --- TRANSIENT DRIVER ---
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

# --- POST-PROCESSING: TERMINAL OUTPUT ---
print("\n=== FINAL RESULTS ===")
print(f"{'Step':<6} | {'Indium Density (g/cm³)':<22} | {'Keff'}")
print("-" * 55)
for res in results:
    print(f"{res['step']:<6} | {res['density']:<22.10f} | {res['keff']:.5f} ± {res['error']:.5f}")


# --- POST-PROCESSING: KEFF PLOT ---
print("\nGenerating Keff plot...")
steps = [res['step'] for res in results]
keffs = [res['keff'] for res in results]
errors = [res['error'] for res in results]
densities = [res['density'] for res in results]

fig1, ax1 = plt.subplots(figsize=(10, 6))
color = 'tab:red'
ax1.set_xlabel('Simulation Step')
ax1.set_ylabel('Keff', color=color)
ax1.errorbar(steps, keffs, yerr=errors, fmt='-o', color=color, capsize=5, label='Keff')
ax1.tick_params(axis='y', labelcolor=color)
ax1.grid(True, linestyle='--', alpha=0.6)

ax2 = ax1.twinx()  
color = 'tab:blue'
ax2.set_ylabel('Indium Density (g/cm³)', color=color)  
ax2.plot(steps, densities, '-s', color=color, alpha=0.5, label='Density')
ax2.tick_params(axis='y', labelcolor=color)

fig1.suptitle('OpenMC Transient Benchmark: Keff vs Indium Density Shroud')
fig1.tight_layout()
fig1.savefig('benchmark_results.png', dpi=300)
print("Plot saved as 'benchmark_results.png'")


# --- POST-PROCESSING: FLUX HEATMAP ---
print("Extracting final statepoint flux data...")
with openmc.StatePoint(statepoint_filename) as sp:
    tally = sp.get_tally(name='flux_tally')
    flux_mean = tally.get_values(scores=['flux'], value='mean')
    flux_mean = flux_mean.reshape((100, 100, 100))

# Grab the middle slice along the Z-axis (index 50)
flux_slice = flux_mean[:, :, 50]

fig2, ax_flux = plt.subplots(figsize=(8, 6))
im = ax_flux.imshow(flux_slice, origin='lower', extent=[-60, 60, -60, 60], cmap='inferno')

ax_flux.set_title('Neutron Flux Distribution (Midplane Slice)')
ax_flux.set_xlabel('X (cm)')
ax_flux.set_ylabel('Y (cm)')
fig2.colorbar(im, label='Flux (neutrons-cm/src)')

fig2.savefig('flux_heatmap.png', dpi=300)
print("Flux heatmap saved as 'flux_heatmap.png'")
