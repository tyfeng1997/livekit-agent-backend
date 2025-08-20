import asyncio
import json
import logging
import os
import argparse
from livekit import api
from livekit.agents import JobContext, WorkerOptions, cli, JobProcess, RoomInputOptions
from livekit.plugins import silero, noise_cancellation

from session.factory import create_session
from agent.assistant import Assistant
from functools import partial
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")


CLIENT_CONFIG = {}

def parse_arguments():
    parser = argparse.ArgumentParser(description='LiveKit Agent with dynamic configuration')
    parser.add_argument('--client-id', required=False,default='', help='Client ID for this agent')
    parser.add_argument('--instructions', default='', help='Instructions for the assistant')
    parser.add_argument('--agent-name', default='outbound-agent', help='Agent name')
    
    return parser.parse_args()



def prewarm(proc: JobProcess, client_config: dict):
    proc.userdata["vad"] = silero.VAD.load()
    proc.userdata["client_config"] = client_config


async def entrypoint(ctx: JobContext):
    logger.info(f"[outbound] connecting to room {ctx.room.name}")
    await ctx.connect()
    
    client_config = ctx.proc.userdata.get("client_config", {})
    client_id = client_config.get("client_id", "unknown")
    instructions = client_config.get("instructions", "")
    logger.info(f"{client_id} [outbound] instructions: {instructions}")

    
    dial_info = json.loads(ctx.job.metadata)
    participant_identity = phone_number = dial_info["phone_number"]
    transfer_to = dial_info["transfer_to"]
    logger.info(f"{client_id} [outbound] dialing out to {phone_number}, transfer_to: {transfer_to}")
    agent = Assistant(
        instructions=instructions,
        transfer_to=transfer_to,
    )

    
    session = create_session(vad=ctx.proc.userdata["vad"])

    session_started = asyncio.create_task(
        session.start(
            agent=agent,
            room=ctx.room,
            room_input_options=RoomInputOptions(
                noise_cancellation=noise_cancellation.BVCTelephony(),
            ),
        )
    )

    try:
        
        await ctx.api.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                room_name=ctx.room.name,
                sip_trunk_id=outbound_trunk_id,
                sip_call_to=phone_number,
                participant_identity=participant_identity,
                wait_until_answered=True, 
            )
        )

        await session_started
        participant = await ctx.wait_for_participant(identity=participant_identity)
        logger.info(f"{client_id} [outbound] participant joined: {participant.identity}")

        agent.set_participant(participant)

    except api.TwirpError as e:
        logger.error(
            f"{client_id} [outbound] error creating SIP participant: {e.message}, "
            f"SIP status: {e.metadata.get('sip_status_code')} {e.metadata.get('sip_status')}"
        )
        ctx.shutdown()


def main():
    
    # args = parse_arguments()
    instructions=f"""
            You are a voice assistant developed by Feng. Your primary responsibilities are:

            1. Scheduling conversations and appointments.
            2. Searching and providing relevant information from the developer documentation.

            Your interface with the user is voice-based. Always be polite, professional, and concise. If the user requests to speak with a human, confirm their intent before transferring. Provide helpful responses while keeping interactions natural and engaging. Only use your tools (like appointment scheduling or documentation search) when appropriate, based on the user's request.
            """
    args = {
        "client_id": "test_client",
        "instructions": instructions,
        "agent_name": "outbound-agent",
    }
    
    global CLIENT_CONFIG
    CLIENT_CONFIG = {
        "client_id": args["client_id"],
        "instructions": args["instructions"],
        "agent_name": args["agent_name"],
    }
    logging.basicConfig(
        level=logging.INFO,
        format=f'%(asctime)s - [{CLIENT_CONFIG["client_id"]}] - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info(f"Starting agent for client: {CLIENT_CONFIG['client_id']}")
    logger.info(f"Configuration: {CLIENT_CONFIG}")
    
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=partial(prewarm, client_config=CLIENT_CONFIG),
            agent_name=args["agent_name"],
        )
    )
if __name__ == "__main__":
    main()