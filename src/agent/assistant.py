from __future__ import annotations

import asyncio
import logging
from dotenv import load_dotenv
from typing import Any
import aiohttp

from livekit import rtc, api
from livekit.agents import (
    Agent,
    function_tool,
    RunContext,
    get_job_context,
    JobProcess
)
from livekit.plugins import silero
from utils.webhook import push_webhook 
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


# load environment variables, this is optional, only used for local development
load_dotenv(dotenv_path=".env.local")
logger = logging.getLogger("outbound-caller")
logger.setLevel(logging.INFO)



class Assistant(Agent):
    def __init__(
        self,
        *,
        name: str,
        appointment_time: str,
        dial_info: dict[str, Any],
    ):
        super().__init__(
            instructions=f"""
            You are a voice assistant developed by Feng. Your primary responsibilities are:

            1. Scheduling conversations and appointments.
            2. Searching and providing relevant information from the developer documentation.

            Your interface with the user is voice-based. Always be polite, professional, and concise. If the user requests to speak with a human, confirm their intent before transferring. Provide helpful responses while keeping interactions natural and engaging. Only use your tools (like appointment scheduling or documentation search) when appropriate, based on the user's request.
            """
        )
        # keep reference to the participant for transfers
        self.participant: rtc.RemoteParticipant | None = None

        self.dial_info = dial_info

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions="Greet the user with a warm welcome"
        )
    async def on_exit(self):
        await self.session.generate_reply(
            instructions="Tell the user a friendly goodbye before you exit.",
        )
        
    def set_participant(self, participant: rtc.RemoteParticipant):
        self.participant = participant

    async def hangup(self):
        """Helper function to hang up the call by deleting the room"""

        job_ctx = get_job_context()
        await job_ctx.api.room.delete_room(
            api.DeleteRoomRequest(
                room=job_ctx.room.name,
            )
        )
        

    @function_tool()
    async def search_knowledge_base(
        self,
        context: RunContext,
        query: str,
    ) -> str:
        # Send a verbal status update to the user after a short delay
        async def _speak_status_update(delay: float = 0.5):
            await asyncio.sleep(delay)
            await context.session.generate_reply(instructions=f"""
                You are searching the knowledge base for \"{query}\" but it is taking a little while.
                Update the user on your progress, but be very brief.
            """)
        
        status_update_task = asyncio.create_task(_speak_status_update(0.9))

        # Perform search (function definition omitted for brevity)
        async def _perform_search(query:str)-> str:
            payload = {
                "text": query,
                "use_reranking": True
            }
            RAG_ENDPOINT = "http://127.0.0.1:8000/query"

            async with aiohttp.ClientSession() as session:
                async with session.post(RAG_ENDPOINT, json=payload) as resp:
                    if resp.status != 200:
                        logger.error(f"RAG query failed: {await resp.text()}")
                        return f"Error querying knowledge base: {resp.status}"
                    
                    data = await resp.json()
                    # Assuming the endpoint returns something like {"results": [...]} 
                    logger.info(f"RAG query returned {data} ")
            return data


        result = await _perform_search(query)
        
        # Cancel status update if search completed before timeout
        status_update_task.cancel()
        
        return result

    @function_tool()
    async def transfer_call(self, ctx: RunContext):
        """Transfer the call to a human agent, called after confirming with the user"""

        transfer_to = self.dial_info["transfer_to"]
        if not transfer_to:
            return "cannot transfer call"

        logger.info(f"transferring call to {transfer_to}")

        # let the message play fully before transferring
        await ctx.session.generate_reply(
            instructions="let the user know you'll be transferring them"
        )

        job_ctx = get_job_context()
        try:
            await job_ctx.api.sip.transfer_sip_participant(
                api.TransferSIPParticipantRequest(
                    room_name=job_ctx.room.name,
                    participant_identity=self.participant.identity,
                    transfer_to=f"tel:{transfer_to}",
                )
            )

            logger.info(f"transferred call to {transfer_to}")
        except Exception as e:
            logger.error(f"error transferring call: {e}")
            await ctx.session.generate_reply(
                instructions="there was an error transferring the call."
            )
            await self.hangup()

    @function_tool()
    async def end_call(self, ctx: RunContext):
        """Called when the user wants to end the call"""
        logger.info(f"ending the call for {self.participant.identity}")

        # let the agent finish speaking
        current_speech = ctx.session.current_speech
        if current_speech:
            await current_speech.wait_for_playout()

        await self.hangup()

    @function_tool()
    async def detected_answering_machine(self, ctx: RunContext):
        """Called when the call reaches voicemail. Use this tool AFTER you hear the voicemail greeting"""
        logger.info(f"detected answering machine for {self.participant.identity}")
        await self.hangup()
    
    @function_tool()
    async def book_appointment(
        self,
        ctx: RunContext,
        customer_name: str,
        time_slot: str,
        event_summary: str,
    ):
        """
        Booking tool: sends appointment info to a webhook
        Args:
            customer_name: Name of the customer
            time_slot: Time slot for the appointment
            event_summary: Short summary of the event
        """
        payload = {
            "customer_name": customer_name,
            "time_slot": time_slot,
            "event_summary": event_summary,
        }
        logger.info(f"Pushing appointment to webhook: {payload}")
        await push_webhook(payload)

        # Provide voice feedback to the user
        await ctx.session.generate_reply(
            instructions=f"Appointment information sent: {customer_name}, Time: {time_slot}, Summary: {event_summary}"
        )
        return "appointment pushed to webhook"
