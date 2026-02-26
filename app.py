import streamlit as st
import pandas as pd

st.set_page_config(page_title="Logistics Billing Checker", layout="centered")

st.title("📦 Logistics Billing Checker")
st.write("Upload Invoice (CSV) and Contract Rate Card (Excel)")

invoice_file = st.file_uploader("Upload Invoice (CSV)", type=["csv"])
contract_file = st.file_uploader("Upload Contract (Excel)", type=["xlsx"])

if invoice_file and contract_file:

    invoice_df = pd.read_csv(invoice_file)
    contract_df = pd.read_excel(contract_file)

    invoice_df.fillna(0, inplace=True)

    # Duplicate AWB detection
    invoice_df["duplicate"] = invoice_df.duplicated("awb", keep=False)

    merged = invoice_df.merge(contract_df, on="zone", how="left")

    merged["verified_amount"] = (
        merged["weight"] * merged["rate_per_kg"]
        + merged["cod_rate"]
        + merged["rto_rate"]
    )

    merged["status"] = merged.apply(
        lambda x: "ERROR" if abs(x["billed_amount"] - x["verified_amount"]) > 1 or x["duplicate"] else "OK",
        axis=1
    )

    discrepancy_df = merged[merged["status"] == "ERROR"]
    payout_df = merged[merged["status"] == "OK"][["awb", "verified_amount"]]

    st.subheader("📊 Summary")

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