import streamlit as st
import pandas as pd
import pdfplumber
from docx import Document
import re

st.set_page_config(page_title="Logistics Billing Checker", layout="centered")

st.title("📦 Logistics Billing Checker (Multi-Format)")
st.write("Upload Invoice and Contract in PDF, DOCX, Excel, or CSV format")

# -------- Column Normalization -------- #

def normalize_column_name(col):
    col = col.strip().lower()
    col = re.sub(r'[^a-z0-9]', '_', col)
    col = re.sub(r'_+', '_', col)
    return col

def standardize_columns(df):
    df.columns = [normalize_column_name(c) for c in df.columns]
    return df

# -------- PDF Extraction -------- #

def extract_pdf(uploaded_file):
    with pdfplumber.open(uploaded_file) as pdf:
        tables = []
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                df = pd.DataFrame(table[1:], columns=table[0])
                tables.append(df)
        if tables:
            df = pd.concat(tables, ignore_index=True)
            return standardize_columns(df)
    return None

# -------- DOCX Extraction -------- #

def extract_docx(uploaded_file):
    doc = Document(uploaded_file)
    tables = []

    for table in doc.tables:
        data = []
        for row in table.rows:
            data.append([cell.text for cell in row.cells])
        df = pd.DataFrame(data[1:], columns=data[0])
        tables.append(df)

    if tables:
        df = pd.concat(tables, ignore_index=True)
        return standardize_columns(df)

    return None

# -------- Excel / CSV -------- #

def extract_excel(uploaded_file):
    df = pd.read_excel(uploaded_file)
    return standardize_columns(df)

def extract_csv(uploaded_file):
    df = pd.read_csv(uploaded_file)
    return standardize_columns(df)

# -------- Universal Loader -------- #

def load_file(uploaded_file):
    file_name = uploaded_file.name.lower()

    if file_name.endswith(".pdf"):
        return extract_pdf(uploaded_file)
    elif file_name.endswith(".docx"):
        return extract_docx(uploaded_file)
    elif file_name.endswith(".xlsx"):
        return extract_excel(uploaded_file)
    elif file_name.endswith(".csv"):
        return extract_csv(uploaded_file)
    else:
        return None

# -------- Column Mapping -------- #

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

# -------- File Upload -------- #

invoice_file = st.file_uploader("Upload Invoice", type=["pdf", "docx", "xlsx", "csv"])
contract_file = st.file_uploader("Upload Contract", type=["pdf", "docx", "xlsx", "csv"])

if invoice_file and contract_file:

    invoice_df = load_file(invoice_file)
    contract_df = load_file(contract_file)

    if invoice_df is None or contract_df is None:
        st.error("Unsupported file format or extraction failed.")
        st.stop()

    invoice_df = map_columns(invoice_df, invoice_column_map)
    contract_df = map_columns(contract_df, contract_column_map)

    # Convert numeric fields
    invoice_df["weight"] = invoice_df["weight"].astype(float)
    invoice_df["billed_amount"] = invoice_df["billed_amount"].astype(float)
    contract_df["rate_per_kg"] = contract_df["rate_per_kg"].astype(float)
    contract_df["cod_rate"] = contract_df["cod_rate"].astype(float)
    contract_df["rto_rate"] = contract_df["rto_rate"].astype(float)

    # Duplicate Detection
    invoice_df["duplicate"] = invoice_df.duplicated("awb", keep=False)

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