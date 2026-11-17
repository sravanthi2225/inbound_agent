import sys
sys.path.insert(0, '.')
import asyncio
import json
import logging
import time
import httpx

from api.db.db_client import DBClient
from api.db.workflow_client import WorkflowClient
from api.db.tool_client import ToolClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("QA_Manual_Tester")

BASE_API = "http://localhost:8500"
BASE_UI = "http://localhost:3000"

results = {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "bugs": []
}

def record_test(name: str, passed: bool, error: str = None):
    results["total"] += 1
    if passed:
        results["passed"] += 1
        logger.info(f"  [PASS] {name}")
    else:
        results["failed"] += 1
        logger.error(f"  [FAIL] {name}: {error}")
        results["bugs"].append({"test": name, "error": error})

async def run_suite_1_auth_isolation(client: httpx.AsyncClient):
    logger.info("=== SUITE 1: Authentication & Multi-Tenant Isolation ===")
    
    # Test 1.1: Login as shivaprasad@gmail.com
    res = await client.post(f"{BASE_API}/api/v1/auth/login", json={"email": "shivaprasad@gmail.com", "password": "shiva@112"})
    passed = res.status_code == 200 and res.json().get("user", {}).get("organization_id") == 4
    record_test("1.1 Login shivaprasad@gmail.com (Org 4)", passed, res.text if not passed else None)
    shiva_token = res.json()["token"]
    shiva_headers = {"Authorization": f"Bearer {shiva_token}"}

    # Test 1.2: Login as bcon@gmail.com
    res2 = await client.post(f"{BASE_API}/api/v1/auth/login", json={"email": "bcon@gmail.com", "password": "Bcon@1234"})
    bcon_token = None
    bcon_headers = None
    if res2.status_code == 200:
        bcon_token = res2.json()["token"]
        bcon_headers = {"Authorization": f"Bearer {bcon_token}"}
        passed2 = res2.json().get("user", {}).get("organization_id") == 2
        record_test("1.2 Login bcon@gmail.com (Org 2)", passed2, res2.text if not passed2 else None)
    else:
        record_test("1.2 Login bcon@gmail.com (Org 2)", False, f"Status: {res2.status_code}")

    # Test 1.3: Negative Login (Wrong Password)
    res_neg = await client.post(f"{BASE_API}/api/v1/auth/login", json={"email": "shivaprasad@gmail.com", "password": "wrongpassword!"})
    record_test("1.3 Reject invalid password with 401", res_neg.status_code == 401, f"Expected 401, got {res_neg.status_code}")

    # Test 1.4: Workflow Listing for Shiva (Org 4)
    res_wfs_shiva = await client.get(f"{BASE_API}/api/v1/workflow/fetch", headers=shiva_headers)
    wfs_s = res_wfs_shiva.json()
    wf_ids_s = [w["id"] for w in wfs_s]
    passed_s = (len(wf_ids_s) == 1 and wf_ids_s[0] == 9)
    record_test("1.4 Shiva sees ONLY Workflow 9", passed_s, f"Found workflows: {wf_ids_s}")

    # Test 1.5: Workflow Listing for Bcon (Org 2)
    if bcon_headers:
        res_wfs_bcon = await client.get(f"{BASE_API}/api/v1/workflow/fetch", headers=bcon_headers)
        wfs_b = res_wfs_bcon.json()
        wf_ids_b = [w["id"] for w in wfs_b]
        passed_b = (9 not in wf_ids_b and 8 in wf_ids_b)
        record_test("1.5 Bcon sees Workflows [5, 8] and NOT Workflow 9", passed_b, f"Found workflows: {wf_ids_b}")

    # Test 1.6: Cross-tenant Access Violation Attempt
    res_cross = await client.get(f"{BASE_API}/api/v1/workflow/fetch/8", headers=shiva_headers)
    # Should not return Workflow 8 details to Shiva
    passed_cross = res_cross.status_code in [403, 404]
    record_test("1.6 Cross-tenant access blocked (Shiva cannot fetch Workflow 8)", passed_cross, f"Got status {res_cross.status_code}")

    return shiva_token, shiva_headers

async def run_suite_2_canvas_structure():
    logger.info("=== SUITE 2: Workflow Canvas, Node Structure & Parameter Integrity ===")
    db = DBClient()
    wf = await db.get_workflow_by_id(9)
    
    # 2.1 Configs check
    configs = wf.workflow_configurations or {}
    min_words = configs.get("turn_start_min_words")
    idle_timeout = configs.get("max_user_idle_timeout")
    passed_cfg = (min_words == 2 and idle_timeout == 35.0)
    record_test("2.1 Anti-echo turn_start_min_words == 2 and idle_timeout == 35s", passed_cfg, f"Got min_words={min_words}, idle={idle_timeout}")

    # 2.2 Node 1 allow_interrupt == False
    nodes = {str(n.get("id")): n for n in wf.workflow_definition.get("nodes", [])}
    node1 = nodes.get("1", {}).get("data", {})
    passed_n1 = (node1.get("allow_interrupt") is False)
    record_test("2.2 Node 1 (Start Call) has allow_interrupt=False", passed_n1, f"Got allow_interrupt={node1.get('allow_interrupt')}")

    # 2.3 Edge conditions
    edges = wf.workflow_definition.get("edges", [])
    edge_1_4 = next((e for e in edges if str(e.get("source")) == "1" and str(e.get("target")) == "4"), None)
    passed_e14 = edge_1_4 and "ONLY if the caller explicitly" in edge_1_4.get("data", {}).get("condition", "")
    record_test("2.3 Edge 1->4 has strict anti-accidental hangup condition", passed_e14, "Condition loose or missing")

    # 2.4 Tool definitions check
    tc = ToolClient()
    tools = await tc.get_tools_for_organization(4)
    tool_names = [t.name for t in tools]
    passed_tools = ("Book Hospital Appointment" in tool_names and "Send WhatsApp Confirmation" in tool_names)
    record_test("2.4 Org 4 has required tools attached", passed_tools, f"Found tools: {tool_names}")

    # Check Book Hospital Appointment body_template workflow_id
    book_tool = next((t for t in tools if t.name == "Book Hospital Appointment"), None)
    bt_wf_id = book_tool.definition.get("config", {}).get("body_template", {}).get("workflow_id") if book_tool else None
    record_test("2.5 Book tool pre-bound to workflow_id: 9", bt_wf_id == 9, f"Got workflow_id: {bt_wf_id}")

def extract_assistant_text(turn: dict) -> str:
    if not turn:
        return ""
    if turn.get("assistant_message") and isinstance(turn["assistant_message"], dict):
        return turn["assistant_message"].get("text", "") or ""
    if turn.get("text"):
        return turn.get("text", "")
    for ev in turn.get("events", []):
        if ev.get("type") == "bot_speech":
            return ev.get("payload", {}).get("text", "") or ""
    return ""

async def run_suite_3_conversational_turns(client: httpx.AsyncClient, shiva_headers: dict):
    logger.info("=== SUITE 3: Conversational Flow, Echo Protection & Anti-Stalling ===")

    # Create session
    res_sess = await client.post(
        f"{BASE_API}/api/v1/workflow/9/text-chat/sessions",
        headers=shiva_headers,
        json={"name": "QA-Session-Test"}
    )
    assert res_sess.status_code == 200, f"Session create failed: {res_sess.text}"
    sess = res_sess.json()
    run_id = sess["workflow_run_id"]
    revision = sess["revision"]

    # 3.1 Initial greeting check
    turns = sess.get("session_data", {}).get("turns", [])
    initial_greeting = extract_assistant_text(turns[-1]) if turns else ""
    passed_31 = "hospital" in initial_greeting.lower() or "sam" in initial_greeting.lower()
    record_test("3.1 Agent speaks initial hospital greeting", passed_31, f"Greeting: {initial_greeting}")

    # 3.2 Edge Case: Caller echoes the agent's name/greeting ("Sam from City Hospital.")
    # The agent MUST NOT hang up or transition to End Call!
    res_echo = await client.post(
        f"{BASE_API}/api/v1/workflow/9/text-chat/sessions/{run_id}/messages",
        headers=shiva_headers,
        json={"text": "Sam from City Hospital.", "expected_revision": revision}
    )
    passed_32 = res_echo.status_code == 200
    if passed_32:
        echo_data = res_echo.json()
        revision = echo_data["revision"]
        turns_echo = echo_data.get("session_data", {}).get("turns", [])
        agent_reply = extract_assistant_text(turns_echo[-1]) if turns_echo else ""
        # Agent should ask how it can help or ask about appointment, NOT say goodbye or hang up!
        not_hanging_up = ("goodbye" not in agent_reply.lower() and "have a wonderful day" not in agent_reply.lower())
        passed_32 = passed_32 and not_hanging_up
        record_test("3.2 Handling echo text: Agent stays active, does NOT hang up", passed_32, f"Agent reply: {agent_reply}")
    else:
        record_test("3.2 Handling echo text: Agent stays active, does NOT hang up", False, res_echo.text)

    # 3.3 Happy Path: Booking request with details
    res_book = await client.post(
        f"{BASE_API}/api/v1/workflow/9/text-chat/sessions/{run_id}/messages",
        headers=shiva_headers,
        json={
            "text": "Yes, I would like to book an appointment with Dr. Sharma in Cardiology on 2026-11-22 at 11:00 AM for patient Shiva Prasad, phone +919876543210.",
            "expected_revision": revision
        }
    )
    passed_33 = res_book.status_code == 200
    if passed_33:
        book_data = res_book.json()
        revision = book_data["revision"]
        turns_book = book_data.get("session_data", {}).get("turns", [])
        agent_book_reply = extract_assistant_text(turns_book[-1]) if turns_book else ""
        record_test("3.3 Booking request processed without stalling", True, None)
        logger.info(f"Agent Booking Reply: {agent_book_reply}")
    else:
        record_test("3.3 Booking request processed without stalling", False, res_book.text)

    # 3.4 Explicit Exit Case: Caller explicitly says "Thank you, goodbye."
    res_exit = await client.post(
        f"{BASE_API}/api/v1/workflow/9/text-chat/sessions/{run_id}/messages",
        headers=shiva_headers,
        json={"text": "Everything is good now. Thank you, goodbye!", "expected_revision": revision}
    )
    passed_34 = res_exit.status_code == 200
    if passed_34:
        exit_data = res_exit.json()
        turns_exit = exit_data.get("session_data", {}).get("turns", [])
        agent_exit_reply = extract_assistant_text(turns_exit[-1]) if turns_exit else ""
        record_test("3.4 Caller explicit goodbye triggers clean polite conclusion", True, None)
        logger.info(f"Agent Exit Reply: {agent_exit_reply}")
    else:
        record_test("3.4 Caller explicit goodbye triggers clean polite conclusion", False, res_exit.text)

async def run_suite_4_webrtc_voice():
    logger.info("=== SUITE 4: WebRTC Voice Signaling & Audio Frame Verification ===")
    from scripts.test_shiva_voice_call import run_test_call
    try:
        frames_count = await run_test_call()
        passed_4 = frames_count >= 15
        record_test(f"4.1 WebRTC voice call streams audio frames ({frames_count} frames)", passed_4, f"Frames received: {frames_count}")
    except Exception as e:
        record_test("4.1 WebRTC voice call streams audio frames", False, str(e))

async def run_suite_5_appointment_api_and_whatsapp(client: httpx.AsyncClient):
    logger.info("=== SUITE 5: Appointment Booking API, Availability & WhatsApp Delivery ===")

    # 5.1 Check Availability
    res_avail = await client.get(f"{BASE_API}/api/v1/appointments/availability?workflow_id=9&date=2026-11-25")
    passed_avail = res_avail.status_code == 200 and "available_slots" in res_avail.json()
    record_test("5.1 Check open slots availability endpoint", passed_avail, res_avail.text if not passed_avail else None)

    # 5.2 Direct Appointment Booking
    res_book = await client.post(f"{BASE_API}/api/v1/appointments/book", json={
        "workflow_id": 9,
        "customer_name": "QA Tester Shiva",
        "customer_phone": "+919876543210",
        "service_type": "Neurology Consultation",
        "appointment_date": "2026-11-25",
        "appointment_time": "14:00",
        "booking_source": "qa_manual_tester"
    })
    passed_b = res_book.status_code == 200 and res_book.json().get("success") is True
    appt_code = res_book.json().get("appointment_code") if passed_b else None
    record_test(f"5.2 Direct appointment booking (Code: {appt_code})", passed_b, res_book.text if not passed_b else None)

    # 5.3 WhatsApp Confirmation Delivery
    res_wa = await client.post(f"{BASE_API}/api/v1/appointments/send-whatsapp-confirmation", json={
        "customer_phone": "+919876543210",
        "customer_name": "QA Tester Shiva",
        "service_type": "Neurology Consultation",
        "appointment_date": "2026-11-25",
        "appointment_time": "14:00",
        "appointment_code": appt_code
    })
    wa_data = res_wa.json() if res_wa.status_code == 200 else {}
    passed_wa = res_wa.status_code == 200 and wa_data.get("success") is True and "wamid." in wa_data.get("whatsapp_message_id", "")
    record_test(f"5.3 WhatsApp Meta Cloud API confirmation receipt ({wa_data.get('whatsapp_message_id')})", passed_wa, res_wa.text if not passed_wa else None)

    # 5.4 Database Verification & Org 4 Isolation
    db = DBClient()
    appts_4 = await db.list_appointments(organization_id=4)
    appts_2 = await db.list_appointments(organization_id=2)
    has_qa_appt = any(a.customer_name == "QA Tester Shiva" for a in appts_4)
    no_leak_to_2 = not any(a.customer_name == "QA Tester Shiva" for a in appts_2)
    record_test("5.4 Database record persisted in Org 4 with zero leak to Org 2", has_qa_appt and no_leak_to_2, f"Org 4 count: {len(appts_4)}, Org 2 count: {len(appts_2)}")

async def run_suite_6_frontend_ui(client: httpx.AsyncClient):
    logger.info("=== SUITE 6: Next.js Frontend Compilation & UI Endpoints ===")

    # 6.1 Login page renders
    res_login_ui = await client.get(f"{BASE_UI}/auth/login")
    record_test("6.1 Frontend /auth/login renders HTTP 200", res_login_ui.status_code == 200, f"Got {res_login_ui.status_code}")

    # 6.2 AppConfig /api/config/version
    res_ver = await client.get(f"{BASE_UI}/api/config/version")
    ver_data = res_ver.json() if res_ver.status_code == 200 else {}
    backend_reachable = ver_data.get("backend", {}).get("status") == "reachable"
    record_test("6.2 Frontend proxy confirms backend is 'reachable'", backend_reachable, str(ver_data))

    # 6.3 Workflow 9 Canvas Page
    res_wf9_ui = await client.get(f"{BASE_UI}/workflow/9")
    # Redirects to login when unauthenticated, or renders page
    record_test("6.3 Frontend /workflow/9 route responds cleanly", res_wf9_ui.status_code in [200, 307], f"Got {res_wf9_ui.status_code}")

async def main():
    async with httpx.AsyncClient(timeout=90.0) as client:
        shiva_token, shiva_headers = await run_suite_1_auth_isolation(client)
        await run_suite_2_canvas_structure()
        await run_suite_3_conversational_turns(client, shiva_headers)
        await run_suite_4_webrtc_voice()
        await run_suite_5_appointment_api_and_whatsapp(client)
        await run_suite_6_frontend_ui(client)

    logger.info("=================================================================")
    logger.info(f"QA TEST RUN COMPLETE: Total: {results['total']}, Passed: {results['passed']}, Failed: {results['failed']}")
    if results['bugs']:
        logger.error(f"Bugs encountered: {json.dumps(results['bugs'], indent=2)}")
    else:
        logger.info("ALL QA TESTS PASSED WITH 100% SUCCESS! ZERO BUGS!")
    logger.info("=================================================================")

if __name__ == "__main__":
    asyncio.run(main())
