#!/usr/bin/env python3
import subprocess
import time
import csv
import os
from datetime import datetime
from urllib.request import urlretrieve

# chmod +x this thing and run with ./fuelbench.sh
# change file locatations where needed

# URLs for the benchmark scripts
FUEL_URL = "https://raw.githubusercontent.com/jeroomuuu/Turbo-Fuel-Test/refs/heads/main/fuel2.py"
FORENSIC_URL = "https://raw.githubusercontent.com/jeroomuuu/Forensic-Scanner/refs/heads/main/forensic-scanner-1.0.py"

# Local filenames
FUEL_FILE = "fuel2.py"
FORENSIC_FILE = "forensic-scanner-1.0.py"
RESULTS_FILE = "benchmark_results.csv"

def download_scripts():
    """Download the latest versions of the benchmark scripts."""
    print("[*] Downloading benchmark scripts...")
    urlretrieve(FUEL_URL, FUEL_FILE)
    urlretrieve(FORENSIC_URL, FORENSIC_FILE)
    print("[+] Scripts downloaded.")

def run_script(script_path):
    """Run a Python script and capture its stdout and execution time."""
    print(f"[*] Running {script_path}...")
    start = time.perf_counter()
    try:
        result = subprocess.run(
            ["python3", script_path],
            capture_output=True,
            text=True,
            check=True
        )
        elapsed = time.perf_counter() - start
        print(f"[+] Finished {script_path} in {elapsed:.2f} seconds.")
        return result.stdout.strip(), elapsed
    except subprocess.CalledProcessError as e:
        print(f"[!] Error running {script_path}: {e}")
        return f"ERROR: {e}", None

def save_results(timestamp, fuel_output, fuel_time, forensic_output, forensic_time):
    """Save benchmark results to CSV."""
    file_exists = os.path.isfile(RESULTS_FILE)
    with open(RESULTS_FILE, mode="a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow([
                "Timestamp",
                "Fuel2 Output",
                "Fuel2 Time (s)",
                "Forensic Output",
                "Forensic Time (s)"
            ])
        writer.writerow([
            timestamp,
            fuel_output.replace("\n", " "),
            f"{fuel_time:.2f}" if fuel_time else "N/A",
            forensic_output.replace("\n", " "),
            f"{forensic_time:.2f}" if forensic_time else "N/A"
        ])

def main():
    download_scripts()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    fuel_output, fuel_time = run_script(FUEL_FILE)
    forensic_output, forensic_time = run_script(FORENSIC_FILE)

    print("\n=== Benchmark Summary ===")
    print(f"Timestamp: {timestamp}")
    print(f"Fuel2 Time: {fuel_time:.2f} s")
    print(f"Fuel2 Output: {fuel_output}")
    print(f"Forensic Time: {forensic_time:.2f} s")
    print(f"Forensic Output: {forensic_output}")

    save_results(timestamp, fuel_output, fuel_time, forensic_output, forensic_time)
    print(f"[+] Results saved to {RESULTS_FILE}")

if __name__ == "__main__":
    main()
