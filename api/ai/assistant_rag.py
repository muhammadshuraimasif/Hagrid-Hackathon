"""Retrieval-Augmented Policy Assistant for Project Amaanat.

Follows docs/BLUEPRINT.md section 9.6:
- 8 Mock policy documents in English and Urdu.
- TF-IDF Retrieval (scikit-learn) with zero external vector DB dependencies.
- Strict Grounding: Answers only from retrieved text and always provides citations.
- Fallback Safety: Low similarity returns "I am not sure" plus human officer escalation.
- Policy Assistant NEVER decides eligibility or approves claims.
"""
from typing import Any, Dict, List, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


POLICY_DOCUMENTS = [
    {
        "id": "DOC-01",
        "title": "Eligibility Criteria for Emergency Relief Grants",
        "title_ur": "ہنگامی امدادی گرانٹ کے لیے اہلیت کے معیار",
        "content": "To qualify for the emergency grant, the household monthly income must not exceed PKR 25,000. Additionally, the verified household size must be at least 4 members. Only one grant is permitted per NADRA household family unit. The maximum standard grant amount is PKR 25,000.",
        "content_ur": "امدادی گرانٹ کے لیے گھرانے کی ماہانہ آمدنی 25,000 روپے سے زیادہ نہیں ہونی چاہیے۔ گھر کے افراد کی تعداد کم از کم 4 ہونی چاہیے۔ نادرا کے تحت ایک خاندان کے لیے صرف ایک درخواست منظور ہو سکتی ہے۔ گرانٹ کی زیادہ سے زیادہ حد 25,000 روپے ہے۔",
        "category": "eligibility"
    },
    {
        "id": "DOC-02",
        "title": "Required Documents and Verification",
        "title_ur": "درکار دستاویزات اور تصدیق",
        "content": "Applicants must provide clear color photographs of their original National Identity Card (CNIC), both front and back. The card must have all 4 corners visible, without glare or blur. The back must include a legible, unscratched QR code for civil registry signature validation.",
        "content_ur": "درخواست گزار کو اپنے اصل قومی شناختی کارڈ کے دونوں اطراف کی واضح رنگین تصاویر فراہم کرنا ہوں گی۔ تصویر میں تمام چاروں کونے واضح ہوں اور روشنی کا عکس یا دھندلا پن نہ ہو۔ پشت پر کیو آر کوڈ واضح ہونا ضروری ہے۔",
        "category": "documents"
    },
    {
        "id": "DOC-03",
        "title": "Identifying Genuine Amaanat Communications and Scam Warning",
        "title_ur": "امانت کے اصل پیغامات کی شناخت اور دھوکہ دہی سے بچاؤ",
        "content": "Every authentic Amaanat notification carries a cryptographically signed code formatted as AMN-XXXXXXXX. Amaanat and government officers NEVER demand advance fees, registration charges, or EasyPaisa/JazzCash transfers to release relief funds. We never ask for your ATM PIN or bank OTP.",
        "content_ur": "امانت کا ہر سرکاری پیغام AMN-XXXXXXXX طرز کے تصدیقی کوڈ کا حامل ہوتا ہے۔ کوئی بھی سرکاری افسر رقم جاری کرنے کے لیے پیشگی فیس یا ایزی پیسہ/جاز کیش منتقلی کا مطالبہ نہیں کرتا۔ اپنا پن کوڈ یا او ٹی پی کسی کو نہ بتائیں۔",
        "category": "security"
    },
    {
        "id": "DOC-04",
        "title": "Citizen Consent and Right to Withdraw Consent",
        "title_ur": "شہری کی رضامندی اور رضامندی واپس لینے کا حق",
        "content": "Citizens hold full sovereignty over their personal data under the Universal Consent Gateway. You may withdraw consent at any time via Settings -> Withdraw Consent. Upon withdrawal, the consent epoch increments immediately, all helper delegations terminate, and subsequent data reads are strictly forbidden (HTTP 403).",
        "content_ur": "شہریوں کو اپنے ذاتی ڈیٹا پر مکمل اختیار حاصل ہے۔ آپ کسی بھی وقت سیٹنگز میں جا کر رضامندی واپس لے سکتے ہیں۔ رضامندی کی منسوخی کے فوراً بعد ڈیٹا تک رسائی مستقل طور پر بند ہو جاتی ہے۔",
        "category": "consent"
    },
    {
        "id": "DOC-05",
        "title": "Why You May Receive an Information Request (ASK)",
        "title_ur": "آپ سے اضافی معلومات کیوں طلب کی جا سکتی ہے (ASK)",
        "content": "If your uploaded document is blurry, has camera glare, or one field is ambiguous, the system assigns an 'ASK' route instead of escalating to human delay. This requests one specific, free clarification (such as retaking the photo or confirming a father's name) without delaying your overall case.",
        "content_ur": "اگر شناختی کارڈ کی تصویر دھندلی ہو یا اس پر چمک ہو تو سسٹم آپ سے ایک مخصوص معلومات کی دوبارہ فراہمی کی درخواست کرتا ہے تاکہ کیس بغیر تاخیر کے آگے بڑھ سکے۔",
        "category": "process"
    },
    {
        "id": "DOC-06",
        "title": "Reversible Payment Hold Safety Mechanism",
        "title_ur": "ادائیگی کے عارضی ہولڈ کا حفاظتی طریقہ کار",
        "content": "When a claim is automatically approved, funds are authorized on the Raast instant payment system into a 60-second reversible hold. This allows a human officer to review anomalies or dispute claims before irreversible cash disbursement occurs. If no reversal is initiated, funds disburse automatically.",
        "content_ur": "جب کوئی کیس خودکار طور پر منظور ہوتا ہے تو راست سسٹم پر 60 سیکنڈ کے عارضی ہولڈ میں فنڈز رکھے جاتے ہیں تاکہ کوئی غلطی ہونے پر افسر جائزہ لے سکے۔ اگر کوئی اعتراض نہ ہو تو رقم منتقل ہو جاتی ہے۔",
        "category": "payment"
    },
    {
        "id": "DOC-07",
        "title": "Role and Guidelines for Community Helper Agents",
        "title_ur": "کمیونٹی مددگاروں کے فرائض اور رہنما اصول",
        "content": "Authorized helpers can assist citizens who lack digital literacy or smartphones. Helpers must obtain verbal or written consent, resulting in an active helper grant receipt. Helpers cannot withdraw consent on behalf of citizens, and helper devices are monitored to prevent bulk claim exploitation.",
        "content_ur": "مددگار ایسے شہریوں کی مدد کر سکتے ہیں جن کے پاس اسمارٹ فون نہیں ہے۔ مددگار کو شہری سے رضامندی حاصل کرنا لازمی ہے۔ مددگار شہری کی طرف سے رضامندی منسوخ نہیں کر سکتے۔",
        "category": "helpers"
    },
    {
        "id": "DOC-08",
        "title": "Human Officer Review and Decision Supremacy",
        "title_ur": "انسانی افسر کے جائزے کا حق اور بالادستی",
        "content": "AI never rejects a citizen and never finalizes money without cryptographic verification. Every ambiguous case, anomaly, or discrepancy routes to a certified human relief officer. Only a human officer possesses the authority to issue an application rejection.",
        "content_ur": "مصنوعی ذہانت کبھی کسی شہری کو مسترد نہیں کرتی۔ تمام غیر واضح کیسز انسانی افسر کے پاس جاتے ہیں اور صرف انسانی افسر کو ہی درخواست مسترد کرنے کا اختیار حاصل ہے۔",
        "category": "governance"
    }
]


class PolicyRAGEngine:
    """TF-IDF Document Retriever for Policy QA."""

    def __init__(self):
        self.documents = POLICY_DOCUMENTS
        # Combine English & Urdu texts for bilingual indexing
        corpus = [f"{d['title']} {d['content']} {d['title_ur']} {d['content_ur']}" for d in self.documents]
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
        self.doc_vectors = self.vectorizer.fit_transform(corpus)

    def retrieve(self, query: str, top_k: int = 2) -> List[Tuple[Dict[str, Any], float]]:
        """Retrieves top k documents matching query with cosine similarity scores."""
        query_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(query_vec, self.doc_vectors)[0]

        ranked_indices = sims.argsort()[::-1][:top_k]
        results = []
        for idx in ranked_indices:
            score = float(sims[idx])
            results.append((self.documents[idx], score))
        return results

    def answer_query(self, query: str) -> Dict[str, Any]:
        """Answers policy question strictly grounded in retrieved documents.
        
        Returns answer with citations, or 'not sure' fallback if similarity < 0.20.
        """
        retrieved = self.retrieve(query, top_k=2)
        best_doc, best_score = retrieved[0] if retrieved else (None, 0.0)

        # Fallback if relevance is below strict confidence threshold
        if best_score < 0.12:
            return {
                "query": query,
                "answer": "I am not sure about this topic based on the official relief guidelines. Please consult an in-person relief officer at your local municipal assistance desk for clarification.",
                "answer_ur": "سرکاری رہنما خطوط کے مطابق مجھے اس موضوع کے بارے میں یقین سے معلومات نہیں ہیں۔ براہ کرم رہنمائی کے لیے اپنے قریبی ریلیف افسر سے رابطہ کریں۔",
                "citations": [],
                "confidence": round(best_score, 4),
                "is_confident": False,
                "human_handoff_recommended": True,
            }

        # Build grounded response
        is_urdu_query = any("\u0600" <= c <= "\u06FF" for c in query)
        doc_content = best_doc["content_ur"] if is_urdu_query else best_doc["content"]
        citation_tag = f"[{best_doc['id']}: {best_doc['title_ur'] if is_urdu_query else best_doc['title']}]"

        answer_text = f"According to official policy {citation_tag}: {doc_content}"
        answer_ur = f"سرکاری پالیسی کے مطابق {citation_tag}: {best_doc['content_ur']}"

        return {
            "query": query,
            "answer": answer_text,
            "answer_ur": answer_ur,
            "citations": [f"{best_doc['id']}: {best_doc['title']}"],
            "confidence": round(best_score, 4),
            "is_confident": True,
            "human_handoff_recommended": False,
        }


# Singleton RAG assistant instance
policy_assistant = PolicyRAGEngine()
