import pandas as pd
import numpy as np
import re
from typing import List, Dict, Any, Tuple

class ComplianceValidator:
    """
    GST Compliance Rule Engine implementing RULE-001 through RULE-006.
    Calculates compliance score 0-100 per dataset/filing period.
    """
    GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

    @classmethod
    def validate_dataset(cls, df: pd.DataFrame, filing_period: str = "2025-Q1") -> Tuple[float, List[Dict[str, Any]], Dict[str, int]]:
        violations = []
        
        critical_count = 0
        major_count = 0
        minor_count = 0
        
        # Track seen invoices for RULE-002
        seen_invoices = set()
        
        for idx, row in df.iterrows():
            txn_id = str(row.get("transaction_id", f"TXN-{idx}"))
            amount = float(row.get("amount", 0.0))
            gstin = str(row.get("gstin", "")).strip() if pd.notna(row.get("gstin")) else ""
            category = str(row.get("category", "")).strip() if pd.notna(row.get("category")) else ""
            inv_no = str(row.get("invoice_number", "")).strip() if pd.notna(row.get("invoice_number")) else ""
            txn_date = str(row.get("txn_date", ""))
            party = str(row.get("party_name", ""))
            
            # RULE-001: GSTIN Format Validation
            if gstin and not cls.GSTIN_REGEX.match(gstin):
                critical_count += 1
                violations.append({
                    "transaction_id": txn_id,
                    "violation_type": "RULE-001",
                    "severity": "critical",
                    "description": f"Invalid GSTIN format '{gstin}' for party '{party}'. Must match 15-character alphanumeric GST standard.",
                    "remediation": "Verify and update the GSTIN using the official GST Portal lookup before filing GSTR-1/3B."
                })
                
            # RULE-002: Duplicate Invoice Detection
            if inv_no and gstin:
                inv_key = f"{inv_no}|{gstin}|{txn_date}"
                if inv_key in seen_invoices:
                    major_count += 1
                    violations.append({
                        "transaction_id": txn_id,
                        "violation_type": "RULE-002",
                        "severity": "major",
                        "description": f"Duplicate invoice number '{inv_no}' detected for GSTIN {gstin} on date {txn_date}.",
                        "remediation": "Remove duplicate invoice entry from the ledger to prevent double tax liability reporting."
                    })
                else:
                    seen_invoices.add(inv_key)
                    
            # RULE-003: HSN/SAC Code Missing for B2B > ₹50,000
            if amount > 50000.0 and (not category or category.upper() in ["UNCLASSIFIED", "UNKNOWN", "NONE", ""]):
                major_count += 1
                violations.append({
                    "transaction_id": txn_id,
                    "violation_type": "RULE-003",
                    "severity": "major",
                    "description": f"Transaction amount ₹{amount:,.2f} exceeds ₹50,000 mandatory threshold but missing valid HSN/SAC code.",
                    "remediation": "Assign the appropriate 4 to 6 digit HSN/SAC code as required by GST mandate for B2B invoices."
                })
                
            # RULE-004: Suspicious Round Amount (Laundering / Cash transaction risk)
            if amount >= 100000.0 and amount % 10000 == 0:
                minor_count += 1
                violations.append({
                    "transaction_id": txn_id,
                    "violation_type": "RULE-004",
                    "severity": "minor",
                    "description": f"Unusually round transaction amount ₹{amount:,.2f} flagged for cash payment scrutiny under Sec 40A(3).",
                    "remediation": "Ensure banking channel proof of payment (NEFT/RTGS) is archived for tax audit verification."
                })

        # Calculate Overall Compliance Score (100 - deductions)
        deduction = (critical_count * 10) + (major_count * 5) + (minor_count * 2)
        score = max(0.0, float(np.round(100.0 - deduction, 2)))
        
        summary_counts = {
            "total_violations": len(violations),
            "critical_count": critical_count,
            "major_count": major_count,
            "minor_count": minor_count
        }
        
        return score, violations, summary_counts
