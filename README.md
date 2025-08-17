# LiveKit Agent Backend Project

This project is a backend for a voice AI agent based on [LiveKit Agents](https://docs.livekit.io/agents/). It can be used as a reference for building your own LiveKit Agent or Twilio Agent voice service. The codebase includes workers for web frontend, trunk inbound, and outbound scenarios.

## Project Structure

- `src/agent/assistant.py`: Core logic for the voice assistant, including appointment confirmation, transfer to human, hangup, etc.
- `src/session/factory.py`: Encapsulates AgentSession creation, integrating LLM, STT, TTS, VAD, etc.
- `src/workers/web_worker.py`: Worker for web frontend voice interaction.
- `src/workers/inbound_worker.py`: Worker for trunk inbound call scenarios.
- `src/workers/outbound_worker.py`: Worker for outbound call scenarios.

## LiveKit Agent Logic

LiveKit Agents use a worker registration and automatic dispatch mechanism:

- **Worker Registration**: Each worker registers with LiveKit Cloud via `cli.run_app`, making it available for scheduling.
- **Automatic Dispatch**: LiveKit Cloud automatically assigns call tasks to the appropriate worker based on Dispatch Rules and Inbound Rules. For example, you can route calls to different agents depending on the incoming phone number.
- **Custom Rules**: You can configure Dispatch Rules and Inbound Rules in the LiveKit Cloud console for flexible routing and distribution.

## Important Notice

This project is **not plug-and-play**. To run a complete voice agent service, you need to:

- Purchase Twilio phone numbers
- Configure Twilio SIP Trunk
- Set up SIP Server in LiveKit Cloud
- Configure Dispatch Rules and Inbound Rules

These steps require third-party services and configuration. If you need help, I can write a detailed article or make a YouTube video explaining the process.

## About the Solution

I am building a low-cost, cost-controllable voice customer service and outbound solution based on Twilio + LiveKit Agent, aimed at small and medium businesses with sales, booking, and customer service needs. The project is currently in MVP development.

The full version will include:

- RAG (Retrieval-Augmented Generation) system and dashboard
- Ability to add your private data for the agent, so it can use this knowledge to serve customers during inbound and outbound calls
- Automatic transcription of agent-customer conversations and saving to CRM
- Ability for the agent to transfer to a human customer service representative

Stay tuned for updates and more features!
