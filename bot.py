import os
import discord
import asyncio
import yt_dlp
import random
from discord.ext import commands
from discord import FFmpegPCMAudio
from discord import app_commands, Interaction
from discord.ui import View, Select

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

TOKEN = os.getenv("TOKEN")

@bot.event
async def on_ready():
    print(f"🌙 EchoMond has awakened as {bot.user}.")

# ========== GLOBALS ==========

music_queues = {}
last_played = {}

def get_guild_queue(guild_id):
    return music_queues.setdefault(guild_id, [])

def set_last_played(guild_id, url):
    last_played[guild_id] = url

def get_last_played(guild_id):
    return last_played.get(guild_id)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        ytcookies_path = "cookies.txt"

        # Save Railway's cookie string to a temp file for yt_dlp to use
        with open(ytcookies_path, "w", encoding="utf-8") as f:
            f.write(os.getenv("YTDLP_COOKIES", ""))

        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'noplaylist': True,
            'cookiefile': ytcookies_path,
            'default_search': 'ytsearch',
            'source_address': '0.0.0.0',
        }

        if stream:
            ydl_opts['noplaylist'] = True

        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else yt_dlp.YoutubeDL(ydl_opts).prepare_filename(data)
        return cls(FFmpegPCMAudio(filename), data=data)

MUSIC_FOLDER = "downloads/"
os.makedirs(MUSIC_FOLDER, exist_ok=True)

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
    await bot.process_commands(message)  # always process commands!

    # Ignore other bots and DMs
    if message.author.bot or not message.guild:
        return

    guild_id = message.guild.id
    user_id = message.author.id

    FLAVOR = {
        "upload_message": "🌙 EchoMond received your starlit sound.",
        "tag_prompt": "💫 Add your constellations — tags like `lunar`, `ambient`, `echo`.",
        "tag_none_found": "🚫 No tags drifted in the ether — try again, softly.",
        "tag_success_reply": "✨ Cosmic tags have been etched in the soundwaves."
    }

    # 🌒 Handle uploads
    if message.attachments:
        new_files = []
        for attachment in message.attachments:
            if attachment.filename.endswith(('.mp3', '.wav')):
                file_path = os.path.join(MUSIC_FOLDER, attachment.filename)

                # 🚫 Check for duplicate filename
                if attachment.filename in uploaded_files_by_guild[guild_id]:
                    await message.channel.send(f"⚠️ `{attachment.filename}` already echoes in the vault.")
                    continue

                try:
                    await attachment.save(file_path)
                    uploaded_files_by_guild[guild_id].append(attachment.filename)
                    new_files.append(attachment.filename)
                except Exception as e:
                    await message.channel.send(f"🚨 Error saving `{attachment.filename}`: {e}")
                    continue

        if new_files:
            pending_tag_uploads[guild_id][user_id] = new_files
            await message.channel.send(
                f"{FLAVOR['upload_message']}\n"
                f"🎵 Uploaded: **{', '.join(new_files)}**\n"
                f"💫 {FLAVOR['tag_prompt']}"
            )
            save_upload_data()
        return

    # 🌙 Handle tag replies
    if message.reference and user_id in pending_tag_uploads[guild_id]:
        try:
            replied_message = await message.channel.fetch_message(message.reference.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

        if replied_message.author.id != bot.user.id or not replied_message.content.startswith(FLAVOR['upload_message']):
            return

        # Parse tags from message
        tags = [t.strip().lower() for t in message.content.replace(",", " ").split() if t.strip()]
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

# ========== UTILITY ==========

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
                    "📜 **!queue** – View what echoes next. Alias: q\n"
                    "🧺 **!clearqueue** – Clear the current journey. Alias: cq"
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

@bot.command()
async def join(ctx):
    """Invite EchoMond into your current voice channel."""
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send("🔗 EchoMond has entered the stream of stars... 🌌")
    else:
        await ctx.send("🚫 You must be in a voice channel for EchoMond to arrive.")

@bot.command()
async def leave(ctx):
    """Let EchoMond slip quietly from the voice channel."""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("🚪 EchoMond fades into silence, waiting for the next call... 💫")
    else:
        await ctx.send("🌙 EchoMond is already adrift beyond the soundwaves.")

# ========== PLAYBACK ==========

@bot.command(aliases=["p"])
async def play(ctx, *, url):
    """🎶 Add a melody to the cosmic queue."""
    queue = get_guild_queue(ctx.guild.id)

    # Connect if needed
    if ctx.voice_client is None:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("🚫 You must be in a voice channel to summon EchoMond.")
            return

    # Extract metadata before adding to queue
    try:
        ytcookies_path = "cookies.txt"
        with open(ytcookies_path, "w", encoding="utf-8") as f:
            f.write(os.getenv("YTDLP_COOKIES", ""))

        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'noplaylist': True,
            'cookiefile': ytcookies_path,
            'default_search': 'ytsearch',
            'source_address': '0.0.0.0',
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                info = info['entries'][0]

            title = info.get("title", "Unknown Song")
            stream_url = info["url"]
    except Exception as e:
        await ctx.send(f"⚠️ Trouble pulling cosmic data: {e}")
        return

    # Add to queue
    queue.append((title, url))
    await ctx.send(f"✨ Added to the constellation: **{title}**")

    # Start playback if idle
    if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
        await play_next_in_queue(ctx)

@bot.command(name="pause", aliases=["hush"])
async def pause_command(ctx):
    """⏸️ Let the sound breathe..."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("🌙 EchoMond grows quiet for a moment...")
    else:
        await ctx.send("🫧 There is no melody to still.")

@bot.command(name="resume", aliases=["youmayspeak"])
async def resume_command(ctx):
    """▶️ Resume EchoMond's whisper."""
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("💫 EchoMond lifts his voice once more...")
    else:
        await ctx.send("🔇 Nothing paused—silence still reigns.")

@bot.command(aliases=["next", "skippy", "nothanks"])
async def skip(ctx):
    """⏭️ Gently pass to the next."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()  # triggers `after`, so queue moves
        await ctx.send("🌠 Skipping forward...")
    else:
        await ctx.send("🚫 EchoMond is not playing anything.")

@bot.command(aliases=["back", "repeat", "again"])
async def rewind(ctx):
    """⏪ Replay the last cosmic note."""
    last = get_last_played(ctx.guild.id)
    if last:
        await ctx.invoke(bot.get_command("play"), url=last)
    else:
        await ctx.send("🔄 EchoMond has no memory of the previous song...")

@bot.command(aliases=["end", "shutup"])
async def stop(ctx):
    """⏹️ Silence the stars, clear the queue."""
    if ctx.voice_client:
        ctx.voice_client.stop()  # Halts current track
        get_guild_queue(ctx.guild.id).clear()  # Nukes the queue
        set_last_played(ctx.guild.id, None)  # Wipe last played too
        await ctx.send("🌌 EchoMond bows. The melody ceases. The constellation scatters. All is quiet now.")
    else:
        await ctx.send("🌑 EchoMond is already at rest — the sky is empty.")

@bot.command(aliases=["v"])
async def volume(ctx, level: int):
    """🔊 Adjust the magnitude of the wave."""
    if ctx.voice_client and ctx.voice_client.source:
        if 0 <= level <= 200:
            ctx.voice_client.source.volume = level / 100

            if level == 100:
                msg = "🎼 Balanced in starlight. EchoMond flows at perfect harmony."
            elif level < 50:
                msg = f"🌙 A soft shimmer... volume set to `{level}%`."
            elif level < 100:
                msg = f"💫 EchoMond hums gently at `{level}%` power."
            elif level <= 130:
                msg = f"⚡ EchoMond pulses brighter... volume at `{level}%`."
            elif level <= 160:
                msg = f"🌪️ Reality begins to wobble. `{level}%`... are you *sure?*"
            elif level <= 190:
                msg = f"🌀 Sound tears space. EchoMond howls across the aether... `{level}%`"
            else:
                msg = f"☄️ **THE MUSIC TRANSCENDS FORM. ECHOMOND IS THE WAVE.** `{level}%`"

            await ctx.send(msg)
        else:
            await ctx.send("🚫 Volume must shimmer between `0` and `200`, traveler.")
    else:
        await ctx.send("🫧 There is no melody to mold.")

@bot.command(aliases=["mixit", "shuff"])
async def shuffle(ctx):
    """🔀 Scatter the songs like stardust."""
    queue = get_guild_queue(ctx.guild.id)
    if len(queue) > 1:
        random.shuffle(queue)
        await ctx.send("💫 EchoMond swirls the constellation... the queue is now scattered!")
    elif queue:
        await ctx.send("🌠 Only one song in the queue... EchoMond simply hums.")
    else:
        await ctx.send("🫧 Nothing to shuffle in the void.")

@bot.command(aliases=["cq"])
async def clearqueue(ctx):
    """🧺 Empty the cosmic queue."""
    queue = get_guild_queue(ctx.guild.id)
    if queue:
        queue.clear()
        await ctx.send("🧹 EchoMond clears the constellation. The path is open.")
    else:
        await ctx.send("🫧 The queue is already silent.")

# ========== UPLOADS ==========

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
        embed.set_footer(text="✨ Let your playlist bloom. Use the buttons or !playbynumber to select.")
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
            queue = get_guild_queue(guild_id)
            start = state.current_page * per_page
            end = start + per_page
            for filename in state.filtered_files[start:end]:
                song_path = os.path.join(MUSIC_FOLDER, filename)
                queue.append((filename, song_path))  # title + local path

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
                await play_next_in_queue(ctx)

        @discord.ui.button(label="🔀 Shuffle Page", style=discord.ButtonStyle.primary, row=1)
        async def shuffle_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            queue = get_guild_queue(guild_id)
            start = state.current_page * per_page
            end = start + per_page
            page = state.filtered_files[start:end]
            random.shuffle(page)

            for filename in page:
                song_path = os.path.join(MUSIC_FOLDER, filename)
                queue.append((filename, song_path))

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
                await play_next_in_queue(ctx)

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

@bot.command(aliases=["n"])
async def playbynumber(ctx, *numbers: int):
    """🔢 Queue one or more uploaded songs by number."""
    guild_id = ctx.guild.id
    uploaded_files = uploaded_files_by_guild.get(guild_id, [])

    if not uploaded_files:
        await ctx.send("☁️ No songs rest in the vault.")
        return

    if not numbers:
        await ctx.send("⚠️ Please provide at least one song number.")
        return

    queue = get_guild_queue(guild_id)
    added = []

    for num in numbers:
        if 1 <= num <= len(uploaded_files):
            filename = uploaded_files[num - 1]
            file_path = os.path.join(MUSIC_FOLDER, filename)
            queue.append((filename, file_path))
            added.append(f"{num}. {filename}")
        else:
            await ctx.send(f"❌ `{num}` isn’t in range (1–{len(uploaded_files)}).")

    if added:
        await ctx.send(f"🎶 Added to queue:\n" + "\n".join(added))

        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("🔇 EchoMond drifts... join a voice channel to call him down.")
                return

        if not ctx.voice_client.is_playing():
            await play_next_in_queue(ctx)

@bot.command(aliases=["everything", "alle"])
async def playalluploads(ctx):
    """🌠 Let all uploaded songs shimmer in shuffled sequence."""
    guild_id = ctx.guild.id
    uploaded_files = uploaded_files_by_guild.get(guild_id, [])

    if not uploaded_files:
        await ctx.send("☁️ No songs rest in the vault yet — upload one to begin.")
        return

    queue = get_guild_queue(guild_id)

    # Shuffle a copy to preserve original upload order
    shuffled = uploaded_files[:]
    random.shuffle(shuffled)

    for filename in shuffled:
        file_path = os.path.join(MUSIC_FOLDER, filename)
        queue.append((filename, file_path))

    await ctx.send(f"🌌 All {len(shuffled)} uploaded echoes have been scattered into the cosmos...")

    # Auto-join if not already connected
    if ctx.voice_client is None:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("🔇 EchoMond floats unanchored... join a voice channel to ground him.")
            return

    # Start playback if idle
    if not ctx.voice_client.is_playing():
        await play_next_in_queue(ctx)

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
            super().__init__(timeout=20)

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
                if os.path.isfile(file_path):
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

@bot.command(aliases=["du"])
async def deleteupload(ctx, *numbers: int):
    """❌ Delete one or more uploaded songs by number."""
    guild_id = ctx.guild.id
    uploaded_files = uploaded_files_by_guild.get(guild_id, [])

    if not uploaded_files:
        await ctx.send("☁️ No echoes exist to erase.")
        return

    if not numbers:
        await ctx.send("⚠️ Please give the number(s) of the song(s) to release.")
        return

    deleted = []
    not_found = []

    for num in numbers:
        if 1 <= num <= len(uploaded_files):
            filename = uploaded_files[num - 1]
            file_path = os.path.join(MUSIC_FOLDER, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                deleted.append(filename)
            except Exception as e:
                await ctx.send(f"⚠️ Trouble unbinding `{filename}`: {e}")
        else:
            not_found.append(str(num))

    # Remove from records after loop to avoid indexing issues
    for filename in deleted:
        uploaded_files.remove(filename)
        file_tags_by_guild[guild_id].pop(filename, None)

    save_upload_data()

    msg = ""
    if deleted:
        msg += f"🗑️ Released: `{', '.join(deleted)}`\n"
    if not_found:
        msg += f"❓ Not found in the starscape: `{', '.join(not_found)}`"

    await ctx.send(msg or "🌌 Nothing was touched.")

# ========== TAGGING SYSTEM ==========

@bot.command(aliases=["flag", "etikett"])
async def tag(ctx, *args):
    """🏷️ Tag uploaded songs with labels. Usage: !tag <number(s)> <tags>"""
    guild_id = ctx.guild.id
    uploaded_files = uploaded_files_by_guild.get(guild_id, [])
    file_tags = file_tags_by_guild.setdefault(guild_id, {})

    if len(args) < 2:
        await ctx.send("🏷️ Usage: `!tag <numbers> <tags>` — e.g., `!tag 1 3 chill ambient`")
        return

    numbers, tags = [], []

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
            await ctx.send(f"🌘 Song number `{num}` is outside the vault. Skipping.")

    if tagged:
        await ctx.send(f"🌠 Tagged: **{', '.join(tagged)}** with `{', '.join(tags)}`")
        save_upload_data()
    else:
        await ctx.send("🌫️ No songs were tagged — double-check your numbers and tags.")

@bot.command(aliases=["tagplay", "greenflag", "pt"])
async def playbytag(ctx, *search_tags):
    """🎶 Play all uploaded songs matching one or more tags. Usage: !playbytag chill vibe"""
    guild_id = ctx.guild.id
    uploaded_files = uploaded_files_by_guild.setdefault(guild_id, [])
    file_tags = file_tags_by_guild.setdefault(guild_id, {})
    queue = get_guild_queue(guild_id)

    if not uploaded_files:
        await ctx.send("🌑 The archive is silent — upload something first.")
        return

    if not search_tags:
        await ctx.send("🌠 Whisper one or more tags. Example: `!playbytag ambient drift`")
        return

    tags_lower = {tag.lower() for tag in search_tags}

    matched = [
        filename for filename in uploaded_files
        if any(tag in (file_tags.get(filename) or []) for tag in tags_lower)
    ]

    if not matched:
        await ctx.send(f"🌘 No songs matched `{', '.join(tags_lower)}` — the sky remains quiet.")
        return

    for filename in matched:
        path = os.path.join(MUSIC_FOLDER, filename)
        queue.append((filename, path))

    await ctx.send(f"🌌 Queued **{len(matched)}** tagged echoes: `{', '.join(tags_lower)}`")

    if ctx.voice_client is None:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("🔇 EchoMond drifts in silence. Join a voice channel to summon him.")
            return

    if not ctx.voice_client.is_playing():
        await play_next_in_queue(ctx)

@bot.command(aliases=["untag", "deletetag", "cleartags"])
async def removetag(ctx, *args):
    """Removes all tags from specified songs by number, or a specific tag from all songs."""
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

    # Option 1: clear tags from songs by number
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
            shown = ", ".join(cleared[:10]) + ("..." if len(cleared) > 10 else "")
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

    # Option 2: remove a specific tag from all songs
    else:
        tag_to_remove = args[0].lower()
        removed_from = []

        for filename, tags in file_tags.items():
            if tag_to_remove in tags:
                file_tags[filename] = [t for t in tags if t != tag_to_remove]
                removed_from.append(filename)
                did_change = True

        if removed_from:
            shown = ", ".join(removed_from[:10]) + ("..." if len(removed_from) > 10 else "")
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

@bot.command(aliases=["whiteflag", "viewtags", "showtags"])
async def listtags(ctx):
    """🌼 Shows all tags currently in use for uploaded songs (per server)."""
    guild_id = ctx.guild.id
    file_tags = file_tags_by_guild.setdefault(guild_id, {})

    # Collect all unique tags
    unique_tags = {tag for tags in file_tags.values() for tag in tags}

    if not unique_tags:
        await ctx.send("🌫️ No tags exist yet — nothing is dancing in the air.")
        return

    sorted_tags = sorted(unique_tags)
    tag_text = ", ".join(sorted_tags)

    # Limit description length to avoid exceeding embed max
    if len(tag_text) > 4000:
        last_comma = tag_text.rfind(",", 0, 4000)
        trimmed = tag_text[:last_comma] + "..."
        description = f"`{trimmed}`\n\n⚠️ Some tags are hidden due to space. Use filters to browse!"
    else:
        description = f"`{tag_text}`"

    embed = discord.Embed(
        title="🌼 Tags Blooming in the Archive",
        description=description,
        color=discord.Color(0xb9a1ff)
    )
    embed.set_footer(text="✨ Tag your uploads to help them shine brighter.")

    await ctx.send(embed=embed)

TOKEN = os.getenv("TOKEN")
load_upload_data()
bot.run(TOKEN)