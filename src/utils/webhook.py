import aiohttp
import logging
logger = logging.getLogger("outbound-caller")
logger.setLevel(logging.INFO)

WEBHOOK_URL = "https://hooks.zapier.com/hooks/catch/XXXX/YYYY/"

async def push_webhook(data: dict):
    """Unified function to push data to a webhook"""

    async with aiohttp.ClientSession() as session:
        async with session.post(WEBHOOK_URL, json=data) as resp:
            if resp.status == 200:
                logger.info("Webhook sent successfully")
            else:
                logger.error(f"Webhook failed: {await resp.text()}")

