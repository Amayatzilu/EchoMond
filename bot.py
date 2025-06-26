import os
import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import random
import math
import json
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
from discord.ui import View, Select, Button
from discord import Interaction
from datetime import datetime

asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

# 🌌 EchoMond: Cosmic Edition
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Allow tracking for later interaction if needed

# 🎶 Local upload storage
MUSIC_FOLDER = "downloads/"
os.makedirs(MUSIC_FOLDER, exist_ok=True)

#☁️ Initialize the bot
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)  # help command disabled

# 🌒 YouTube download config (rare use, but kept for edge cases)
cookies_path = "/app/cookies.txt"
cookie_data = os.getenv("YOUTUBE_COOKIES", "")

if cookie_data:
    with open(cookies_path, "w") as f:
        f.write(cookie_data)

@bot.event
async def on_ready():
    for guild in bot.guilds:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)
    print(f"🌙 EchoMond wakes... and the old echoes are gone.")
    print(f"[EchoMond Online] Logged in as: {bot.user} (ID: {bot.user.id})")
    print("Connected to these realms:")

    for guild in bot.guilds:
        print(f"— {guild.name} (ID: {guild.id})")

    print("🌌 EchoMond floats through the stars, listening for your signal.")

@bot.command(aliases=["lost", "helfen"])
async def help(ctx):
    """EchoMond's celestial help command – quiet, poetic, cosmic."""

    class HelpDropdown(Select):
        def __init__(self):
            options = [
                discord.SelectOption(label="🌠 Playback", description="Commands to shape the soundwaves."),
                discord.SelectOption(label="🌌 Uploads", description="Manage your personal sound constellation."),
                discord.SelectOption(label="🏷️ Tagging", description="Label and filter your music by feel."),
                discord.SelectOption(label="🔧 Utility", description="Quiet commands that help EchoMond flow.")
            ]
            super().__init__(placeholder="Choose a path through the stars...", options=options)

        async def callback(self, interaction: Interaction):
            choice = self.values[0]

            embed = discord.Embed(
                color=discord.Color(0xb9a1ff),
                title="🌙 EchoMond Guide – Commands Whispered in Starlight",
                description=""
            )
            embed.set_footer(text="🩵 EchoMond drifts where harmony calls...")

            if "Playback" in choice:
                embed.title = "🌠 Playback – Shape the Echo"
                embed.description = (
                    "🎶 **!play** – Play a melody from the universe. Alias: p\n"
                    "⏸️ **!pause** – Let the sound breathe\n"
                    "▶️ **!resume** – Resume its flow\n"
                    "⏭️ **!skip** – Gently pass to the next\n"
                    "⏹️ **!stop** – Silence the space and clear the queue\n"
                    "🔊 **!volume** – Adjust the magnitude of the wave. Alias: v\n"
                    "🔀 **!shuffle** – Scatter the songs like stardust\n"
                    "📜 **!queue** – View what echoes next. Alias: q"
                )
            elif "Uploads" in choice:
                embed.title = "🌌 Uploads – Build Your Personal Universe"
                embed.description = (
                    "📁 **!listsongs** – Explore what you've offered to the void\n"
                    "🔢 **!playbynumber** – Play by cosmic order. Alias: n\n"
                    "🌠 **!playalluploads** – Let it all shimmer\n"
                    "❌ **!deleteupload** – Retire a track from orbit. Alias: du\n"
                    "🧹 **!clearuploads** – Empty your sky of echoes. Alias: cu"
                )
            elif "Tagging" in choice:
                embed.title = "🏷️ Tagging – Classify Constellations"
                embed.description = (
                    "🔖 **!tag** – Attach feelings or ideas to your songs\n"
                    "💫 **!playbytag** – Call songs by shared celestial theme\n"
                    "📑 **!listtags** – Review your lyrical galaxy\n"
                    "🌿 **!removetag** – Let labels fall like leaves. Alias: untag"
                )
            elif "Utility" in choice:
                embed.title = "🔧 Utility – Keep Things in Orbit"
                embed.description = (
                    "🔗 **!join** – Invite EchoMond into your channel\n"
                    "🚪 **!leave** – Let him slip quietly away\n"
                    "🧺 **!clearqueue** – Clear the current journey. Alias: cq\n"
                    "📖 **!help** – Reopen this cosmic guide at any time"
                )

            await interaction.response.edit_message(embed=embed, view=self.view)

    class HelpView(View):
        def __init__(self):
            super().__init__(timeout=60)
            dropdown = HelpDropdown()
            dropdown.view = self
            self.add_item(dropdown)

    intro_embed = discord.Embed(
        title="🌙 EchoMond Help – Let the Silence Speak",
        description="Choose a command category below and let EchoMond guide you.",
        color=discord.Color(0xb9a1ff)
    )
    intro_embed.set_footer(text="💫 A guide through moonlight and melody...")

    await ctx.send(embed=intro_embed, view=HelpView())

YDL_OPTIONS = {
    'format': 'bestaudio[ext=m4a]/bestaudio/best',
    'noplaylist': 'False',
    'cookiefile': cookies_path,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': f'{MUSIC_FOLDER}%(title)s.%(ext)s',
    'quiet': True,
    'source_address': '0.0.0.0',
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    },
}

# 🔊 FFmpeg configs for local vs streamed
FFMPEG_OPTIONS = {
    'options': '-vn -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}
FFMPEG_LOCAL_OPTIONS = {
    'before_options': '-nostdin',
    'options': '-vn'
}

# 🌠 EchoMond’s data constellations
from collections import defaultdict
usage_counters = defaultdict(int)
pending_tag_uploads = defaultdict(dict)  # {guild_id: {user_id: [filenames]}}
file_tags_by_guild = defaultdict(dict)
uploaded_files_by_guild = defaultdict(list)
song_queue_by_guild = defaultdict(list)
last_now_playing_message_by_guild = defaultdict(lambda: None)
volume_levels_by_guild = defaultdict(lambda: 1.0)

# 📦 Persistent file galaxy
SAVE_FILE = "uploads_data.json"

def save_upload_data():
    try:
        data = {
            "uploaded_files_by_guild": uploaded_files_by_guild,
            "file_tags_by_guild": file_tags_by_guild,
        }
        with open(SAVE_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[Save Error] Could not save upload data: {e}")

def load_upload_data():
    try:
        with open(SAVE_FILE, "r") as f:
            data = json.load(f)
            for guild_id, files in data.get("uploaded_files_by_guild", {}).items():
                uploaded_files_by_guild[int(guild_id)] = files
            for guild_id, tags in data.get("file_tags_by_guild", {}).items():
                file_tags_by_guild[int(guild_id)] = tags
        print("[Startup] 🌙 EchoMond loaded past uploads from the stardust.")
    except FileNotFoundError:
        print("[Startup] ✨ No upload memory found. Beginning anew.")
    except Exception as e:
        print(f"[Load Error] 🚨 Could not load upload data: {e}")

load_upload_data()

@bot.event
async def on_message(message):
    # Let cosmic whispers reach the stars 🌌
    await bot.process_commands(message)

    # Gently ignore other bots and DMs
    if message.author.bot or not message.guild:
        return

    guild_id = message.guild.id
    user_id = message.author.id

    # 🌠 EchoMond's static flavor
    FLAVOR = {
        "upload_message": "🌙 EchoMond received your starlit sound.",
        "tag_prompt": "💫 Add your constellations — tags like `lunar`, `ambient`, `echo`.",
        "tag_none_found": "🚫 No tags drifted in the ether — try again, softly.",
        "tag_success_reply": "✨ Cosmic tags have been etched in the soundwaves."
    }

    # Handle song uploads 🌒
    if message.attachments:
        new_files = []
        for attachment in message.attachments:
            if attachment.filename.endswith(('.mp3', '.wav')):
                file_path = os.path.join(MUSIC_FOLDER, attachment.filename)
                await attachment.save(file_path)
                uploaded_files_by_guild[guild_id].append(attachment.filename)
                new_files.append(attachment.filename)

        if new_files:
            pending_tag_uploads[guild_id][user_id] = new_files
            await message.channel.send(
                f"{FLAVOR['upload_message']}\n"
                f"🎵 Uploaded: **{', '.join(new_files)}**\n"
                f"💫 {FLAVOR['tag_prompt']}"
            )
            save_upload_data()
        return

    # Handle tag replies 🌙
    if message.reference and user_id in pending_tag_uploads[guild_id]:
        try:
            replied_message = await message.channel.fetch_message(message.reference.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

        if replied_message.author.id != bot.user.id or not replied_message.content.startswith(FLAVOR['upload_message']):
            return

        tags = [t.strip().lower() for t in message.content.replace(",", " ").split()]
        if not tags:
            await message.channel.send(FLAVOR['tag_none_found'])
            return

        for filename in pending_tag_uploads[guild_id][user_id]:
            file_tags_by_guild[guild_id].setdefault(filename, []).extend(tags)

        await message.channel.send(
            f"{FLAVOR['tag_success_reply']}\n"
            f"🌌 Tagged **{len(pending_tag_uploads[guild_id][user_id])}** file(s) with: `{', '.join(tags)}`"
        )

        del pending_tag_uploads[guild_id][user_id]
        save_upload_data()

import asyncio  # Make sure this is at the top of your file

@bot.command(aliases=["playwithme", "connect", "verbinden", "kisses"])
async def join(ctx):
    """EchoMond joins your voice channel with moonlit grace 🌙"""

    # Step 1: Make sure the user is in a voice channel
    user_voice = ctx.author.voice
    if not user_voice or not user_voice.channel:
        await ctx.send("❌ I can’t hear your echo — join a voice channel first, and I’ll follow like moonlight.")
        return

    # Step 2: Grab the voice channel and check bot status
    channel = user_voice.channel
    vc = ctx.guild.voice_client

    try:
        # Already in that channel?
        if vc and vc.is_connected() and vc.channel == channel:
            await ctx.send("🌌 I’m already resonating in your sky. No need to summon me twice.")
            return

        # In the wrong channel? Try moving
        if vc and vc.is_connected():
            await vc.move_to(channel)
            await ctx.send("🔄 I’ve realigned my orbit — shifting to your constellation...")
            return

        # Not connected at all? Join fresh
        new_vc = await channel.connect(timeout=10)

        # Confirm connection
        if new_vc and new_vc.is_connected():
            await ctx.send("🌠 EchoMond descends on a trail of stardust to join your melody.")
        else:
            await ctx.send("⚠️ I tried... but something silenced me before I could echo back.")

    except asyncio.TimeoutError:
        await ctx.send("⏳ I reached, but couldn’t connect in time — the stars were unkind.")
    except discord.ClientException as e:
        await ctx.send(f"⚠️ Discord resisted the pull: `{e}`")
    except Exception as e:
        await ctx.send(f"💥 Something exploded in the ether: `{e}`")
        raise  # Let it show in Railway logs

@bot.command(aliases=["goaway", "disconnect", "verlassen", "hugs"])
async def leave(ctx):
    """EchoMond floats away from the voice channel 🌒"""
    vc = ctx.guild.voice_client

    if vc and vc.is_connected():
        try:
            await vc.disconnect()
            await ctx.send("🌠 EchoMond slips quietly from the soundstream, returning to the space between songs.")
            print(f"[EchoMond] Disconnected from {vc.channel} in {ctx.guild.name}.")
        except Exception as e:
            await ctx.send(f"⚠️ I tried to drift away, but something tethered me: `{e}`")
            print(f"[EchoMond] Failed to disconnect: {e}")
    else:
        await ctx.send("💤 I drift in silence already — call me again when music stirs.")

@bot.command(aliases=["p", "gimme", "spielen"])
async def play(ctx, url: str = None):
    """Streams a song from the stars (YouTube) or adds it to the moonlit queue."""
    guild_id = ctx.guild.id
    vc = ctx.guild.voice_client

    if not url:
        await ctx.send("🌑 A song link would help me find your rhythm in the void.")
        return

    if not vc or not vc.is_connected():
        await ctx.send("🔇 EchoMond floats beyond the sound... use `!join` to summon him first.")
        return

    await ctx.send("🔭 EchoMond tunes into your frequency...")

    try:
        with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(url, download=False)

            if 'entries' in info:  # Playlist
                added = 0
                for entry in info['entries']:
                    if entry:
                        entry_info = (
                            ydl.extract_info(entry['url'], download=False)
                            if entry.get('_type') == 'url'
                            else entry
                        )
                        song_queue_by_guild[guild_id].append((entry_info['webpage_url'], entry_info['title']))
                        added += 1
                await ctx.send(f"🌌 {added} celestial echoes added to the queue.")
            else:  # Single video
                song_queue_by_guild[guild_id].append((info['webpage_url'], info['title']))
                await ctx.send(f"🎶 **{info['title']}** has been tethered to the stars.")

    except Exception as e:
        await ctx.send(f"⚠️ The constellations whispered of an error: `{e}`")
        return

    if not vc.is_playing():
        await play_next(ctx)

async def play_next(ctx):
    guild_id = ctx.guild.id
    vc = ctx.voice_client or ctx.guild.voice_client  # 🌌 Fallback in case context is stale

    if not vc or not vc.is_connected():
        await ctx.send("🔇 I’m untethered from sound — use `!join` to bring me into your sky.")
        return

    if not song_queue_by_guild[guild_id]:
        await ctx.send("🌌 The queue is empty — the void hums in silence.")
        return

    usage_counters[guild_id] += 1
    is_high_usage = usage_counters[guild_id] >= 30

    # Clear previous now playing
    if last_now_playing_message_by_guild.get(guild_id):
        try:
            embed = last_now_playing_message_by_guild[guild_id].embeds[0]
            embed.set_field_at(0, name="Progress", value="🌑 Echo rests. `Complete`", inline=False)
            await last_now_playing_message_by_guild[guild_id].edit(embed=embed)
        except Exception:
            pass
        last_now_playing_message_by_guild[guild_id] = None

    song_data = song_queue_by_guild[guild_id].pop(0)
    is_temp_youtube = False

    if isinstance(song_data, tuple):
        original_url, song_title = song_data
        try:
            with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(original_url, download=True)
                song_url = info['requested_downloads'][0]['filepath'] if 'requested_downloads' in info else ydl.prepare_filename(info)
                duration = info.get('duration', 0)
                is_temp_youtube = True
        except Exception as e:
            await ctx.send(f"⚠️ Could not fetch audio: {e}\nSkipping to next song...")
            return await play_next(ctx)
        ffmpeg_options = FFMPEG_LOCAL_OPTIONS
    else:
        song_url = song_data
        song_title = os.path.basename(song_url)
        try:
            audio = MP3(song_url) if song_url.endswith(".mp3") else WAVE(song_url)
            duration = int(audio.info.length) if audio and audio.info else 0
        except Exception:
            duration = 0
        ffmpeg_options = FFMPEG_LOCAL_OPTIONS

    def after_play(error):
        if error:
            print(f"⚠️ Playback error: {error}")
        if is_temp_youtube and os.path.exists(song_url):
            try:
                os.remove(song_url)
            except Exception as e:
                print(f"[Cleanup Error] Could not delete file: {e}")
        asyncio.create_task(play_next(ctx))

    if vc and vc.is_connected():
        vc.play(discord.FFmpegPCMAudio(song_url, **ffmpeg_options), after=after_play)
        vc.source = discord.PCMVolumeTransformer(vc.source, volume_levels_by_guild[guild_id])
    else:
        await ctx.send("💥 EchoMond lost connection mid-orbit. Please call `!join` again.")
        return

    def cosmic_progress_bar(current, total, segments=10):
        moon_phases = ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘", "🌑", "🌑"]
        filled = int((current / total) * segments) if total else 0
        return ''.join(moon_phases[i] if i < filled else "🌑" for i in range(segments))

    embed = discord.Embed(
        title="🌙 EchoMond – Moonbound Melody",
        description=f"🎶 **{song_title}** emerges beneath starlit skies.",
        color=0xb9a1ff
    )

    if duration:
        embed.add_field(name="Progress", value=f"{cosmic_progress_bar(0, duration)} `0:00 / {duration // 60}:{duration % 60:02d}`", inline=False)

    message = await ctx.send(embed=embed)
    last_now_playing_message_by_guild[guild_id] = message

    # Periodic update (unless high-usage)
    if duration and not is_high_usage:
        for second in range(1, duration + 1):
            if second % 10 == 0 or second == duration:
                bar = cosmic_progress_bar(second, duration)
                timestamp = f"{second // 60}:{second % 60:02d} / {duration // 60}:{duration % 60:02d}"
                try:
                    embed.set_field_at(0, name="Progress", value=f"{bar} `{timestamp}`", inline=False)
                    await message.edit(embed=embed)
                except discord.HTTPException:
                    pass
            await asyncio.sleep(1)

        # Final phase shift
        try:
            embed.title = "🌌 Fadeout"
            embed.description = f"**{song_title}** drifts into cosmic silence."
            embed.set_field_at(0, name="Progress", value="🌕🌕🌕🌕🌕🌕🌕🌕🌕🌕 `Finished`", inline=False)
            await message.edit(embed=embed)
        except discord.HTTPException:
            pass

        await asyncio.sleep(6)

        try:
            embed.set_field_at(0, name="Progress", value="🌙 The glow fades gently... `Complete`", inline=False)
            await message.edit(embed=embed)
        except discord.HTTPException:
            pass
    else:
        await message.edit(content=f"▶️ Now playing: **{song_title}**")

@bot.command(aliases=["mixitup", "mischen", "shuff"])
async def shuffle(ctx):
    """Shuffles the current music queue with lunar grace."""
    guild_id = ctx.guild.id
    queue = song_queue_by_guild.get(guild_id, [])

    if len(queue) > 1:
        random.shuffle(queue)
        await ctx.send("🔀 The starlit playlist realigns — let the cosmos surprise you.")
    else:
        await ctx.send("🌘 Not enough echoes to twist the thread — add more moonlight.")

@bot.command(aliases=["hush"])
async def pause(ctx):
    """Pauses the current song with cosmic stillness."""
    vc = ctx.voice_client or ctx.guild.voice_client
    if not vc or not vc.is_connected():
        await ctx.send("🔇 I’m not resonating with your skies right now. Use `!join` to summon me first.")
        return
    if vc.is_playing():
        vc.pause()
        await ctx.send("🌑 The music slips into a lunar hush.")
    else:
        await ctx.send("🤫 There's no melody to silence — the void sings on its own.")

@bot.command(aliases=["youmayspeak"])
async def resume(ctx):
    """Resumes paused music with celestial flow."""
    vc = ctx.voice_client or ctx.guild.voice_client
    if not vc or not vc.is_connected():
        await ctx.send("🔇 I float in silence, untethered. Use `!join` to awaken the melody.")
        return
    if vc.is_paused():
        vc.resume()
        await ctx.send("🌔 The pulse returns — starlight rising in rhythm once more.")
    else:
        await ctx.send("🎵 I’m already playing the music of the spheres — no need to resume.")

@bot.command(aliases=["again", "rewind", "moonspin", "encore"])
async def replay(ctx):
    """Replays the last song played — a loop of lunar longing."""
    guild_id = ctx.guild.id
    vc = ctx.voice_client or ctx.guild.voice_client

    if not vc or not vc.is_connected():
        await ctx.send("🔇 I drift untethered — call `!join` to bring me close again.")
        return

    last_message = last_now_playing_message_by_guild.get(guild_id)
    if not last_message:
        await ctx.send("🌑 I can’t echo what hasn’t been sung. No track to replay.")
        return

    try:
        title_line = last_message.embeds[0].description
        # Extract the song title from: 🎶 **{song_title}** emerges beneath starlit skies.
        if title_line and "🎶 **" in title_line:
            song_title = title_line.split("🎶 **")[1].split("**")[0]
        else:
            song_title = None
    except Exception:
        song_title = None

    if not song_title:
        await ctx.send("🌀 The stars blur — I can’t trace the last song’s name.")
        return

    # Search for it in uploaded files (by filename match)
    uploaded_files = uploaded_files_by_guild.get(guild_id, [])
    match = next((f for f in uploaded_files if song_title in f), None)

    if not match:
        await ctx.send("💫 That melody has drifted out of the archive... I can't find it.")
        return

    song_path = os.path.join(MUSIC_FOLDER, match)
    song_queue_by_guild[guild_id].insert(0, song_path)
    await ctx.send(f"🔄 **{song_title}** spins once more through the cosmos...")

    if not vc.is_playing():
        await play_next(ctx)

@bot.command(aliases=["nextplease", "next", "skippy"])
async def skip(ctx):
    """Skips the current song with a stardust swirl."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("🌠 A star blinks out — skipping to the next celestial note.")
    else:
        await ctx.send("🌑 There's no melody to skip... silence echoes.")
    await play_next(ctx)

@bot.command(aliases=["turnitup", "tooloud", "v"])
async def volume(ctx, volume: int = None):
    """Adjusts the volume with lunar resonance."""
    guild_id = ctx.guild.id

    if volume is None:
        # Report current volume if not provided
        current = int((volume_levels_by_guild.get(guild_id, 0.5)) * 100)
        await ctx.send(f"🔊 Echo’s current resonance rings at **{current}%**.")
        return

    if 1 <= volume <= 100:
        volume_levels_by_guild[guild_id] = volume / 100.0

        if ctx.voice_client and ctx.voice_client.source:
            ctx.voice_client.source.volume = volume_levels_by_guild[guild_id]

        await ctx.send(f"🌌 Echo resonates now at **{volume}%** clarity.")
    else:
        await ctx.send("🌒 Volume must fall between **1** and **100** moons.")

@bot.command(aliases=["whatsnext", "q"])
async def queue(ctx):
    """Displays the current queue with cosmic pagination and moonlit shuffle."""
    guild_id = ctx.guild.id

    if not song_queue_by_guild[guild_id]:
        await ctx.send("🌌 The queue drifts silent... no songs orbit yet.")
        return

    class QueuePages(View):
        def __init__(self, guild_id):
            super().__init__(timeout=60)
            self.guild_id = guild_id
            self.page = 0
            self.items_per_page = 10

        async def send_page(self, interaction=None, message=None):
            queue = song_queue_by_guild[self.guild_id]
            start = self.page * self.items_per_page
            end = start + self.items_per_page
            page_items = queue[start:end]

            queue_display = '\n'.join([
                f"{i+1}. {os.path.basename(song[1]) if isinstance(song, tuple) else os.path.basename(song)}"
                for i, song in enumerate(page_items, start=start)
            ])

            embed = discord.Embed(
                title=f"🌙 EchoMond’s Queue — Page {self.page + 1}",
                description=queue_display or "🌑 The page echoes... nothing stirs here.",
                color=0x9A8DF2
            )
            embed.set_footer(text="Navigate the stars, or stir them anew.")

            if interaction:
                await interaction.response.edit_message(embed=embed, view=self)
            elif message:
                await message.edit(embed=embed, view=self)

        @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.blurple)
        async def prev_page(self, interaction: discord.Interaction, button: Button):
            if self.page > 0:
                self.page -= 1
                await self.send_page(interaction)

        @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.blurple)
        async def next_page(self, interaction: discord.Interaction, button: Button):
            queue = song_queue_by_guild[self.guild_id]
            max_pages = (len(queue) - 1) // self.items_per_page
            if self.page < max_pages:
                self.page += 1
                await self.send_page(interaction)

        @discord.ui.button(label="🌗 Shuffle", style=discord.ButtonStyle.green)
        async def shuffle_queue(self, interaction: discord.Interaction, button: Button):
            queue = song_queue_by_guild[self.guild_id]
            random.shuffle(queue)
            self.page = 0
            await interaction.response.send_message("🌠 The stars have realigned — queue reshuffled.", ephemeral=True)
            await self.send_page(interaction)

    view = QueuePages(guild_id)
    await view.send_page(message=await ctx.send(view=view))

@bot.command(aliases=["whatwegot"])
async def listsongs(ctx):
    """Lists uploaded songs with pagination, tagging filters, and celestial controls."""
    guild_id = ctx.guild.id
    uploaded_files = uploaded_files_by_guild.get(guild_id, [])
    file_tags = file_tags_by_guild.get(guild_id, {})

    if not uploaded_files:
        await ctx.send("☁️ No starlit uploads found yet — offer a melody to the cosmos.")
        return

    per_page = 10

    class State:
        def __init__(self):
            self.current_page = 0
            self.filtered_files = uploaded_files[:]
            self.selected_tag = None

    state = State()

    def get_page_embed():
        start = state.current_page * per_page
        end = start + per_page
        page = state.filtered_files[start:end]
        song_list = "\n".join(
            f"{start + i + 1}. {song or '[Unknown]'}"
            for i, song in enumerate(page)
        ) or "☁️ No songs found on this page."

        total_pages = max(1, math.ceil(len(state.filtered_files) / per_page))
        tag_title = f" – Tag: {state.selected_tag}" if state.selected_tag else ""
        embed = discord.Embed(
            title=f"📂 Uploaded Songs{tag_title} (Page {state.current_page + 1}/{total_pages})",
            description=song_list,
            color=discord.Color(0xb9a1ff)
        )
        embed.set_footer(text="✨ Let your playlist bloom. Use the buttons or !playnumber to select.")
        return embed

    class TagSelector(discord.ui.Select):
        def __init__(self):
            all_tags = sorted(set(
                tag for tags in file_tags.values() if tags
                for tag in tags
            ))
            options = [discord.SelectOption(label="All Songs", value="all")] + [
                discord.SelectOption(label=tag, value=tag) for tag in all_tags[:24]
            ]
            super().__init__(placeholder="Filter by tag...", options=options, row=0)

        async def callback(self, interaction: discord.Interaction):
            choice = self.values[0]
            state.selected_tag = None if choice == "all" else choice
            state.current_page = 0
            state.filtered_files = [
                f for f in uploaded_files if state.selected_tag in (file_tags.get(f) or [])
            ] if state.selected_tag else uploaded_files[:]
            await interaction.response.edit_message(embed=get_page_embed(), view=view)

    class PaginationView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
            self.add_item(TagSelector())
            self.message = None

        async def on_timeout(self):
            for item in self.children:
                item.disabled = True
            if self.message:
                await self.message.edit(view=self)

        @discord.ui.button(label="⏮️ Prev", style=discord.ButtonStyle.blurple, row=1)
        async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            if state.current_page > 0:
                state.current_page -= 1
                await interaction.response.edit_message(embed=get_page_embed(), view=self)

        @discord.ui.button(label="▶️ Play This Page", style=discord.ButtonStyle.green, row=1)
        async def play_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            start = state.current_page * per_page
            end = start + per_page
            for filename in state.filtered_files[start:end]:
                song_path = os.path.join(MUSIC_FOLDER, filename)
                song_queue_by_guild[guild_id].append(song_path)

            await interaction.response.send_message(
                f"🎶 {end - start} melodies stirred from the ether.\n🌌 EchoMond listens, and the cosmos hums in reply...",
                ephemeral=True
            )

            if not ctx.voice_client or not ctx.voice_client.is_connected():
                await interaction.followup.send(
                    "🔇 EchoMond is adrift... use `!join` to draw him into your sky.",
                    ephemeral=True
                )
                return

            if not ctx.voice_client.is_playing():
                await play_next(ctx)

        @discord.ui.button(label="🔀 Shuffle Page", style=discord.ButtonStyle.primary, row=1)
        async def shuffle_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            start = state.current_page * per_page
            end = start + per_page
            page = state.filtered_files[start:end]
            random.shuffle(page)

            for filename in page:
                song_path = os.path.join(MUSIC_FOLDER, filename)
                song_queue_by_guild[guild_id].append(song_path)

            await interaction.response.send_message(
                f"🔀 {len(page)} tracks shuffled and queued beneath the stars.",
                ephemeral=True
            )

            if not ctx.voice_client or not ctx.voice_client.is_connected():
                await interaction.followup.send(
                    "🔇 EchoMond awaits connection. Use `!join` to begin playback.",
                    ephemeral=True
                )
                return

            if not ctx.voice_client.is_playing():
                await play_next(ctx)

        @discord.ui.button(label="⏭️ Next", style=discord.ButtonStyle.blurple, row=1)
        async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            total_pages = max(1, math.ceil(len(state.filtered_files) / per_page))
            if state.current_page < total_pages - 1:
                state.current_page += 1
                await interaction.response.edit_message(embed=get_page_embed(), view=self)

        @discord.ui.button(label="🔢 Jump to Page", style=discord.ButtonStyle.secondary, row=2)
        async def jump_to_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            class PageJumpModal(discord.ui.Modal, title="Jump to Page"):
                page = discord.ui.TextInput(
                    label="Enter a page number:",
                    placeholder="e.g. 1, 2, 3...",
                    required=True,
                    max_length=4
                )

                async def on_submit(modal_self, modal_interaction: discord.Interaction):
                    try:
                        total_pages = max(1, math.ceil(len(state.filtered_files) / per_page))
                        page_num = int(str(modal_self.page).strip())
                        if 1 <= page_num <= total_pages:
                            state.current_page = page_num - 1
                            await modal_interaction.response.edit_message(embed=get_page_embed(), view=view)
                        else:
                            await modal_interaction.response.send_message(
                                f"⚠️ Page {page_num} isn’t in the starscape (1–{total_pages}).", ephemeral=True
                            )
                    except ValueError:
                        await modal_interaction.response.send_message("🚫 Invalid input — please enter a number.", ephemeral=True)

            await interaction.response.send_modal(PageJumpModal())

    view = PaginationView()
    view.message = await ctx.send(embed=get_page_embed(), view=view)

@bot.command(aliases=["everything", "alle", "expulso", "mruniverse"])
async def playalluploads(ctx):
    """Adds all uploaded songs to the queue in a cosmic shuffle."""
    guild_id = ctx.guild.id
    uploaded_files = uploaded_files_by_guild.get(guild_id, [])
    song_queue = song_queue_by_guild.setdefault(guild_id, [])

    if not uploaded_files:
        await ctx.send("🌘 No celestial notes found — upload a tune to begin.")
        return

    # Filter out any None or blank filenames
    valid_files = [f for f in uploaded_files if f and isinstance(f, str)]

    if not valid_files:
        await ctx.send("🪐 I tried, but found only echoes of silence. No usable uploads.")
        return

    random.shuffle(valid_files)

    for filename in valid_files:
        song_path = os.path.join(MUSIC_FOLDER, filename)
        song_queue.append(song_path)

    await ctx.send(f"🌌 {len(valid_files)} songs shimmered into your queue from the void.")

    if not ctx.voice_client or not ctx.voice_client.is_connected():
        await ctx.send("🔇 EchoMond is waiting beyond the stars... use `!join` to bring him into the flow.")
        return

    if not ctx.voice_client.is_playing():
        await play_next(ctx)

@bot.command(aliases=["number", "playnumber", "n", "galaxynote"])
async def playbynumber(ctx, *numbers):
    """Plays one or more uploaded songs using their numerical index."""
    guild_id = ctx.guild.id
    uploaded_files = uploaded_files_by_guild.get(guild_id, [])
    song_queue = song_queue_by_guild.setdefault(guild_id, [])
    added_songs = []

    if not numbers:
        await ctx.send("🌘 Whisper a number or two from the stars... (`!n 2 7`)")
        return

    for num in numbers:
        try:
            index = int(num.strip(","))
            if 1 <= index <= len(uploaded_files):
                filename = uploaded_files[index - 1]
                song_path = os.path.join(MUSIC_FOLDER, filename)
                song_queue.append(song_path)
                added_songs.append(filename)
            else:
                await ctx.send(f"☄️ `{index}` drifts beyond your orbit. Use `!listsongs` to align.")
        except ValueError:
            await ctx.send(f"❌ `{num}` isn’t a valid lunar mark. Try again with clear numerals.")

    if not added_songs:
        await ctx.send("🌑 The silence holds. No songs joined your queue.")
        return

    await ctx.send(f"🌌 Queued {len(added_songs)} cosmic notes.")

    if not ctx.voice_client or not ctx.voice_client.is_connected():
        await ctx.send("🔇 EchoMond awaits your call — use `!join` to guide him into harmony.")
        return

    if not ctx.voice_client.is_playing():
        await play_next(ctx)

@bot.command(aliases=["flag", "etikett"])
async def tag(ctx, *args):
    """Tags uploaded songs with custom labels. Usage: !tag <number(s)> <tags>"""
    guild_id = ctx.guild.id
    uploaded_files = uploaded_files_by_guild.get(guild_id, [])
    file_tags = file_tags_by_guild.setdefault(guild_id, {})

    if len(args) < 2:
        await ctx.send("🏷️ Usage: `!tag <numbers> <tags>` — e.g., `!tag 1 3 chill ambient` to mark your sonic stars.")
        return

    numbers = []
    tags = []

    for arg in args:
        if arg.isdigit():
            numbers.append(int(arg))
        else:
            tags.append(arg.lower())

    if not numbers or not tags:
        await ctx.send("☄️ Please provide at least one valid number and one tag.")
        return

    tagged = []
    for num in numbers:
        if 1 <= num <= len(uploaded_files):
            filename = uploaded_files[num - 1]
            file_tags.setdefault(filename, [])
            for tag in tags:
                if tag not in file_tags[filename]:
                    file_tags[filename].append(tag)
            tagged.append(filename)
        else:
            await ctx.send(f"🌘 Song number `{num}` drifts beyond this playlist... skipping.")

    if tagged:
        await ctx.send(f"🌠 Tagged: **{', '.join(tagged)}** with `{', '.join(tags)}`")
        save_upload_data()
    else:
        await ctx.send("🌫️ No songs were tagged — check your numbers and try again.")

@bot.command(aliases=["tagplay", "greenflag", "pt"])
async def playbytag(ctx, *search_tags):
    """Plays all uploaded songs that match one or more tags. Usage: !playbytag chill vibe"""
    guild_id = ctx.guild.id
    uploaded_files = uploaded_files_by_guild.setdefault(guild_id, [])
    file_tags = file_tags_by_guild.setdefault(guild_id, {})

    if not uploaded_files:
        await ctx.send("🌑 There are no songs in the archive yet... cast your first star.")
        return

    if not search_tags:
        await ctx.send("🌠 Whisper one or more tags. Example: `!playbytag ambient drift`")
        return

    tags_lower = {tag.lower() for tag in search_tags}

    matched = [
        filename for filename in uploaded_files
        if file_tags.get(filename) and any(tag in file_tags[filename] for tag in tags_lower)
    ]

    if not matched:
        await ctx.send(f"🌘 No songs aligned with `{', '.join(tags_lower)}` — the night remains still.")
        return

    for filename in matched:
        song_path = os.path.join(MUSIC_FOLDER, filename)
        song_queue_by_guild[guild_id].append(song_path)

    await ctx.send(f"🌌 Added **{len(matched)}** songs shimmering with `{', '.join(tags_lower)}`.")

    if not ctx.voice_client or not ctx.voice_client.is_connected():
        await ctx.send("🔇 EchoMond awaits connection — use `!join` to guide him into the stream.")
        return

    if not ctx.voice_client.is_playing():
        await play_next(ctx)

@bot.command(aliases=["whiteflag", "viewtags", "showtags"])
async def listtags(ctx):
    """Shows all tags currently in use for uploaded songs (per-server)."""
    guild_id = ctx.guild.id
    file_tags = file_tags_by_guild.setdefault(guild_id, {})

    unique_tags = {tag for tags in file_tags.values() for tag in tags}

    if not unique_tags:
        await ctx.send("🌫️ No tags exist yet — nothing is dancing in the air.")
        return

    sorted_tags = sorted(unique_tags)
    tag_text = ", ".join(sorted_tags)

    if len(tag_text) > 4000:
        last_comma = tag_text.rfind(",", 0, 4000)
        trimmed = tag_text[:last_comma] + "..."
        description = f"`{trimmed}`\n\n⚠️ Some tags are hidden due to space. Use filters to browse!"
    else:
        description = f"`{tag_text}`"

    embed = discord.Embed(
        title="🌼 Tags Blooming in the Archive",
        description=description,
        color=0xb9a1ff
    )
    embed.set_footer(text="Tag your uploads to help them shine brighter ✨")

    await ctx.send(embed=embed)

@bot.command(aliases=["untag", "deletetag", "cleartags"])
async def removetag(ctx, *args):
    """Removes all tags from specified songs, or removes a specific tag from all songs."""
    guild_id = ctx.guild.id
    file_tags = file_tags_by_guild.setdefault(guild_id, {})
    uploaded_files = uploaded_files_by_guild.setdefault(guild_id, [])

    if not args:
        embed = discord.Embed(
            title="🌙 Echo drifts in, but you forgot something...",
            description=(
                "Try one of these starlit options:\n\n"
                "➔ `!removetag <song number(s)>` to clear **all tags** from songs\n"
                "➔ `!removetag <tag>` to remove a tag from **all songs** that carry it"
            ),
            color=discord.Color(0xb9a1ff)
        )
        await ctx.send(embed=embed)
        return

    loading_message = await ctx.send("✨ Whispering to the stars... one moment... 🎶")
    await asyncio.sleep(1)
    did_change = False

    if args[0].isdigit():
        numbers, invalid = [], []
        for arg in args:
            if arg.isdigit():
                numbers.append(int(arg))
            else:
                invalid.append(arg)

        cleared = []
        for num in numbers:
            if 1 <= num <= len(uploaded_files):
                filename = uploaded_files[num - 1]
                if filename in file_tags and file_tags[filename]:
                    file_tags[filename] = []
                    cleared.append(filename)
                    did_change = True

        if cleared:
            shown = ", ".join(cleared[:10]) + (", ..." if len(cleared) > 10 else "")
            embed = discord.Embed(
                title="🌌 Tags Cleansed",
                description=f"Removed all tags from {len(cleared)} song(s):\n{shown}",
                color=discord.Color(0xb9a1ff)
            )
            embed.set_footer(text="✨ Float free, little tunes.")
        else:
            embed = discord.Embed(
                title="🫧 Nothing to Clear",
                description="None of the selected songs had any tags to begin with.",
                color=discord.Color(0xb9a1ff)
            )

        if invalid:
            embed.add_field(
                name="Ignored Inputs 🌠",
                value=f"Couldn’t recognize these as numbers: {', '.join(invalid)}",
                inline=False
            )

        await loading_message.edit(content=None, embed=embed)

    else:
        tag_to_remove = args[0].lower()
        removed_from = []

        for filename, tags in file_tags.items():
            tags_lowered = [t.lower() for t in tags]
            if tag_to_remove in tags_lowered:
                index = tags_lowered.index(tag_to_remove)
                tags.pop(index)
                removed_from.append(filename)
                did_change = True

        if removed_from:
            shown = ", ".join(removed_from[:10]) + (", ..." if len(removed_from) > 10 else "")
            embed = discord.Embed(
                title="🌠 Tag Lifted",
                description=f"`{tag_to_remove}` unpinned from {len(removed_from)} song(s):\n{shown}",
                color=discord.Color(0xb9a1ff)
            )
            embed.set_footer(text="✨ They shimmer a little differently now.")
        else:
            embed = discord.Embed(
                title="🌫 No Songs Matched",
                description=f"No songs carried the tag `{tag_to_remove}`. EchoMond heard only silence.",
                color=discord.Color(0xb9a1ff)
            )

        await loading_message.edit(content=None, embed=embed)

    if did_change:
        save_upload_data()

@bot.command(aliases=["shutup", "nomore", "stoppen"])
async def stop(ctx):
    """Stops playback and clears the queue."""
    guild_id = ctx.guild.id

    # Clear the queue first
    queue = song_queue_by_guild.get(guild_id, [])
    queue.clear()

    # Reset usage tracking or "now playing" state if you track those too
    last_now_playing_message_by_guild[guild_id] = None
    usage_counters[guild_id] = 0

    # Stop the current song if playing
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("🌑 Playback stilled — the stars fall quiet.")
    else:
        await ctx.send("🌌 Already silent… but your queue has been swept like cosmic dust.")

@bot.command(aliases=["delete", "removeupload", "du", "byebish"])
async def deleteupload(ctx, *numbers):
    """Deletes one or multiple uploaded songs by their numbers (from !listsongs)."""
    guild_id = ctx.guild.id
    uploaded_files = uploaded_files_by_guild.get(guild_id, [])
    file_tags = file_tags_by_guild.get(guild_id, {})
    song_queue = song_queue_by_guild.get(guild_id, [])

    if not numbers:
        await ctx.send("🌙 Whisper a number or two — I need to know which songs to let go.")
        return

    deleted = []
    invalid = []

    for num_str in numbers:
        try:
            num = int(num_str.strip(','))
            if 1 <= num <= len(uploaded_files):
                filename = uploaded_files[num - 1]
                file_path = os.path.join(MUSIC_FOLDER, filename)

                # Delete the file if it exists
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"[Warning] Could not delete {filename}: {e}")

                # Remove from queue if present
                song_queue[:] = [s for s in song_queue if not s.endswith(filename)]

                deleted.append(filename)
            else:
                invalid.append(num_str)
        except ValueError:
            invalid.append(num_str)

    # Remove metadata
    for filename in deleted:
        if filename in uploaded_files:
            uploaded_files.remove(filename)
        file_tags.pop(filename, None)

    # Save state
    uploaded_files_by_guild[guild_id] = uploaded_files
    file_tags_by_guild[guild_id] = file_tags
    song_queue_by_guild[guild_id] = song_queue
    save_upload_data()

    if deleted:
        await ctx.send(
            f"🗑️ Cast away: `{', '.join(deleted)}`\n✨ Their echoes fade into the stars."
        )
    if invalid:
        await ctx.send(
            f"⚠️ I couldn't read these celestial coordinates: `{', '.join(invalid)}`"
        )

@bot.command(aliases=["spankies", "cq"])
async def clearqueue(ctx):
    """Clears the music queue for this server only."""
    guild_id = ctx.guild.id
    song_queue_by_guild[guild_id] = []

    await ctx.send("🌌 The queue is now a blank sky — ready for new constellations.")

@bot.command(aliases=["exterminate", "cu"])
async def clearuploads(ctx):
    """Deletes all uploaded files for this server to free space, with confirmation."""
    guild_id = ctx.guild.id
    uploaded_files = uploaded_files_by_guild.get(guild_id, [])

    if not uploaded_files:
        await ctx.send("🌙 All is already still — no uploads to release.")
        return

    class ConfirmClearView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=15)

        @discord.ui.button(label="✅ Yes, release them", style=discord.ButtonStyle.danger)
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message(
                    "❌ Only the one who beckoned the moon may clear the sky.",
                    ephemeral=True
                )
                return

            file_count = 0
            for filename in uploaded_files_by_guild[guild_id]:
                file_path = os.path.join(MUSIC_FOLDER, filename)
                if os.path.exists(file_path) and filename.lower().endswith(('.mp3', '.wav')):
                    try:
                        os.remove(file_path)
                        file_count += 1
                    except Exception as e:
                        print(f"[Warning] Failed to delete {filename}: {e}")

            uploaded_files_by_guild[guild_id] = []
            file_tags_by_guild[guild_id] = {}
            save_upload_data()

            await interaction.response.edit_message(
                content=f"💫 Released {file_count} file{'s' if file_count != 1 else ''}. The echoes are now adrift.",
                view=None
            )

        @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id == ctx.author.id:
                await interaction.response.edit_message(
                    content="🌒 Cancelled — nothing was disturbed.",
                    view=None
                )
            else:
                await interaction.response.send_message(
                    "❌ Only the original starlighter can call it off.",
                    ephemeral=True
                )

    await ctx.send(
        "⚠️ Are you sure you wish to clear all uploaded songs? This starlit purge cannot be undone.",
        view=ConfirmClearView()
    )

# Run the bot
TOKEN = os.getenv("TOKEN")  # Reads token from environment variables
load_upload_data()
bot.run(TOKEN)