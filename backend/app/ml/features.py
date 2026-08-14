import pandas as pd
import numpy as np
import re
from scipy.stats import zscore, percentileofscore

class FeatureEngineeringPipeline:
    """
    Transforms raw GST transaction DataFrame into 16 engineered numerical features
    for Isolation Forest and ML inference.
    """
    GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

    @classmethod
    def validate_gstin(cls, gstin_str: str) -> float:
        if not gstin_str or pd.isna(gstin_str):
            return 0.0
        return 1.0 if bool(cls.GSTIN_REGEX.match(str(gstin_str).strip())) else 0.0

    @classmethod
    def transform(cls, df: pd.DataFrame) -> pd.DataFrame:
        df_feat = pd.DataFrame(index=df.index)
        
        # 1. Base amount
        df_feat["amount"] = df["amount"].astype(float)
        
        # 2. Log-transformed amount
        df_feat["log_amount"] = np.log1p(np.maximum(0, df_feat["amount"]))
        
        # 3. Amount Z-score
        std_val = df_feat["amount"].std()
        if std_val == 0 or np.isnan(std_val):
            df_feat["amount_zscore"] = 0.0
        else:
            df_feat["amount_zscore"] = (df_feat["amount"] - df_feat["amount"].mean()) / std_val
            
        # Parse dates
        dates = pd.to_datetime(df["txn_date"], errors="coerce").fillna(pd.Timestamp.now())
        
        # 4. Day of week (0-6)
        df_feat["day_of_week"] = dates.dt.weekday.astype(float)
        
        # 5. Month (1-12)
        df_feat["month"] = dates.dt.month.astype(float)
        
        # 6. Quarter (1-4)
        df_feat["quarter"] = dates.dt.quarter.astype(float)
        
        # 7. Is Weekend (0 or 1)
        df_feat["is_weekend"] = df_feat["day_of_week"].isin([5, 6]).astype(float)
        
        # Party aggregations
        party_groups = df.groupby("party_name")["amount"]
        party_counts = party_groups.transform("count")
        party_means = party_groups.transform("mean")
        party_stds = party_groups.transform("std").fillna(0.0)
        
        # 8. Party Txn Count
        df_feat["party_txn_count"] = party_counts.astype(float)
        
        # 9. Party Amount Mean
        df_feat["party_amount_mean"] = party_means.astype(float)
        
        # 10. Party Amount Std
        df_feat["party_amount_std"] = party_stds.astype(float)
        
        # 11. Amount Deviation from Party Baseline (Z-score per party)
        denom = party_stds + 1e-5
        df_feat["amount_deviation_from_party"] = (df_feat["amount"] - party_means) / denom
        
        # 12. Category Frequency
        cat_counts = df["category"].fillna("UNKNOWN").map(df["category"].value_counts(normalize=True))
        df_feat["category_frequency"] = cat_counts.astype(float)
        
        # 13. GSTIN Valid Flag
        df_feat["gstin_valid"] = df["gstin"].apply(cls.validate_gstin).astype(float)
        
        # 14. Invoice Duplicate Flag
        dup_series = df.duplicated(subset=["invoice_number", "gstin", "txn_date"], keep=False)
        df_feat["invoice_duplicate_flag"] = dup_series.astype(float)
        
        # 15. Round Amount Flag (e.g., amount % 1000 == 0)
        df_feat["round_amount_flag"] = ((df_feat["amount"] > 10000) & (df_feat["amount"] % 1000 == 0)).astype(float)
        
        # 16. Amount Percentile in Dataset
        amounts = df_feat["amount"].values
        df_feat["amount_percentile_in_dataset"] = [percentileofscore(amounts, a) / 100.0 for a in amounts]
        
        # Fill any unexpected NaN values with 0.0
        return df_feat.fillna(0.0)
