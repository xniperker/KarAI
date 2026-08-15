import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

def generate_synthetic_gst_dataset(num_records=1000, seed=42):
    np.random.seed(seed)
    random.seed(seed)
    
    parties = [
        "Tata Consultancy Services Ltd", "Reliance Industries Ltd", "Infosys Limited",
        "Sharma Logistics & Freight", "Gupta Steel & Hardware Corp", "Verma Stationery Traders",
        "Mehta Tech Solutions LLP", "Aggarwal Auto Components", "Delhi Distribution Network",
        "Global Enterprises", "Kapur Electronics", "Singhania Textiles Pvt Ltd",
        "Apex Packaging Solutions", "Bharat Petroleum Dealer", "Chawla IT Services"
    ]
    
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
            "is_anomaly": 0
        })
        
    df = pd.DataFrame(records)
    
    # Varied, realistic anomaly counts per rule
    # RULE-001 (Invalid GSTIN): 14 txns
    # RULE-002 (Duplicate Invoice): 7 txns
    # RULE-003 (Missing HSN > 50k): 19 txns
    # RULE-004 (Round Amount Cash Risk): 33 txns
    # RULE-005 (Missing TDS Sec 194J): 11 txns
    # RULE-006 (Cash Sec 269ST > 2L): 8 txns
    
    available_indices = list(range(num_records))
    random.shuffle(available_indices)
    
    def pop_indices(n):
        res = available_indices[:n]
        del available_indices[:n]
        return res

    # 1. RULE-001 (14 txns)
    for idx in pop_indices(14):
        df.at[idx, "is_anomaly"] = 1
        df.at[idx, "gstin"] = "07INVALIDGSTIN12"

    # 2. RULE-002 (7 txns)
    for idx in pop_indices(7):
        df.at[idx, "is_anomaly"] = 1
        target_idx = (idx - 5) % num_records
        df.at[idx, "invoice_number"] = df.at[target_idx, "invoice_number"]
        df.at[idx, "gstin"] = df.at[target_idx, "gstin"]
        df.at[idx, "txn_date"] = df.at[target_idx, "txn_date"]

    # 3. RULE-003 (19 txns)
    for idx in pop_indices(19):
        df.at[idx, "is_anomaly"] = 1
        df.at[idx, "amount"] = float(np.round(random.uniform(75000.0, 220000.0), 2))
        df.at[idx, "category"] = "UNCLASSIFIED"

    # 4. RULE-004 (33 txns)
    for idx in pop_indices(33):
        df.at[idx, "is_anomaly"] = 1
        df.at[idx, "amount"] = float(random.choice([400000.0, 500000.0, 800000.0, 1000000.0]))

    # 5. RULE-005 (11 txns)
    for idx in pop_indices(11):
        df.at[idx, "is_anomaly"] = 1
        df.at[idx, "amount"] = float(np.round(random.uniform(45000.0, 150000.0), 2))
        df.at[idx, "category"] = "SAC 9983 (NO TDS)"
        df.at[idx, "is_tds_deducted"] = False

    # 6. RULE-006 (8 txns)
    for idx in pop_indices(8):
        df.at[idx, "is_anomaly"] = 1
        df.at[idx, "amount"] = float(np.round(random.uniform(210000.0, 350000.0), 2))
        df.at[idx, "category"] = "CASH PAYMENT"

    # Huge amount spikes (10 txns)
    for idx in pop_indices(10):
        df.at[idx, "is_anomaly"] = 1
        df.at[idx, "amount"] = float(np.round(df.at[idx, "amount"] * random.uniform(15.0, 25.0), 2))
            
    return df

if __name__ == "__main__":
    import os
    os.makedirs("/Users/xniperker/Vault/KarAI/datasets", exist_ok=True)
    
    df_1000 = generate_synthetic_gst_dataset(num_records=1000, seed=42)
    df_1000.to_csv("/Users/xniperker/Vault/KarAI/datasets/sample_gst_transactions_1000.csv", index=False)
    print("Generated datasets/sample_gst_transactions_1000.csv with realistic varied rule distributions (14, 7, 19, 33, 11, 8).")
