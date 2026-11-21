"""Scorer interfaces and deterministic stubs for Identity and Document analysis.

Follows docs/BLUEPRINT.md section 8.3.
Stubs are clearly marked as 'STUB' in traces and will be swapped with full AI models in Module 6.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class IdentityScorer(ABC):
    """Interface for evaluating identity match strength between claimant and registry."""

    @abstractmethod
    def score(self, person_data: Dict[str, Any], nadra_record: Optional[Dict[str, Any]]) -> Tuple[float, Dict[str, Any]]:
        pass


class DocumentScorer(ABC):
    """Interface for evaluating document authenticity, clarity, and completeness."""

    @abstractmethod
    def score(self, uploaded_docs: List[Dict[str, Any]]) -> Tuple[float, Dict[str, Any]]:
        pass


class StubIdentityScorer(IdentityScorer):
    """Deterministic stub identity scorer marked STUB in trace."""

    def score(self, person_data: Dict[str, Any], nadra_record: Optional[Dict[str, Any]]) -> Tuple[float, Dict[str, Any]]:
        if not nadra_record:
            return 0.50, {
                "scorer": "STUB",
                "match_type": "NO_RECORD",
                "identity_match_exact": False,
                "notes": "No matching NADRA record found"
            }

        claimant_name = (person_data.get("canonical_name") or person_data.get("name") or "").strip().upper()
        nadra_name = (nadra_record.get("name") or "").strip().upper()

        if claimant_name == nadra_name:
            return 0.98, {
                "scorer": "STUB",
                "match_type": "EXACT",
                "identity_match_exact": True,
                "notes": "Exact identity match verified"
            }

        # Check common name variants
        v_tokens = {"MUHAMMAD", "MOHAMMAD", "MUHAMMED", "MOHD", "MD"}
        c_set = set(claimant_name.split())
        n_set = set(nadra_name.split())
        if c_set.intersection(v_tokens) and n_set.intersection(v_tokens):
            return 0.88, {
                "scorer": "STUB",
                "match_type": "PROBABLE_VARIANT",
                "identity_match_exact": False,
                "notes": "Transliteration/spelling variant detected"
            }

        return 0.60, {
            "scorer": "STUB",
            "match_type": "CONFLICT",
            "identity_match_exact": False,
            "notes": "Name disparity between application and registry"
        }


class StubDocumentScorer(DocumentScorer):
    """Deterministic stub document scorer marked STUB in trace."""

    def score(self, uploaded_docs: List[Dict[str, Any]]) -> Tuple[float, Dict[str, Any]]:
        if not uploaded_docs:
            return 0.10, {
                "scorer": "STUB",
                "authenticity_score": 0.10,
                "document_authenticity_above_limit": False,
                "notes": "No documents uploaded"
            }

        all_complete = all(doc.get("is_complete", False) for doc in uploaded_docs)
        has_blurry = any("blurry" in doc.get("filename", "").lower() for doc in uploaded_docs)
        has_forged = any("forged" in doc.get("filename", "").lower() for doc in uploaded_docs)

        if has_forged:
            return 0.25, {
                "scorer": "STUB",
                "authenticity_score": 0.25,
                "document_authenticity_above_limit": False,
                "notes": "Document tampering/forgery markers detected"
            }

        if has_blurry:
            return 0.65, {
                "scorer": "STUB",
                "authenticity_score": 0.65,
                "document_authenticity_above_limit": False,
                "notes": "Image resolution or clarity is borderline"
            }

        if all_complete:
            return 0.96, {
                "scorer": "STUB",
                "authenticity_score": 0.96,
                "document_authenticity_above_limit": True,
                "notes": "Valid genuine document format verified"
            }

        return 0.75, {
            "scorer": "STUB",
            "authenticity_score": 0.75,
            "document_authenticity_above_limit": True,
            "notes": "Partial document set verified"
        }
