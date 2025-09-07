import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def join_channel(self, ctx_or_interaction):
        # 支援 Context 或 Interaction
        if isinstance(ctx_or_interaction, commands.Context):
            user = ctx_or_interaction.author
            guild = ctx_or_interaction.guild
        else:
            user = ctx_or_interaction.user
            guild = ctx_or_interaction.guild

        if not user.voice or not user.voice.channel:
            msg = "❌ 你不在語音頻道！"
            if isinstance(ctx_or_interaction, commands.Context):
                await ctx_or_interaction.send(msg)
            else:
                await ctx_or_interaction.response.send_message(msg, ephemeral=True)
            return None

        voice_channel = user.voice.channel
        voice_client = guild.voice_client
        if not voice_client:
            voice_client = await voice_channel.connect()
        elif voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)

        return voice_client

    async def play_next(self, ctx_or_interaction):
        queue = self.bot.queues.get(ctx_or_interaction.guild.id)
        voice_client = ctx_or_interaction.guild.voice_client

        if not queue or queue.empty():
            # 自動推薦功能
            if self.bot.auto_play_enabled.get(ctx_or_interaction.guild.id, True):
                last_url = self.bot.last_played_urls.get(ctx_or_interaction.guild.id)
                if last_url:
                    recommended_url, recommended_title = await self.get_recommended(last_url)
                    if recommended_url:
                        await queue.put((recommended_url, recommended_title))
                        send_func = ctx_or_interaction.followup.send if isinstance(ctx_or_interaction, discord.Interaction) else ctx_or_interaction.send
                        await send_func(f"🤖 自動推薦：{recommended_title}")
                        # 繼續播放推薦歌
                        await self.play_next(ctx_or_interaction)
                        return
            send_func = ctx_or_interaction.followup.send if isinstance(ctx_or_interaction, discord.Interaction) else ctx_or_interaction.send
            await send_func("🛑 播放完畢，暫無更多歌曲。")
            return

        url, title = await queue.get()
        self.bot.last_played_urls[ctx_or_interaction.guild.id] = url
        source = discord.FFmpegPCMAudio(url, before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5")

        def after_play(error):
            fut = asyncio.run_coroutine_threadsafe(self.play_next(ctx_or_interaction), self.bot.loop)
            try:
                fut.result()
            except Exception as e:
                print(f"播放下一首出錯: {e}")

        voice_client.play(source, after=after_play)

        send_func = ctx_or_interaction.followup.send if isinstance(ctx_or_interaction, discord.Interaction) else ctx_or_interaction.send
        await send_func(f"▶️ 現在播放：{title}")

    async def get_recommended(self, webpage_url):
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'force_generic_extractor': False,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(webpage_url, download=False)
                related = info.get('related_videos', [])
                for video in related:
                    if 'id' in video:
                        video_id = video['id']
                        title = video.get('title', '推薦影片')
                        return f"https://www.youtube.com/watch?v={video_id}", title
        except Exception as e:
            print("推薦失敗：", e)
        return None, None

    async def play_music(self, source_url, title, guild_id, ctx_or_interaction):
        queue = self.bot.queues.setdefault(guild_id, asyncio.Queue())
        await queue.put((source_url, title))

        voice_client = ctx_or_interaction.guild.voice_client
        if voice_client and not voice_client.is_playing() and not voice_client.is_paused():
            await self.play_next(ctx_or_interaction)

        send_func = ctx_or_interaction.followup.send if isinstance(ctx_or_interaction, discord.Interaction) else ctx_or_interaction.send
        await send_func(f"🎵 已加入佇列：{title}")

    # -------- Slash 指令 --------
    @app_commands.command(name="play", description="播放歌曲或加入佇列")
    @app_commands.describe(search="關鍵字或YouTube連結")
    async def slash_play(self, interaction: discord.Interaction, search: str):
        await interaction.response.defer()
        voice_client = await self.join_channel(interaction)
        if not voice_client:
            return

        ydl_opts = {'format': 'bestaudio', 'noplaylist': True, 'quiet': True, 'default_search': 'ytsearch'}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search, download=False)
            if 'entries' in info:
                info = info['entries'][0]
            url = info['url']
            title = info['title']
            webpage_url = info.get('webpage_url')
            self.bot.last_played_urls[interaction.guild.id] = webpage_url

        await self.play_music(url, title, interaction.guild.id, interaction)

    @app_commands.command(name="pause", description="暫停播放")
    async def slash_pause(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.followup.send("⏸ 已暫停播放")
        else:
            await interaction.followup.send("❌ 目前沒有正在播放的音樂")

    @app_commands.command(name="resume", description="恢復播放")
    async def slash_resume(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.followup.send("▶️ 已恢復播放")
        else:
            await interaction.followup.send("❌ 目前沒有暫停的音樂")

    @app_commands.command(name="skip", description="跳過目前播放的歌曲")
    async def slash_skip(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.followup.send("⏭ 已跳過")
        else:
            await interaction.followup.send("❌ 目前沒有正在播放的音樂")

    @app_commands.command(name="stop", description="停止播放並清空佇列")
    async def slash_stop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if vc:
            vc.stop()
        self.bot.queues[interaction.guild.id] = asyncio.Queue()
        await interaction.followup.send("⏹ 已停止播放並清空佇列")

    @app_commands.command(name="queue", description="顯示目前播放佇列")
    async def slash_queue(self, interaction: discord.Interaction):
        queue = self.bot.queues.get(interaction.guild.id)
        if not queue or queue.empty():
            await interaction.response.send_message("📭 播放佇列是空的", ephemeral=True)
            return
        items = list(queue._queue)
        message = "\n".join([f"{i+1}. {title}" for i, (_, title) in enumerate(items)])
        await interaction.response.send_message(f"🎶 當前佇列：\n{message}", ephemeral=True)

    @app_commands.command(name="leave", description="離開語音頻道")
    async def slash_leave(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            await vc.disconnect()
            await interaction.response.send_message("👋 已離開語音頻道")
        else:
            await interaction.response.send_message("❌ 我不在語音頻道")

    @app_commands.command(name="auto", description="切換自動推薦播放開關")
    async def slash_auto(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        current = self.bot.auto_play_enabled.get(guild_id, True)
        self.bot.auto_play_enabled[guild_id] = not current
        status = "✅ 開啟" if not current else "❌ 關閉"
        await interaction.response.send_message(f"🔁 自動推薦功能已{status}")

    @app_commands.command(name="status", description="顯示自動推薦播放狀態")
    async def slash_status(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        current = self.bot.auto_play_enabled.get(guild_id, True)
        status = "✅ 已開啟" if current else "❌ 已關閉"
        await interaction.response.send_message(f"🔁 自動推薦播放狀態：{status}")

    # -------- 傳統 prefix 指令 --------

    @commands.command(name="pause")
    async def prefix_pause(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.send("⏸ 已暫停播放")
        else:
            await ctx.send("❌ 目前沒有正在播放的音樂")

    @commands.command(name="resume")
    async def prefix_resume(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.send("▶️ 已恢復播放")
        else:
            await ctx.send("❌ 目前沒有暫停的音樂")

    @commands.command(name="skip")
    async def prefix_skip(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await ctx.send("⏭ 已跳過")
        else:
            await ctx.send("❌ 目前沒有正在播放的音樂")

    @commands.command(name="stop")
    async def prefix_stop(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc:
            vc.stop()
        self.bot.queues[ctx.guild.id] = asyncio.Queue()
        await ctx.send("⏹ 已停止播放並清空佇列")

    @commands.command(name="queue")
    async def prefix_queue(self, ctx: commands.Context):
        queue = self.bot.queues.get(ctx.guild.id)
        if not queue or queue.empty():
            await ctx.send("📭 播放佇列是空的")
            return
        items = list(queue._queue)
        message = "\n".join([f"{i+1}. {title}" for i, (_, title) in enumerate(items)])
        await ctx.send(f"🎶 當前佇列：\n{message}")

    @commands.command(name="leave")
    async def prefix_leave(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc:
            await vc.disconnect()
            await ctx.send("👋 已離開語音頻道")
        else:
            await ctx.send("❌ 我不在語音頻道")

    @commands.command(name="auto")
    async def prefix_auto(self, ctx: commands.Context):
        guild_id = ctx.guild.id
        current = self.bot.auto_play_enabled.get(guild_id, True)
        self.bot.auto_play_enabled[guild_id] = not current
        status = "✅ 開啟" if not current else "❌ 關閉"
        await ctx.send(f"🔁 自動推薦功能已{status}")

    @commands.command(name="status")
    async def prefix_status(self, ctx: commands.Context):
        guild_id = ctx.guild.id
        current = self.bot.auto_play_enabled.get(guild_id, True)
        status = "✅ 已開啟" if current else "❌ 已關閉"
        await ctx.send(f"🔁 自動推薦播放狀態：{status}")

async def setup(bot):
    await bot.add_cog(MusicCog(bot))
