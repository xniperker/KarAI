# KarAI — Automated Tax Compliance & Anomaly Detection Platform

> **7th Semester Minor Project**  
> **Institution:** Maharaja Agrasen Institute of Technology (MAIT), Delhi (Affiliated to GGSIPU)  
> **Department:** Computer Science & Engineering (Data Science)  
> **Team:** Harsh Arora | Nikhil Bokaria | Himanshu Bhushan  

---

## 📌 Executive Summary

**KarAI** is an intelligent, web-based audit platform designed for Indian SMEs and taxpayers. It ingests financial ledger transaction datasets (CSV), runs **Isolation Forest Machine Learning** for unsupervised financial anomaly detection, generates **SHAP TreeExplainer feature explanations** per flagged item, and validates records against **GST Compliance Rules (RULE-001 to RULE-006)**.

---

## 🛠️ Architecture & Tech Stack

- **Core Backend Framework:** Python 3.12, FastAPI, Uvicorn, Pydantic v2
- **Machine Learning Engine:** Scikit-learn (Isolation Forest), SHAP TreeExplainer, Pandas, NumPy, SciPy
- **GST Compliance Engine:** Rule-based validation (GSTIN Regex, Duplicate Invoices, HSN Thresholds, Cash Laundering Flags)
- **Database & Persistence:** Async SQLAlchemy 2.0 + SQLite (`aiosqlite`) / PostgreSQL (`asyncpg`)
- **Authentication & Security:** JWT (HS256/python-jose), Bcrypt password hashing, Fernet (AES-256) data encryption
- **Audit Export Modules:** ReportLab (PDF Audit Reports) & openpyxl (Excel Ledgers)
- **User Interfaces:**
  1. **Primary Web SPA (`http://127.0.0.1:8000/`)**: Dynamic glassmorphism dark-mode dashboard with interactive Plotly scatter plots, SHAP waterfall modals, and 1-click PDF export.
  2. **Streamlit Admin App (`http://127.0.0.1:8501/`)**: Model evaluation & threshold tuning dashboard.

---

## 🚀 Quickstart Guide (Local Run)

### 1. Initialize Virtual Environment & Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Generate Synthetic Test Datasets
```bash
python scripts/generate_synthetic_gst_data.py
```

### 3. Run FastAPI Backend & Web SPA
```bash
PYTHONPATH=backend python -m uvicorn app.main:app --port 8000 --reload
```
Access the application dashboard at: **`http://127.0.0.1:8000/`**  
OpenAPI Swagger Documentation: **`http://127.0.0.1:8000/docs`**

### 4. 1-Click Presentation Launch (Recommended)

| Platform | Script | Usage |
|----------|--------|-------|
| Mac / Linux | `run.sh` | `chmod +x run.sh && ./run.sh` |
| Windows | `run.bat` | Double-click `run.bat` |

These scripts automatically create the virtual environment, install dependencies, start the server, and open the dashboard in your browser.

### 5. Run Streamlit Admin App (Optional)
```bash
streamlit run streamlit_app.py --server.port 8501
```
Access the Streamlit admin prototype at: **`http://127.0.0.1:8501/`**

---

## 🐋 Docker Compose Run (Production)

```bash
docker-compose up --build -d
```

---

## 📝 IEEE 830 / Master Documentation
Full IEEE 830 compliant SRS & SDD documentation available in [KarAIMasterDocumentation.pdf](./KarAIMasterDocumentation.pdf).
