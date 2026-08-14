import os
import pandas as pd
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.db.models import User, Dataset, Transaction, ModelRun, AnomalyResult, ComplianceCheck, Violation
from app.api.auth import get_current_user

router = APIRouter(prefix="/copilot", tags=["KarAI Chatbot"])

class ChatRequest(BaseModel):
    message: str
    dataset_id: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    suggested_actions: List[str]

# Expanded GST & Tax Regulations Knowledge Base
TAX_KNOWLEDGE_BASE = {
    "RULE-001": {
        "name": "Invalid GSTIN Standard Format",
        "section": "Section 25 of CGST Act, 2017",
        "advice": "Under Section 25 of CGST Act, every GST registered entity in India has a 15-character alphanumeric GSTIN (2 state digits + 10-char PAN + 1 entity code + 'Z' + 1 checksum). If invalid, Input Tax Credit (ITC) will be rejected by GSTN portal upon GSTR-2B matching.",
        "action": "Use the official GST Portal (gst.gov.in) Taxpayer Search tool to verify the vendor's PAN and update the master ledger."
    },
    "RULE-002": {
        "name": "Duplicate Invoice Detection",
        "section": "Rule 36(4) of CGST Rules",
        "advice": "Duplicate invoice numbers for the same GSTIN and date result in double liability reporting and severe penalties during GST audit under Rule 36(4).",
        "action": "Reverse the duplicate invoice entry via a Credit Note or adjust in GSTR-1 prior to month-end filing."
    },
    "RULE-003": {
        "name": "Missing HSN/SAC Code > ₹50,000",
        "section": "Notification No. 78/2020 – Central Tax",
        "advice": "Taxpayers with turnover > ₹5 Cr must mandate 6-digit HSN/SAC codes on all B2B invoices. Missing HSN codes on invoices above ₹50,000 invite penal provisions under Section 125 of CGST Act.",
        "action": "Map the correct 4 to 6 digit HSN code based on the GST commodity tariff master table."
    },
    "RULE-004": {
        "name": "Round Amount Cash Payment Scrutiny",
        "section": "Section 40A(3) of Income Tax Act, 1961",
        "advice": "Round payments (e.g. ₹5,00,000, ₹10,00,000) trigger cash payment scrutiny under Sec 40A(3) of IT Act. Payments exceeding ₹10,00,000 in cash per day are dis-allowed as business expenses.",
        "action": "Ensure banking channel proof (RTGS/NEFT/IMPS bank statements) is linked to the voucher for audit trails."
    },
    "RULE-005": {
        "name": "Round-Trip Transaction Circular Trading Risk",
        "section": "Section 132(1)(b) of CGST Act",
        "advice": "Circular trading / round-trip invoices issued without actual goods delivery to inflate turnover constitute fake invoice offenses under Section 132(1)(b).",
        "action": "Verify e-Way Bills and transport lorry receipts (LR) for physical movement of goods."
    },
    "RULE-006": {
        "name": "Abnormal ITC Claim vs Turnover Ratio",
        "section": "Section 16(2) of CGST Act",
        "advice": "Input Tax Credit claims exceeding 1.5x of outward turnover trigger automated red flags on the GSTN analytical dashboard.",
        "action": "Reconcile GSTR-2B with purchase register before filing GSTR-3B."
    }
}

@router.post("/chat", response_model=ChatResponse)
async def chat_with_chatbot(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    raw_msg = req.message.strip()
    query = raw_msg.lower()
    dataset_id = req.dataset_id

    # Categorized Numeric Selection Shortcuts (1, 2, 3, 4, 5)
    if query in ["1", "1.", "option 1", "opt 1"]:
        query = "summarize"
    elif query in ["2", "2.", "option 2", "opt 2"]:
        query = "explain rules"
    elif query in ["3", "3.", "option 3", "opt 3"]:
        query = "investigate transaction"
    elif query in ["4", "4.", "option 4", "opt 4"]:
        query = "remediation advice"
    elif query in ["5", "5.", "option 5", "opt 5"]:
        query = "export reports"

    # Fetch dataset audit context if available
    cc = None
    top_anom = None
    if dataset_id:
        cc_res = await db.execute(
            select(ComplianceCheck)
            .options(selectinload(ComplianceCheck.violations))
            .where(ComplianceCheck.dataset_id == dataset_id)
            .order_by(ComplianceCheck.checked_at.desc())
        )
        cc = cc_res.scalars().first()

        mr_res = await db.execute(
            select(ModelRun)
            .where(ModelRun.dataset_id == dataset_id, ModelRun.status == "completed")
            .order_by(ModelRun.run_timestamp.desc())
        )
        mr = mr_res.scalars().first()
        if mr:
            anom_res = await db.execute(
                select(AnomalyResult)
                .options(selectinload(AnomalyResult.transaction))
                .where(AnomalyResult.model_run_id == mr.id)
                .order_by(AnomalyResult.anomaly_score.desc())
            )
            top_anom = anom_res.scalars().first()

    # Category 1: Executive Summary
    if "summarize" in query or "summary" in query or "report" in query or "overview" in query:
        if cc:
            reply = (
                f"🤖 <b>Executive Tax Audit Summary</b>:<br/><br/>"
                f"• <b>Compliance Score</b>: <code>{cc.compliance_score:.1f} / 100</code><br/>"
                f"• <b>Total Violations</b>: {cc.total_violations} breaches ({cc.critical_count} Critical, {cc.major_count} Major, {cc.minor_count} Minor).<br/><br/>"
                f"<b>Key Insights</b>: Primary audit risks stem from invalid GSTIN formats (RULE-001) and missing HSN/SAC codes on B2B invoices over ₹50,000 (RULE-003). "
                f"Resolving the {cc.critical_count} critical breaches before filing GSTR-3B will raise your compliance score to ~95+."
            )
            actions = ["Export Audit PDF", "Export Excel Ledger", "View Critical Violations", "Filter High-Risk Ledger"]
        else:
            reply = "🤖 Please click 'Run Demo (500 Txns)' or upload a CSV ledger first so I can summarize your specific audit report."
            actions = ["Run Demo Dataset", "Upload CSV File"]

    # Category 2: Explain Any Tax / GST Rule
    elif "explain rules" in query or "rules" in query or "rule" in query:
        reply = (
            f"🤖 <b>GST & Tax Regulatory Knowledge Engine</b>:<br/><br/>"
            f"I can explain any of the following regulatory compliance rules in detail:<br/><br/>"
            f"• <b>RULE-001</b>: Invalid GSTIN Format (Sec 25 CGST Act)<br/>"
            f"• <b>RULE-002</b>: Duplicate Invoice Flags (Rule 36(4) CGST)<br/>"
            f"• <b>RULE-003</b>: Missing HSN/SAC Codes > ₹50k (Notif 78/2020)<br/>"
            f"• <b>RULE-004</b>: Cash Payment Risk (Sec 40A(3) IT Act)<br/>"
            f"• <b>RULE-005</b>: Circular Trading / Round-Trip Invoices (Sec 132)<br/>"
            f"• <b>RULE-006</b>: Abnormal ITC vs Turnover Ratio (Sec 16(2))<br/><br/>"
            f"<i>Type any rule code (e.g. 'explain RULE-001' or 'rule 3') to get full legal advice!</i>"
        )
        actions = ["Explain RULE-001", "Explain RULE-002", "Explain RULE-003", "Explain RULE-004"]

    elif "rule-001" in query or "invalid gstin" in query:
        kb = TAX_KNOWLEDGE_BASE["RULE-001"]
        reply = f"🤖 <b>GSTIN Analysis ({kb['section']})</b>:<br/><br/>{kb['advice']}<br/><br/>💡 <b>Remediation Action</b>: {kb['action']}"
        actions = ["Filter RULE-001 Breaches", "Export Audit PDF"]

    elif "rule-002" in query:
        kb = TAX_KNOWLEDGE_BASE["RULE-002"]
        reply = f"🤖 <b>Duplicate Invoice Analysis ({kb['section']})</b>:<br/><br/>{kb['advice']}<br/><br/>💡 <b>Remediation Action</b>: {kb['action']}"
        actions = ["Filter Duplicate Invoices", "Export Excel Ledger"]

    elif "rule-003" in query or "hsn" in query or "50000" in query:
        kb = TAX_KNOWLEDGE_BASE["RULE-003"]
        reply = f"🤖 <b>HSN/SAC Mandate Analysis ({kb['section']})</b>:<br/><br/>{kb['advice']}<br/><br/>💡 <b>Remediation Action</b>: {kb['action']}"
        actions = ["Filter Missing HSN > ₹50k", "Export Audit PDF"]

    elif "rule-004" in query or "cash" in query or "40a" in query:
        kb = TAX_KNOWLEDGE_BASE["RULE-004"]
        reply = f"🤖 <b>Cash Payment Scrutiny ({kb['section']})</b>:<br/><br/>{kb['advice']}<br/><br/>💡 <b>Remediation Action</b>: {kb['action']}"
        actions = ["Filter High Round Transactions", "Filter High-Risk Ledger"]

    # Category 3: Investigate Specific Transaction (SHAP XAI)
    elif "investigate transaction" in query or "txn-" in query or "transaction" in query or "shap" in query:
        if top_anom and top_anom.transaction:
            t = top_anom.transaction
            reply = (
                f"🤖 <b>Transaction Investigation for <code>{t.transaction_id}</code></b>:<br/><br/>"
                f"• <b>Party Name</b>: {t.party_name}<br/>"
                f"• <b>Amount</b>: ₹{t.amount:,.2f}<br/>"
                f"• <b>ML Anomaly Risk</b>: <code>{top_anom.anomaly_score:.4f}</code> ({top_anom.risk_category.upper()})<br/>"
                f"• <b>SHAP Drivers</b>: Amount deviation (+{top_anom.shap_values.get('amount_deviation', 0):.3f}) and Z-score (+{top_anom.shap_values.get('amount_zscore', 0):.3f})."
            )
            actions = ["Inspect SHAP XAI Breakdown", "Filter High-Risk Ledger"]
        else:
            reply = "🤖 Please specify a transaction ID (e.g. 'TXN-2025-00080') or run demo dataset first."
            actions = ["Run Demo Dataset", "Filter High-Risk Ledger"]

    # Category 4: CA Audit & Remediation Advice
    elif "remediation advice" in query or "remediation" in query or "fix" in query or "ca" in query:
        reply = (
            f"🤖 <b>CA Pre-Filing Remediation Checklist</b>:<br/><br/>"
            f"1. <b>Fix Critical GSTIN Errors</b>: Search and update supplier GSTINs on gst.gov.in.<br/>"
            f"2. <b>Remove Duplicate Invoices</b>: Issue Credit Notes for duplicate entries before GSTR-1 lock.<br/>"
            f"3. <b>Assign Missing HSN Codes</b>: Add 6-digit HSN codes for all invoices > ₹50,000.<br/>"
            f"4. <b>Archive Bank Proofs</b>: Ensure RTGS/NEFT payment vouchers exist for round transactions > ₹10L."
        )
        actions = ["View Critical Violations", "Export Audit PDF", "Export Excel Ledger"]

    # Category 5: Export Reports & Filter Screen
    elif "export reports" in query or "export" in query or "excel" in query or "pdf" in query:
        reply = (
            f"🤖 <b>Report Export & Screen Navigation</b>:<br/><br/>"
            f"Click any button below to instantly trigger downloads or filter your dashboard:"
        )
        actions = ["Export Audit PDF", "Export Excel Ledger", "Filter High-Risk Ledger", "View Critical Violations"]

    # Default Full Categorized Options Menu
    else:
        reply = (
            f"🤖 <b>KarAI Tax Advisory Chatbot</b>:<br/><br/>"
            f"Select an option by typing <b>1, 2, 3, 4, or 5</b> (or ask any question in plain English):<br/><br/>"
            f"<b>1. Executive Audit Summary</b> (Overall compliance score & findings)<br/>"
            f"<b>2. Explain Any GST / Tax Rule</b> (Legal sections & CGST provisions)<br/>"
            f"<b>3. Investigate High-Risk Transaction</b> (SHAP XAI feature drivers)<br/>"
            f"<b>4. CA Remediation Advice</b> (Step-by-step pre-filing checklist)<br/>"
            f"<b>5. Export Audit Reports & Filter Ledger</b> (Instant PDF/Excel download & filter)"
        )
        actions = ["1", "2", "3", "4", "5"]

    return ChatResponse(reply=reply, suggested_actions=actions)
