import streamlit as st
import pandas as pd
import pdfplumber
import re

st.set_page_config(page_title="Logistics Billing Checker", layout="centered")

st.title("📦 Logistics Billing Checker (PDF Version)")
st.write("Upload Invoice and Contract Rate Card in PDF format")

# -------- Column Normalization -------- #

def normalize_column_name(col):
    col = col.strip().lower()
    col = re.sub(r'[^a-z0-9]', '_', col)   # remove special characters
    col = re.sub(r'_+', '_', col)          # remove multiple underscores
    return col

def standardize_columns(df):
    df.columns = [normalize_column_name(c) for c in df.columns]
    return df

# -------- PDF Extraction -------- #

def extract_pdf_table(uploaded_file):
    with pdfplumber.open(uploaded_file) as pdf:
        all_tables = []

        for page in pdf.pages:
            table = page.extract_table()
            if table:
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append(df)

        if all_tables:
            df = pd.concat(all_tables, ignore_index=True)
            df = standardize_columns(df)
            return df

        return None

# -------- File Upload -------- #

invoice_file = st.file_uploader("Upload Invoice (PDF)", type=["pdf"])
contract_file = st.file_uploader("Upload Contract (PDF)", type=["pdf"])

if invoice_file and contract_file:

    invoice_df = extract_pdf_table(invoice_file)
    contract_df = extract_pdf_table(contract_file)

    if invoice_df is None or contract_df is None:
        st.error("❌ Could not extract table from one of the PDFs.")
        st.stop()

    # -------- Flexible Column Mapping -------- #

    invoice_column_map = {
        "awb": ["awb", "awb_no", "tracking_id"],
        "weight": ["weight", "weight_kg", "chargeable_weight"],
        "zone": ["zone"],
        "billed_amount": ["billed_amount", "total_amount", "amount"]
    }

    contract_column_map = {
        "zone": ["zone"],
        "rate_per_kg": ["rate_per_kg", "rate", "freight_rate"],
        "cod_rate": ["cod_rate", "cod"],
        "rto_rate": ["rto_rate", "rto"]
    }

    def map_columns(df, column_map):
        mapped_df = pd.DataFrame()

        for standard_col, possible_names in column_map.items():
            found = False
            for name in possible_names:
                if name in df.columns:
                    mapped_df[standard_col] = df[name]
                    found = True
                    break
            if not found:
                st.error(f"Missing required column: {standard_col}")
                st.stop()

        return mapped_df

    invoice_df = map_columns(invoice_df, invoice_column_map)
    contract_df = map_columns(contract_df, contract_column_map)

    # -------- Type Conversion -------- #

    invoice_df["weight"] = invoice_df["weight"].astype(float)
    invoice_df["billed_amount"] = invoice_df["billed_amount"].astype(float)
    contract_df["rate_per_kg"] = contract_df["rate_per_kg"].astype(float)
    contract_df["cod_rate"] = contract_df["cod_rate"].astype(float)
    contract_df["rto_rate"] = contract_df["rto_rate"].astype(float)

    # -------- Duplicate Detection -------- #

    invoice_df["duplicate"] = invoice_df.duplicated("awb", keep=False)

    # -------- Merge -------- #

    merged = invoice_df.merge(contract_df, on="zone", how="left")

    merged["verified_amount"] = (
        merged["weight"] * merged["rate_per_kg"]
        + merged["cod_rate"]
        + merged["rto_rate"]
    )

    merged["status"] = merged.apply(
        lambda x: "ERROR"
        if abs(x["billed_amount"] - x["verified_amount"]) > 1 or x["duplicate"]
        else "OK",
        axis=1
    )

    discrepancy_df = merged[merged["status"] == "ERROR"]
    payout_df = merged[merged["status"] == "OK"][["awb", "verified_amount"]]

    # -------- Dashboard -------- #

    st.subheader("📊 Summary Dashboard")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Billed", round(merged["billed_amount"].sum(), 2))
    col2.metric("Total Verified", round(merged["verified_amount"].sum(), 2))
    col3.metric("Errors Found", len(discrepancy_df))

    st.subheader("⚠ Discrepancy Report")
    st.dataframe(discrepancy_df)

    st.subheader("✅ Payout Ready File")
    st.dataframe(payout_df)

    st.download_button(
        "Download Payout File",
        payout_df.to_csv(index=False),
        "payout_ready.csv",
        "text/csv"
    )

    st.download_button(
        "Download Discrepancy Report",
        discrepancy_df.to_csv(index=False),
        "discrepancy_report.csv",
        "text/csv"
    )