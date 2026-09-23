# orthodontics - events

| Event | Direction | Payload |
|---|---|---|
| `orthodontics.case_created` | published | `case_id`, `clinic_id`, `patient_id`, `appliance_type` |
| `orthodontics.case_status_changed` | published | `case_id`, `clinic_id`, `patient_id`, `previous_status`, `status` |
| `orthodontics.control_registered` | published | `case_id`, `control_id`, `clinic_id`, `patient_id`, `upper_wire`, `lower_wire`, `procedures`, `next_due` |

All three are consumed by `patient_timeline` (payload-only rows).
Slice-b adds no new events; the recall upsert reuses the recalls
module's own surface.
