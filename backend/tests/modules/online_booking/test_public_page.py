"""Settings and HTTP contract behind the public Nuxt booking page."""

from __future__ import annotations

import pytest
from booking_helpers import configure, professional, proof_for, tomorrow_at
from pydantic import ValidationError

from app.modules.online_booking.schemas import SettingsInput, https_origin


def test_embed_origins_accept_only_https_origins_and_are_normalised():
    assert https_origin("https://Clinic.Example.ES") == "https://clinic.example.es"
    assert https_origin("https://clinic.example.es:8443") == "https://clinic.example.es:8443"
    for bad in (
        "http://clinic.example.es",
        "https://clinic.example.es/path",
        "https://clinic.example.es/",
        "https://clinic.example.es?x=1",
        "https://user@clinic.example.es",
        "https://*.example.es",
        "https://example.es; script-src *",
        "https://",
        "*",
        "",
    ):
        assert https_origin(bad) is None, bad
    value = SettingsInput(embed_origins=["https://A.example.es", "https://a.example.es"])
    assert value.embed_origins == ["https://a.example.es"]
    with pytest.raises(ValidationError):
        SettingsInput(embed_origins=["https://a.example.es/booking"])
    with pytest.raises(ValidationError):
        SettingsInput(embed_origins=[f"https://s{i}.example.es" for i in range(11)])


def test_privacy_url_must_be_plain_https():
    assert SettingsInput(privacy_url="https://clinic.example.es/privacy").privacy_url
    with pytest.raises(ValidationError):
        SettingsInput(privacy_url="http://clinic.example.es/privacy")


@pytest.mark.asyncio
async def test_public_config_exposes_page_settings(client, db_session, test_clinic):
    pro = await professional(db_session, test_clinic.id)
    config = await configure(db_session, test_clinic.id, pro.id)
    config.privacy_url = "https://clinic.example.es/privacy"
    config.embed_origins = ["https://clinic.example.es"]
    await db_session.commit()
    response = await client.get(f"/api/v1/online_booking/public/{test_clinic.id}/config")
    data = response.json()["data"]
    assert data["privacy_url"] == "https://clinic.example.es/privacy"
    assert data["embed_origins"] == ["https://clinic.example.es"]


@pytest.mark.asyncio
async def test_captcha_domain_errors_map_to_http_statuses(
    client, db_session, test_clinic, open_hours, delivery
):
    pro = await professional(db_session, test_clinic.id)
    await configure(db_session, test_clinic.id, pro.id)
    url = f"/api/v1/online_booking/public/{test_clinic.id}/requests"
    body = {
        "start_time": tomorrow_at(10).isoformat(),
        "contact_name": "Synthetic Person",
        "contact_email": "synthetic@example.com",
        "contact_phone": "+34600123456",
        "reason": "checkup",
        "altcha": "not-a-payload",
    }
    invalid = await client.post(url, json=body)
    assert invalid.status_code == 400
    proof = proof_for(test_clinic.id)
    assert (await client.post(url, json={**body, "altcha": proof})).status_code == 201
    other = {
        **body,
        "contact_email": "other@example.com",
        "start_time": tomorrow_at(11).isoformat(),
    }
    assert (await client.post(url, json={**other, "altcha": proof})).status_code == 409


@pytest.mark.parametrize(
    "environment,allowed", [("development", True), ("test", False), ("production", False)]
)
@pytest.mark.parametrize("host", ["localhost:3000", "127.0.0.1:3000"])
def test_http_local_urls_are_development_only(monkeypatch, environment, allowed, host):
    from app.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", environment)
    values = {
        "public_url": f"http://{host}/book",
        "privacy_url": f"http://{host}/privacy",
        "embed_origins": [f"http://{host}"],
    }
    if allowed:
        assert SettingsInput(**values).embed_origins == [f"http://{host}"]
    else:
        with pytest.raises(ValidationError):
            SettingsInput(**values)
    with pytest.raises(ValidationError):
        SettingsInput(embed_origins=["http://example.invalid:3000"])
    with pytest.raises(ValidationError):
        SettingsInput(redirect_url=f"http://{host}/thanks")
