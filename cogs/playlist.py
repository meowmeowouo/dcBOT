import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
import os
import json
import random

PLAYLISTS_DIR = "playlists"
os.makedirs(PLAYLISTS_DIR, exist_ok=True)

def get_user_file(user_id):
    return os.path.join(PLAYLISTS_DIR, f"{user_id}.json")

def load_playlists(user_id):
    path = get_user_file(user_id)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_playlists(user_id, playlists):
    path = get_user_file(user_id)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(playlists, f, indent=2, ensure_ascii=False)

class PlaylistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # { guild_id: list of URLs }
        if not hasattr(bot, 'queues'):
            bot.queues = {}
        if not hasattr(bot, 'leave_tasks'):
            bot.leave_tasks = {}

    async def send(self, ctx_or_interaction, content, ephemeral=False):
        if isinstance(ctx_or_interaction, commands.Context):
            await ctx_or_interaction.send(content)
        elif isinstance(ctx_or_interaction, discord.Interaction):
            await ctx_or_interaction.response.send_message(content, ephemeral=ephemeral)

    async def join_voice(self, ctx_or_interaction):
        guild = ctx_or_interaction.guild
        voice_client = guild.voice_client

        user = ctx_or_interaction.author if isinstance(ctx_or_interaction, commands.Context) else ctx_or_interaction.user
        if not user.voice or not user.voice.channel:
            await self.send(ctx_or_interaction, "⚠️ 你必須先加入語音頻道。", ephemeral=True)
            return None

        channel = user.voice.channel

        if voice_client and voice_client.is_connected():
            if voice_client.channel.id != channel.id:
                try:
                    await voice_client.move_to(channel)
                except Exception as e:
                    await self.send(ctx_or_interaction, f"⚠️ 無法移動語音頻道: {e}")
                    return None
        else:
            try:
                voice_client = await channel.connect()
            except Exception as e:
                await self.send(ctx_or_interaction, f"⚠️ 無法加入語音頻道: {e}")
                return None

        return voice_client

    async def start_leave_timer(self, guild_id, voice_client, timeout=300):
        if guild_id in self.bot.leave_tasks:
            self.bot.leave_tasks[guild_id].cancel()

        async def leave_after_timeout():
            try:
                await asyncio.sleep(timeout)
                if voice_client.is_connected():
                    await voice_client.disconnect()
                    print(f"已自動離開語音頻道 (guild_id={guild_id})")
            except asyncio.CancelledError:
                pass
            finally:
                if guild_id in self.bot.leave_tasks:
                    del self.bot.leave_tasks[guild_id]

        task = self.bot.loop.create_task(leave_after_timeout())
        self.bot.leave_tasks[guild_id] = task

    async def play_next(self, ctx_or_interaction):
        guild_id = ctx_or_interaction.guild.id
        queue = self.bot.queues.get(guild_id)

        voice_client = ctx_or_interaction.guild.voice_client

        if not queue or len(queue) == 0:
            # 佇列空，啟動離開計時器
            if voice_client and voice_client.is_connected():
                await self.start_leave_timer(guild_id, voice_client)
            await self.send(ctx_or_interaction, "🛑 播放完畢，佇列已空。")
            return

        # 有歌，取消離開計時器
        if guild_id in self.bot.leave_tasks:
            self.bot.leave_tasks[guild_id].cancel()
            del self.bot.leave_tasks[guild_id]

        url = queue.pop(0)

        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "default_search": "auto",
            "source_address": "0.0.0.0",
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if "entries" in info:
                    info = info["entries"][0]
                audio_url = info["url"]
                title = info.get("title", "未知歌曲")
        except Exception:
            await self.send(ctx_or_interaction, f"⚠️ 解析歌曲失敗：{url}")
            await self.play_next(ctx_or_interaction)
            return

        if not voice_client or not voice_client.is_connected():
            voice_client = await self.join_voice(ctx_or_interaction)
            if not voice_client:
                return

        def after_play(error):
            fut = asyncio.run_coroutine_threadsafe(self.play_next(ctx_or_interaction), self.bot.loop)
            try:
                fut.result()
            except Exception as e:
                print(f"播放下一首錯誤: {e}")

        source = discord.FFmpegPCMAudio(audio_url,
                                       before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5")
        voice_client.play(source, after=after_play)
        await self.send(ctx_or_interaction, f"▶️ 現在播放：{title}")

    async def _create_playlist(self, ctx_or_interaction, name):
        user_id = ctx_or_interaction.author.id if isinstance(ctx_or_interaction, commands.Context) else ctx_or_interaction.user.id
        playlists = load_playlists(user_id)
        if name in playlists:
            await self.send(ctx_or_interaction, f"⚠️ 歌單 `{name}` 已存在。")
            return
        playlists[name] = []
        save_playlists(user_id, playlists)
        await self.send(ctx_or_interaction, f"✅ 已建立歌單 `{name}`。")

    @commands.command(name="create_playlist")
    async def create_playlist(self, ctx, *, name: str):
        await self._create_playlist(ctx, name)

    @app_commands.command(name="create_playlist", description="建立一個新的歌單")
    @app_commands.describe(name="歌單名稱")
    async def slash_create_playlist(self, interaction: discord.Interaction, name: str):
        await self._create_playlist(interaction, name)

    async def _delete_playlist(self, ctx_or_interaction, name):
        user_id = ctx_or_interaction.author.id if isinstance(ctx_or_interaction, commands.Context) else ctx_or_interaction.user.id
        playlists = load_playlists(user_id)
        if name not in playlists:
            await self.send(ctx_or_interaction, f"⚠️ 找不到歌單 `{name}`。")
            return
        del playlists[name]
        save_playlists(user_id, playlists)
        await self.send(ctx_or_interaction, f"🗑️ 已刪除歌單 `{name}`。")

    @commands.command(name="delete_playlist")
    async def delete_playlist(self, ctx, *, name: str):
        await self._delete_playlist(ctx, name)

    @app_commands.command(name="delete_playlist", description="刪除指定的歌單")
    @app_commands.describe(name="歌單名稱")
    async def slash_delete_playlist(self, interaction: discord.Interaction, name: str):
        await self._delete_playlist(interaction, name)

    async def _view_playlists(self, ctx_or_interaction):
        user_id = ctx_or_interaction.author.id if isinstance(ctx_or_interaction, commands.Context) else ctx_or_interaction.user.id
        playlists = load_playlists(user_id)
        if not playlists:
            await self.send(ctx_or_interaction, "⚠️ 你還沒有任何歌單。")
            return
        msg = "📂 你的歌單：\n" + "\n".join(f"- {name} ({len(songs)} 首)" for name, songs in playlists.items())
        await self.send(ctx_or_interaction, msg)

    @commands.command(name="view_playlists")
    async def view_playlists(self, ctx):
        await self._view_playlists(ctx)

    @app_commands.command(name="view_playlists", description="查看所有歌單")
    async def slash_view_playlists(self, interaction: discord.Interaction):
        await self._view_playlists(interaction)

    async def _add_to_playlist(self, ctx_or_interaction, name, url):
        user_id = ctx_or_interaction.author.id if isinstance(ctx_or_interaction, commands.Context) else ctx_or_interaction.user.id
        playlists = load_playlists(user_id)
        if name not in playlists:
            await self.send(ctx_or_interaction, f"⚠️ 找不到歌單 `{name}`。")
            return
        playlists[name].append(url)
        save_playlists(user_id, playlists)
        await self.send(ctx_or_interaction, f"✅ 已加入 `{url}` 到 `{name}`。")

    @commands.command(name="add_to_playlist")
    async def add_to_playlist(self, ctx, name: str, url: str):
        await self._add_to_playlist(ctx, name, url)

    @app_commands.command(name="add_to_playlist", description="將歌曲加入指定歌單")
    @app_commands.describe(name="歌單名稱", url="歌曲網址或關鍵字")
    async def slash_add_to_playlist(self, interaction: discord.Interaction, name: str, url: str):
        await self._add_to_playlist(interaction, name, url)

    async def _remove_from_playlist(self, ctx_or_interaction, name, index):
        user_id = ctx_or_interaction.author.id if isinstance(ctx_or_interaction, commands.Context) else ctx_or_interaction.user.id
        playlists = load_playlists(user_id)
        if name not in playlists:
            await self.send(ctx_or_interaction, f"⚠️ 找不到歌單 `{name}`。")
            return
        if index < 1 or index > len(playlists[name]):
            await self.send(ctx_or_interaction, f"⚠️ 索引 `{index}` 無效，請輸入 1 到 {len(playlists[name])}。")
            return
        removed = playlists[name].pop(index - 1)
        save_playlists(user_id, playlists)
        await self.send(ctx_or_interaction, f"🗑️ 已從 `{name}` 移除第 {index} 首：{removed}")

    @commands.command(name="remove_from_playlist")
    async def remove_from_playlist(self, ctx, name: str, index: int):
        await self._remove_from_playlist(ctx, name, index)

    @app_commands.command(name="remove_from_playlist", description="從歌單中移除指定位置的歌曲")
    @app_commands.describe(name="歌單名稱", index="歌曲索引(從1開始)")
    async def slash_remove_from_playlist(self, interaction: discord.Interaction, name: str, index: int):
        await self._remove_from_playlist(interaction, name, index)

    async def _move_in_playlist(self, ctx_or_interaction, name, old_index, new_index):
        user_id = ctx_or_interaction.author.id if isinstance(ctx_or_interaction, commands.Context) else ctx_or_interaction.user.id
        playlists = load_playlists(user_id)
        if name not in playlists:
            await self.send(ctx_or_interaction, f"⚠️ 找不到歌單 `{name}`。")
            return
        if (old_index < 1 or old_index > len(playlists[name]) or
            new_index < 1 or new_index > len(playlists[name])):
            await self.send(ctx_or_interaction, "⚠️ 無效的索引。請提供有效位置。")
            return
        song = playlists[name].pop(old_index - 1)
        playlists[name].insert(new_index - 1, song)
        save_playlists(user_id, playlists)
        await self.send(ctx_or_interaction, f"↔️ 已將 `{song}` 從位置 {old_index} 移動到 {new_index}。")

    @commands.command(name="move_in_playlist")
    async def move_in_playlist(self, ctx, name: str, old_index: int, new_index: int):
        await self._move_in_playlist(ctx, name, old_index, new_index)

    @app_commands.command(name="move_in_playlist", description="移動歌單中的歌曲位置")
    @app_commands.describe(name="歌單名稱", old_index="原位置", new_index="新位置")
    async def slash_move_in_playlist(self, interaction: discord.Interaction, name: str, old_index: int, new_index: int):
        await self._move_in_playlist(interaction, name, old_index, new_index)

    async def _shuffle_playlist(self, ctx_or_interaction, name):
        user_id = ctx_or_interaction.author.id if isinstance(ctx_or_interaction, commands.Context) else ctx_or_interaction.user.id
        playlists = load_playlists(user_id)
        if name not in playlists:
            await self.send(ctx_or_interaction, f"⚠️ 找不到歌單 `{name}`。")
            return
        random.shuffle(playlists[name])
        save_playlists(user_id, playlists)
        await self.send(ctx_or_interaction, f"🔀 歌單 `{name}` 已隨機排序。")

    @commands.command(name="shuffle_playlist")
    async def shuffle_playlist(self, ctx, name: str):
        await self._shuffle_playlist(ctx, name)

    @app_commands.command(name="shuffle_playlist", description="隨機洗牌歌單中的歌曲")
    @app_commands.describe(name="歌單名稱")
    async def slash_shuffle_playlist(self, interaction: discord.Interaction, name: str):
        await self._shuffle_playlist(interaction, name)

    async def _play_playlist(self, ctx_or_interaction, name):
        user_id = ctx_or_interaction.author.id if isinstance(ctx_or_interaction, commands.Context) else ctx_or_interaction.user.id
        playlists = load_playlists(user_id)
        if name not in playlists:
            await self.send(ctx_or_interaction, f"⚠️ 找不到歌單 `{name}`。")
            return

        urls = playlists[name]
        if not urls:
            await self.send(ctx_or_interaction, f"⚠️ 歌單 `{name}` 是空的。")
            return

        guild_id = ctx_or_interaction.guild.id
        if guild_id not in self.bot.queues:
            self.bot.queues[guild_id] = []

        self.bot.queues[guild_id].extend(urls)

        await self.send(ctx_or_interaction, f"🎶 已將歌單 `{name}` 加入佇列。開始播放...")
        await self.play_next(ctx_or_interaction)

    @commands.command(name="play2")
    async def play2(self, ctx, *, name: str):
        await self._play_playlist(ctx, name)

    @app_commands.command(name="play_playlist", description="播放指定歌單")
    @app_commands.describe(name="歌單名稱")
    async def slash_play_playlist(self, interaction: discord.Interaction, name: str):
        await self._play_playlist(interaction, name)

async def setup(bot):
    await bot.add_cog(PlaylistCog(bot))
