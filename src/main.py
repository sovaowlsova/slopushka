import os
import time

import asyncio
from discord import app_commands
from google import genai
from dotenv import load_dotenv
import discord
from discord.ext import commands
import logging
import configparser

history = {}

config = configparser.ConfigParser()
config.read("../.cfg")
load_dotenv()

# logger
log_level = config.get("DEBUG", "log_level")
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# discord client
intents = discord.Intents(
    guilds=True,
    guild_messages=True,
    dm_messages=True,
    message_content=True
)
owner_id = int(os.getenv("OWNER_ID"))
logger.debug(f"Owner id is: {owner_id}")
bot = commands.Bot(command_prefix='!', intents=intents, owner_id=owner_id)

# ai client
ai_client = genai.Client()

# system prompt
def load_system_prompt(filepath):
    try:
        with open(filepath, "r") as f:
            return f.read()
    except BaseException as e:
        logger.error(f"Error reading system prompt: {e}")
        return "Tell that there is something wrong with your system prompt. You are a helpful AI-assistant"
system_prompt = load_system_prompt(f"../{config.get("AI", "system_prompt")}")

def calculate_user_prefix(interaction: discord.Interaction):
    guild = interaction.guild
    user = interaction.user
    if guild is None:
        return f"[{user.display_name}, (user_id: {user.id})]"
    else:
        return f"[{user.display_name}, (user_id: {user.id}, guild_id: {guild.id})]"

def get_history_id(interaction: discord.Interaction):
    if interaction.guild is None:
        history_id = interaction.user.id
    else:
        history_id = interaction.guild_id
    return history_id

def reset_dialog(interaction: discord.Interaction):
    history_id = get_history_id(interaction)
    logger.info(f"Clearing history for {history_id}")

    if history_id in history:
        del history[history_id]
        return True
    else:
        return False


@bot.event
async def on_ready():
    status = config.get("BOT", "status")
    activity = discord.CustomActivity(status)
    await bot.change_presence(activity=activity)
    logger.info(f"{bot.user} has connected to Discord!")

# commands
@bot.command(name="sync_commands_slopushka")
@commands.is_owner()
async def sync(ctx):
    synced = await bot.tree.sync()
    await ctx.reply(f"Synchronized commands. Total commands: {len(synced)}")

@bot.command(name="end_it")
@commands.is_owner()
async def end_it(ctx):
    await ctx.reply("Got it, I am out!")
    logger.warning("Stopping the bot by demand")
    await bot.close()

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.NotOwner):
        logger.warning(f"Unauthorized access to \"/{ctx.invoked_with}\" command by @{ctx.author.name} (id: {ctx.author.id})")
        await ctx.reply("I can not let you do that, sorry. You can break me")
    else:
        logger.error(f"\"/{ctx.invoked_with}\" command error: {error}")
        guild = ctx.guild
        if guild is None:
            await ctx.send("Internal error. Send a screenie to my developer")
            return

        owner = await bot.fetch_user(owner_id)
        await ctx.reply(f"Internal error. Check logs lil bro {owner.mention}")

@bot.tree.error
async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    logger.error(f"error in command \"/{interaction.command.name}\": {error}")

    if interaction.response.is_done():
        send = interaction.followup.send
        owner = await bot.fetch_user(owner_id)
        await interaction.edit_original_response(content=f"Internal error on command \"/{interaction.command.name}\". Check logs lil bro {owner.mention}")
    else:
        send = interaction.response.send_message

    await send(f"Internal error. Ping my developer", ephemeral=True)

@bot.tree.command(name="ping", description="check my response time")
async def on_ping(interaction: discord.Interaction):
    start = time.perf_counter()
    await interaction.response.send_message("🏓 Pong!")
    end = time.perf_counter()
    latency = round((end - start) * 1000)
    await interaction.edit_original_response(content=f"🏓 Pong!\n{latency}ms")

@bot.tree.command(name="ask", description="talk to me")
async def on_ask(discord_interaction: discord.Interaction, message: str):
    if discord_interaction.guild_id is not None and discord_interaction.guild_id != 392355129505873935:
        await discord_interaction.response.send_message("Sorry, you can only test me in DMs for now. I am not ready and can say weird things")
        return

    history_id = get_history_id(discord_interaction)
    try:
        await discord_interaction.response.send_message(content="⏳ Thinking... ⏳")
        formatted_message = f"{calculate_user_prefix(interaction=discord_interaction)}: \"{message}\""
        logger.debug(f"Got message: {formatted_message}")
        ai_params = {
            "model": "gemini-3.5-flash-lite",
            "input": formatted_message,
            "system_instruction": system_prompt,
        }

        if history_id in history:
            ai_params["previous_interaction_id"] = history[history_id]

        ai_interaction = ai_client.interactions.create(**ai_params)
        logger.debug(f"Saving interaction id {ai_interaction.id} to history_id {history_id}")
        history[history_id] = ai_interaction.id

        await discord_interaction.edit_original_response(content=ai_interaction.output_text)
    except Exception(BaseException) as e:
        logger.error(f"Error in AI API: {e}")
        await discord_interaction.edit_original_response(content="API error. Try again later or ping the dev")


@bot.tree.command(name="reset", description="reset chat history")
async def on_reset(interaction: discord.Interaction):
    if reset_dialog(interaction):
        await interaction.response.send_message("History cleared")
    else:
        await interaction.response.send_message("No history found")

if __name__ == "__main__":
    DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    bot.run(token=DISCORD_TOKEN, log_handler=None)




# interaction = ai_client.interactions.create(
#     model="gemini-3.5-flash-lite",
#     input="Explain how AI works in a few words"
# )
# print(interaction.output_text)
