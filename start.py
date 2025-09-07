import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

class MusicBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.queues = {}
        self.last_played_urls = {}
        self.auto_play_enabled = {}

    async def setup_hook(self):
        await self.load_extension("cogs.music")
        await self.load_extension("cogs.playlist")
        await self.load_extension("cogs.stock_tools")
        await self.load_extension("cogs.df")
        await self.load_extension("cogs.bilibili")
        await self.tree.sync()
        print("✅ 指令同步完成")

bot = MusicBot()

@bot.event
async def on_ready():
    print(f"✅ Bot 已上線：{bot.user}")


bot.run('TOKEN')