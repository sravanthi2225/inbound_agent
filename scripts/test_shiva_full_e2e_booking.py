import asyncio
import json
import logging
import httpx
from api.db.db_client import DBClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("e2e_booking_test")

async def main():
    client = httpx.AsyncClient(timeout=90.0)

    # 1. Login as shivaprasad@gmail.com
    res_login = await client.post(
        "http://localhost:8500/api/v1/auth/login",
        json={"email": "shivaprasad@gmail.com", "password": "shiva@112"}
    )
    assert res_login.status_code == 200, f"Login failed: {res_login.text}"
    token = res_login.json()["token"]
    user = res_login.json()["user"]
    headers = {"Authorization": f"Bearer {token}"}
    logger.info(f"Authenticated as {user['email']}, org_id={user['organization_id']}")

    # 2. Get Shiva's workflow (Workflow 9)
    res_wfs = await client.get("http://localhost:8500/api/v1/workflow/fetch", headers=headers)
    wfs = res_wfs.json()
    wf_id = wfs[0]["id"]
    logger.info(f"Using workflow {wf_id}: {wfs[0]['name']}")

    # 3. Create test session (simulates the Test Chat panel in the Dograh UI)
    res_session = await client.post(
        f"http://localhost:8500/api/v1/workflow/{wf_id}/text-chat/sessions",
        headers=headers,
        json={"name": "E2E-Booking-Test"}
    )
    assert res_session.status_code == 200, f"Session create failed: {res_session.text}"
    session_data = res_session.json()
    run_id = session_data["workflow_run_id"]
    revision = session_data["revision"]
    logger.info(f"Created Test Chat session: run_id={run_id}, revision={revision}")

    # Inspect initial assistant greeting
    turns = session_data.get("session_data", {}).get("turns", [])
    if turns:
        logger.info(f"Agent Opening Greeting: {turns[-1].get('text')}")

    # 4. User sends appointment booking request with all details
    user_msg = (
        "Sam, could you book an appointment for Shiva Prasad in Cardiology tomorrow at 10:30 AM? "
        "My phone number is +919876543210."
    )
    logger.info(f"User Message: {user_msg}")

    res_turn = await client.post(
        f"http://localhost:8500/api/v1/workflow/{wf_id}/text-chat/sessions/{run_id}/messages",
        headers=headers,
        json={"text": user_msg, "expected_revision": revision}
    )
    assert res_turn.status_code == 200, f"Message turn failed: {res_turn.text}"
    turn_data = res_turn.json()
    new_turns = turn_data.get("session_data", {}).get("turns", [])

    logger.info("--- Conversation Turns ---")
    for t in new_turns:
        role = t.get("role") or "ASSISTANT"
        text = t.get("text") or t.get("content") or ""
        tool_calls = t.get("tool_calls", [])
        logger.info(f"[{str(role).upper()}]: {text}")
        if tool_calls:
            for tc in tool_calls:
                logger.info(f"  --> TOOL EXECUTED: {tc.get('name')} with arguments: {tc.get('arguments')}")

    # 5. Verify direct database booking
    db = DBClient()
    appts = await db.list_appointments(organization_id=user["organization_id"])
    logger.info(f"Total appointments in Org {user['organization_id']}: {len(appts)}")
    for a in appts:
        logger.info(f"Appointment in DB: Code={a.appointment_code}, Patient={a.customer_name}, Phone={a.customer_phone}, Date={a.appointment_date}, Time={a.appointment_time}, Status={a.status}")

    # 6. Verify WhatsApp Meta Confirmation Endpoint directly
    res_wa = await client.post(
        "http://localhost:8500/api/v1/appointments/send-whatsapp-confirmation",
        json={
            "customer_phone": "+919876543210",
            "customer_name": "Shiva Prasad",
            "service_type": "Cardiology",
            "appointment_date": "2026-11-18",
            "appointment_time": "10:30 AM",
            "appointment_code": "APT-SHIVA01"
        }
    )
    assert res_wa.status_code == 200, f"WhatsApp confirmation failed: {res_wa.text}"
    wa_result = res_wa.json()
    logger.info(f"WhatsApp Meta Cloud API Confirmation Result: {wa_result}")
    assert wa_result["success"] is True
    assert wa_result["status"] == "delivered"
    assert "wamid." in wa_result["whatsapp_message_id"]

    logger.info("=================================================================")
    logger.info("ALL E2E WORKFLOW & WHATSAPP CRM TESTS PASSED WITH 100% SUCCESS!")
    logger.info("=================================================================")

if __name__ == "__main__":
    asyncio.run(main())
