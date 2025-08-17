from livekit.agents import AgentSession
from livekit.plugins import assemblyai, elevenlabs, anthropic

def create_session(vad) -> AgentSession:
    return AgentSession(
        llm=anthropic.LLM(model="claude-sonnet-4-20250514"),
        stt=assemblyai.STT(
            end_of_turn_confidence_threshold=0.7,
            min_end_of_turn_silence_when_confident=160,
            max_turn_silence=2400,
        ),
        tts=elevenlabs.TTS(
            voice_id="ODq5zmih8GrVes37Dizd",
            model="eleven_multilingual_v2"
        ),
        vad=vad,
        turn_detection="stt",
        preemptive_generation=True,
    )
