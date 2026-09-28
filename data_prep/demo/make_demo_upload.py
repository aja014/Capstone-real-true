"""Builds the 4-file live-upload demo folder (two new clients, one per line).

    python data_prep/demo/make_demo_upload.py --quote-date 2026-10-13
    python data_prep/demo/make_demo_upload.py            # quote date = yesterday

Writes only Excel files (default: data_prep/demo/demo_upload/); never touches the database.
Headers are copied from data_prep/synthetic_v2/ (same wording, same order), so each file
auto-detects in folder mode. No Vehicle Information file on purpose: its headers are a subset
of Motor Quotation's, so it can never auto-detect -- the Motor Quotation creates the vehicle.

Both addresses are already in geocode_cache (no Nominatim call, works offline):
  Barangay Panghulo, Obando  -> river none, storm surge High -> High (coastal)
  Canalate, Malolos City     -> river Medium, storm surge none -> Medium
"""
import argparse
import datetime as dt
import shutil
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE / "demo_upload"

FIRE_NAME = ("Dimaculangan", "Rosalinda", "Manalastas")   # last, first, middle
MOTOR_NAME = ("Pagsisihan", "Joel", "Balagtas")
FIRE_ADDRESS = "Barangay Panghulo, Obando, Bulacan, Philippines"
MOTOR_ADDRESS = "Canalate, Malolos City, Bulacan, Philippines"


def full(name):
    last, first, middle = name
    return f"{first} {middle} {last}"


def customers():
    return pd.DataFrame([
        {"Last Name": "Dimaculangan", "First Name": "Rosalinda", "Middle Name": "Manalastas",
         "Gender": "Female", "Marital Status": "Married",
         "Complete Name of Spouse": "Ernesto Pascual Dimaculangan", "Nationality": "Filipino",
         "Present Address": FIRE_ADDRESS, "Permanent Address": FIRE_ADDRESS,
         "Residence Phone Number": "(044) 294-6173", "Mobile Number": "09178642305",
         "Email Address": "rosalinda.dimaculangan@gmail.com", "Zip Code": "3021",
         "Occupation": "Sari-sari Store Owner", "Employer": "Self-Employed",
         "TIN": "427-815-306-000", "SSS No.": "33-5820417-9"},
        {"Last Name": "Pagsisihan", "First Name": "Joel", "Middle Name": "Balagtas",
         "Gender": "Male", "Marital Status": "Single",
         "Complete Name of Spouse": None, "Nationality": "Filipino",   # single: doesn't apply
         "Present Address": MOTOR_ADDRESS, "Permanent Address": MOTOR_ADDRESS,
         "Residence Phone Number": "(044) 791-3582", "Mobile Number": "09285517492",
         "Email Address": "joel.pagsisihan@yahoo.com", "Zip Code": "3000",
         "Occupation": "Engineer", "Employer": "City Government of Malolos",
         "TIN": "508-163-274-000", "SSS No.": "04-2716385-2"},
    ])


def fire_survey():
    perils = {"Fire": "Moderate", "Earthquake": "Moderate", "Typhoon": "High", "Flood": "High",
              "Burglary/Robbery": "Low", "RSMD": "Low", "Landslide/Subsidence": "Low",
              "Smoke/Aircraft/Vehicle Impact/Explosion": "Low", "Volcanic Eruption": "Low",
              "Tsunami": "Moderate", "Terrorist Attack": "Low", "Spontaneous Combustion": "Low",
              "Machinery Breakdown": "Low", "General Liability": "Low", "Money": "Moderate",
              "Fidelity Guarantee": "Low", "Goods Transit": "Low", "Others": "Low"}
    row = {"Name of Insured": full(FIRE_NAME), "Contact Person": full(FIRE_NAME),
           "Brief Description of Owner's Business": "Sari-sari store with residence",
           "Location of Risk": FIRE_ADDRESS, "Tel/Fax No.": "09178642305", "Risk Class": "b",
           "Description": "Two-storey store and residential building",
           "Maximum Amount Subject": "3200000", "Loss Record": "With loss history: Flood, 2024",
           **perils,
           "Maintenance": "Fair", "Housekeeping": "Good", "Storage Arrangement": "Fair",
           "Safety/Security": "Fair", "Block Condition": "Fair", "Surrounding Community": "Fair",
           "Overall Risk Assessment": "Fair", "Surveyor Risk Acceptability": "Key Consideration",
           "Protection Facilities": "Fire Extinguisher, Flood Control, Power Supply, Water Supply",
           "District No./Block No.": "D-11 / B-087", "Current Block Accumulation": "PHP 14,350,000.00",
           "Zone": "Zone 2", "T.I.": "TI-112 (Store with Dwelling)",
           # parts add up to the total (no warning); M/E and BI/LOP don't apply
           "Occupancy - Building": "1850000", "Occupancy - Main Occupancy": "250000",
           "Occupancy - Stocks": "780000", "Occupancy - M/E": None, "Occupancy - FFF": "220000",
           "Occupancy - BI/LOP": None, "Occupancy - Others": "100000", "Occupancy - Total": "3200000",
           "Boundary - Front": "Barangay road", "Boundary - Right": "Residential house",
           "Boundary - Left": "Sari-sari store", "Boundary - Rear": "Fishpond",
           "Boundary - Sketch": "Refer to attached location sketch"}
    return pd.DataFrame([row])


def motor_quotation(quote_date):
    return pd.DataFrame([{
        "Date": quote_date.isoformat(), "Insured Name": full(MOTOR_NAME), "Address": MOTOR_ADDRESS,
        "Unit": "1", "Classification": "Private", "Color": "Silver", "Deductible": "4500",
        "Plate No.": "NDQ4817", "Total Amount Due": "27468.35", "Sum Insured": "900000",
        "Model": "2024", "Make": "Toyota", "Body Type": "Sedan", "Motor/Engine No.": "2TR-K481726",
        "Serial/Chassis No.": "MHFBW3F30R1048217", "Authorized Capacity": "5", "Bank": "BDO Unibank"}])


def fire_quotation(quote_date):
    return pd.DataFrame([{
        "Date": quote_date.isoformat(), "Name of Insured": full(FIRE_NAME),
        "Location of Risk": FIRE_ADDRESS,   # must equal the survey's text exactly
        "Period of Cover": "One (1) Year", "Property Sums Insured": "3200000",
        "Total Sum Insured": "3200000", "Total Premium": "13478.40",
        "Deductibles": "Fire/Lightning: NIL; Earthquake/Typhoon/Flood: 2% of ACV per claim; "
                       "Extended Cover: 1% of SI (min P1,000, max P500,000)",
        "Occupancy": "Store with Dwelling", "Basis of Evaluation": "Replacement Cost",
        "Perils Covered": "Fire and Lightning, Extended Coverage, Earthquake, Typhoon and Flood",
        "Line of Insurance": "Fire"}])


def replace_folder(path: Path):
    """Empty `path` for a fresh copy -- but only if it holds nothing except .xlsx files,
    so a mistyped path can never wipe anything else."""
    if path.exists():
        others = [p.name for p in path.iterdir() if p.suffix.lower() != ".xlsx"]
        if others:
            sys.exit(f"Refusing to replace {path}: it contains non-.xlsx items {others[:5]}.")
        shutil.rmtree(path)
    path.mkdir(parents=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quote-date", help="YYYY-MM-DD, 1-2 days before the demo (default: yesterday)")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help=f"output folder (default: {DEFAULT_OUT})")
    parser.add_argument("--copy-to", help="also copy the finished folder here (replaced if it exists)")
    args = parser.parse_args()

    today = dt.date.today()
    quote_date = dt.date.fromisoformat(args.quote_date) if args.quote_date else today - dt.timedelta(days=1)
    if quote_date > today:
        sys.exit(f"Refusing: quote date {quote_date} is in the future (today is {today}).")
    if (today - quote_date).days > 7:
        sys.exit(f"Refusing: quote date {quote_date} is more than 7 days ago -- use 1-2 days before the demo.")
    if (today - quote_date).days not in (1, 2):
        print(f"Warning: quote date {quote_date} is {(today - quote_date).days} day(s) before today; "
              f"1-2 days is the plan.")

    out = Path(args.out)
    replace_folder(out)
    files = {
        "1_customer_information.xlsx": customers(),
        "2_fire_survey.xlsx": fire_survey(),
        "3_motor_quotation.xlsx": motor_quotation(quote_date),
        "4_fire_quotation.xlsx": fire_quotation(quote_date),
    }
    for name, frame in files.items():
        frame.to_excel(out / name, index=False)
    print(f"Wrote {len(files)} files to {out} (quote date {quote_date}):")
    for name, frame in files.items():
        print(f"  {name}: {len(frame)} row(s), {len(frame.columns)} columns")

    if args.copy_to:
        dest = Path(args.copy_to)
        replace_folder(dest)
        for f in out.iterdir():
            shutil.copy2(f, dest / f.name)
        print(f"Copied to {dest}")


if __name__ == "__main__":
    main()
