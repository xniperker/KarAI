import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

def generate_synthetic_gst_dataset(num_records=1000, seed=42):
    np.random.seed(seed)
    random.seed(seed)
    
    # Common Indian SME vendors / parties
    parties = [
        "Tata Consultancy Services Ltd", "Reliance Industries Ltd", "Infosys Limited",
        "Sharma Logistics & Freight", "Gupta Steel & Hardware Corp", "Verma Stationery Traders",
        "Mehta Tech Solutions LLP", "Aggarwal Auto Components", "Delhi Distribution Network",
        "Global Enterprises", "Kapur Electronics", "Singhania Textiles Pvt Ltd",
        "Apex Packaging Solutions", "Bharat Petroleum Dealer", "Chawla IT Services"
    ]
    
    # Valid Indian GSTIN format
    valid_gstin_prefixes = ["07AAAAA", "27BBBBB", "09CCCCC", "19DDDDD", "33EEEEE"]
    categories = ["HSN 8471", "HSN 7208", "HSN 5208", "HSN 2710", "SAC 9983", "SAC 9965", "HSN 4819"]
    
    start_date = datetime(2025, 1, 1)
    
    records = []
    
    party_gstin_map = {}
    for party in parties:
        prefix = random.choice(valid_gstin_prefixes)
        rand_num = random.randint(1000, 9999)
        pan_char = random.choice(["A", "B", "C", "P", "F"])
        entity_code = str(random.randint(1, 9))
        checksum = str(random.randint(1, 9))
        party_gstin_map[party] = f"{prefix}{rand_num}{pan_char}{entity_code}Z{checksum}"
        
    for i in range(1, num_records + 1):
        txn_id = f"TXN-2025-{i:05d}"
        days_offset = random.randint(0, 180)
        txn_date = (start_date + timedelta(days=days_offset)).strftime("%Y-%m-%d")
        
        party = random.choice(parties)
        gstin = party_gstin_map[party]
        category = random.choice(categories)
        invoice_no = f"INV/2025/{random.randint(10000, 99999)}"
        
        # Log-normal distribution for amounts
        base_amount = float(np.round(np.random.lognormal(mean=9.5, sigma=0.8), 2))
        amount = max(1000.0, min(base_amount, 250000.0))
        
        records.append({
            "transaction_id": txn_id,
            "txn_date": txn_date,
            "amount": amount,
            "party_name": party,
            "gstin": gstin,
            "category": category,
            "invoice_number": invoice_no,
            "is_tds_deducted": True,
            "is_anomaly": 0  # Default normal
        })
        
    df = pd.DataFrame(records)
    
    # Inject 5% anomalies (GST & Income Tax specific violations)
    anomaly_indices = random.sample(range(num_records), int(num_records * 0.05))
    
    for idx in anomaly_indices:
        anomaly_type = random.choice([
            "huge_amount_spike", "invalid_gstin", "duplicate_invoice", 
            "round_amount_laundering", "missing_hsn_large_b2b", "missing_tds_sec194", "cash_sec269st"
        ])
        
        df.at[idx, "is_anomaly"] = 1  # Ground-truth anomaly label
        
        if anomaly_type == "huge_amount_spike":
            df.at[idx, "amount"] = float(np.round(df.at[idx, "amount"] * random.uniform(15.0, 30.0), 2))
            
        elif anomaly_type == "invalid_gstin":
            df.at[idx, "gstin"] = "07INVALIDGSTIN12"
            
        elif anomaly_type == "duplicate_invoice":
            target_idx = (idx - 5) % num_records
            df.at[idx, "invoice_number"] = df.at[target_idx, "invoice_number"]
            df.at[idx, "gstin"] = df.at[target_idx, "gstin"]
            df.at[idx, "txn_date"] = df.at[target_idx, "txn_date"]
            
        elif anomaly_type == "round_amount_laundering":
            df.at[idx, "amount"] = float(random.choice([500000.0, 1000000.0, 1500000.0]))
            
        elif anomaly_type == "missing_hsn_large_b2b":
            df.at[idx, "amount"] = 185000.0
            df.at[idx, "category"] = "UNCLASSIFIED"

        elif anomaly_type == "missing_tds_sec194":
            df.at[idx, "amount"] = 120000.0
            df.at[idx, "category"] = "SAC 9983"
            df.at[idx, "is_tds_deducted"] = False  # Income Tax Sec 194J breach

        elif anomaly_type == "cash_sec269st":
            df.at[idx, "amount"] = 250000.0
            df.at[idx, "category"] = "CASH PAYMENT"
            
    return df

if __name__ == "__main__":
    import os
    os.makedirs("/Users/xniperker/Vault/KarAI/datasets", exist_ok=True)
    
    df_500 = generate_synthetic_gst_dataset(num_records=500, seed=42)
    df_500.to_csv("/Users/xniperker/Vault/KarAI/datasets/sample_gst_transactions_500.csv", index=False)
    print("Generated datasets/sample_gst_transactions_500.csv with ground truth labels.")
    
    df_2000 = generate_synthetic_gst_dataset(num_records=2000, seed=101)
    df_2000.to_csv("/Users/xniperker/Vault/KarAI/datasets/sample_gst_transactions_2000.csv", index=False)
    print("Generated datasets/sample_gst_transactions_2000.csv with ground truth labels.")
