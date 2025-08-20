import logging
from livekit.agents import JobContext, WorkerOptions, cli, JobProcess, RoomInputOptions
from session.factory import create_session
from agent.assistant import Assistant
from livekit.plugins import silero, noise_cancellation

import logging

from dotenv import load_dotenv
from livekit.agents import (
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    metrics
)
from livekit.plugins import  noise_cancellation, silero
from livekit.agents import UserStateChangedEvent, AgentStateChangedEvent
from livekit.plugins import silero
import argparse
from functools import partial
load_dotenv(".env.local")


logger = logging.getLogger(__name__)


CLIENT_CONFIG = {}

def parse_arguments():
    parser = argparse.ArgumentParser(description='LiveKit Agent with dynamic configuration')
    parser.add_argument('--client-id', required=False,default='', help='Client ID for this agent')
    parser.add_argument('--instructions', default='', help='Instructions for the assistant')
    parser.add_argument('--transfer-to', default='', help='Transfer to number/destination')
    parser.add_argument('--agent-name', default='inbound-agent', help='Agent name')
    
    return parser.parse_args()


def prewarm(proc: JobProcess, client_config: dict):
    proc.userdata["vad"] = silero.VAD.load()
    proc.userdata["client_config"] = client_config


async def entrypoint(ctx: JobContext):

    client_config = ctx.proc.userdata.get("client_config", {})
    client_id = client_config.get("client_id", "unknown")
    instructions = client_config.get("instructions", "")
    transfer_to = client_config.get("transfer_to", "")
    logger.debug(f"{client_id} [inbound] instructions: {instructions}")
    logger.debug(f"{client_id} [inbound] transfer_to: {transfer_to}")
    ctx.log_context_fields = {
        "room": ctx.room.name,
        "client_id": client_id,

    }
    session = create_session(vad=ctx.proc.userdata["vad"])
    
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    
    @session.on("user_state_changed")
    def on_user_state_changed(ev: UserStateChangedEvent):
        if ev.new_state == "speaking":
            print("User started speaking")
        elif ev.new_state == "listening":
            print("User stopped speaking")
        elif ev.new_state == "away":
            print("User is not present (e.g. disconnected)")



    @session.on("agent_state_changed")
    def on_agent_state_changed(ev: AgentStateChangedEvent):
        if ev.new_state == "initializing":
            print("Agent is starting up")
        elif ev.new_state == "idle":
            print("Agent is ready but not processing")
        elif ev.new_state == "listening":
            print("Agent is listening for user input")
        elif ev.new_state == "thinking":
            print("Agent is processing user input and generating a response")
        elif ev.new_state == "speaking":
            print("Agent started speaking")
    
    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    
    await session.start(
        agent=Assistant(
           instructions=instructions,
            transfer_to=transfer_to,
        ),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    await ctx.connect()

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
        "transfer_to": "+1xxxxxxx",
        "agent_name": "inbound-agent",
    }
    
    global CLIENT_CONFIG
    CLIENT_CONFIG = {
        "client_id": args["client_id"],
        "instructions": args["instructions"],
        "transfer_to": args["transfer_to"],
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