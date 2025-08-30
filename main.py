import discord
from discord.ext import commands
import re
import asyncio
import logging
from dotenv import load_dotenv
import os
import pandas as pd
from datetime import datetime
from flask import Flask
import threading
import json

import gspread
from google.oauth2.service_account import Credentials

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

def keep_alive():
    t = threading.Thread(target=run_web)
    t.start()

# Google Sheets connection function
def connect_google_sheets():
    try:
        with open("/etc/secrets/GOOGLE_SERVICE_CREDS") as f:
            creds_dict = json.load(f)

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)

        logging.info("✅ Successfully connected to Google Sheets (read-only)")
        return gc
    except Exception as e:
        logging.error(f"❌ Failed to connect to Google Sheets: {e}")
        return None

# Load environment variables
load_dotenv()

# Logging setup
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Config
VERIFIED_ROLE_ID = 1218217885940318328
NEW_MAN_ROLE_ID = 1407458727556026510
NEW_WOMAN_ROLE_ID = 1407458804437880915
VERIFICATION_CHANNEL_ID = 1407046741458555062
WELCOME_CHANNEL_ID = 1408820923905216602
VERIFICATION_EMOJI = "🙏"
TOKEN = os.getenv("DISCORD_TOKEN")

# --- GOOGLE SHEET CONFIG ---
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_NAME = "rapih"

# Google Sheets client
gc = connect_google_sheets()

def get_latest_df():
    """Fetch the latest data from Google Sheets."""
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet(SHEET_NAME)
        data = worksheet.get_all_values()
        return pd.DataFrame(data[1:], columns=data[0])
    except Exception as e:
        logging.error(f"❌ Failed to reload Google Sheet: {e}")
        return pd.DataFrame(columns=["Email", "Nama Lengkap", "Tgl Lahir", "Display Nama Line", "No Anggota", "Jenis Kelamin"])

EMAIL_REGEX = r"(^[a-z0-9_.+-]+@[a-z0-9-]+\.[a-z0-9-.]+$)"

def format_birthdate(date_str: str) -> str:
    try:
        parsed = datetime.strptime(date_str.strip(), "%d/%m")
        return parsed.strftime("%d %B")
    except Exception:
        return date_str

# --- INPUT VALIDATION ---
def validate_input(user_input):
    try:
        parts = [p.strip() for p in user_input.split(",")]
        if len(parts) != 4:
            return False, "❌ Wrong number of fields. Format: email, nama lengkap, tanggal lahir, nickname.", None

        email, nama, tgl, nickname = parts

        if not re.match(EMAIL_REGEX, email):
            return False, f"❌ Invalid email format: `{email}`", None

        if not nama or len(nama) < 2:
            return False, f"❌ Invalid name: `{nama}`", None

        try:
            datetime.strptime(tgl, "%d-%m-%Y")
        except:
            try:
                datetime.strptime(tgl, "%d-%m")
            except:
                try:
                    datetime.strptime(tgl, "%d/%m")
                except:
                    return False, f"❌ Salah ya formatnya: `{tgl}`. pakai format DD/MM (Contohnya DD/MM)", None

        if not nickname:
            return False, "❌ Nickname cannot be empty.", None

        return True, None, (email, nama, tgl, nickname)

    except Exception as e:
        logging.error(f"Validation error: {e}")
        return False, "❌ Unexpected error during validation.", None

# --- ASSIGN ROLE ---
async def assign_role(member, guild, gender=None):
    try:
        role_verified = guild.get_role(VERIFIED_ROLE_ID)
        role_new_man = guild.get_role(NEW_MAN_ROLE_ID)
        role_new_woman = guild.get_role(NEW_WOMAN_ROLE_ID)

        roles_to_remove = []
        if role_new_man in member.roles:
            roles_to_remove.append(role_new_man)
        if role_new_woman in member.roles:
            roles_to_remove.append(role_new_woman)

        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)

        if role_verified:
            await member.add_roles(role_verified)
    except Exception as e:
        logging.error(f"Error assigning role: {e}")

# --- START VERIFICATION ---
async def start_verification(member, guild):
    verification_channel = guild.get_channel(VERIFICATION_CHANNEL_ID)
    welcome_channel = guild.get_channel(WELCOME_CHANNEL_ID)

    try:
        dm = await member.create_dm()
        embed = discord.Embed(
            title="🙏 Verification Start",
            description="Masukin Input data pakai format berikut ya..:\n"
                        "`email, nama lengkap, tanggal lahir(DD/MM), nickname`",
            color=discord.Color.gold()
        )
        await dm.send(embed=embed)
    except discord.Forbidden:
        if verification_channel:
            await verification_channel.send(
                f"{member.mention} ⚠️ Aku gabisa DM kamu nih :(, enable DM nya yahh ."
            )
        return

    try:
        while True:
            msg = await bot.wait_for(
                "message", timeout=180,
                check=lambda m: m.author == member and isinstance(m.channel, discord.DMChannel)
            )
            valid, error_msg, parsed = validate_input(msg.content)

            if not valid:
                embed_invalid = discord.Embed(
                    title="❌ Invalid Input",
                    description=(f"{error_msg}\n\n"
                                 f"Your input was:\n```{msg.content}```\n"
                                 "👉 Correct format:\n"
                                 "`email, nama lengkap, tanggal lahir(dd-mm-yyyy), nickname`"),
                    color=discord.Color.red()
                )
                await dm.send(embed=embed_invalid)
                continue

            email, nama, tgl, nickname = parsed
            break

        # 🔄 Always fetch fresh Google Sheet data
        df_latest = get_latest_df()

        match = df_latest[df_latest["Email"].str.lower() == email.lower()]
        if not match.empty:
            row = match.iloc[0]
            nama_db = row["Nama Lengkap"]
            no_anggota = row["No Anggota"]
            tgl_lahir = format_birthdate(row["Tgl Lahir"])

            await assign_role(member, guild, gender)
            try:
                await member.edit(nick=f"{no_anggota} | {nama_db}")
            except discord.Forbidden:
                pass

            if welcome_channel:
                embed_welcome = discord.Embed(
                    title="🎉 Welcome to Oracle!",
                    description=(f"Welcome **{member.display_name}** ({member.mention})!\n\n"
                                 f"No Anggota: {no_anggota}\n\n"
                                 "You are now part of Member Oracle. 🎉"),
                    color=discord.Color.green()
                )
                await welcome_channel.send(embed=embed_welcome)

        else:
            await dm.send(embed=discord.Embed(
                title="❌ Not Found",
                description="Your data was not found in our database. Please contact an administrator.",
                color=discord.Color.red()
            ))

    except asyncio.TimeoutError:
        await dm.send(embed=discord.Embed(
            title="⌛ Timeout",
            description="Verification timed out. Please restart.",
            color=discord.Color.red()
        ))

# --- ACTIVE VERIFICATION TRACKER ---
active_verifications = set()

# --- REACTION TRIGGER ---
@bot.event
async def on_raw_reaction_add(payload):
    if str(payload.emoji.name) != VERIFICATION_EMOJI:
        return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if member.bot:
        return
    channel = guild.get_channel(payload.channel_id)
    if channel.id != VERIFICATION_CHANNEL_ID:
        return
    message = await channel.fetch_message(payload.message_id)
    if message.author.id != bot.user.id:
        return

    verified_role = guild.get_role(VERIFIED_ROLE_ID)
    if verified_role in member.roles:
        try:
            dm = await member.create_dm()
            await dm.send(embed=discord.Embed(
                title="✅ Already Verified",
                description="You are already verified.",
                color=discord.Color.green()
            ))
        except discord.Forbidden:
            await channel.send(f"{member.mention} ✅ You are already verified.", delete_after=10)
        return

    if member.id in active_verifications:
        try:
            dm = await member.create_dm()
            await dm.send(embed=discord.Embed(
                title="⚠️ Verification Already Started",
                description="You already started verification.\n\n👉 Please check your DM.",
                color=discord.Color.orange()
            ))
        except discord.Forbidden:
            await channel.send(
                f"{member.mention} ⚠️ You already started verification. Please check your DM.",
                delete_after=15
            )
        return

    active_verifications.add(member.id)
    try:
        await start_verification(member, guild)
    except Exception as e:
        logging.error(f"Error during verification for {member.display_name} ({member.id}): {e}")
    finally:
        active_verifications.discard(member.id)

# --- MANUAL COMMAND ---
@bot.command()
@commands.has_permissions(administrator=True)
async def sendverify(ctx):
    if ctx.channel.id != VERIFICATION_CHANNEL_ID:
        await ctx.send(f"⚠️ Please use this command in <#{VERIFICATION_CHANNEL_ID}>")
        return

    embed = discord.Embed(
        title="🔰 Member Verification",
        description=(f"React with {VERIFICATION_EMOJI} to begin verification.\n\n"
                     "I will DM you for your data."),
        color=discord.Color.blue()
    )
    msg = await ctx.send(embed=embed)
    await msg.add_reaction(VERIFICATION_EMOJI)
    try:
        await msg.pin()
    except discord.Forbidden:
        await ctx.send("⚠️ I don’t have permission to pin messages.")

# --- BOT READY ---
@bot.event
async def on_ready():
    logging.info(f"Bot connected as {bot.user}")

# --- RUN BOT ---
keep_alive()
bot.run(TOKEN, reconnect=True)
