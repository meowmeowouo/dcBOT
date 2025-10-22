# TranslationCog.py
import discord
from discord.ext import commands
from discord import app_commands
from deep_translator import GoogleTranslator

class TranslationCog(commands.Cog):
    """翻譯功能 Cog，支援多行文字、slash 和 prefix 指令"""

    def __init__(self, bot):
        self.bot = bot
        self.default_lang = "zh-TW"  # 預設目標語言

    # ------------------- Slash 指令 -------------------
    @app_commands.command(name="tr", description="翻譯文字到指定語言（預設繁體中文）")
    @app_commands.describe(text="要翻譯的文字，可多行", target_lang="目標語言代碼，例如 en、ja，不填預設繁體中文")
    async def translate_slash(self, interaction: discord.Interaction, text: str, target_lang: str = None):
        target_lang = target_lang or self.default_lang
        try:
            translated = GoogleTranslator(source='auto', target=target_lang).translate(text)
            # Discord 訊息過長會出問題，分段處理
            messages = self.split_message(translated)
            await interaction.response.send_message(f"**原文:**\n{text}")
            for msg in messages:
                await interaction.followup.send(f"**翻譯({target_lang}):**\n{msg}")
        except Exception as e:
            await interaction.response.send_message(f"❌ 翻譯失敗: {e}")

    # ------------------- Prefix 指令 -------------------
    @commands.command(name="tr")
    async def translate_prefix(self, ctx: commands.Context, *, args: str):
        """
        Prefix 指令格式:
        !tr [目標語言代碼] 要翻譯的文字（可多行）
        例如:
        !tr en 你好
        !tr 這是一段
        多行文字
        """
        lines = args.splitlines()
        if not lines:
            return await ctx.send("❌ 沒有要翻譯的文字")

        # 判斷是否有目標語言代碼
        first_line_parts = lines[0].split(maxsplit=1)
        if len(first_line_parts) == 1:
            target_lang = self.default_lang
            text = args
        else:
            target_lang = first_line_parts[0]
            lines[0] = first_line_parts[1]
            text = "\n".join(lines)

        try:
            translated = GoogleTranslator(source='auto', target=target_lang).translate(text)
            # 分段避免 Discord 訊息過長
            messages = self.split_message(translated)
            await ctx.send(f"**原文:**\n{text}")
            for msg in messages:
                await ctx.send(f"**翻譯({target_lang}):**\n{msg}")
        except Exception as e:
            await ctx.send(f"❌ 翻譯失敗: {e}")

    # ------------------- 工具函數 -------------------
    @staticmethod
    def split_message(text: str, max_len: int = 1900):
        """將長文字拆成多個 Discord 訊息片段"""
        lines = text.splitlines()
        result = []
        buffer = ""
        for line in lines:
            if len(buffer) + len(line) + 1 > max_len:
                result.append(buffer)
                buffer = line
            else:
                buffer += ("\n" if buffer else "") + line
        if buffer:
            result.append(buffer)
        return result

# ------------------- setup -------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(TranslationCog(bot))
