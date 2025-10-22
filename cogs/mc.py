import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from mcstatus import JavaServer, BedrockServer
import time
import matplotlib.pyplot as plt
import io

class MinecraftCog(commands.Cog):
    """Minecraft 伺服器查詢 Cog，自動辨識伺服器類型，並提供連線測試及趨勢圖"""

    def __init__(self, bot):
        self.bot = bot

    # ------------------- Prefix 指令 -------------------
    @commands.command(name="mc")
    async def mc_prefix(self, ctx, server_ip: str):
        """查詢 Minecraft 伺服器狀態 (prefix 指令)"""
        await self.query_mc(ctx, server_ip)

    @commands.command(name="mc_test")
    async def mc_test_prefix(self, ctx, server_ip: str, times: int = 60, show_graph: bool = False):
        """測試伺服器連線 (prefix 指令)"""
        await self.test_mc(ctx, server_ip, times, show_graph)

    # ------------------- Slash 指令 -------------------
    @app_commands.command(name="mc", description="查詢 Minecraft 伺服器狀態")
    @app_commands.describe(server_ip="伺服器 IP")
    async def mc_slash(self, interaction: discord.Interaction, server_ip: str):
        await self.query_mc(interaction, server_ip)

    @app_commands.command(name="mc_test", description="測試 Minecraft 伺服器連線")
    @app_commands.describe(server_ip="伺服器 IP", times="測試次數", show_graph="是否顯示延遲圖表")
    async def mc_test_slash(self, interaction: discord.Interaction, server_ip: str, times: int = 60, show_graph: bool = False):
        await self.test_mc(interaction, server_ip, times, show_graph)

    # ------------------- 查詢伺服器狀態 -------------------
    async def query_mc(self, ctx_or_interaction, server_ip: str):
        try:
            # 嘗試 Java
            try:
                server = JavaServer.lookup(server_ip)
                status = await asyncio.to_thread(server.status)
                query = await asyncio.to_thread(server.query)
                server_type = "Java"
                players_online = status.players.online
                max_players = status.players.max
                latency = round(status.latency, 2)
                motd = status.description if hasattr(status, 'description') else "N/A"
                player_list = ", ".join(query.players.names) if query.players.names else "無玩家在線"
                map_name = query.map if hasattr(query, 'map') else "N/A"
            except Exception:
                # 嘗試 Bedrock
                server = BedrockServer.lookup(server_ip)
                status = await asyncio.to_thread(server.status)
                server_type = "Bedrock"
                players_online = status.players_online
                max_players = status.players_max
                latency = round(status.latency, 2)
                motd = "N/A"
                player_list = "N/A"
                map_name = "N/A"

            msg = f"🎮 **Minecraft {server_type} 伺服器狀態**\n"
            msg += f"🌐 IP: {server_ip}\n"
            msg += f"🧑 玩家: {players_online}/{max_players}\n"
            msg += f"👥 在線玩家: {player_list}\n"
            msg += f"🗺 地圖名稱: {map_name}\n"
            msg += f"💬 Motd: {motd}\n"
            msg += f"🕹 版本: {status.version.name if hasattr(status, 'version') else '未知'}\n"
            msg += f"⏱ 延遲: {latency} ms"

            if isinstance(ctx_or_interaction, commands.Context):
                await ctx_or_interaction.send(msg)
            else:
                await ctx_or_interaction.response.send_message(msg)

        except Exception as e:
            msg = f"❌ 查詢失敗: {e}"
            if isinstance(ctx_or_interaction, commands.Context):
                await ctx_or_interaction.send(msg)
            else:
                await ctx_or_interaction.response.send_message(msg)

    # ------------------- 伺服器連線測試 -------------------
    async def test_mc(self, ctx_or_interaction, server_ip: str, times: int = 60, show_graph: bool = False):
        latencies = []
        results = []
        server_type = "未知"

        for i in range(times):
            try:
                # Java
                try:
                    server = JavaServer.lookup(server_ip)
                    status = await asyncio.to_thread(server.status)
                    latency = round(status.latency, 2)
                    server_type = "Java"
                except Exception:
                    # Bedrock
                    server = BedrockServer.lookup(server_ip)
                    status = await asyncio.to_thread(server.status)
                    latency = round(status.latency, 2)
                    server_type = "Bedrock"

                latencies.append(latency)
                results.append(f"測試 {i+1}: {latency} ms")
            except Exception:
                results.append(f"測試 {i+1}: 連線失敗")
                latencies.append(None)
            await asyncio.sleep(1)

        avg_latency = round(sum([l for l in latencies if l is not None])/len([l for l in latencies if l is not None]), 2) if any(latencies) else "N/A"
        msg = f"🎮 **Minecraft {server_type} 伺服器連線測試 ({times} 次)**\n"
        msg += f"🌐 IP: {server_ip}\n"
        msg += "\n".join(results) + "\n"
        msg += f"⏱ 平均延遲: {avg_latency} ms"

        if isinstance(ctx_or_interaction, commands.Context):
            await ctx_or_interaction.send(msg)
        else:
            await ctx_or_interaction.response.send_message(msg)

        # ------------------- 延遲圖表 -------------------
        if show_graph:
            plt.figure(figsize=(8, 4))
            x = list(range(1, times + 1))
            y = [l if l is not None else 0 for l in latencies]
            plt.plot(x, y, marker='o', linestyle='-', color='blue')
            plt.title(f"{server_ip} 延遲趨勢圖")
            plt.xlabel("測試次數")
            plt.ylabel("延遲 (ms)")
            plt.grid(True)
            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format="png")
            buf.seek(0)
            plt.close()

            file = discord.File(fp=buf, filename="mc_latency.png")
            if isinstance(ctx_or_interaction, commands.Context):
                await ctx_or_interaction.send(file=file)
            else:
                await ctx_or_interaction.followup.send(file=file)

# ------------------- setup -------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(MinecraftCog(bot))
