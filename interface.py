import streamlit as st
import pdfplumber
import re
import pandas as pd
import math

st.set_page_config(page_title="Frac Fluid Calculator", layout="centered")

st.title("🧪 Frac Fluid Calculation Tool")
st.markdown("Upload a FracFocus PDF or enter values manually to calculate fluid volumes.")

# --- PDF Upload ---
uploaded_file = st.file_uploader("📄 Upload FracFocus PDF", type=["pdf"])

# === PDF Extraction ===
def extract_values_from_pdf(file):
    with pdfplumber.open(file) as pdf:
        raw_lines = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                raw_lines.extend(text.splitlines())

    # Fix common line splits
    fixed_lines = []
    skip_next = False
    for i in range(len(raw_lines) - 1):
        if skip_next:
            skip_next = False
            continue
        current = raw_lines[i].strip()
        next_line = raw_lines[i + 1].strip()
        if current.lower() == "hydrochloric" and next_line.lower().startswith("acid"):
            fixed_lines.append(f"{current} {next_line}")
            skip_next = True
        elif current.lower() == "crystalline" and next_line.lower().startswith("silica"):
            fixed_lines.append(f"{current} {next_line}")
            skip_next = True
        else:
            fixed_lines.append(current)
    if not skip_next and raw_lines:
        fixed_lines.append(raw_lines[-1].strip())

    def find_number(pattern):
        for line in fixed_lines:
            if pattern in line:
                nums = re.findall(r"\d+(?:\.\d+)?", line)
                if nums:
                    return float(nums[-1])
        return None

    def find_by_cas(cas):
        for line in fixed_lines:
            if cas in line:
                nums = re.findall(r"\d+(?:\.\d+)?", line)
                if nums:
                    return float(nums[-1])
        return None

    total_water = re.search(r"Total Base Water Volume.*?:\s*(\d+)", "\n".join(fixed_lines), re.IGNORECASE)

    return {
        "total_water_volume": int(total_water.group(1)) if total_water else None,
        "water_percent": find_number("Water 7732-18-5"),
        "hcl_percent": find_by_cas("7647-01-0"),
        "proppant_percent": find_by_cas("14808-60-7"),
        "gas_percent": 0.0
    }

# === Calculation Logic ===
def calculate(total_water_volume, water_percent, hcl_percent, proppant_percents, gas_percent, gas_type):
    # Constants
    WATER_DENSITY_LBPGAL = 8.3454
    HCL_DENSITY_LBPGAL = 8.95  # for 15% HCL solution
    GALLONS_PER_BBL = 42

    total_proppant_percent = sum(proppant_percents)
    total_mass_percent = (water_percent or 0) + (hcl_percent or 0) + total_proppant_percent

    # Convert volumes to weights
    total_water_weight = total_water_volume * WATER_DENSITY_LBPGAL

    # Acid calculations
    total_acid_weight = (hcl_percent / 100) * total_water_weight if hcl_percent else 0
    total_acid_volume_gal = total_acid_weight / HCL_DENSITY_LBPGAL if total_acid_weight else 0
    total_acid_volume_bbl = total_acid_volume_gal / GALLONS_PER_BBL if total_acid_volume_gal else 0

    # FF fluid volume (subtract acid job volume)
    total_ff_fluid_volume_gal = total_water_volume - total_acid_volume_gal
    total_ff_fluid_volume_bbl = total_ff_fluid_volume_gal / GALLONS_PER_BBL if total_ff_fluid_volume_gal else 0

    # Proppant
    total_proppant_weight = (total_proppant_percent / 100) * total_water_weight if total_proppant_percent else 0
    proppant_weight_tons = total_proppant_weight / 2000 if total_proppant_weight else 0
    ppg = total_proppant_weight / total_ff_fluid_volume_gal if total_ff_fluid_volume_gal else math.nan

    # Gas (Nitrogen vs CO2)
    nitrogen_volume_scf = None
    co2_weight_tons = None
    gas_weight_lbs = None

    if gas_type == "Nitrogen (N2)" and gas_percent > 0:
        gas_weight_lbs = (gas_percent / 100) * total_water_weight
        nitrogen_volume_scf = gas_weight_lbs * 13.803
    elif gas_type == "Carbon Dioxide (CO2)" and gas_percent > 0:
        gas_weight_lbs = (gas_percent / 100) * total_water_weight
        co2_weight_tons = gas_weight_lbs / 2000

    return {
        "Total % Mass (Water+Acid+Proppant)": total_mass_percent,
        "Total Water Weight (lbs)": total_water_weight,
        "Total Acid(HCL) Weight (lbs)": total_acid_weight,
        "Total Acid(HCL) Volume (gal)": total_acid_volume_gal,
        "Total Acid(HCL) Volume (bbl)": total_acid_volume_bbl,
        "Total FF Fluid Volume (gal)": total_ff_fluid_volume_gal,
        "Total FF Fluid Volume (bbl)": total_ff_fluid_volume_bbl,
        "Total Proppant Weight (lbs)": total_proppant_weight,
        "Proppant Weight (tons)": proppant_weight_tons,
        "Proppant to Fluid Ratio (PPG)": ppg,
        "Total Gas Weight (lbs)": gas_weight_lbs,
        "Total CO2 Weight (tons)": co2_weight_tons,
        "Total Nitrogen Volume (SCF)": nitrogen_volume_scf
    }

# === Autofill from PDF ===
values = {
    "total_water_volume": None,
    "water_percent": None,
    "hcl_percent": None,
    "proppant_percent": None,
    "gas_percent": 0.0
}
if uploaded_file:
    st.success("✅ PDF uploaded. Extracting values...")
    values.update(extract_values_from_pdf(uploaded_file))

# === Input Form ===
with st.form("calc_form"):
    total_water_volume = st.number_input(
        "Total Base Water Volume (gallons)", 
        value=float(values["total_water_volume"] or 0), step=1.0, format="%.0f"
    )
    water_percent = st.number_input("Water Concentration (%)", value=values["water_percent"] or 0.0, step=0.0001)
    hcl_percent = st.number_input("HCL Concentration (%)", value=values["hcl_percent"] or 0.0, step=0.0001)

    st.markdown("### Proppant Concentrations (%)")
    proppant_percents = []
    for i in range(1, 7):
        val = values["proppant_percent"] if i == 1 else 0.0
        p = st.number_input(f"Proppant {i} (%)", value=val, step=0.0001)
        proppant_percents.append(p)

    gas_type = st.selectbox("Gas Type", ["None", "Nitrogen (N2)", "Carbon Dioxide (CO2)"])
    gas_percent = st.number_input("Gas Concentration (%)", value=values.get("gas_percent", 0.0), step=0.0001)

    submitted = st.form_submit_button("Calculate")

# === Show Results ===
if submitted:
    result = calculate(total_water_volume, water_percent, hcl_percent, proppant_percents, gas_percent, gas_type)
    
    st.markdown("### 🧮 Calculation Results")
    df = pd.DataFrame([result])
    st.dataframe(df.style.format("{:,.2f}"))

    # Highlight mass balance check
    if result["Total % Mass (Water+Acid+Proppant)"] < 90 or result["Total % Mass (Water+Acid+Proppant)"] > 110:
        st.warning("⚠️ Mass balance outside 90–110%. Please verify input values.")
