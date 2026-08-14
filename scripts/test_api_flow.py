import requests
import json
import os

BASE_URL = "http://127.0.0.1:8000/api/v1"

def test_full_pipeline():
    print("--- Testing KarAI API Pipeline ---")
    
    # 1. Register User (or login if exists)
    reg_payload = {
        "email": "test.sme@karai.io",
        "password": "Password123!",
        "role": "sme_user"
    }
    r_reg = requests.post(f"{BASE_URL}/auth/register", json=reg_payload)
    print("Register Status:", r_reg.status_code, r_reg.text)
    
    # 2. Login User
    login_payload = {
        "email": "test.sme@karai.io",
        "password": "Password123!"
    }
    r_login = requests.post(f"{BASE_URL}/auth/login", json=login_payload)
    print("Login Status:", r_login.status_code, r_login.text)
    token_data = r_login.json()
    token = token_data.get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Upload Synthetic Dataset
    csv_file = "/Users/xniperker/Vault/KarAI/datasets/sample_gst_transactions_500.csv"
    with open(csv_file, "rb") as f:
        files = {"file": (os.path.basename(csv_file), f, "text/csv")}
        data = {"filing_period": "2025-Q1"}
        r_up = requests.post(f"{BASE_URL}/datasets/upload", headers=headers, files=files, data=data)
    print("Upload Status:", r_up.status_code, r_up.text)
    ds_data = r_up.json()
    dataset_id = ds_data["id"]
    print("Dataset ID:", dataset_id, "| Rows:", ds_data["row_count"])
    
    # 4. Run Anomaly Detection (Isolation Forest + SHAP)
    r_ml = requests.post(f"{BASE_URL}/analysis/run?dataset_id={dataset_id}&contamination=0.05", headers=headers)
    print("ML Analysis Status:", r_ml.status_code, r_ml.text)
    ml_data = r_ml.json()
    run_id = ml_data["id"]
    print("Model Run Metrics:", ml_data.get("metrics"))
    
    # 5. Run GST Compliance Check
    r_comp = requests.post(f"{BASE_URL}/compliance/check?dataset_id={dataset_id}&filing_period=2025-Q1", headers=headers)
    print("GST Compliance Status:", r_comp.status_code, r_comp.text)
    comp_data = r_comp.json()
    print("Compliance Score:", comp_data["compliance_score"], "/ 100 | Total Violations:", comp_data["total_violations"])
    
    # 6. Fetch Dashboard Summary
    r_dash = requests.get(f"{BASE_URL}/dashboard/summary?dataset_id={dataset_id}", headers=headers)
    print("Dashboard Status:", r_dash.status_code, r_dash.text)
    dash_data = r_dash.json()
    print("Overall Risk Level:", dash_data["overall_risk_level"], "| Risk Dist:", dash_data["risk_distribution"])
    
    # 7. Generate PDF Audit Report
    r_pdf = requests.post(f"{BASE_URL}/reports/generate?dataset_id={dataset_id}&report_type=pdf", headers=headers)
    print("Generate PDF Status:", r_pdf.status_code, r_pdf.text)
    pdf_info = r_pdf.json()
    print("Generated PDF Path:", pdf_info.get("file_path"))
    
    print("\n✅ KarAI API Pipeline Fully Functional!")

if __name__ == "__main__":
    test_full_pipeline()
