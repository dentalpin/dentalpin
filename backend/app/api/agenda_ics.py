
"""ICS calendar export endpoint for dental appointments."""

from datetime import datetime
from fastapi import APIRouter, HTTPException
from uuid import UUID

router = APIRouter(prefix="/api/agenda", tags=["agenda"])

def _generate_ics(appointment: dict) -> str:
    """Generate RFC 5545 compliant .ics content from an appointment."""
    uid = str(appointment.get("id", ""))
    dtstart = appointment.get("start_time", datetime.now()).strftime("%Y%m%dT%H%M%S")
    dtend = appointment.get("end_time", datetime.now()).strftime("%Y%m%dT%H%M%S")
    summary = f"Appointment: {appointment.get('patient_name', 'Patient')}"
    description = appointment.get("notes", "")
    location = appointment.get("location", "")
    
    ics = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//DentalPin//Calendar Export//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}@dentalpin",
        f"DTSTART:{dtstart}",
        f"DTEND:{dtend}",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{description}",
        f"LOCATION:{location}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(ics)


@router.get("/appointments/{appointment_id}/ics")
async def export_appointment_ics(appointment_id: UUID):
    """Export an appointment as an .ics calendar file."""
    # In practice, fetch from DB - here we provide the structure
    return {"message": "ICS export endpoint - integrate with your appointment service"}
