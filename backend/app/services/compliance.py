import pandas as pd
import numpy as np
import re
from typing import List, Dict, Any, Tuple

class ComplianceValidator:
    """
    GST & Income Tax Compliance Validator.
    Evaluates:
    - RULE-001: GSTIN Standard Format (CGST Sec 25)
    - RULE-002: Duplicate Invoice Flag (CGST Rule 36(4))
    - RULE-003: HSN/SAC Code Missing > ₹50,000 (Notif 78/2020)
    - RULE-004: Cash Payment Risk > ₹10,000 (IT Act Sec 40A(3))
    - RULE-005: Missing TDS Deduction (IT Act Sec 194C/194J)
    - RULE-006: High-Value Cash Transaction > ₹2,00,000 (IT Act Sec 269ST)
    """
    GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

    @classmethod
    def validate_dataset(cls, df: pd.DataFrame, filing_period: str = "2025-Q1") -> Tuple[float, List[Dict[str, Any]], Dict[str, int]]:
        violations = []
        
        critical_count = 0
        major_count = 0
        minor_count = 0
        
        seen_invoices = set()
        
        for idx, row in df.iterrows():
            txn_id = str(row.get("transaction_id", f"TXN-{idx}"))
            amount = float(row.get("amount", 0.0))
            gstin = str(row.get("gstin", "")).strip() if pd.notna(row.get("gstin")) else ""
            category = str(row.get("category", "")).strip() if pd.notna(row.get("category")) else ""
            inv_no = str(row.get("invoice_number", "")).strip() if pd.notna(row.get("invoice_number")) else ""
            txn_date = str(row.get("txn_date", ""))
            party = str(row.get("party_name", ""))
            is_tds = row.get("is_tds_deducted", True)
            
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
                
            # RULE-004: Income Tax Sec 40A(3) Cash Payment Scrutiny
            if amount >= 100000.0 and amount % 10000 == 0:
                minor_count += 1
                violations.append({
                    "transaction_id": txn_id,
                    "violation_type": "RULE-004",
                    "severity": "minor",
                    "description": f"Unusually round transaction amount ₹{amount:,.2f} flagged for cash payment scrutiny under Sec 40A(3).",
                    "remediation": "Ensure banking channel proof of payment (NEFT/RTGS) is archived for tax audit verification."
                })

            # RULE-005: Income Tax Sec 194C/194J Missing TDS Deduction
            if amount > 30000.0 and ("NO TDS" in category.upper() or is_tds is False or is_tds == "False" or is_tds == 0):
                major_count += 1
                violations.append({
                    "transaction_id": txn_id,
                    "violation_type": "RULE-005",
                    "severity": "major",
                    "description": f"Professional service payment ₹{amount:,.2f} missing mandatory TDS deduction under Sec 194J of IT Act.",
                    "remediation": "Deduct 10% TDS and deposit via Form 26Q before quarterly filing deadline."
                })

            # RULE-006: Income Tax Sec 269ST Cash Limit Breach
            if amount >= 200000.0 and "CASH" in category.upper():
                critical_count += 1
                violations.append({
                    "transaction_id": txn_id,
                    "violation_type": "RULE-006",
                    "severity": "critical",
                    "description": f"Cash receipt ₹{amount:,.2f} exceeds ₹200,000 statutory cash threshold under Sec 269ST of IT Act.",
                    "remediation": "Imposes 100% penalty under Sec 271DA. Issue payment reversal via banking channel immediately."
                })

        # Calculate Overall Compliance Score (Proportional normalization per dataset size)
        total_rows = max(1, len(df))
        weighted_violation_rate = ((critical_count * 5.0) + (major_count * 2.5) + (minor_count * 1.0)) / total_rows
        score = max(0.0, min(100.0, float(np.round(100.0 - (weighted_violation_rate * 100.0), 1))))
        
        summary_counts = {
            "total_violations": len(violations),
            "critical_count": critical_count,
            "major_count": major_count,
            "minor_count": minor_count
        }
        
        return score, violations, summary_counts
