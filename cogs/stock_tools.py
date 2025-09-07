import discord
from discord.ext import commands
from discord import app_commands
import yfinance as yf

class StockTools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            synced = await self.bot.tree.sync()
            print(f"✅ Slash 指令已同步，共 {len(synced)} 條")
        except Exception as e:
            print(f"⚠️ Slash 指令同步失敗：{e}")

    @commands.command(name="stock")
    async def stock(self, ctx, *, symbol: str):
        """使用 !stock [股票代號] 查詢"""
        await self.send_stock_info(ctx, symbol)

    @app_commands.command(name="stock", description="查詢股票資訊")
    @app_commands.describe(symbol="輸入股票代碼，如 2330 或 AAPL")
    async def stock_slash(self, interaction: discord.Interaction, symbol: str):
        """使用 /stock 查詢"""
        await self.send_stock_info(interaction, symbol)

    async def send_stock_info(self, where, symbol: str):
        symbol = symbol.upper().strip()
        if symbol.isdigit():
            symbol += ".TW"

        try:
            stock = yf.Ticker(symbol)
            info = stock.info

            name = info.get("longName") or info.get("shortName") or "未知名稱"
            currency = info.get("currency", "未知幣別")
            price = info.get("regularMarketPrice")

            if price is None:
                raise ValueError("查無此股票")

            change = info.get("regularMarketChange", 0)
            percent = info.get("regularMarketChangePercent", 0)

            embed = discord.Embed(
                title=f"{name} ({symbol})",
                description=f"💵 現價: **{price} {currency}**\n📉 漲跌: {change:.2f} ({percent:.2f}%)",
                color=discord.Color.green() if change >= 0 else discord.Color.red()
            )
            await where.response.send_message(embed=embed) if isinstance(where, discord.Interaction) else await where.send(embed=embed)

        except Exception as e:
            error_msg = f"❌ 查詢失敗，請確認代碼是否正確。({e})"
            await where.response.send_message(error_msg) if isinstance(where, discord.Interaction) else await where.send(error_msg)

async def setup(bot):
    await bot.add_cog(StockTools(bot))
