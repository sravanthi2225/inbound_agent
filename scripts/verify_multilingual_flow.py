import asyncio
import os
from api.db.db_client import DBClient
from api.db.models import WorkflowModel
from api.services.workflow.dto import ReactFlowDTO
from api.services.workflow.pipecat_engine_context_composer import compose_system_prompt_for_node
from api.services.workflow.workflow_graph import WorkflowGraph
from pipecat.services.sarvam.tts import detect_script_language

# Check test cases
test_inputs = [
    ("Telugu", "నమస్కారం, నాకు కార్డియాలజీ డిపార్ట్‌మెంట్‌లో డాక్టర్ శర్మతో అపాయింట్‌మెంట్ కావాలి."),
    ("Hindi", "नमस्ते, मुझे ऑर्थोपेडिक डिपार्टमेंट में अपॉइंटमेंट बुक करना है।"),
    ("English", "Hi, I need an appointment with Dr. Rao tomorrow morning."),
]

async def test_workflow(wf_id: int):
    db = DBClient()
    async with db.async_session() as session:
        wf = await session.get(WorkflowModel, wf_id)
        if not wf:
            print(f"Workflow {wf_id} not found")
            return
        
        dto = ReactFlowDTO.model_validate(wf.workflow_definition)
        graph = WorkflowGraph(dto)
        start_node = graph.nodes.get("1") or graph.nodes.get(1) or list(graph.nodes.values())[0]
        
        composed = compose_system_prompt_for_node(node=start_node, workflow=graph, format_prompt=lambda p: p, has_recordings=False)
        system_prompt = composed.text
        print(f"=== Testing Workflow {wf_id} System Prompt Multilingual Directives ===")
        assert "CRITICAL MULTILINGUAL & AUTOMATIC LANGUAGE ADAPTATION" in system_prompt
        print("✓ Verified Multilingual Directive present in system prompt")

        # Test script detection on user inputs and simulated bot responses
        for lang_name, user_input in test_inputs:
            detected_input_lang = detect_script_language(user_input)
            print(f"  User input ({lang_name}): {user_input[:40]}... -> Detected: {detected_input_lang}")
            
        print(f"Workflow {wf_id} prompt verification PASSED!\n")

async def main():
    for wf_id in [8, 9, 10]:
        await test_workflow(wf_id)

if __name__ == "__main__":
    asyncio.run(main())
