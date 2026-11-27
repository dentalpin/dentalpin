"""GDPR erasure contributor for the documents module (#657).

Owns the ``documents`` coverage scope: generated prescriptions,
certificates and referrals are issued records, so this contributor
retains them and reports what it holds. Registered via
``DocumentsModule.get_erasure_contributors``; pulled by ``gdpr`` inside
the erasure transaction (ADR 0038).
"""

from __future__ import annotations

from app.core.erasure.retention import RetainedScopeContributor


class DocumentsErasureContributor(RetainedScopeContributor):
    """Retain generated clinical documents on a GDPR erasure.

    ``GeneratedDocument.content`` is a free-form JSONB snapshot of the
    document as issued, and ``file_path`` points at the rendered file, so
    any erasure category can appear, so all three are declared. A
    prescription or certificate is retained under
    Art. 17(3)(c)/(h): it is a clinical record that must match the copy
    handed to the patient or the pharmacy.

    Consent signature evidence (``ConsentEvidence``) is retained as a whole,
    including ``signer_name`` and ``signer_id_document`` (the DNI/NIE or
    passport number of the signer, who may be a guardian or representative
    rather than the patient). The signed PDF prints both and its SHA-256 is
    the legal proof of the consent, so neither column can be blanked without
    invalidating it; they sit in the declared ``identity`` category. Both are
    treated the same way: retained under Art. 17(3)(c)/(h), never nulled.

    This module is ``auto_install: False``, so a clinic that never
    installed it gets no ``documents`` row at all — the registry only
    collects from active modules.
    """

    scope_name = "documents"
    categories = frozenset({"email", "phone", "identity"})
    detail = "Issued prescriptions, certificates, referrals, consents and signature evidence (including the signer's name and ID document) retained as clinical records (Art. 17(3)(c)/(h)); the stored snapshot may quote erased contacts."
