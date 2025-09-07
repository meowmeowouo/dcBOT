# cogs/search.py
import discord
from discord.ext import commands
import random
import asyncio

class DeltaForceSearch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.setup_data()

    def setup_data(self):
        """遊戲資料初始化"""
        self.ITEMS = {
            # 白色 (普通)
            "彈藥": {"rarity": "白色", "icon": ""},
            "繃帶": {"rarity": "白色", "icon": ""},
            
            # 綠色 (高級)
            "手榴彈": {"rarity": "綠色", "icon": ""},
            "急救包": {"rarity": "綠色", "icon": ""},
            
            # 藍色 (稀有)
            "手槍": {"rarity": "藍色", "icon": ""},
            "步槍配件": {"rarity": "藍色", "icon": ""},
            
            # 紫色 (史詩)
            "止痛藥": {"rarity": "紫色", "icon": ""},
            "夜視鏡": {"rarity": "紫色", "icon": ""},
            
            # 金色 (傳說)
            "腎上腺素": {"rarity": "金色", "icon": ""},
            
            # 紅色 (特殊)
            #工藝藏品
            "非洲之心": {"rarity": "紅色", "icon": ""},
            "主戰坦克模型": {"rarity": "紅色", "icon": ""},
            "[縱橫]": {"rarity": "紅色", "icon": ""},
            "萬金淚冠": {"rarity": "紅色", "icon": ""},
            "步戰車模型": {"rarity": "紅色", "icon": ""},
            "雷斯的留聲機": {"rarity": "紅色", "icon": ""},
            "克勞迪烏斯半身像": {"rarity": "紅色", "icon": ""},
            "滑膛槍展品": {"rarity": "紅色", "icon": ""},
            "海洋之淚": {"rarity": "紅色", "icon": ""},
            "[天圓地方]": {"rarity": "紅色", "icon": ""},
            "黃金蹬羚": {"rarity": "紅色", "icon": ""},
            "棘龍爪化石": {"rarity": "紅色", "icon": ""}
        }

        self.CONTAINERS = {
            "大保險": {
                "items": ["非洲之心", "主戰坦克模型",  "步戰車模型", "雷斯的留聲機", "克勞迪烏斯半身像", "滑膛槍展品", "海洋之淚", "黃金蹬羚", "棘龍爪化石"],
                "max_search": 5,
                "icon": "https://media.9game.cn/gamebase/ieu-gdc-pre-process/images/20240926/12/28/628c5217fb9c882f58ef1716446bedea.jpg"
                
            }
        }

        # 稀有度設定 (名稱: 時間, 顏色, emoji)
        self.RARITY_SETTINGS = {
            "白色": {"time": 0.3, "color": 0xdddddd, "emoji": "⚪"},
            "綠色": {"time": 0.5, "color": 0x00ff00, "emoji": "🟢"},
            "藍色": {"time": 0.9, "color": 0x0099ff, "emoji": "🔵"},
            "紫色": {"time": 1.3, "color": 0x9900ff, "emoji": "🟣"},
            "金色": {"time": 1.5, "color": 0xffcc00, "emoji": "🟡"},
            "紅色": {"time": 1.8, "color": 0xff0000, "emoji": "🔴"}
        }

    async def run_progress_bar(self, ctx, current, total):
        """純進度條顯示 (完全不含物品資訊)"""
        msg = await ctx.send(f"🔄 正在搜索 ({current}/{total})...\n[░░░░░░░░░░] 0%")
        
        # 用固定速度避免透露稀有度
        base_time = 0.8 / 20  # 每步0.04秒
        for percent in range(10, 101, 5):
            await asyncio.sleep(base_time)
            bar = "█" * (percent // 10) + "░" * (10 - percent // 10)
            await msg.edit(content=f"🔄 正在搜索 ({current}/{total})...\n[{bar}] {percent}%")
        return msg

    @commands.command()
    async def search(self, ctx):
        """執行神秘化搜索"""
        container_type = random.choice(list(self.CONTAINERS.keys()))
        container = self.CONTAINERS[container_type]
        search_count = random.randint(1, container["max_search"])
        
        # 容器發現訊息
        embed = discord.Embed(
            title=f"🔍 發現 {container_type}",
            description=f"可搜索次數: **{search_count}**次",
            color=0x00ffff
        )
        embed.set_thumbnail(url=container["icon"])
        await ctx.send(embed=embed)
        
        found_items = []
        
        for i in range(search_count):
            item_name = random.choice(container["items"])
            item_data = self.ITEMS[item_name]
            rarity_settings = self.RARITY_SETTINGS[item_data["rarity"]]
            
            # 顯示純進度條 (無任何物品提示)
            await self.run_progress_bar(ctx, i+1, search_count)
            
            # 突然顯示結果
            reveal_embed = discord.Embed(
                title="🎉 搜索完成！",
                description=f"{rarity_settings['emoji']} **{item_name}**",
                color=rarity_settings["color"]
            )
            reveal_embed.add_field(
                name="稀有度",
                value=f"**{item_data['rarity']}**",
                inline=True
            )
            reveal_embed.set_thumbnail(url=item_data["icon"])
            await ctx.send(embed=reveal_embed)
            found_items.append((item_name, item_data["rarity"]))
        
        # 最終報告 (按稀有度排序)
        found_items.sort(key=lambda x: list(self.RARITY_SETTINGS.keys()).index(x[1]), reverse=True)
        
        report = discord.Embed(
            title=f"📊 {container_type} 搜索報告",
            description="\n".join(
                f"{self.RARITY_SETTINGS[rarity]['emoji']} **{name}**"
                for name, rarity in found_items
            ),
            color=0x7289da
        )
        report.set_thumbnail(url=container["icon"])
        await ctx.send(embed=report)

async def setup(bot):
    await bot.add_cog(DeltaForceSearch(bot))