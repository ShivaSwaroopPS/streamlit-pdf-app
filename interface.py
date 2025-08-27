import streamlit as st
import pdfplumber
import re
import pandas as pd
import math
import random
import time

st.set_page_config(page_title="Frac Fluid Calculator", layout="wide")

# === Custom CSS Styling & Animations ===
st.markdown("""
<style>
/* Full black background */
body {
    background-color: #000000;
    color: white;
}

/* 🔥 Fire Typewriter Effect (bright + visible) */
.typewriter {
  font-size: 36px;        /* smaller size */
  font-weight: bold;
  color: #ffff66;         /* bright yellow text for visibility */
  display: inline-block;
  overflow: hidden;
  border-right: .15em solid #ff4500; /* blinking fire cursor */
  white-space: nowrap;
  letter-spacing: .1em;
  width: 0;
  animation: typing 4s steps(40, end) forwards,   /* type once & stay */
             blink .75s step-end infinite,
             fireglow 1s infinite alternate;
  text-shadow:
     0 0 10px #ff6600,
     0 0 20px #ff3300,
     0 0 30px #ff0000,
     0 0 40px #ff2200;
}

/* Type once then stop */
@keyframes typing {
  from { width: 0 }
  to { width: 40ch }   /* match text length */
}

/* Cursor blink */
@keyframes blink {
  50% { border-color: transparent }
}

/* Fire glow flicker */
@keyframes fireglow {
  from { text-shadow: 0 0 10px #ff6600, 0 0 20px #ff3300, 0 0 30px #ff0000; }
  to   { text-shadow: 0 0 15px #ffaa00, 0 0 25px #ff5500, 0 0 35px #ff2200; }
}
</style>
""", unsafe_allow_html=True)

# === Title with fire typing effect ===
st.markdown(
    '<div style="text-align:center;"><span class="typewriter">🧪 Frac Fluid Calculation Tool v2.0</span></div>',
    unsafe_allow_html=True
)

# === Subtitle (smaller + grey) ===
st.markdown("""
<p style='text-align:center; font-size:12px; color: #888888;'>
Upload a FracFocus PDF or enter values manually to calculate fluid volumes.
</p>
""", unsafe_allow_html=True)

# --- PDF Extraction ---
def extract_values_from_pdf(file):
    raw_lines = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                raw_lines.extend(text.splitlines())

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

    total_water = re.search(
        r"Total Base Water Volume.*?:\s*(\d+)",
        "\n".join(fixed_lines),
        re.IGNORECASE
    )

    return {
        "total_water_volume": int(total_water.group(1)) if total_water else None,
        "water_percent": find_number("Water 7732-18-5"),
        "hcl_percent": find_by_cas("7647-01-0"),
        "proppant_percent": find_by_cas("14808-60-7"),
        "gas_percent": 0.0,
        "raw_lines": fixed_lines
    }

# --- Calculation Logic ---
def calculate(total_water_volume, water_percent, hcl_percent, proppant_percents, gas_percent, gas_type):
    WATER_DENSITY_LBPGAL = 8.3454
    HCL_DENSITY_LBPGAL = 8.95
    GALLONS_PER_BBL = 42

    total_proppant_percent = sum(proppant_percents)
    total_mass_percent = (water_percent or 0) + (hcl_percent or 0) + total_proppant_percent

    total_water_weight = total_water_volume * WATER_DENSITY_LBPGAL
    total_acid_weight = (hcl_percent / 100) * total_water_weight if hcl_percent else 0
    total_acid_volume_gal = total_acid_weight / HCL_DENSITY_LBPGAL if total_acid_weight else 0
    total_acid_volume_bbl = total_acid_volume_gal / GALLONS_PER_BBL if total_acid_volume_gal else 0

    total_ff_fluid_volume_gal = total_water_volume - total_acid_volume_gal
    total_ff_fluid_volume_bbl = total_ff_fluid_volume_gal / GALLONS_PER_BBL if total_ff_fluid_volume_gal else 0

    total_proppant_weight = (total_proppant_percent / 100) * total_water_weight if total_proppant_percent else 0
    proppant_weight_tons = total_proppant_weight / 2000 if total_proppant_weight else 0
    ppg = total_proppant_weight / total_ff_fluid_volume_gal if total_ff_fluid_volume_gal else math.nan

    nitrogen_volume_scf = None
    co2_weight_tons = None
    gas_weight_lbs = None
    remark = ""

    if gas_type == "Nitrogen (N2)" and gas_percent > 0:
        gas_weight_lbs = (gas_percent / 100) * total_water_weight
        nitrogen_volume_scf = gas_weight_lbs * 13.803
        remark = f"Nitrogen included at {gas_percent:.2f}% → {nitrogen_volume_scf:.0f} SCF estimated."
    elif gas_type == "Carbon Dioxide (CO2)" and gas_percent > 0:
        gas_weight_lbs = (gas_percent / 100) * total_water_weight
        co2_weight_tons = gas_weight_lbs / 2000
        remark = f"CO₂ included at {gas_percent:.2f}% → {co2_weight_tons:.2f} tons estimated."
    else:
        remark = "No gas contribution reported."

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
        "Total Nitrogen Volume (SCF)": nitrogen_volume_scf,
        "Remarks": remark
    }

# === Single Well Mode ===
st.markdown("##  Single Well Mode")

uploaded_file = st.file_uploader("📄 Upload a single FracFocus PDF", type=["pdf"], key="single")

values = {
    "total_water_volume": None,
    "water_percent": None,
    "hcl_percent": None,
    "proppant_percent": None,
    "gas_percent": 0.0,
    "raw_lines": []
}
if uploaded_file:
    st.success("✅ Targets acquired, numbers incoming….")
    values.update(extract_values_from_pdf(uploaded_file))

with st.sidebar:
    st.header("⚙️ Inputs (Single Well)")
    total_water_volume = st.number_input("Total Base Water Volume (gallons)", value=float(values["total_water_volume"] or 0), step=1.0, format="%.0f")
    water_percent = st.number_input("Water Concentration (%)", value=values["water_percent"] or 0.0, step=0.0001)
    hcl_percent = st.number_input("HCL Concentration (%)", value=values["hcl_percent"] or 0.0, step=0.0001)

    st.subheader("Proppant Concentrations (%)")
    proppant_percents = []
    for i in range(1, 7):
        val = values["proppant_percent"] if i == 1 else 0.0
        p = st.number_input(f"Proppant {i} (%)", value=val, step=0.0001)
        proppant_percents.append(p)

    gas_type = st.selectbox("Gas Type", ["None", "Nitrogen (N2)", "Carbon Dioxide (CO2)"])
    gas_percent = st.number_input("Gas Concentration (%)", value=values.get("gas_percent", 0.0), step=0.0001)

submitted = st.button(" Calculate (Single Well)")

if submitted:
    result = calculate(total_water_volume, water_percent, hcl_percent, proppant_percents, gas_percent, gas_type)

    # KPI Cards
    col1, col2, col3 = st.columns(3)
    col1.metric("FF Fluid Volume (bbl)", f"{result['Total FF Fluid Volume (bbl)']:.2f}")
    col2.metric("Proppant to Fluid Ratio (PPG)", f"{result['Proppant to Fluid Ratio (PPG)']:.2f}")
    col3.metric("% Mass", f"{result['Total % Mass (Water+Acid+Proppant)']:.2f}%")

    st.markdown("### 🧮 Detailed Results")
    for key, val in result.items():
        if isinstance(val, (int, float)) and not pd.isna(val):
            st.write(f"**{key}:** {val:.2f}")
        elif val is not None:
            st.write(f"**{key}:** {val}")

    st.info(f" {result['Remarks']}")

    if result["Total % Mass (Water+Acid+Proppant)"] < 90 or result["Total % Mass (Water+Acid+Proppant)"] > 110:
        st.warning("⚠️ Mass balance outside 90–110%. Please verify input values.")

    # Copy-as-CSV
    df = pd.DataFrame([result])
    tsv_text = df.to_csv(index=False, sep="\t", float_format="%.2f")
    st.text_area("📋 Copy Results (Excel-friendly)", tsv_text, height=200)
    st.caption("Tip: Ctrl+A → Ctrl+C → Paste into Excel → splits into columns.")

    # Excel Export
    excel_file = "frac_fluid_results.xlsx"
    df.to_excel(excel_file, index=False)
    with open(excel_file, "rb") as f:
        st.download_button("⬇️ Download Excel", f, file_name=excel_file, mime="application/vnd.ms-excel")

    # Debug Panel
    with st.expander("🔍 Debug Panel: Extracted PDF Lines"):
        col1, col2 = st.columns(2)
        col1.markdown("**Raw PDF Lines**")
        col1.write(values["raw_lines"])
        col2.markdown("**Parsed Values**")
        col2.write(values)

# === Multi-Well Batch Mode ===
st.markdown("---")
st.markdown("##  Multi-Well Batch Mode")

fun_phrases = [
    "🚀 Now we are talking!",
    "🔥 Welcome to Beast Mode!",
    "⚡ Buckle up, big jobs ahead…",
    "💪 Time to crush multi-well madness!",
    "🎯 Precision loading multiple PDFs…",
    "🌋 Explosive data power unlocked!",
    "🛢 Big data needs big energy!",
    "⚔️ Entering Power User Mode…",
    "🎮 God Mode Activated…",
    "🔮 Multi-Well Magic starts now!"
]

if "show_batch" not in st.session_state:
    st.session_state.show_batch = False

if not st.session_state.show_batch:
    if st.button("🐉 Multi-Wells, Batch Mode"):
        phrase = random.choice(fun_phrases)
        st.success(phrase)
        time.sleep(1.5)
        st.session_state.show_batch = True
        st.rerun()
else:
    st.markdown("### 📂 Upload Multiple PDFs")
    uploaded_files = st.file_uploader("Upload multiple FracFocus PDFs", type=["pdf"], accept_multiple_files=True, key="multi")

    if uploaded_files:
        all_results = []
        for file in uploaded_files:
            try:
                vals = extract_values_from_pdf(file)
                calc = calculate(
                    vals["total_water_volume"] or 0,
                    vals["water_percent"] or 0.0,
                    vals["hcl_percent"] or 0.0,
                    [vals["proppant_percent"] or 0.0],
                    vals["gas_percent"] or 0.0,
                    "None"
                )
                calc["File"] = file.name
                all_results.append(calc)
            except Exception as e:
                st.error(f"❌ Failed to process {file.name}: {e}")

        if all_results:
            batch_df = pd.DataFrame(all_results)
            st.markdown("### 📊 Batch Results Summary")
            st.dataframe(batch_df)

            excel_file = "multi_well_results.xlsx"
            batch_df.to_excel(excel_file, index=False)
            with open(excel_file, "rb") as f:
                st.download_button("⬇️ Download All Results (Excel)", f, file_name=excel_file, mime="application/vnd.ms-excel")



