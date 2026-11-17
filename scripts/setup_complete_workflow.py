import asyncio
import json
import uuid
from datetime import datetime, UTC
from copy import deepcopy

from api.db.db_client import DBClient
from api.enums import ToolCategory, ToolStatus

async def setup_tools_for_org(db: DBClient, org_id: int, user_id: int):
    # Check existing tools
    existing_tools = await db.get_tools_for_organization(org_id)
    tool_map = {t.name: t for t in existing_tools}

    # 1. Book Hospital Appointment
    if "Book Hospital Appointment" not in tool_map:
        book_tool_def = {
            "schema_version": 1,
            "messages": [],
            "type": "http_api",
            "config": {
                "method": "POST",
                "url": "/api/v1/appointments/book",
                "headers": None,
                "credential_uuid": None,
                "parameters": [
                    {
                        "name": "customer_name",
                        "type": "string",
                        "description": "Full name of the patient.",
                        "required": True,
                    },
                    {
                        "name": "customer_phone",
                        "type": "string",
                        "description": "Mobile contact phone number of the patient.",
                        "required": True,
                    },
                    {
                        "name": "service_type",
                        "type": "string",
                        "description": "Doctor name or medical department (e.g. Cardiology, Orthopedics, General Medicine).",
                        "required": False,
                    },
                    {
                        "name": "appointment_date",
                        "type": "string",
                        "description": "Desired appointment date in YYYY-MM-DD format.",
                        "required": True,
                    },
                    {
                        "name": "appointment_time",
                        "type": "string",
                        "description": "Preferred slot time (e.g. 10:30 AM).",
                        "required": True,
                    },
                ],
                "preset_parameters": None,
                "timeout_ms": 6000,
                "body_template": {
                    "workflow_id": 1,
                    "customer_name": "{{customer_name}}",
                    "customer_phone": "{{customer_phone}}",
                    "service_type": "{{service_type}}",
                    "appointment_date": "{{appointment_date}}",
                    "appointment_time": "{{appointment_time}}",
                    "booking_source": "voice_call",
                },
                "body_format": "json",
            },
        }
        t1 = await db.create_tool(
            organization_id=org_id,
            user_id=user_id,
            name="Book Hospital Appointment",
            definition=book_tool_def,
            category=ToolCategory.HTTP_API.value,
            description="Book an appointment for a patient in the hospital appointment system.",
        )
        tool_map["Book Hospital Appointment"] = t1
        print(f"Created Book Hospital Appointment tool: {t1.tool_uuid} for org {org_id}")

    # 2. Send WhatsApp Confirmation
    if "Send WhatsApp Confirmation" not in tool_map:
        wa_tool_def = {
            "schema_version": 1,
            "messages": [],
            "type": "http_api",
            "config": {
                "method": "POST",
                "url": "/api/v1/appointments/send-whatsapp-confirmation",
                "headers": None,
                "credential_uuid": None,
                "parameters": [
                    {
                        "name": "customer_name",
                        "type": "string",
                        "description": "Full name of the patient.",
                        "required": True,
                    },
                    {
                        "name": "customer_phone",
                        "type": "string",
                        "description": "Recipient phone number for WhatsApp confirmation (with country code).",
                        "required": True,
                    },
                    {
                        "name": "service_type",
                        "type": "string",
                        "description": "Doctor name or department (e.g. Cardiology, Dr. Sharma).",
                        "required": False,
                    },
                    {
                        "name": "appointment_date",
                        "type": "string",
                        "description": "Confirmed appointment date (e.g. 2026-11-18).",
                        "required": True,
                    },
                    {
                        "name": "appointment_time",
                        "type": "string",
                        "description": "Confirmed appointment time slot (e.g. 10:30 AM).",
                        "required": True,
                    },
                    {
                        "name": "appointment_code",
                        "type": "string",
                        "description": "Booking reference code returned by booking tool (e.g. APT-12345).",
                        "required": False,
                    },
                ],
                "preset_parameters": None,
                "timeout_ms": 6000,
                "body_template": {
                    "customer_name": "{{customer_name}}",
                    "customer_phone": "{{customer_phone}}",
                    "service_type": "{{service_type}}",
                    "appointment_date": "{{appointment_date}}",
                    "appointment_time": "{{appointment_time}}",
                    "appointment_code": "{{appointment_code}}",
                },
                "body_format": "json",
            },
        }
        t2 = await db.create_tool(
            organization_id=org_id,
            user_id=user_id,
            name="Send WhatsApp Confirmation",
            definition=wa_tool_def,
            category=ToolCategory.HTTP_API.value,
            description="Trigger Meta WhatsApp CRM confirmation message for booked appointment.",
        )
        tool_map["Send WhatsApp Confirmation"] = t2
        print(f"Created Send WhatsApp Confirmation tool: {t2.tool_uuid} for org {org_id}")

    # 3. Check Doctor & Slot Availability
    if "Check Doctor & Slot Availability" not in tool_map:
        avail_def = {
            "schema_version": 1,
            "messages": [],
            "type": "http_api",
            "config": {
                "method": "GET",
                "url": "/api/v1/appointments/availability",
                "headers": None,
                "credential_uuid": None,
                "parameters": [
                    {
                        "name": "date",
                        "type": "string",
                        "description": "Date to check availability for in YYYY-MM-DD format.",
                        "required": False,
                    },
                    {
                        "name": "workflow_id",
                        "type": "number",
                        "description": "Workflow ID.",
                        "required": False,
                    },
                ],
                "preset_parameters": None,
                "timeout_ms": 5000,
                "body_template": None,
                "body_format": "json",
            },
        }
        t3 = await db.create_tool(
            organization_id=org_id,
            user_id=user_id,
            name="Check Doctor & Slot Availability",
            definition=avail_def,
            category=ToolCategory.HTTP_API.value,
            description="Check available doctor appointment slots.",
        )
        tool_map["Check Doctor & Slot Availability"] = t3
        print(f"Created Check Doctor & Slot Availability tool: {t3.tool_uuid} for org {org_id}")

    return tool_map

async def main():
    db = DBClient()

    # Provision tools for Org 4 (Shiva)
    shiva_tools = await setup_tools_for_org(db, org_id=4, user_id=4)
    # Also provision tools for Org 2 (Bcon) so WhatsApp CRM tool is available there too
    bcon_tools = await setup_tools_for_org(db, org_id=2, user_id=2)

    shiva_tool_uuids = [
        shiva_tools["Book Hospital Appointment"].tool_uuid,
        shiva_tools["Send WhatsApp Confirmation"].tool_uuid,
        shiva_tools["Check Doctor & Slot Availability"].tool_uuid,
    ]

    # Global Prompt
    global_prompt = """# OVERALL GOAL

You are Sam, the AI voice coordinator for **City Hospital Appointment Booking Desk**.
Your goal is to warmly assist callers in booking new doctor consultations, rescheduling existing appointments, and providing department information.
Keep all spoken replies short, natural, and conversational (1 to 2 sentences, 10 to 25 words).
Never use robotic phrasing or output special symbols.
Speak with polite warmth and listen carefully.

## HANDLING CALLERS
- If the user asks to book an appointment, immediately help them book it.
- Ask questions one at a time: patient name, department/doctor, preferred date and time, and mobile number.
- When all details are gathered, use the booking tool to book the appointment.
- Immediately after booking, use the Send WhatsApp Confirmation tool so the patient receives instant confirmation on their phone.
- If there is background noise, clarify politely without repeating phrases.
- Keep the conversation moving smoothly to completion.
"""

    # Start Call Node Prompt
    start_prompt = """# MAIN ACTION POINT AT THIS STAGE

You have received an inbound call from a patient or caller.
Greet them warmly and clearly:
"Hi, I am Sam from City Hospital. How can I help you with your appointment today?"

## FLOW OF CALL
- If the caller says they want to book an appointment, see a doctor, or schedule a visit:
  Immediately transition to Main Agenda to collect their details. Do NOT stall or delay.
- If the caller gives their name right away, acknowledge it politely and transition to Main Agenda.
- If it is a wrong number, spam, or caller wishes to hang up, transition to End Call.
"""

    # Main Agenda Node Prompt
    agenda_prompt = """# MAIN ACTION POINT AT THIS STAGE: APPOINTMENT BOOKING & WHATSAPP CONFIRMATION

Collect the following details one by one in a friendly manner:
1. Patient's full name: "May I have the patient's full name, please?"
2. Department or doctor: "Which department or doctor would you like to consult? We have Cardiology, Orthopedics, Pediatrics, and General Medicine."
3. Preferred Date & Time: "What date and time slot would work best for you?"
4. WhatsApp Contact Number: "And what is the best mobile number to send your WhatsApp confirmation to?"

## BOOKING EXECUTION
- Once you have the patient's name, doctor/department, date, time, and phone number:
  1. Call `Book Hospital Appointment` to reserve the slot.
  2. Call `Send WhatsApp Confirmation` to dispatch the Meta WhatsApp confirmation message.
  3. Inform the caller: "Your appointment is confirmed! I have sent the details directly to your WhatsApp. Is there anything else I can assist you with today?"

If the caller has no further requests, transition to End Call.
"""

    # End Call Node Prompt
    end_prompt = """# MAIN ACTION POINT AT THIS STAGE: CALL CONCLUSION

The appointment has been confirmed and the caller's request is handled.
End the call politely in 1 short sentence:
"Thank you for choosing City Hospital. We look forward to seeing you, and have a wonderful day!"

The call is now complete.
"""

    workflow_json = {
        "nodes": [
            {
                "id": "0",
                "type": "globalNode",
                "position": {"x": 100, "y": 250},
                "data": {
                    "name": "Global Node",
                    "label": "Global Node",
                    "prompt": global_prompt,
                    "tools": shiva_tool_uuids,
                },
            },
            {
                "id": "1",
                "type": "startCall",
                "position": {"x": 450, "y": 50},
                "data": {
                    "name": "start call",
                    "label": "Start Call",
                    "is_start": True,
                    "prompt": start_prompt,
                    "tools": shiva_tool_uuids,
                },
            },
            {
                "id": "2",
                "type": "agentNode",
                "position": {"x": 650, "y": 250},
                "data": {
                    "name": "Main Agenda and Questions",
                    "label": "Main Agenda & Booking",
                    "prompt": agenda_prompt,
                    "tools": shiva_tool_uuids,
                },
            },
            {
                "id": "4",
                "type": "endCall",
                "position": {"x": 450, "y": 450},
                "data": {
                    "name": "End Call",
                    "label": "End Call",
                    "is_end": True,
                    "prompt": end_prompt,
                    "tools": shiva_tool_uuids,
                },
            },
        ],
        "edges": [
            {
                "id": "1-2",
                "source": "1",
                "target": "2",
                "sourceHandle": "bottom",
                "targetHandle": "top",
                "animated": True,
                "type": "default",
                "data": {
                    "label": "Move to Main Agenda",
                    "condition": "Choose this pathway when the caller wants to book, reschedule, or inquire about an appointment or doctor consultation.",
                },
            },
            {
                "id": "1-4",
                "source": "1",
                "target": "4",
                "sourceHandle": "bottom",
                "targetHandle": "top",
                "animated": True,
                "type": "default",
                "data": {
                    "label": "End call",
                    "condition": "Choose this pathway if the caller dialed a wrong number, is spam, or asks to end the call immediately.",
                },
            },
            {
                "id": "2-4",
                "source": "2",
                "target": "4",
                "sourceHandle": "bottom",
                "targetHandle": "top",
                "animated": True,
                "type": "default",
                "data": {
                    "label": "End call",
                    "condition": "Choose this pathway once the appointment has been confirmed, WhatsApp notification sent, and the caller is done.",
                },
            },
        ],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }

    # Validate against ReactFlowDTO
    from api.services.workflow.dto import ReactFlowDTO
    dto = ReactFlowDTO(**workflow_json)
    print("ReactFlowDTO validation succeeded!")

    # Workflow configurations for Org 4 (Shiva)
    # Using Sarvam-105b-conversations (150ms TTFT) and connection 4c77f3a3-8ea8-4313-b320-8991f7b91a41
    workflow_configs = {
        "model_configuration_override": {
            "mode": "pipeline",
            "llm": {
                "settings": {
                    "model": "sarvam-105b-conversations",
                    "temperature": 0.5,
                },
                "provider_connection_uuid": "4c77f3a3-8ea8-4313-b320-8991f7b91a41",
            },
            "llm_fallback": {"rules": []},
            "stt": {
                "settings": {
                    "model": "saaras:v4",
                    "language": "unknown",
                },
                "provider_connection_uuid": "4c77f3a3-8ea8-4313-b320-8991f7b91a41",
            },
            "tts": {
                "settings": {
                    "model": "bulbul:v3",
                    "voice": "shubh",
                    "language": "te-IN",
                    "speed": 1.0,
                },
                "provider_connection_uuid": "4c77f3a3-8ea8-4313-b320-8991f7b91a41",
            },
            "embeddings": None,
        },
        "ambient_noise_configuration": {"enabled": False, "volume": 0.3},
        "max_call_duration": 300,
        "max_user_idle_timeout": 35.0,
        "smart_turn_stop_secs": 0.8,
        "turn_start_strategy": "min_words",
        "turn_start_min_words": 1,
        "turn_stop_strategy": "transcription",
        "dictionary": "",
        "context_compaction_enabled": False,
        "tts_cache_enabled": False,
        "call_dispositions": [],
        "text_chat_inactivity_timeout_seconds": 1800,
        "external_pbx_field_mappings": [],
        "external_pbx_lead_headers": [],
        "transcript_configuration": {"include_end_timestamps": False},
    }

    # Check if Shiva already has a workflow
    shiva_wfs = await db.get_all_workflows_for_listing(4, status=None)
    if not shiva_wfs:
        wf = await db.create_workflow(
            name="Hospital Appointment Booking & WhatsApp CRM",
            workflow_definition=workflow_json,
            user_id=4,
            organization_id=4,
        )
        print(f"Created Workflow {wf.id} for Shiva (Org 4)")
        # Save draft with custom configurations & tools
        draft = await db.save_workflow_draft(
            workflow_id=wf.id,
            workflow_definition=workflow_json,
            workflow_configurations=workflow_configs,
        )
        print(f"Saved Draft V{draft.version_number} for Workflow {wf.id}")
        await db.publish_workflow_draft(wf.id)
        print(f"Published Workflow {wf.id} successfully!")
        # Create draft V2 so editor has editable draft ready
        await db.save_workflow_draft(
            workflow_id=wf.id,
            workflow_definition=workflow_json,
            workflow_configurations=workflow_configs,
        )
        print(f"Initialized Draft V2 for Workflow {wf.id}")
    else:
        wf_id = shiva_wfs[0].id
        await db.save_workflow_draft(
            workflow_id=wf_id,
            workflow_definition=workflow_json,
            workflow_configurations=workflow_configs,
        )
        print(f"Updated Draft for Workflow {wf_id} (Org 4)")

    # 4. ALSO update Workflow 8 in Org 2 (Bcon) to fix the transition flaw!
    wf8_draft = await db.get_draft_version(8)
    if wf8_draft:
        wf8_json = deepcopy(wf8_draft.workflow_json)
        # Update Node 1 prompt
        for n in wf8_json.get("nodes", []):
            if n.get("id") == "1":
                n["data"]["prompt"] = start_prompt
                # Add WhatsApp tool if not present
                wa_uuid = bcon_tools["Send WhatsApp Confirmation"].tool_uuid
                if wa_uuid not in n["data"].get("tools", []):
                    n["data"]["tools"].append(wa_uuid)
            elif n.get("id") == "2":
                wa_uuid = bcon_tools["Send WhatsApp Confirmation"].tool_uuid
                if wa_uuid not in n["data"].get("tools", []):
                    n["data"]["tools"].append(wa_uuid)
                n["data"]["prompt"] = agenda_prompt
            elif n.get("id") == "0":
                wa_uuid = bcon_tools["Send WhatsApp Confirmation"].tool_uuid
                if wa_uuid not in n["data"].get("tools", []):
                    n["data"]["tools"].append(wa_uuid)
        # Update Edge 1 -> 2 condition
        for e in wf8_json.get("edges", []):
            if e.get("source") == "1" and e.get("target") == "2":
                e["data"]["condition"] = "Choose this pathway when the caller wants to book, reschedule, or inquire about an appointment or doctor consultation."
        
        # Update configs to 35s idle timeout
        wf8_configs = deepcopy(wf8_draft.workflow_configurations or {})
        wf8_configs["max_user_idle_timeout"] = 35.0
        wf8_configs["turn_start_min_words"] = 1
        wf8_configs["smart_turn_stop_secs"] = 0.8
        
        await db.save_workflow_draft(
            workflow_id=8,
            workflow_definition=wf8_json,
            workflow_configurations=wf8_configs,
        )
        print("Successfully updated Workflow 8 in Org 2 with transition fix and WhatsApp tool!")

if __name__ == "__main__":
    asyncio.run(main())
