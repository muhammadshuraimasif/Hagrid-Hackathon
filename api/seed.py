import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select, func
from api.database import AsyncSessionLocal, init_db
from api.models import Tenant, User, RuleSet, Decision, Case, Person
from api.security import hash_password
from api.rules.engine import compute_content_hash, evaluate_case, normalize_input_snapshot

logger = logging.getLogger(__name__)

SEED_TENANTS = [
    {
        "id": "tenant-prd",
        "code": "prd",
        "name": "Provincial Relief Department",
        "income_limit": 40000,
        "auto_approval_cap": 25000,
    },
    {
        "id": "tenant-mao",
        "code": "mao",
        "name": "Municipal Aid Office",
        "income_limit": 35000,
        "auto_approval_cap": 20000,
    },
]

ROLES = ["citizen", "helper", "officer", "admin", "auditor"]
DEFAULT_PASSWORD = "Demo@12345"

def make_rule_set_definition(income_limit: int, auto_approval_cap: int) -> dict:
    return {
        "eligibility_rules": [
            {
                "id": "valid_identity",
                "name": "Identity Verification",
                "rule": {"==": [{"var": "identity_verified"}, True]},
                "required_field": "identity_verified",
                "doc_type": "cnic_front",
                "reason_code": "IDENTITY_NOT_VERIFIED",
            },
            {
                "id": "income_limit",
                "name": "Income Limit",
                "rule": {"<=": [{"var": "monthly_income"}, income_limit]},
                "required_field": "monthly_income",
                "doc_type": "salary_slip",
                "reason_code": "INCOME_EXCEEDS_LIMIT",
            },
            {
                "id": "household_size",
                "name": "Household Size",
                "rule": {">=": [{"var": "household_size"}, 1]},
                "required_field": "household_size",
                "doc_type": "family_registration_certificate",
                "reason_code": "INVALID_HOUSEHOLD_SIZE",
            },
        ],
        "required_documents": ["cnic_front", "salary_slip"],
        "thresholds": {
            "auto_approval_p_min": 0.85,
            "fraud_risk_p_max": 0.20,
        },
        "cost_table": {
            "wrong_approval": 100,
            "human_review": 4,
            "ask_round": 1,
            "wrong_fraud_tag": 20,
            "unit_pkr": 250,
        },
        "auto_approval_cap": auto_approval_cap,
        "reason_codes": {
            "ELIGIBLE_AUTO": {
                "en": "Your application meets all criteria and has been approved on hold.",
                "ur": "آپ کی درخواست تمام شرائط پر پوری اترتی ہے اور اسے عارضی طور پر منظور کر لیا گیا ہے۔",
            },
            "MISSING_EVIDENCE": {
                "en": "Please provide the requested missing document or information.",
                "ur": "براہ کرم درکار دستاویز یا معلومات فراہم کریں۔",
            },
            "ESCALATED_HUMAN": {
                "en": "Your application has been referred to an officer for human review.",
                "ur": "آپ کی درخواست کو تفصیلی جائزے کے لیے افسر کے پاس بھیج دیا گیا ہے۔",
            },
            "INCOME_EXCEEDS_LIMIT": {
                "en": "Stated income exceeds the maximum allowable threshold.",
                "ur": "بتائی گئی آمدنی ریلیف کی حد سے تجاوز کرتی ہے۔",
            },
            "IDENTITY_NOT_VERIFIED": {
                "en": "Identity document could not be verified.",
                "ur": "شناختی دستاویز کی تصدیق نہیں ہو سکی۔",
            },
            "INVALID_HOUSEHOLD_SIZE": {
                "en": "Household size is not valid.",
                "ur": "خاندان کے افراد کی تعداد درست نہیں ہے۔",
            },
            "AMOUNT_EXCEEDS_CAP": {
                "en": "Requested amount exceeds the auto-approval cap.",
                "ur": "درخواست کردہ رقم خودکار منظوری کی حد سے زیادہ ہے۔",
            },
            "RISK_FLAGGED_FOR_HUMAN": {
                "en": "Application flagged for routine officer review.",
                "ur": "درخواست کو معمول کے جائزے کے لیے افسر کو بھیج دیا گیا ہے۔",
            },
        },
    }

async def seed_data():
    """Idempotently seed tenants, test users, published rules, and 30 baseline decisions."""
    await init_db()
    pwd_hash = hash_password(DEFAULT_PASSWORD)

    async with AsyncSessionLocal() as session:
        # Seed Tenants
        for t_info in SEED_TENANTS:
            res = await session.execute(select(Tenant).where(Tenant.code == t_info["code"]))
            existing_tenant = res.scalars().first()
            if not existing_tenant:
                tenant = Tenant(
                    id=t_info["id"],
                    code=t_info["code"],
                    name=t_info["name"],
                    is_active=True,
                )
                session.add(tenant)
                await session.flush()
                logger.info(f"Seeded tenant: {t_info['code']}")
            else:
                t_info["id"] = existing_tenant.id

        # Seed Users
        for t_info in SEED_TENANTS:
            tenant_id = t_info["id"]
            code = t_info["code"]
            for role in ROLES:
                email = f"{role}@{code}.test"
                user_res = await session.execute(select(User).where(User.email == email))
                existing_user = user_res.scalars().first()
                if not existing_user:
                    user = User(
                        tenant_id=tenant_id,
                        email=email,
                        password_hash=pwd_hash,
                        role=role,
                        language="ur",
                        is_active=True,
                    )
                    session.add(user)
                    logger.info(f"Seeded user: {email} ({role})")

        # Seed Published Rule Sets
        tenant_prd_ruleset = None
        for t_info in SEED_TENANTS:
            tenant_id = t_info["id"]
            code = t_info["code"]
            rs_res = await session.execute(
                select(RuleSet).where(RuleSet.tenant_id == tenant_id, RuleSet.version == 1)
            )
            existing_rs = rs_res.scalars().first()
            if not existing_rs:
                rs_def = make_rule_set_definition(t_info["income_limit"], t_info["auto_approval_cap"])
                content_hash = compute_content_hash(rs_def)
                rule_set = RuleSet(
                    tenant_id=tenant_id,
                    version=1,
                    status="published",
                    author=f"admin@{code}.test",
                    effective_at=datetime.now(timezone.utc),
                    content_hash=content_hash,
                    definition=rs_def,
                    twin_report=None,
                )
                session.add(rule_set)
                await session.flush()
                logger.info(f"Seeded published rule set v1 for {code}")
                if code == "prd":
                    tenant_prd_ruleset = rule_set
            elif code == "prd":
                tenant_prd_ruleset = existing_rs

        # Seed 30 Decisions for tenant-prd if none exist
        dec_count_res = await session.execute(
            select(func.count(Decision.id)).where(Decision.tenant_id == "tenant-prd")
        )
        dec_count = dec_count_res.scalar() or 0
        if dec_count < 30 and tenant_prd_ruleset:
            logger.info("Seeding 30 baseline decisions for tenant-prd Digital Twin simulation...")
            test_inputs = []
            
            # 10 AUTO inputs
            for i in range(10):
                test_inputs.append({
                    "monthly_income": 20000 + (i * 1000),  # 20k to 29k (<= 40k)
                    "identity_verified": True,
                    "household_size": 3 + (i % 3),
                    "requested_amount": 15000,  # <= 25k cap
                    "uploaded_documents": ["cnic_front", "salary_slip"],
                    "confidence_score": 0.95,
                    "fraud_risk_score": 0.04,
                })

            # 10 ASK inputs (missing salary_slip)
            for i in range(10):
                test_inputs.append({
                    "monthly_income": 22000 + (i * 1000),
                    "identity_verified": True,
                    "household_size": 2 + (i % 4),
                    "requested_amount": 18000,
                    "uploaded_documents": ["cnic_front"],  # missing salary_slip
                    "confidence_score": 0.90,
                    "fraud_risk_score": 0.05,
                })

            # 10 HUMAN inputs (5 income exceeds limit, 5 amount exceeds cap)
            for i in range(5):
                test_inputs.append({
                    "monthly_income": 45000 + (i * 2000),  # > 40k
                    "identity_verified": True,
                    "household_size": 4,
                    "requested_amount": 20000,
                    "uploaded_documents": ["cnic_front", "salary_slip"],
                    "confidence_score": 0.95,
                    "fraud_risk_score": 0.05,
                })
            for i in range(5):
                test_inputs.append({
                    "monthly_income": 25000,
                    "identity_verified": True,
                    "household_size": 4,
                    "requested_amount": 35000 + (i * 1000),  # > 25k cap
                    "uploaded_documents": ["cnic_front", "salary_slip"],
                    "confidence_score": 0.95,
                    "fraud_risk_score": 0.05,
                })

            # Evaluate each and insert Decision row
            for idx, raw_inp in enumerate(test_inputs):
                eval_res = evaluate_case(tenant_prd_ruleset.definition, raw_inp)
                case_id = f"seed-case-prd-{idx+1:03d}"
                decision = Decision(
                    tenant_id="tenant-prd",
                    case_id=case_id,
                    rule_version_id=tenant_prd_ruleset.id,
                    rule_version=tenant_prd_ruleset.version,
                    rule_hash=tenant_prd_ruleset.content_hash,
                    route=eval_res.route,
                    p=eval_res.p,
                    expected_cost=eval_res.expected_cost,
                    input_snapshot=eval_res.input_snapshot,
                    trace=eval_res.trace,
                    citizen_reason=eval_res.citizen_reason,
                )
                session.add(decision)

            logger.info("Successfully seeded 30 baseline decisions.")

        await session.commit()
        logger.info("Database seeding completed idempotently.")

if __name__ == "__main__":
    asyncio.run(seed_data())
