---
module: odontogram
last_verified_commit: 4e5364c6
---

# Dental chart and diagnosis workflow

The odontogram is part of the patient's **Clinical** tab. Use it to
record a diagnosis on a tooth, note affected surfaces, and add a mapped
procedure to a treatment plan after clinician review.

## Record a diagnosis

1. Open the patient and select **Clinical**.
2. Select **Diagnosis** mode and click the tooth.
3. In the first step, choose a diagnosis from the catalog. If no diagnosis
   is selected, **Next** stays disabled.
4. In the second step, select affected tooth surfaces. You can click the
   occlusal diagram, the surface buttons, or the crown in the lateral
   view to toggle the vestibular surface. **Back** returns to diagnosis
   selection without discarding the selected diagnosis or surfaces.
5. Confirm to save the diagnosis. If the catalog entry maps to a
   recommended procedure, the app asks whether to add it to a treatment
   plan. A clinician must confirm this choice; manual procedure entry
   remains available.

## Treatment plans

The diagnosis sidebar shows one prominent action to create a plan or
continue an existing draft. With multiple drafts, select the plan first.
If the patient has no plan, the summary card explains that a plan has not
been created and links directly to creation.

## Responsive use

At desktop, tablet, and mobile widths the tooth chart scales to its
container. The lateral view remains available alongside the occlusal
view, and the modal keeps the diagnosis and surface controls scrollable.

## Permissions

- `odontogram.read`
- `odontogram.write`
- `odontogram.treatments.read`
- `odontogram.treatments.write`

## Technical references

- [Technical overview](../../../technical/odontogram/overview.md)
- [Permissions](../../../technical/odontogram/permissions.md)
- [Events](../../../technical/odontogram/events.md)

## Technical references

- [Technical overview](../../../technical/odontogram/overview.md)
- [Permissions](../../../technical/odontogram/permissions.md)
- [Events](../../../technical/odontogram/events.md)
