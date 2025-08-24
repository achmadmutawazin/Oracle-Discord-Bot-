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

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

def keep_alive():
    t = threading.Thread(target=run_web)
    t.start()

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
VERIFIED_ROLE_NAME = "Member Oracle"
VERIFICATION_CHANNEL_NAME = "verification"
WELCOME_CHANNEL_NAME = "welcome-oracle-member-❤️"
VERIFICATION_EMOJI = "🙏"
TOKEN = os.getenv("DISCORD_TOKEN")

# --- DB CONFIG ---
DB_FILE = "Pendataan Ulang Anggota Oracle (Jawaban).xlsx"
SHEET_NAME = "rapih"

try:
    df = pd.read_excel(DB_FILE, sheet_name=SHEET_NAME, header=None)
    df = df.rename(columns={
        0: "Email",
        1: "Nama Lengkap",
        2: "Tgl Lahir",
        3: "Display Nama Line",
        4: "No Anggota"
    })
except Exception as e:
    logging.error(f"❌ Failed to open database file: {e}")
    df = pd.DataFrame(columns=["Email", "Nama Lengkap", "Tgl Lahir", "Display Nama Line", "No Anggota"])

EMAIL_REGEX = r"(^[a-z0-9_.+-]+@[a-z0-9-]+\.[a-z0-9-.]+$)"

def generate_no_anggota():
    global df
    try:
        if df.empty or df["No Anggota"].isna().all():
            return "OTM-112"

        existing = df["No Anggota"].dropna().astype(str)
        nums = []
        for x in existing:
            if x.startswith("OTM-"):
                try:
                    nums.append(int(x.split("-")[1]))
                except:
                    continue

        if not nums:
            return "OTM-112"

        nums = [n for n in nums if n >= 112]
        if not nums:
            return "OTM-112"

        next_num = max(nums) + 1
        return f"OTM-{next_num:03d}"
    except Exception as e:
        logging.error(f"Error generating No Anggota: {e}")
        return "OTM-999"

def save_db():
    try:
        with pd.ExcelWriter(DB_FILE, engine="openpyxl", mode="w") as writer:
            df.to_excel(writer, sheet_name=SHEET_NAME, index=False, header=False)
    except Exception as e:
        logging.error(f"❌ Failed to save database: {e}")

def check_and_update(email, nama, tgl, nickname):
    global df
    try:
        for idx, row in df.iterrows():
            if str(row["Email"]).strip().lower() == str(email).strip().lower():
                if (
                    str(row["Nama Lengkap"]).strip() == nama.strip()
                    and str(row["Tgl Lahir"]).strip() == tgl.strip()
                    and str(row["Display Nama Line"]).strip() == nickname.strip()
                ):
                    return "UNCHANGED", row["No Anggota"], row["Nama Lengkap"]

                df.at[idx, "Nama Lengkap"] = nama
                df.at[idx, "Tgl Lahir"] = tgl
                df.at[idx, "Display Nama Line"] = nickname
                no_anggota = df.at[idx, "No Anggota"]
                save_db()
                return "UPDATED", no_anggota, nama

        for idx, row in df.iterrows():
            if (
                (pd.isna(row["Email"]) or str(row["Email"]).strip() == "")
                and not pd.isna(row["No Anggota"])
                and str(row["No Anggota"]).startswith("OTM-")
            ):
                try:
                    num = int(str(row["No Anggota"]).split("-")[1])
                except:
                    continue
                if num >= 112:
                    df.at[idx, "Email"] = email
                    df.at[idx, "Nama Lengkap"] = nama
                    df.at[idx, "Tgl Lahir"] = tgl
                    df.at[idx, "Display Nama Line"] = nickname
                    no_anggota = row["No Anggota"]
                    save_db()
                    return "NEW", no_anggota, nama

        no_anggota = generate_no_anggota()
        new_row = {
            "Email": email,
            "Nama Lengkap": nama,
            "Tgl Lahir": tgl,
            "Display Nama Line": nickname,
            "No Anggota": no_anggota,
        }
        df.loc[len(df)] = new_row
        save_db()
        return "NEW", no_anggota, nama

    except Exception as e:
        logging.error(f"❌ Error updating DB: {e}")
        return "ERROR", "OTM-999", nama

# --- INPUT VALIDATION ---
def validate_input(user_input):
    try:
        parts = [p.strip() for p in user_input.split(",")]
        if len(parts) != 4:
            return False, None
        email, nama, tgl, nickname = parts
        if not re.match(EMAIL_REGEX, email):
            return False, None
        try:
            datetime.strptime(tgl, "%d-%m-%Y")
        except:
            try:
                datetime.strptime(tgl, "%d-%m")
            except:
                return False, None
        return True, (email, nama, tgl, nickname)
    except Exception as e:
        logging.error(f"Validation error: {e}")
        return False, None

# --- ASSIGN ROLE ---
async def assign_role(member, guild):
    try:
        role_verified = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)
        role_new_man = discord.utils.get(guild.roles, name="new man")
        role_new_woman = discord.utils.get(guild.roles, name="new woman")

        roles_to_remove = []
        if role_new_man in member.roles:
            roles_to_remove.append(role_new_man)
        if role_new_woman in member.roles:
            roles_to_remove.append(role_new_woman)

        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)

        if role_verified:
            await member.add_roles(role_verified)
        else:
            logging.error(f"Role '{VERIFIED_ROLE_NAME}' not found.")
    except Exception as e:
        logging.error(f"Error assigning role: {e}")

# --- START VERIFICATION ---
async def start_verification(member, guild):
    verification_channel = discord.utils.get(guild.text_channels, name=VERIFICATION_CHANNEL_NAME)
    welcome_channel = discord.utils.get(guild.text_channels, name=WELCOME_CHANNEL_NAME)

    try:
        dm = await member.create_dm()
        embed = discord.Embed(
            title="🙏 Verification Start",
            description="Please enter your data in this format:\n"
                        "`email, nama lengkap, tanggal lahir(dd-mm-yyyy), nickname`",
            color=discord.Color.gold()
        )
        await dm.send(embed=embed)
    except discord.Forbidden:
        if verification_channel:
            await verification_channel.send(
                f"{member.mention} ⚠️ I couldn’t DM you. Please enable DMs from server members."
            )
        return

    try:
        # ⬇️ FIX: Keep asking until valid input
        while True:
            msg = await bot.wait_for(
                "message", timeout=180,
                check=lambda m: m.author == member and isinstance(m.channel, discord.DMChannel)
            )
            valid, parsed = validate_input(msg.content)
            if not valid:
                embed_invalid = discord.Embed(
                    title="❌ Invalid Input",
                    description=f"Your input was:\n```{msg.content}```\n"
                                "⚠️ Format must be:\n"
                                "`email, nama lengkap, tanggal lahir(dd-mm-yyyy), nickname`",
                    color=discord.Color.red()
                )
                await dm.send(embed=embed_invalid)
                continue  # ask again
            email, nama, tgl, nickname = parsed
            break  # ✅ valid, exit loop

        # --- (the rest of your existing logic below remains unchanged) ---
        match = df[df["Email"].str.lower() == email.lower()]
        if not match.empty:
            row = match.iloc[0]
            no_anggota = row["No Anggota"]
            old_nama = row["Nama Lengkap"]
            old_tgl = row["Tgl Lahir"]
            old_nick = row["Display Nama Line"]

            embed_exist = discord.Embed(
                title="📌 Data Found",
                description=(
                    f"**Current Data in DB:**\n"
                    f"No Anggota: {no_anggota}\n"
                    f"Nama: {old_nama}\n"
                    f"Tgl Lahir: {old_tgl}\n"
                    f"Nickname: {old_nick}\n\n"
                    "**Your New Input:**\n"
                    f"Nama: {nama}\n"
                    f"Tgl Lahir: {tgl}\n"
                    f"Nickname: {nickname}\n\n"
                    "React ✅ to keep old DB data.\n"
                    "React 🔄 to update with your new input."
                ),
                color=discord.Color.blue()
            )
            prompt = await dm.send(embed=embed_exist)
            await prompt.add_reaction("✅")
            await prompt.add_reaction("🔄")

            def check_react(payload):
                return (
                    payload.user_id == member.id
                    and str(payload.emoji) in ["✅", "🔄"]
                    and payload.message_id == prompt.id
                )

            try:
                reaction = await bot.wait_for("raw_reaction_add", timeout=180, check=check_react)
                emoji = str(reaction.emoji)

                if emoji == "✅":
                    await assign_role(member, guild)
                    try:
                        await member.edit(nick=f"{no_anggota} | {old_nama}")
                    except discord.Forbidden:
                        pass
                    if welcome_channel:
                        embed_welcome = discord.Embed(
                            title="🎉 Welcome to Oracle!",
                            description=(f"Welcome {member.mention}!\n\n"
                                         f"No Anggota: {no_anggota}\n\n"
                                         f"You are now part of Member Oracle. 🎉"),
                            color=discord.Color.green()
                        )
                        await welcome_channel.send(embed=embed_welcome)

                elif emoji == "🔄":
                    status, no_anggota, final_nama = check_and_update(email, nama, tgl, nickname)
                    if status == "UNCHANGED":
                        await dm.send(embed=discord.Embed(
                            title="⚠️ No Changes",
                            description="Your new data is identical to old data. No changes made, but you are verified.",
                            color=discord.Color.orange()
                        ))
                    elif status == "UPDATED":
                        await dm.send(embed=discord.Embed(
                            title="✅ Data Updated",
                            description="Your data has been updated successfully.",
                            color=discord.Color.green()
                        ))

                    await assign_role(member, guild)
                    try:
                        await member.edit(nick=f"{no_anggota} | {final_nama}")
                    except discord.Forbidden:
                        pass
                    if welcome_channel:
                        embed_welcome = discord.Embed(
                            title="🎉 Welcome to Oracle!",
                            description=(f"Welcome {member.mention}!\n\n"
                                         f"No Anggota: {no_anggota}\n\n"
                                         f"You are now part of Member Oracle. 🎉"),
                            color=discord.Color.green()
                        )
                        await welcome_channel.send(embed=embed_welcome)

            except asyncio.TimeoutError:
                await dm.send(embed=discord.Embed(
                    title="⌛ Timeout",
                    description="Verification timed out. Please restart.",
                    color=discord.Color.red()
                ))

        else:
            status, no_anggota, final_nama = check_and_update(email, nama, tgl, nickname)
            if status == "NEW":
                await dm.send(embed=discord.Embed(
                    title="🆕 Registered",
                    description="You have been registered successfully.",
                    color=discord.Color.green()
                ))

            await assign_role(member, guild)
            try:
                await member.edit(nick=f"{no_anggota} | {final_nama}")
            except discord.Forbidden:
                pass
            if welcome_channel:
                embed_welcome = discord.Embed(
                    title="🎉 Welcome to Oracle!",
                    description=(f"Welcome {member.mention}!\n\n"
                                 f"No Anggota: {no_anggota}\n\n"
                                 f"You are now part of Member Oracle. 🎉"),
                    color=discord.Color.green()
                )
                await welcome_channel.send(embed=embed_welcome)

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
    if channel.name != VERIFICATION_CHANNEL_NAME:
        return
    message = await channel.fetch_message(payload.message_id)
    if message.author.id != bot.user.id:
        return

    verified_role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)
    if verified_role in member.roles:
        try:
            dm = await member.create_dm()
            embed_verified = discord.Embed(
                title="✅ Already Verified",
                description="You are already verified.",
                color=discord.Color.green()
            )
            await dm.send(embed=embed_verified)
        except discord.Forbidden:
            await channel.send(f"{member.mention} ✅ You are already verified.", delete_after=10)
        return

    if member.id in active_verifications:
        try:
            dm = await member.create_dm()
            embed_reminder = discord.Embed(
                title="⚠️ Verification Already Started",
                description="You already started verification.\n\n"
                            "👉 Please check your DM and complete it there.",
                color=discord.Color.orange()
            )
            await dm.send(embed=embed_reminder)
        except discord.Forbidden:
            await channel.send(
                f"{member.mention} ⚠️ You already started verification. Please check your DM to continue.",
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
    if ctx.channel.name != VERIFICATION_CHANNEL_NAME:
        await ctx.send(f"⚠️ Please use this command in #{VERIFICATION_CHANNEL_NAME}")
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
bot.run(TOKEN)
