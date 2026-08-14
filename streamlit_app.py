import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as bg
import os
import sys

# Add backend directory to python path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from app.ml.engine import AnomalyEngine
from app.services.compliance import ComplianceValidator
from app.services.reports import ReportGenerator

st.set_page_config(
    page_title="KarAI — Admin & Model Evaluation Dashboard",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ KarAI — Admin & Model Evaluation Prototype")
st.caption("MAIT Delhi 7th Sem Minor Project | B.Tech CSE (Data Science)")

# Sidebar Configuration
st.sidebar.header("⚙️ Model & Sensitivity Settings")
contamination = st.sidebar.slider("Isolation Forest Contamination Ratio", min_value=0.01, max_value=0.20, value=0.05, step=0.01)
filing_period = st.sidebar.selectbox("Select Filing Period", ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"])

# File Uploader
uploaded_file = st.sidebar.file_uploader("Upload Transaction CSV", type=["csv"])

if uploaded_file is None:
    # Use synthetic sample file
    sample_path = "datasets/sample_gst_transactions_500.csv"
    if os.path.exists(sample_path):
        df = pd.read_csv(sample_path)
        st.info("Loaded default synthetic GST ledger (500 transactions). Upload your CSV in the sidebar to test custom datasets.")
    else:
        st.warning("Please upload a CSV file.")
        st.stop()
else:
    df = pd.read_csv(uploaded_file)

# Run ML Engine & Compliance Check
with st.spinner("Executing Isolation Forest & SHAP TreeExplainer..."):
    anomalies_list, metrics = AnomalyEngine.run_detection(df, contamination=contamination)
    score, violations, v_counts = ComplianceValidator.validate_dataset(df, filing_period=filing_period)

# Executive Metrics Cards
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Transactions", f"{len(df):,}")
col2.metric("Compliance Health Score", f"{score:.1f} / 100", delta=f"-{100 - score:.1f} pts" if score < 100 else "Optimal")
col3.metric("Flagged ML Anomalies", f"{metrics.get('high_risk_count', 0) + metrics.get('critical_count', 0):,}")
col4.metric("GST Rule Violations", f"{v_counts['total_violations']:,}")

st.divider()

# Tab Navigation
tab1, tab2, tab3, tab4 = st.tabs(["📊 ML Anomaly Dashboard", "📜 GST Compliance Rules", "🔍 SHAP Explainability", "📥 Export Audit Reports"])

with tab1:
    st.subheader("Isolation Forest Anomaly Distribution")
    
    anom_df = pd.DataFrame(anomalies_list)
    df_merged = df.copy()
    df_merged["anomaly_score"] = anom_df["anomaly_score"]
    df_merged["risk_category"] = anom_df["risk_category"]
    
    c1, c2 = st.columns([2, 1])
    
    with c1:
        fig_scatter = px.scatter(
            df_merged,
            x="amount",
            y="anomaly_score",
            color="risk_category",
            hover_data=["transaction_id", "party_name", "gstin"],
            log_x=True,
            title="Transaction Amount vs Anomaly Risk Score",
            color_discrete_map={"normal": "#10B981", "suspicious": "#3B82F6", "high_risk": "#F59E0B", "critical": "#EF4444"}
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
        
    with c2:
        risk_counts = df_merged["risk_category"].value_counts().reset_index()
        risk_counts.columns = ["risk_category", "count"]
        fig_pie = px.pie(
            risk_counts,
            names="risk_category",
            values="count",
            title="Risk Category Breakdown",
            hole=0.5,
            color="risk_category",
            color_discrete_map={"normal": "#10B981", "suspicious": "#3B82F6", "high_risk": "#F59E0B", "critical": "#EF4444"}
        )
        st.plotly_chart(fig_pie, use_container_width=True)

with tab2:
    st.subheader("GST Regulatory Violations")
    if violations:
        v_df = pd.DataFrame(violations)
        st.dataframe(v_df[["transaction_id", "violation_type", "severity", "description", "remediation"]], use_container_width=True)
    else:
        st.success("No GST violations detected.")

with tab3:
    st.subheader("Per-Prediction SHAP Feature Importance")
    high_risk_txns = df_merged[df_merged["risk_category"].isin(["high_risk", "critical"])]
    if not high_risk_txns.empty:
        selected_txn_id = st.selectbox("Select Flagged Transaction for Explanation", high_risk_txns["transaction_id"].unique())
        selected_row = df_merged[df_merged["transaction_id"] == selected_txn_id].iloc[0]
        
        selected_idx = selected_row.name
        shap_values = anomalies_list[selected_idx]["shap_values"]
        
        st.write(f"**Party Name:** {selected_row['party_name']} | **Amount:** ₹{selected_row['amount']:,.2f} | **Risk Score:** `{anomalies_list[selected_idx]['anomaly_score']:.4f}`")
        
        shap_df = pd.DataFrame(list(shap_values.items()), columns=["Feature", "SHAP Value"]).sort_values(by="SHAP Value", ascending=True)
        fig_shap = px.bar(
            shap_df,
            x="SHAP Value",
            y="Feature",
            orientation="h",
            color="SHAP Value",
            color_continuous_scale="RdYlGn_r",
            title=f"SHAP TreeExplainer Contribution for {selected_txn_id}"
        )
        st.plotly_chart(fig_shap, use_container_width=True)
    else:
        st.info("No high-risk transactions to display.")

with tab4:
    st.subheader("Generate Audit Reports")
    col_pdf, col_excel = st.columns(2)
    
    with col_pdf:
        if st.button("📄 Generate ReportLab PDF Audit Report"):
            pdf_path = ReportGenerator.generate_pdf_report(
                report_id="streamlit_demo",
                dataset_name="GST_Ledger.csv",
                filing_period=filing_period,
                compliance_score=score,
                total_txns=len(df),
                flagged_count=len(df_merged[df_merged["risk_category"].isin(["high_risk", "critical"])]),
                violations=violations,
                anomalies=anomalies_list
            )
            with open(pdf_path, "rb") as f:
                st.download_button("Download Audit PDF", f, file_name=os.path.basename(pdf_path), mime="application/pdf")
                
    with col_excel:
        if st.button("📊 Export openpyxl Excel Ledger"):
            excel_path = ReportGenerator.generate_excel_report(
                report_id="streamlit_demo",
                df_txns=df,
                results=anomalies_list,
                violations=violations
            )
            with open(excel_path, "rb") as f:
                st.download_button("Download Excel File", f, file_name=os.path.basename(excel_path), mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
