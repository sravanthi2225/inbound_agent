import asyncio
import copy
from sqlalchemy import select
from api.db.db_client import DBClient
from api.db.models import WorkflowModel, WorkflowDefinitionModel

MULTILINGUAL_DIRECTIVE = """## CRITICAL MULTILINGUAL & AUTOMATIC LANGUAGE ADAPTATION
- AUTOMATIC LANGUAGE DETECTION: You must automatically detect the language spoken by the caller from their words (e.g., Telugu, Hindi, English, Tamil, Kannada, etc.).
- NEVER ASK FOR LANGUAGE PREFERENCE: NEVER ask questions like "Which language do you prefer?", "Should I speak in Hindi?", or "Do you speak Telugu?". Do NOT ask for language confirmation or options under any circumstance.
- INSTANT SEAMLESS SWITCH: Immediately and naturally respond in the caller's detected language from your very first response to them.
- CONTINUE IN DETECTED LANGUAGE: Continue the entire conversation in that detected language for all subsequent turns, unless the caller switches to a different language (in which case, smoothly follow them into the new language).
- NATIVE SCRIPT OUTPUT: Always write your response in the native script of that language (Telugu in తెలుగు script, Hindi in देवनागरी script, Tamil in தமிழ் script, Kannada in ಕನ್ನಡ script, English in Latin script). This ensures the text-to-speech engine speaks with 100% natural native pronunciation and perfect accent.
"""

def update_node_prompts(wf_def: dict) -> dict:
    updated_def = copy.deepcopy(wf_def)
    nodes = updated_def.get("nodes", [])
    for node in nodes:
        nid = node.get("id")
        ntype = node.get("type")
        prompt = node.get("data", {}).get("prompt", "")

        # 1. Global Node
        if ntype == "globalNode" or nid == 0:
            if "CRITICAL MULTILINGUAL & AUTOMATIC LANGUAGE ADAPTATION" not in prompt:
                # Prepend or insert after # OVERALL GOAL
                if "## Response Language" in prompt:
                    # Replace Response Language section
                    import re
                    prompt = re.sub(r"## Response Language.*?(?=\n## |\Z)", MULTILINGUAL_DIRECTIVE + "\n", prompt, flags=re.DOTALL)
                else:
                    prompt = MULTILINGUAL_DIRECTIVE + "\n\n" + prompt
                node["data"]["prompt"] = prompt

        # 2. Start Call Node
        elif ntype == "startCall" or nid == 1:
            if "CRITICAL MULTILINGUAL RULE" not in prompt:
                start_note = "\n\n## CRITICAL MULTILINGUAL RULE:\n- If the caller speaks or greets first in Telugu, Hindi, Tamil, Kannada, or any other language, immediately greet and respond in that exact language without asking! Never ask which language they prefer.\n- Use native script for Telugu, Hindi, etc.\n"
                node["data"]["prompt"] = prompt + start_note

        # 3. Main Agenda Node
        elif ntype == "agentNode" or nid == 2:
            if "CRITICAL MULTILINGUAL RULE" not in prompt:
                agenda_note = "\n\n## CRITICAL MULTILINGUAL RULE:\n- Continue the entire conversation in the caller's detected language without ever asking for language preference.\n- Output all spoken responses in the native script of that language (Telugu script for Telugu, Devanagari for Hindi, etc.).\n"
                node["data"]["prompt"] = prompt + agenda_note

    return updated_def

async def main():
    db = DBClient()
    async with db.async_session() as session:
        for wf_id in [8, 9, 10]:
            wf = await session.get(WorkflowModel, wf_id)
            if not wf:
                print(f"Workflow {wf_id} not found")
                continue
            print(f"Updating Workflow {wf_id}: {wf.name} (org {wf.organization_id})")
            if wf.workflow_definition:
                wf.workflow_definition = update_node_prompts(wf.workflow_definition)

            # Also update all WorkflowDefinitionModel records
            stmt = select(WorkflowDefinitionModel).where(WorkflowDefinitionModel.workflow_id == wf_id)
            res = await session.execute(stmt)
            defs = res.scalars().all()
            for d in defs:
                if d.workflow_json:
                    d.workflow_json = update_node_prompts(d.workflow_json)
                print(f"  Updated WorkflowDefinitionModel {d.id} (version {d.version_number})")

        await session.commit()
        print("Successfully committed updated workflow definitions to database.")

if __name__ == "__main__":
    asyncio.run(main())
