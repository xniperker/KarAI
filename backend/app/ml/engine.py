import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
import shap
from typing import List, Dict, Any, Tuple
from app.ml.features import FeatureEngineeringPipeline

class AnomalyEngine:
    """
    ML Anomaly Engine using Isolation Forest + SHAP TreeExplainer.
    Classifies transactions into:
    - Normal (0.00 - 0.30)
    - Suspicious (0.30 - 0.60)
    - High-Risk (0.60 - 0.85)
    - Critical (0.85 - 1.00)
    """

    @classmethod
    def classify_risk(cls, score: float) -> str:
        if score >= 0.85:
            return "critical"
        elif score >= 0.60:
            return "high_risk"
        elif score >= 0.30:
            return "suspicious"
        else:
            return "normal"

    @classmethod
    def run_detection(cls, df_raw: pd.DataFrame, contamination: float = 0.05) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        if df_raw.empty:
            return [], {}

        # 1. Generate 16 Features
        X_feat = FeatureEngineeringPipeline.transform(df_raw)

        # 2. Fit Isolation Forest
        model = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=42,
            bootstrap=False,
            n_jobs=-1
        )
        model.fit(X_feat)

        # 3. Compute raw decision scores and map to [0.0 - 1.0] continuous anomaly score
        # IsolationForest decision_function returns negative for anomalies, positive for normal
        raw_scores = model.decision_function(X_feat)
        
        # Scale scores so that higher value = higher anomaly risk (0.0 to 1.0)
        # Offset and scale raw scores smoothly
        scaled_scores = 1.0 - (1.0 / (1.0 + np.exp(-raw_scores * 8.0)))
        
        # Boost score if hard compliance indicators are violated (e.g. invalid GSTIN or Duplicate Invoice)
        hard_boost = (X_feat["gstin_valid"] == 0.0) * 0.4 + (X_feat["invoice_duplicate_flag"] == 1.0) * 0.4
        final_scores = np.clip(scaled_scores + hard_boost, 0.0, 1.0)

        # 4. Compute SHAP Values for feature importance using TreeExplainer
        shap_values_dict_list = []
        try:
            explainer = shap.TreeExplainer(model, check_additivity=False)
            shap_matrix = explainer.shap_values(X_feat)
            
            feature_names = list(X_feat.columns)
            for idx in range(len(X_feat)):
                row_shap = shap_matrix[idx] if isinstance(shap_matrix, np.ndarray) else shap_matrix
                # Extract top feature contributions sorted by magnitude
                shap_dict = {}
                for f_idx, f_name in enumerate(feature_names):
                    val = float(np.round(row_shap[f_idx], 4))
                    if abs(val) > 0.001:
                        shap_dict[f_name] = val
                # Keep top 5 features by absolute weight
                sorted_shap = dict(sorted(shap_dict.items(), key=lambda item: abs(item[1]), reverse=True)[:5])
                shap_values_dict_list.append(sorted_shap)
        except Exception:
            # Fallback if SHAP calculation encounters edge case
            feature_names = list(X_feat.columns)
            for idx in range(len(X_feat)):
                row_feat = X_feat.iloc[idx]
                fallback_shap = {
                    "amount_deviation": float(np.round(row_feat.get("amount_deviation_from_party", 0.0), 3)),
                    "amount_zscore": float(np.round(row_feat.get("amount_zscore", 0.0), 3)),
                    "gstin_valid": float(row_feat.get("gstin_valid", 1.0)),
                    "duplicate_flag": float(row_feat.get("invoice_duplicate_flag", 0.0))
                }
                shap_values_dict_list.append(fallback_shap)

        # 5. Build Result Structures
        results = []
        for idx in range(len(df_raw)):
            score = float(np.round(final_scores[idx], 4))
            risk_cat = cls.classify_risk(score)
            results.append({
                "index": idx,
                "anomaly_score": score,
                "risk_category": risk_cat,
                "shap_values": shap_values_dict_list[idx]
            })

        metrics = {
            "total_evaluated": len(df_raw),
            "normal_count": int(np.sum([r["risk_category"] == "normal" for r in results])),
            "suspicious_count": int(np.sum([r["risk_category"] == "suspicious" for r in results])),
            "high_risk_count": int(np.sum([r["risk_category"] == "high_risk" for r in results])),
            "critical_count": int(np.sum([r["risk_category"] == "critical" for r in results])),
            "contamination_used": contamination
        }

        return results, metrics
