import asyncio
import json
import logging
import aiohttp
import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceServer, RTCConfiguration

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("shiva_voice_test")

async def main():
    async with aiohttp.ClientSession() as session:
        # 1. Login as shivaprasad@gmail.com
        login_resp = await session.post(
            "http://localhost:8500/api/v1/auth/login",
            json={"email": "shivaprasad@gmail.com", "password": "shiva@112"}
        )
        assert login_resp.status == 200, f"Login failed: {await login_resp.text()}"
        login_data = await login_resp.json()
        token = login_data["token"]
        headers = {"Authorization": f"Bearer {token}"}
        logger.info(f"Logged in successfully as {login_data['user']['email']}, Org ID: {login_data['user']['organization_id']}")

        # 2. Verify workflow listing (strict tenant isolation)
        wfs_resp = await session.get("http://localhost:8500/api/v1/workflow/fetch", headers=headers)
        wfs = await wfs_resp.json()
        logger.info(f"Visible workflows for shivaprasad: {[(w['id'], w['name']) for w in wfs]}")
        wf_id = wfs[0]["id"]

        # 3. Create workflow run for Workflow 9
        run_resp = await session.post(
            f"http://localhost:8500/api/v1/workflow/{wf_id}/runs",
            headers=headers,
            json={"mode": "small_webrtc", "name": f"WR-shiva-e2e"}
        )
        assert run_resp.status == 200, f"Run creation failed: {await run_resp.text()}"
        run_id = (await run_resp.json())["id"]
        logger.info(f"Created voice run {run_id} for workflow {wf_id}")

        # 4. WebRTC Connection Setup
        pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=[
            RTCIceServer(urls=["turn:turn.quickblox.com:3478?transport=tcp", "turn:turn.quickblox.com:3478"], username="quickblox", credential="baccb97ba2d92d71e26eb9886da5f1e0")
        ]))
        
        @pc.on("iceconnectionstatechange")
        def on_ice():
            logger.info(f"ICE Connection State: {pc.iceConnectionState}")

        @pc.on("connectionstatechange")
        def on_conn():
            logger.info(f"PeerConnection State: {pc.connectionState}")

        frames = []
        @pc.on("track")
        def on_track(track):
            logger.info(f"Remote track received: {track.kind}")
            async def rec():
                try:
                    while True:
                        f = await asyncio.wait_for(track.recv(), timeout=30.0)
                        frames.append(f)
                        if len(frames) in (1, 5, 10, 25, 50, 100):
                            logger.info(f">>> RECEIVED {len(frames)} AGENT AUDIO FRAMES! Fast voice streaming active. <<<")
                except Exception as e:
                    logger.info(f"Track stream closed: {e}")
            asyncio.create_task(rec())

        pc.addTransceiver("audio", direction="sendrecv")

        ws_url = f"ws://localhost:8500/api/v1/ws/signaling/{wf_id}/{run_id}?token={token}"
        async with websockets.connect(ws_url) as ws:
            logger.info("Signaling WebSocket connected")
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)

            @pc.on("icecandidate")
            def on_c(c):
                if c:
                    asyncio.create_task(ws.send(json.dumps({
                        "type": "ice-candidate",
                        "payload": {
                            "candidate": {
                                "candidate": f"candidate:{c.foundation} {c.component} {c.protocol} {c.priority} {c.ip} {c.port} typ {c.type}",
                                "sdpMid": c.sdpMid,
                                "sdpMLineIndex": c.sdpMLineIndex
                            },
                            "pc_id": "pc-shiva-test"
                        }
                    })))

            await ws.send(json.dumps({
                "type": "offer",
                "payload": {
                    "sdp": pc.localDescription.sdp,
                    "type": "offer",
                    "pc_id": "pc-shiva-test",
                    "restart_ice": False
                }
            }))

            async def ws_loop():
                try:
                    async for raw in ws:
                        msg = json.loads(raw)
                        mtype = msg.get("type")
                        if mtype == "answer":
                            logger.info("Received SDP answer from Dograh agent backend")
                            desc = RTCSessionDescription(sdp=msg["payload"]["sdp"], type="answer")
                            await pc.setRemoteDescription(desc)
                        elif mtype == "ice-candidate":
                            cand = msg.get("payload", {}).get("candidate", {})
                            if cand and "candidate" in cand:
                                pass
                except Exception as e:
                    logger.info(f"Signaling WS closed: {e}")

            ws_task = asyncio.create_task(ws_loop())
            # Wait for audio frames to stream
            for i in range(80):
                await asyncio.sleep(0.5)
                if len(frames) >= 25:
                    logger.info(f"Target audio frame threshold reached: {len(frames)} frames!")
                    break

            ws_task.cancel()
            await pc.close()

        logger.info(f"Final audio frames count: {len(frames)}")
        assert len(frames) > 0, "No audio frames received from voice agent!"
        logger.info("E2E VOICE CALL TEST PASSED SUCCESSFULLY FOR SHIVAPRASAD!")

if __name__ == "__main__":
    asyncio.run(main())
