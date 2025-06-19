import streamlit as st
import pdfplumber
import re

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
            raw_lines.extend(page.extract_text().splitlines())

    # Fix common line splits (Hydrochloric acid, Crystalline silica)
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
    if not skip_next:
        fixed_lines.append(raw_lines[-1].strip())

    def find_float(pattern):
        for line in fixed_lines:
            if pattern in line:
                numbers = re.findall(r"\d+\.\d+", line)
                if numbers:
                    return float(numbers[-1])
        return None

    def find_by_cas(cas):
        for line in fixed_lines:
            if cas in line:
                numbers = re.findall(r"\d+\.\d+", line)
                if numbers:
                    return float(numbers[-1])
        return None

    total_water = re.search(r"Total Base Water Volume.*?:\s*(\d+)", "\n".join(fixed_lines), re.IGNORECASE)
    return {
        "total_water_volume": int(total_water.group(1)) if total_water else None,
        "water_percent": find_float("Water 7732-18-5"),
        "hcl_percent": find_by_cas("7647-01-0"),
        "proppant_percent": find_by_cas("14808-60-7"),
        "gas_percent": 0.0  # default fallback
    }

# === Calculation Logic ===
def calculate(total_water_volume, water_percent, hcl_percent, proppant_percent, gas_percent=0):
    total_water_weight = total_water_volume * 8.3454
    total_acid_hcl_weight = (hcl_percent / 100) * total_water_weight
    total_acid_hcl_volume = total_acid_hcl_weight / 8.95
    total_acid_hcl_volume_bbl = total_acid_hcl_volume / 42
    total_proppant_weight = (proppant_percent / 100) * total_water_weight
    proppant_volume_tons = total_proppant_weight / 2000
    total_ff_fluid_volume = total_water_volume - total_acid_hcl_volume
    total_ff_fluid_volume_bbl = total_ff_fluid_volume / 42
    proppant_to_fluid_ratio = total_proppant_weight / total_ff_fluid_volume if total_ff_fluid_volume else float("nan")
    nitrogen_volume = (gas_percent / 100 * total_water_weight) * 13.803 if gas_percent else float("nan")
    co2_weight = (gas_percent / 100 * total_water_weight) / 2000 if gas_percent else float("nan")

    return {
        "Total Water Weight (lbs)": total_water_weight,
        "Total Acid HCL Weight (lbs)": total_acid_hcl_weight,
        "Total Acid HCL Volume (gallons)": total_acid_hcl_volume,
        "Total Acid HCL Volume (bbl)": total_acid_hcl_volume_bbl,
        "Total Proppant Weight (lbs)": total_proppant_weight,
        "Proppant Volume (tons)": proppant_volume_tons,
        "Total FF Fluid Volume (gallons)": total_ff_fluid_volume,
        "Total FF Fluid Volume (bbl)": total_ff_fluid_volume_bbl,
        "Proppant to Fluid Ratio (PPG)": proppant_to_fluid_ratio,
        "Total Volume of Nitrogen (SCF)": nitrogen_volume,
        "Total Weight of CO2 (tons)": co2_weight
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
    total_water_volume = st.number_input("Total Base Water Volume (gallons)", value=float(values["total_water_volume"] or 0), step=1.0, format="%.0f")
    water_percent = st.number_input("Water Concentration (%)", value=values["water_percent"] or 0.0, step=0.0001, format="%.5f")
    hcl_percent = st.number_input("HCL Concentration (%)", value=values["hcl_percent"] or 0.0, step=0.0001, format="%.5f")
    proppant_percent = st.number_input("Proppant Concentration (%)", value=values["proppant_percent"] or 0.0, step=0.0001, format="%.5f")
    gas_percent = st.number_input("Gas (Nitrogen or CO₂) Concentration (%)", value=values.get("gas_percent", 0.0), step=0.0001, format="%.5f")


    submitted = st.form_submit_button("Calculate")

# === Show Results ===
if submitted:
    result = calculate(total_water_volume, water_percent, hcl_percent, proppant_percent, gas_percent)
    st.markdown("### 🧮 Calculation Results:")
    for key, val in result.items():
        unit = key.split("(")[-1].replace(")", "") if "(" in key else ""
        if isinstance(val, float):
            st.markdown(f"**{key}:** {val:,.2f} {unit}")
