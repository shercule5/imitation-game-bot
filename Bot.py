import os
import random
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional, Dict

# ==========================
# Load token from .env
# ==========================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ==========================
# Bot setup
# ==========================
intents = discord.Intents.default()
intents.message_content = True  # required for reading !commands
bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================
# Data classes for players & sessions
# ==========================
@dataclass
class Player:
    user_id: int
    name: str
    role: Optional[str] = None  # "INTERROGATOR" | "CONTESTANT_A" | "CONTESTANT_B"
    is_ai: bool = False

@dataclass
class Session:
    guild_id: int
    channel_id: int
    interrogator: Optional[Player] = None
    a: Optional[Player] = None
    b: Optional[Player] = None
    active: bool = False
    round_num: int = 0

sessions: Dict[int, Session] = {}

# ==========================
# Simple AI stub (replace later with API/model call)
# ==========================
def ai_reply(question: str) -> str:
    starters = ["Honestly,", "From experience,", "I think", "In my view,", "Probably", "Tough one,"]
    fillers = [
        "it depends on context.", "I’d go with pizza.", "sunset at the beach.", "quality over quantity.",
        "because it’s practical.", "since it’s reliable.", "I could be wrong though."
    ]
    return f"{random.choice(starters)} {random.choice(fillers)}"

# ==========================
# Events & Commands
# ==========================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

@bot.command()
async def ping(ctx):
    await ctx.send("pong")

@bot.command(name="startgame", aliases=["start"])
async def startgame(ctx):
    gid = ctx.guild.id
    if gid in sessions and sessions[gid].active:
        await ctx.reply("A game is already active.")
        return
    sessions[gid] = Session(guild_id=gid, channel_id=ctx.channel.id)
    await ctx.reply("🎮 New Imitation Game session created! Players, type `!join` to enter (need 3 players).")

@bot.command()
async def join(ctx):
    gid = ctx.guild.id
    if gid not in sessions:
        await ctx.reply("No session yet. Start with `!startgame`.")
        return
    s = sessions[gid]
    if s.active:
        await ctx.reply("Game already in progress.")
        return

    uid = ctx.author.id
    if any(p and p.user_id == uid for p in [s.interrogator, s.a, s.b]):
        await ctx.reply("You’re already registered.")
        return

    if not s.interrogator:
        s.interrogator = Player(uid, ctx.author.display_name, role="INTERROGATOR")
        role = "Interrogator"
    elif not s.a:
        s.a = Player(uid, ctx.author.display_name, role="CONTESTANT_A")
        role = "Contestant A"
    elif not s.b:
        s.b = Player(uid, ctx.author.display_name, role="CONTESTANT_B")
        role = "Contestant B"
    else:
        await ctx.reply("This session already has 3 players.")
        return

    try:
        await ctx.author.send(f"You joined as **{role}**. Wait for `!begin`.")
    except:
        pass
    await ctx.reply(f"{ctx.author.mention} joined as **{role}**. When all 3 have joined, run `!begin`.")

@bot.command()
async def begin(ctx):
    gid = ctx.guild.id
    if gid not in sessions:
        await ctx.reply("No session. Use `!startgame`.")
        return
    s = sessions[gid]
    if s.active:
        await ctx.reply("Game already started.")
        return
    if not (s.interrogator and s.a and s.b):
        await ctx.reply("Need exactly 3 players (`!join`) before `!begin`.")
        return

    # Randomly assign AI (hidden)
    ai_is_a = random.choice([True, False])
    s.a.is_ai = ai_is_a
    s.b.is_ai = not ai_is_a
    s.active = True
    s.round_num = 0

    await ctx.reply("Game started! Interrogator uses `!ask <question>`. "
                    "Contestants answer by **DMing** the bot with `!reply <text>`.")

    async def dm(uid, text):
        user = await bot.fetch_user(uid)
        try:
            await user.send(text)
        except:
            pass

    await dm(s.interrogator.user_id, "You are the **Interrogator**. Ask in-channel with `!ask <question>`. "
                                     "When ready, guess with `!guess A` or `!guess B`.")
    await dm(s.a.user_id, "You are **Contestant A**. Reply ONLY here in DM with `!reply <text>`.")
    await dm(s.b.user_id, "You are **Contestant B**. Reply ONLY here in DM with `!reply <text>`.")

@bot.command()
async def ask(ctx, *, question: str):
    gid = ctx.guild.id
    if gid not in sessions:
        await ctx.reply("No session.")
        return
    s = sessions[gid]
    if not s.active:
        await ctx.reply("Game not active. Use `!begin`.")
        return
    if ctx.author.id != s.interrogator.user_id:
        await ctx.reply("Only the Interrogator can ask.")
        return

    s.round_num += 1
    await ctx.reply(f"**Round {s.round_num}** — question sent to contestants.")

    async def send_q(player: Player, label: str):
        if player.is_ai:
            await asyncio.sleep(random.uniform(1.2, 3.5))
            answer = ai_reply(question)
            channel = bot.get_channel(s.channel_id)
            await channel.send(f"**Contestant {label}:** {answer}")
        else:
            try:
                user = await bot.fetch_user(player.user_id)
                await user.send(f"**Round {s.round_num} Question:** {question}\n"
                                f"Reply here with `!reply your answer`.")
            except:
                pass

    await asyncio.gather(send_q(s.a, "A"), send_q(s.b, "B"))

@bot.command()
async def guess(ctx, who: str):
    gid = ctx.guild.id
    if gid not in sessions:
        await ctx.reply("No session.")
        return
    s = sessions[gid]
    if not s.active:
        await ctx.reply("No active game.")
        return
    if ctx.author.id != s.interrogator.user_id:
        await ctx.reply("Only the Interrogator can guess.")
        return

    who = who.strip().upper()
    if who not in ("A", "B"):
        await ctx.reply("Use `!guess A` or `!guess B`.")
        return

    correct = (who == "A" and s.a.is_ai) or (who == "B" and s.b.is_ai)
    reveal = f"AI was Contestant {'A' if s.a.is_ai else 'B'}."
    outcome = "✅ Correct!" if correct else "❌ Incorrect."
    await ctx.reply(f"{outcome} {reveal}")
    s.active = False

# ==========================
# DM listener for contestants
# ==========================
@bot.event
async def on_message(message: discord.Message):
    # keep command processing working
    await bot.process_commands(message)

    # Only handle DMs to the bot
    if message.author.bot or message.guild is not None:
        return
    content = message.content.strip()
    if not content.lower().startswith("!reply "):
        return

    reply_text = content[7:].strip()
    # Find the session this user belongs to
    for s in sessions.values():
        if not s.active:
            continue
        label = None
        if s.a and message.author.id == s.a.user_id and not s.a.is_ai:
            label = "A"
        if s.b and message.author.id == s.b.user_id and not s.b.is_ai:
            label = "B"
        if label:
            channel = bot.get_channel(s.channel_id)
            await asyncio.sleep(random.uniform(0.8, 2.2))  # slight natural delay
            await channel.send(f"**Contestant {label}:** {reply_text}")
            break

# ==========================
# Run the bot
# ==========================
bot.run(TOKEN)


