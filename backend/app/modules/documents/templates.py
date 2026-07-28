"""Jinja2 template strings for each generated document type.

Kept as Python strings (rather than loose .html files) so the module has
zero extra packaging/loader configuration — Jinja2's `Template(...)`
works directly on these. Split into files later if they grow unwieldy.
"""

BASE_STYLE = """
<style>
  @page { size: A4; margin: 2.5cm 2cm; }
  body { font-family: 'Helvetica Neue', Arial, sans-serif; color: #1a1a1a; font-size: 12pt; }
  .letterhead { display: flex; align-items: center; gap: 16px; border-bottom: 2px solid #2b6cb0; padding-bottom: 12px; margin-bottom: 24px; }
  .letterhead img { height: 60px; }
  .letterhead .practice-name { font-size: 16pt; font-weight: 700; color: #2b6cb0; }
  .letterhead .practice-meta { font-size: 9pt; color: #555; }
  .doc-title { font-size: 14pt; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 16px; }
  .field-row { margin-bottom: 6px; }
  .field-label { font-weight: 600; display: inline-block; min-width: 140px; }
  table.items { width: 100%; border-collapse: collapse; margin-top: 12px; }
  table.items th, table.items td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; font-size: 10.5pt; }
  .signature-block { margin-top: 64px; display: flex; justify-content: flex-end; }
  .signature-line { border-top: 1px solid #333; width: 260px; text-align: center; padding-top: 6px; font-size: 10pt; }
  .footer { position: fixed; bottom: 0; font-size: 8pt; color: #888; }
</style>
"""

LETTERHEAD_BLOCK = """
<div class="letterhead">
  {% if letterhead and letterhead.logo_url %}<img src="{{ letterhead.logo_url }}" />{% endif %}
  <div>
    <div class="practice-name">{{ letterhead.practice_name if letterhead else clinic.name }}</div>
    <div class="practice-meta">
      {% if letterhead and letterhead.address %}{{ letterhead.address.get('line1', '') }} — {% endif %}
      {% if letterhead and letterhead.phone %}{{ letterhead.phone }} — {% endif %}
      {% if letterhead and letterhead.email %}{{ letterhead.email }}{% endif %}
    </div>
    {% if letterhead and letterhead.registration_number %}
    <div class="practice-meta">Reg. No. {{ letterhead.registration_number }}</div>
    {% endif %}
  </div>
</div>
"""

SIGNATURE_BLOCK = """
<div class="signature-block">
  <div class="signature-line">{{ practitioner_name or '&nbsp;' }}</div>
</div>
"""

PRESCRIPTION_TEMPLATE = f"""
<html><head><meta charset="utf-8">{BASE_STYLE}</head><body>
{LETTERHEAD_BLOCK}
<div class="doc-title">{{{{ title }}}}</div>
<div class="field-row"><span class="field-label">Patient:</span> {{{{ patient.full_name }}}}</div>
<div class="field-row"><span class="field-label">Date of birth:</span> {{{{ patient.date_of_birth }}}}</div>
<div class="field-row"><span class="field-label">Date:</span> {{{{ generated_date }}}}</div>
<table class="items">
  <thead><tr><th>Medication</th><th>Dosage</th><th>Instructions</th><th>Qty</th></tr></thead>
  <tbody>
  {{% for item in items %}}
    <tr><td>{{{{ item.drug_name }}}}</td><td>{{{{ item.dosage }}}}</td><td>{{{{ item.instructions }}}}</td><td>{{{{ item.quantity or '' }}}}</td></tr>
  {{% endfor %}}
  </tbody>
</table>
{{% if notes %}}<div class="field-row" style="margin-top:16px;"><span class="field-label">Notes:</span> {{{{ notes }}}}</div>{{% endif %}}
{SIGNATURE_BLOCK}
</body></html>
"""

CERTIFICATE_TEMPLATE = f"""
<html><head><meta charset="utf-8">{BASE_STYLE}</head><body>
{LETTERHEAD_BLOCK}
<div class="doc-title">{{{{ title }}}}</div>
<p>
  This is to certify that patient <strong>{{{{ patient.full_name }}}}</strong>
  (DOB {{{{ patient.date_of_birth }}}}) was examined at this practice on {{{{ generated_date }}}}
  {{% if certificate_type == 'work_absence' %}}and is advised to be absent from work{{% endif %}}
  {{% if certificate_type == 'school_absence' %}}and is advised to be absent from school{{% endif %}}
  {{% if certificate_type == 'fitness_for_work' %}}and has been assessed as fit for work{{% endif %}}
  {{% if start_date %}} from {{{{ start_date }}}}{{% endif %}}{{% if end_date %}} to {{{{ end_date }}}}{{% endif %}}.
</p>
{{% if reason %}}<div class="field-row"><span class="field-label">Reason:</span> {{{{ reason }}}}</div>{{% endif %}}
{{% if notes %}}<div class="field-row"><span class="field-label">Notes:</span> {{{{ notes }}}}</div>{{% endif %}}
{SIGNATURE_BLOCK}
</body></html>
"""

REFERRAL_TEMPLATE = f"""
<html><head><meta charset="utf-8">{BASE_STYLE}</head><body>
{LETTERHEAD_BLOCK}
<div class="doc-title">{{{{ title }}}}</div>
<div class="field-row"><span class="field-label">To:</span> {{{{ specialist_name }}}} ({{{{ specialty }}}})</div>
<div class="field-row"><span class="field-label">Patient:</span> {{{{ patient.full_name }}}}</div>
<div class="field-row"><span class="field-label">Date of birth:</span> {{{{ patient.date_of_birth }}}}</div>
<div class="field-row"><span class="field-label">Urgency:</span> {{{{ urgency }}}}</div>
<div class="field-row" style="margin-top:16px;"><span class="field-label">Reason for referral:</span></div>
<p>{{{{ reason }}}}</p>
{{% if clinical_history %}}
<div class="field-row"><span class="field-label">Relevant history:</span></div>
<p>{{{{ clinical_history }}}}</p>
{{% endif %}}
{SIGNATURE_BLOCK}
</body></html>
"""

RADIOLOGY_TEMPLATE = f"""
<html><head><meta charset="utf-8">{BASE_STYLE}</head><body>
{LETTERHEAD_BLOCK}
<div class="doc-title">{{{{ title }}}}</div>
<div class="field-row"><span class="field-label">Patient:</span> {{{{ patient.full_name }}}}</div>
<div class="field-row"><span class="field-label">Date of birth:</span> {{{{ patient.date_of_birth }}}}</div>
<div class="field-row"><span class="field-label">Exam requested:</span> {{{{ exam_type }}}}</div>
{{% if tooth_reference %}}<div class="field-row"><span class="field-label">Tooth reference:</span> {{{{ tooth_reference }}}}</div>{{% endif %}}
<div class="field-row" style="margin-top:16px;"><span class="field-label">Clinical indication:</span></div>
<p>{{{{ clinical_indication }}}}</p>
{{% if notes %}}<div class="field-row"><span class="field-label">Notes:</span> {{{{ notes }}}}</div>{{% endif %}}
{SIGNATURE_BLOCK}
</body></html>
"""

TEMPLATES_BY_TYPE = {
    "prescription": PRESCRIPTION_TEMPLATE,
    "certificate": CERTIFICATE_TEMPLATE,
    "referral": REFERRAL_TEMPLATE,
    "radiology_request": RADIOLOGY_TEMPLATE,
}
