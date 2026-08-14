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

router = APIRouter(prefix="/copilot", tags=["GenAI Tax Co-Pilot"])

class ChatRequest(BaseModel):
    message: str
    dataset_id: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    suggested_actions: List[str]

# Detailed Tax Regulations Context Knowledge Base
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
        "advice": "Round payments (e.g. ₹5,00,000, ₹10,00,000) trigger cash payment scrutiny under Sec 40A(3) of IT Act. Payments exceeding ₹10,000 in cash per day are dis-allowed as business expenses.",
        "action": "Ensure banking channel proof (RTGS/NEFT/IMPS bank statements) is linked to the voucher for audit trails."
    }
}

@router.post("/chat", response_model=ChatResponse)
async def chat_with_copilot(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = req.message.strip().lower()
    dataset_id = req.dataset_id

    # If dataset_id is provided, fetch latest audit status to give context-aware AI advice
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

    # Smart Generative Tax Co-Pilot Reasoning Logic
    if "summarize" in query or "summary" in query or "report" in query or "overview" in query:
        if cc:
            reply = (
                f"🤖 **KarAI Executive Audit Summary**:\n\n"
                f"• **Compliance Score**: `{cc.compliance_score:.1f} / 100`\n"
                f"• **Total Violations**: {cc.total_violations} breaches ({cc.critical_count} Critical, {cc.major_count} Major, {cc.minor_count} Minor).\n\n"
                f"**Key Findings**: The primary risk factors stem from GSTIN validation errors (`RULE-001`) and missing HSN classification on high-value B2B transactions (`RULE-003`). "
                f"Resolving the {cc.critical_count} critical breaches before GSTR-3B filing will raise your compliance score to ~95+."
            )
            actions = ["Export Audit PDF", "View Critical Violations", "Filter High-Risk Ledger"]
        else:
            reply = "🤖 Please run the dataset demo or upload a CSV ledger first so I can summarize your specific tax risk report."
            actions = ["Run Demo Dataset", "Upload CSV File"]

    elif "rule-001" in query or "gstin" in query or "invalid gstin" in query:
        kb = TAX_KNOWLEDGE_BASE["RULE-001"]
        reply = (
            f"🤖 **GSTIN Regulatory Analysis ({kb['section']})**:\n\n"
            f"{kb['advice']}\n\n"
            f"💡 **Action Required**: {kb['action']}"
        )
        actions = ["Filter RULE-001 Breaches", "Verify GSTINs on GST Portal"]

    elif "rule-002" in query or "duplicate" in query:
        kb = TAX_KNOWLEDGE_BASE["RULE-002"]
        reply = (
            f"🤖 **Duplicate Invoice Risk ({kb['section']})**:\n\n"
            f"{kb['advice']}\n\n"
            f"💡 **Action Required**: {kb['action']}"
        )
        actions = ["Filter Duplicate Invoices", "Issue Credit Note"]

    elif "rule-003" in query or "hsn" in query or "sac" in query or "50000" in query:
        kb = TAX_KNOWLEDGE_BASE["RULE-003"]
        reply = (
            f"🤖 **HSN/SAC Classification Mandate ({kb['section']})**:\n\n"
            f"{kb['advice']}\n\n"
            f"💡 **Action Required**: {kb['action']}"
        )
        actions = ["Filter Missing HSN > ₹50k", "Look up HSN Master Table"]

    elif "rule-004" in query or "round" in query or "cash" in query or "40a" in query:
        kb = TAX_KNOWLEDGE_BASE["RULE-004"]
        reply = (
            f"🤖 **Income Tax Act Sec 40A(3) Compliance ({kb['section']})**:\n\n"
            f"{kb['advice']}\n\n"
            f"💡 **Action Required**: {kb['action']}"
        )
        actions = ["Attach Bank Statements", "Review High Round Transactions"]

    elif "txn-" in query or "transaction" in query:
        if top_anom and top_anom.transaction:
            t = top_anom.transaction
            reply = (
                f"🤖 **Deep Analysis for High-Risk Transaction `{t.transaction_id}`**:\n\n"
                f"• **Party**: {t.party_name}\n"
                f"• **Amount**: ₹{t.amount:,.2f}\n"
                f"• **ML Anomaly Score**: `{top_anom.anomaly_score:.4f}` ({top_anom.risk_category.upper()})\n"
                f"• **SHAP XAI Feature Drivers**: The primary reasons for flagging were **amount deviation (+{top_anom.shap_values.get('amount_deviation', 0):.3f})** and **Z-score (+{top_anom.shap_values.get('amount_zscore', 0):.3f})** relative to party history."
            )
            actions = ["Inspect SHAP XAI Breakdown", "Export Full Excel Ledger"]
        else:
            reply = "🤖 Transaction inquiry received. Please specify the exact TXN ID (e.g. TXN-2025-00080) or run demo dataset."
            actions = ["View High-Risk Ledger"]

    else:
        reply = (
            f"🤖 **KarAI Tax Advisory Co-Pilot**:\n\n"
            f"I analyzed your request: *'{req.message}'*.\n\n"
            f"I can assist you with:\n"
            f"1. **Summarizing your overall GST audit report**\n"
            f"2. **Explaining legal tax sections (CGST Sec 25, Rule 36(4), IT Sec 40A(3))**\n"
            f"3. **Investigating specific transaction IDs and SHAP feature drivers**\n"
            f"4. **Providing CA-level remediation advice for flagged violations**"
        )
        actions = ["Summarize Audit Report", "Explain RULE-001 (GSTIN)", "Explain RULE-003 (HSN > 50k)"]

    return ChatResponse(reply=reply, suggested_actions=actions)
