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

logger = logging.getLogger("agent")

load_dotenv(".env.local")


logger = logging.getLogger(__name__)

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
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
            name="Joy",
            appointment_time="next day",
            dial_info={
                "phone_number": "+1234567890",
                "transfer_to": "+1234567890",
            },
            ),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm
        )
    )
