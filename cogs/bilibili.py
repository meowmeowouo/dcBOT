import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import re
import os
import aiohttp
import asyncio

TEMP_DIR = "temp_bili"
os.makedirs(TEMP_DIR, exist_ok=True)

class BilibiliCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cookies_file = "cookies.txt" if os.path.exists("cookies.txt") else None
        self.queues = {}
        self.titles = {}
        self.is_playing = {}

    # ------------------- URL 處理 -------------------
    async def resolve_b23_url(self, url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, allow_redirects=True) as resp:
                return str(resp.url)

    async def extract_full_url(self, url: str) -> str | None:
        if "b23.tv" in url:
            url = await self.resolve_b23_url(url)

        match_bv = re.search(r"(BV[a-zA-Z0-9]+)", url)
        if match_bv:
            return f"https://www.bilibili.com/video/{match_bv.group(1)}"

        match_av = re.search(r"(?:av)(\d+)", url, re.IGNORECASE)
        if match_av:
            return f"https://www.bilibili.com/video/av{match_av.group(1)}"

        return None

    # ------------------- yt-dlp 下載 -------------------
    def get_ydl_options(self, filename: str):
        opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'outtmpl': filename,
            'noplaylist': True,
        }
        if self.cookies_file:
            opts['cookiefile'] = self.cookies_file
        return opts

    async def download_audio(self, url: str) -> str:
        filename = os.path.join(TEMP_DIR, "%(id)s.%(ext)s")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(self.get_ydl_options(filename)).download([url]))
        for file in os.listdir(TEMP_DIR):
            if file.endswith((".webm", ".m4a", ".mp3")):
                return os.path.join(TEMP_DIR, file)
        raise FileNotFoundError("下載失敗")

    # ------------------- 播放邏輯 -------------------
    async def play_next(self, guild_id: int, channel: discord.VoiceChannel):
        if guild_id not in self.queues or not self.queues[guild_id]:
            self.is_playing[guild_id] = False
            return

        url = self.queues[guild_id].pop(0)
        title = self.titles[guild_id].pop(0)
        file_path = await self.download_audio(url)

        vc = channel.guild.voice_client
        if not vc:
            vc = await channel.connect()

        def after_play(error):
            try:
                os.remove(file_path)
            except:
                pass
            asyncio.run_coroutine_threadsafe(self.play_next(guild_id, channel), self.bot.loop)

        vc.stop()
        vc.play(discord.FFmpegPCMAudio(file_path, options='-vn'), after=after_play)

        text_channel = channel.guild.text_channels[0] if channel.guild.text_channels else None
        if text_channel:
            asyncio.run_coroutine_threadsafe(
                text_channel.send(f"🎶 正在播放 **{title}** (Bilibili)"),
                self.bot.loop
            )

    async def clear_temp(self):
        for file in os.listdir(TEMP_DIR):
            try:
                os.remove(os.path.join(TEMP_DIR, file))
            except:
                pass

    async def add_to_queue(self, ctx_or_interaction, urls: list[str]):
        guild_id = ctx_or_interaction.guild.id
        if guild_id not in self.queues:
            self.queues[guild_id] = []
            self.titles[guild_id] = []

        # 判斷使用者語音頻道
        if isinstance(ctx_or_interaction, commands.Context):
            voice_state = ctx_or_interaction.author.voice
        else:
            voice_state = ctx_or_interaction.user.voice

        if not voice_state:
            msg = "❌ 你需要先進入語音頻道"
            if isinstance(ctx_or_interaction, commands.Context):
                return await ctx_or_interaction.send(msg)
            else:
                return await ctx_or_interaction.response.send_message(msg)

        full_urls = []
        titles = []
        for url in urls:
            full_url = await self.extract_full_url(url)
            if full_url:
                full_urls.append(full_url)
                with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                    info = ydl.extract_info(full_url, download=False)
                    titles.append(info.get('title', '未知標題'))

        self.queues[guild_id].extend(full_urls)
        self.titles[guild_id].extend(titles)

        if not self.is_playing.get(guild_id, False):
            self.is_playing[guild_id] = True
            await self.play_next(guild_id, voice_state.channel)

        msg = f"✅ 已將 {len(full_urls)} 首加入播放佇列"
        if isinstance(ctx_or_interaction, commands.Context):
            await ctx_or_interaction.send(msg)
        else:
            await ctx_or_interaction.response.send_message(msg)

    # ------------------- Prefix 指令 -------------------
    @commands.command(name="bplay")
    async def bplay_prefix(self, ctx, url: str):
        await self.add_to_queue(ctx, [url])

    @commands.command(name="bqueue")
    async def bqueue_prefix(self, ctx, *urls):
        await self.add_to_queue(ctx, list(urls))

    @commands.command(name="bskip")
    async def bskip_prefix(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await ctx.send("⏭ 已跳過當前音樂")
        else:
            await ctx.send("❌ 沒有正在播放的音樂")

    @commands.command(name="bplaylist")
    async def bplaylist_prefix(self, ctx):
        guild_id = ctx.guild.id
        if guild_id not in self.queues or not self.queues[guild_id]:
            return await ctx.send("❌ 目前播放清單為空")
        msg = "**🎵 目前播放清單：**\n"
        for i, title in enumerate(self.titles[guild_id], 1):
            msg += f"{i}. {title}\n"
        await ctx.send(msg)

    @commands.command(name="bpause")
    async def bpause_prefix(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.send("⏸ 已暫停播放")
        else:
            await ctx.send("❌ 沒有正在播放的音樂")

    @commands.command(name="bresume")
    async def bresume_prefix(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.send("▶️ 已繼續播放")
        else:
            await ctx.send("❌ 沒有暫停的音樂")

    @commands.command(name="bstop")
    async def bstop_prefix(self, ctx):
        vc = ctx.guild.voice_client
        if vc:
            vc.stop()
            await vc.disconnect()
            await self.clear_temp()
            self.queues[ctx.guild.id] = []
            self.titles[ctx.guild.id] = []
            self.is_playing[ctx.guild.id] = False
            await ctx.send("⏹ 已停止播放並清理暫存")
        else:
            await ctx.send("❌ 沒有正在播放的音樂")

    # ------------------- Slash 指令 -------------------
    @app_commands.command(name="bplay", description="立即播放單首 Bilibili 音樂並加入佇列")
    async def bplay_slash(self, interaction: discord.Interaction, url: str):
        await self.add_to_queue(interaction, [url])

    @app_commands.command(name="bqueue", description="加入多首 Bilibili 音樂到佇列")
    async def bqueue_slash(self, interaction: discord.Interaction, urls: str):
        url_list = urls.split()
        await self.add_to_queue(interaction, url_list)

    @app_commands.command(name="bskip", description="跳過當前播放音樂")
    async def bskip_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭ 已跳過當前音樂")
        else:
            await interaction.response.send_message("❌ 沒有正在播放的音樂")

    @app_commands.command(name="bplaylist", description="顯示目前播放清單")
    async def bplaylist_slash(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        if guild_id not in self.queues or not self.queues[guild_id]:
            return await interaction.response.send_message("❌ 目前播放清單為空")
        msg = "**🎵 目前播放清單：**\n"
        for i, title in enumerate(self.titles[guild_id], 1):
            msg += f"{i}. {title}\n"
        await interaction.response.send_message(msg)

    @app_commands.command(name="bpause", description="暫停播放音樂")
    async def bpause_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸ 已暫停播放")
        else:
            await interaction.response.send_message("❌ 沒有正在播放的音樂")

    @app_commands.command(name="bresume", description="繼續播放音樂")
    async def bresume_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ 已繼續播放")
        else:
            await interaction.response.send_message("❌ 沒有暫停的音樂")

    @app_commands.command(name="bstop", description="停止播放並清理暫存")
    async def bstop_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            vc.stop()
            await vc.disconnect()
            await self.clear_temp()
            self.queues[interaction.guild.id] = []
            self.titles[interaction.guild.id] = []
            self.is_playing[interaction.guild.id] = False
            await interaction.response.send_message("⏹ 已停止播放並清理暫存")
        else:
            await interaction.response.send_message("❌ 沒有正在播放的音樂")


# ------------------- setup -------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(BilibiliCog(bot))
