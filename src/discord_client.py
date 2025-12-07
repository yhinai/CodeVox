"""Discord integration for sending notifications"""

import asyncio
import os
import discord


# Discord configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

# Discord client setup
_discord_client = None
_discord_ready = asyncio.Event()


async def init_discord_client():
    """Initialize Discord client if configured"""
    global _discord_client, _discord_ready

    if not DISCORD_TOKEN or not DISCORD_CHANNEL_ID:
        print("Discord not configured (missing DISCORD_TOKEN or DISCORD_CHANNEL_ID)")
        return

    if _discord_client is not None:
        return  # Already initialized

    # Create Discord client with proper intents
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.guild_messages = True
    _discord_client = discord.Client(intents=intents)

    @_discord_client.event
    async def on_ready():
        print(f"[DISCORD] Connected as {_discord_client.user}")
        print(f"[DISCORD] Bot is in {len(_discord_client.guilds)} guild(s)")

        # Verify channel access
        channel = _discord_client.get_channel(int(DISCORD_CHANNEL_ID))
        if channel:
            print(f"[DISCORD] Found channel: #{channel.name}")
        else:
            print(f"[DISCORD] WARNING: Channel {DISCORD_CHANNEL_ID} not found")

        _discord_ready.set()

    @_discord_client.event
    async def on_error(event, *args, **kwargs):
        print(f"[DISCORD] Error in {event}: {args} {kwargs}")

    # Start Discord client in background
    asyncio.create_task(_discord_client.start(DISCORD_TOKEN))

    # Wait for client to be ready with timeout
    try:
        await asyncio.wait_for(_discord_ready.wait(), timeout=30.0)
        print("[DISCORD] Client ready!")
    except asyncio.TimeoutError:
        print("[DISCORD] ERROR: Timeout waiting for Discord client to connect")
        _discord_client = None


async def send_to_discord(message: str):
    """Send a message to the configured Discord channel"""
    global _discord_client

    if not _discord_client or not DISCORD_CHANNEL_ID:
        return

    try:
        channel = _discord_client.get_channel(int(DISCORD_CHANNEL_ID))
        if not channel:
            print(f"[DISCORD] Channel {DISCORD_CHANNEL_ID} not found")
            return

        # Discord has a 2000 character limit per message
        MAX_LENGTH = 2000
        if len(message) > MAX_LENGTH:
            # Split into chunks
            chunks = [message[i:i+MAX_LENGTH] for i in range(0, len(message), MAX_LENGTH)]
            for i, chunk in enumerate(chunks[:5]):  # Limit to 5 chunks max
                if i > 0:
                    chunk = f"(continued {i+1}/{min(len(chunks), 5)})\n{chunk}"
                await channel.send(chunk)
                await asyncio.sleep(0.5)  # Rate limit protection
            if len(chunks) > 5:
                await channel.send(f"... (truncated, {len(chunks)-5} more chunks)")
            print(f"[DISCORD] Sent long message in {min(len(chunks), 5)} chunks")
        else:
            await channel.send(message)
            print(f"[DISCORD] Sent message: {message[:100]}...")
    except discord.errors.Forbidden:
        print(f"[DISCORD] ERROR: No permission to send messages to channel {DISCORD_CHANNEL_ID}")
    except discord.errors.HTTPException as e:
        print(f"[DISCORD] HTTP Error sending message: {e}")
    except Exception as e:
        print(f"[DISCORD] Error sending message: {e}")
