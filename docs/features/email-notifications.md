# Email & Notifications Module

Documentation for the email and notifications system in DentalPin.

## Overview

The notifications module provides a complete email notification system with:

- **Per-clinic SMTP configuration** - Each clinic can configure its own email server
- **Event-driven notifications** - Automatic emails triggered by system events
- **Manual notifications** - Staff can send emails on demand
- **Customizable templates** - Per-clinic template customization
- **Patient preferences** - Opt-in/opt-out per notification type
- **Email logging** - Full audit trail of all sent emails

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Other Modules                             │
│         (clinical, budget, odontogram, etc.)                     │
└─────────────────────────┬───────────────────────────────────────┘
                          │ Events / Direct calls
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   NotificationService                            │
│  - Check preferences (clinic + patient)                          │
│  - Load templates                                                 │
│  - Send via EmailService                                         │
│  - Log results                                                   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      EmailService                                │
│  - Provider selection (global or per-clinic)                     │
│  - Template rendering (Jinja2)                                   │
│  - Email sending                                                 │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │   SMTP   │   │ Console  │   │ Disabled │
    │ Provider │   │ Provider │   │          │
    └──────────┘   └──────────┘   └──────────┘
```

## Email Providers

### SMTP Provider
Production email sending via SMTP server.

```python
# Configuration via ClinicSmtpSettings model
host: str          # e.g., "smtp.gmail.com"
port: int          # e.g., 587
username: str      # SMTP username
password: str      # Encrypted with Fernet
use_tls: bool      # STARTTLS (port 587)
use_ssl: bool      # SSL/TLS (port 465)
from_email: str    # Sender email
from_name: str     # Sender display name
```

### Console Provider
Development mode - prints emails to console instead of sending.

### Disabled
Email completely disabled for the clinic.

## Per-Clinic SMTP Configuration

Each clinic can configure its own SMTP server from Settings > Notifications.

### Database Model

```python
class ClinicSmtpSettings(Base):
    clinic_id: UUID          # One per clinic (unique)
    provider: str            # "smtp" | "console" | "disabled"
    host: str
    port: int
    username: str
    password_encrypted: str  # Fernet encrypted
    use_tls: bool
    use_ssl: bool
    from_email: str
    from_name: str
    is_verified: bool        # True after successful test
    last_verified_at: datetime
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/notifications/smtp-settings` | Get current SMTP config |
| PUT | `/api/v1/notifications/smtp-settings` | Update SMTP config |
| POST | `/api/v1/notifications/smtp-settings/test` | Test connection |

### Password Encryption

SMTP passwords are encrypted using Fernet symmetric encryption:

```python
from app.core.email.encryption import encrypt_password, decrypt_password

# Encrypt before storing
encrypted = encrypt_password("my_smtp_password")

# Decrypt when needed
password = decrypt_password(encrypted)
```

The encryption key is derived from `SECRET_KEY` using PBKDF2.

## Notification Types

| Type | Event | Description |
|------|-------|-------------|
| `appointment_confirmation` | Appointment created | Confirms scheduled appointment |
| `appointment_cancelled` | Appointment cancelled | Notifies cancellation |
| `appointment_reminder` | Scheduled (cron) | Reminder X hours before |
| `budget_sent` | Budget sent to patient | Quote details |
| `budget_accepted` | Budget accepted | Acceptance confirmation |
| `welcome` | Patient created | Welcome new patient |

## Integration Guide

### Option 1: Event-Driven (Recommended)

Publish events and let the notifications module handle them automatically.

```python
from app.core.events import event_bus

# In your module's service
async def create_appointment(db, clinic_id, data):
    appointment = Appointment(**data)
    db.add(appointment)
    await db.commit()

    # Publish event - notifications module will handle it
    event_bus.publish("appointment.scheduled", {
        "clinic_id": str(clinic_id),
        "appointment_id": str(appointment.id),
        "patient_id": str(appointment.patient_id),
        "patient_email": patient.email,
        "patient_name": f"{patient.first_name} {patient.last_name}",
        "start_time": appointment.start_time.isoformat(),
        "professional_name": professional.first_name,
    })

    return appointment
```

**Available Events:**

| Event | Payload |
|-------|---------|
| `appointment.scheduled` | clinic_id, appointment_id, patient_id, patient_email, patient_name, start_time, professional_name |
| `appointment.cancelled` | clinic_id, appointment_id, patient_id, patient_email, patient_name, reason |
| `patient.created` | clinic_id, patient_id, patient_email, patient_name |
| `budget.sent` | clinic_id, budget_id, patient_id, patient_email, patient_name, budget_number, total |
| `budget.accepted` | clinic_id, budget_id, patient_id, patient_email, patient_name |

### Option 2: Direct NotificationService Call

For more control, call the NotificationService directly.

```python
from app.modules.notifications.service import NotificationService

async def send_custom_notification(db, clinic_id, patient):
    result = await NotificationService.send_notification(
        db=db,
        clinic_id=clinic_id,
        notification_type="welcome",
        to_email=patient.email,
        context={
            "patient_name": f"{patient.first_name} {patient.last_name}",
            "clinic_name": "Mi Clínica Dental",
            "clinic_phone": "+34 123 456 789",
        },
        patient_id=patient.id,
        triggered_by_event="patient.created",
        force_send=False,  # Respect preferences
    )

    if result.is_success:
        print(f"Email sent: {result.message_id}")
    else:
        print(f"Email failed: {result.error_message}")
```

### Option 3: Low-Level EmailService

For non-notification emails (reports, exports, etc.):

```python
from app.core.email import email_service
from app.core.email.providers.base import EmailMessage

async def send_report_email(db, clinic_id, to_email, report_html):
    message = EmailMessage(
        to_email=to_email,
        subject="Monthly Report - DentalPin",
        body_html=report_html,
        body_text="Please view this email in an HTML-capable client.",
    )

    # Uses clinic-specific SMTP if configured
    result = await email_service.send(
        message,
        db=db,
        clinic_id=clinic_id,
    )

    return result
```

## Email Templates

### Template Location

```
backend/templates/email/
├── es/                           # Spanish templates
│   ├── appointment_confirmation.html
│   ├── appointment_cancelled.html
│   ├── appointment_reminder.html
│   ├── budget_sent.html
│   ├── budget_accepted.html
│   └── welcome.html
├── en/                           # English templates
│   └── ...
└── default/                      # Fallback templates
    └── ...
```

### Template Variables

Templates use Jinja2 syntax:

```html
<!DOCTYPE html>
<html>
<body>
    <h1>Hola {{ patient_name }},</h1>
    <p>Tu cita está confirmada para el {{ start_time }}.</p>
    <p>Profesional: {{ professional_name }}</p>
    <hr>
    <p>{{ clinic_name }} - {{ clinic_phone }}</p>
</body>
</html>
```

### Database Template Override

Clinics can customize templates via the database:

```python
# Create custom template for a clinic
template = EmailTemplate(
    clinic_id=clinic_id,
    template_key="appointment_confirmation",
    locale="es",
    subject="Cita confirmada en {{ clinic_name }}",
    body_html="<h1>Custom template HTML...</h1>",
)
```

Priority: Clinic template > System template > File template

## Clinic Settings

### Notification Type Settings

Each clinic can configure per-notification-type behavior:

```python
class ClinicNotificationSettings:
    settings: dict = {
        "appointment_confirmation": {
            "enabled": True,      # Is this notification type active?
            "auto_send": True,    # Send automatically on event?
        },
        "appointment_reminder": {
            "enabled": True,
            "auto_send": True,
            "hours_before": 24,   # When to send reminder
        },
        # ... other types
    }
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/notifications/settings` | Get clinic settings |
| PUT | `/api/v1/notifications/settings` | Update settings |

## Patient Preferences

Patients can opt-out of specific notification types:

```python
class NotificationPreference:
    patient_id: UUID
    email_enabled: bool = True           # Master toggle
    preferences: dict = {
        "appointment_reminder": True,
        "budget_sent": False,            # Opted out
    }
    preferred_locale: str = "es"
```

### Checking Preferences

```python
should_send, reason = await NotificationService.should_send_notification(
    db=db,
    clinic_id=clinic_id,
    notification_type="appointment_reminder",
    patient_id=patient_id,
)

if not should_send:
    print(f"Skipping: {reason}")
    # Possible reasons:
    # - "disabled_at_clinic_level"
    # - "manual_send_required"
    # - "patient_opted_out"
    # - "patient_opted_out_of_appointment_reminder"
```

## Email Logging

All email attempts are logged:

```python
class EmailLog:
    clinic_id: UUID
    recipient_email: str
    patient_id: UUID | None
    template_key: str
    subject: str
    status: str              # "pending" | "sent" | "failed" | "skipped"
    provider: str            # "smtp" | "console"
    provider_message_id: str
    error_message: str | None
    triggered_by_event: str
    triggered_by_user_id: UUID | None
    created_at: datetime
    sent_at: datetime | None
```

### Querying Logs

```python
logs, total = await NotificationService.list_logs(
    db=db,
    clinic_id=clinic_id,
    page=1,
    page_size=20,
    status="failed",          # Filter by status
    patient_id=patient_id,    # Filter by patient
)
```

## Manual Sending

For notifications with `auto_send: False`, users can trigger manual sends:

```python
# API Endpoint
POST /api/v1/notifications/send
{
    "notification_type": "budget_sent",
    "budget_id": "uuid-here",
    "patient_id": "uuid-here"
}
```

The NotificationService will:
1. Load the related entities (budget, patient)
2. Build the template context
3. Send the email
4. Log the result

## Testing

### Test Email Endpoint

```python
POST /api/v1/notifications/test
{
    "to_email": "test@example.com"
}
```

Sends a simple test email to verify the configuration.

### SMTP Test Endpoint

```python
POST /api/v1/notifications/smtp-settings/test
{
    "host": "smtp.gmail.com",
    "port": 587,
    "username": "user@gmail.com",
    "password": "app-password",
    "use_tls": true,
    "use_ssl": false,
    "from_email": "clinic@example.com",
    "to_email": "test@example.com"
}
```

Tests SMTP connection with specific settings before saving.

## Permissions

| Permission | Description |
|------------|-------------|
| `notifications.settings.read` | View clinic notification settings |
| `notifications.settings.write` | Modify SMTP and notification settings |
| `notifications.templates.read` | View email templates |
| `notifications.templates.write` | Edit email templates |
| `notifications.preferences.read` | View patient preferences |
| `notifications.preferences.write` | Modify patient preferences |
| `notifications.logs.read` | View email logs |
| `notifications.send` | Send manual notifications |

## Common Integration Patterns

### Pattern 1: Appointment Module Integration

```python
# In clinical/service.py
async def create_appointment(db, clinic_id, ctx, data):
    appointment = await AppointmentService.create(db, clinic_id, data)

    # Get patient for context
    patient = await PatientService.get(db, clinic_id, data.patient_id)

    # Publish event - notifications module handles the rest
    event_bus.publish("appointment.scheduled", {
        "clinic_id": str(clinic_id),
        "appointment_id": str(appointment.id),
        "patient_id": str(patient.id),
        "patient_email": patient.email,
        "patient_name": f"{patient.first_name} {patient.last_name}",
        "start_time": appointment.start_time.isoformat(),
    })

    return appointment
```

### Pattern 2: Budget Module Integration

```python
# In budget/service.py
async def send_budget(db, clinic_id, budget_id):
    budget = await BudgetService.get(db, clinic_id, budget_id)
    patient = await PatientService.get(db, clinic_id, budget.patient_id)

    # Update status
    budget.status = "sent"
    await db.commit()

    # Trigger notification
    event_bus.publish("budget.sent", {
        "clinic_id": str(clinic_id),
        "budget_id": str(budget.id),
        "patient_id": str(patient.id),
        "patient_email": patient.email,
        "patient_name": f"{patient.first_name} {patient.last_name}",
        "budget_number": budget.budget_number,
        "total": str(budget.total),
        "currency": budget.currency,
    })
```

### Pattern 3: Custom Module with New Notification Type

1. **Add event handler in notifications module:**

```python
# notifications/handlers.py
class NotificationHandlers:
    @staticmethod
    async def on_prescription_issued(data: dict) -> None:
        await NotificationHandlers._send_notification(
            notification_type="prescription_issued",
            data=data,
        )
```

2. **Register in module:**

```python
# notifications/__init__.py
def get_event_handlers(self) -> dict:
    return {
        # ... existing handlers
        "prescription.issued": NotificationHandlers.on_prescription_issued,
    }
```

3. **Add template:**

```html
<!-- templates/email/es/prescription_issued.html -->
<h1>Nueva receta</h1>
<p>Hola {{ patient_name }},</p>
<p>Tu receta está lista para recoger.</p>
```

4. **Publish from your module:**

```python
event_bus.publish("prescription.issued", {
    "clinic_id": str(clinic_id),
    "patient_id": str(patient.id),
    "patient_email": patient.email,
    "patient_name": patient_name,
    "prescription_details": "...",
})
```

## Troubleshooting

### Email not sending

1. Check SMTP settings are configured and verified
2. Check clinic notification settings (`enabled: true`)
3. Check patient hasn't opted out
4. Check email logs for errors

### Template not found

1. Verify template file exists in `templates/email/{locale}/`
2. Check template_key matches filename
3. Fallback order: clinic DB > system DB > file

### SMTP connection failed

1. Verify host and port
2. Check TLS/SSL settings match port (587=TLS, 465=SSL)
3. For Gmail: use App Password, not account password
4. Check firewall allows outbound SMTP

## Environment Variables (Global Fallback)

When no clinic SMTP is configured, falls back to:

```bash
EMAIL_ENABLED=true
EMAIL_PROVIDER=smtp           # smtp | console
EMAIL_SMTP_HOST=smtp.example.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USER=user@example.com
EMAIL_SMTP_PASSWORD=password
EMAIL_SMTP_TLS=true
EMAIL_FROM_ADDRESS=noreply@example.com
EMAIL_FROM_NAME=DentalPin
```
