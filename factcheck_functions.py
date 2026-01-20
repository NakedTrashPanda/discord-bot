import discord
import json
from datetime import datetime
from pathlib import Path
from config import GEMINI_API_KEY
import gemini_functions

FACTCHECK_HISTORY = Path("factcheck_history.json")

def load_factcheck_history():
    if FACTCHECK_HISTORY.exists():
        with open(FACTCHECK_HISTORY, "r") as f:
            return json.load(f)
    return []

def save_factcheck_history(history):
    with open(FACTCHECK_HISTORY, "w") as f:
        json.dump(history, f, indent=2)

async def factcheck(interaction: discord.Interaction, claim: str):
    prompt = "Fact-check this claim using current web sources. Start with VERDICT: [True/False/Mixed/Unverified] then explain in 2-3 sentences with sources. Claim: %s" % claim
    
    result = await gemini_functions.generate_with_grounding(prompt)
    
    if not result["text"]:
        await interaction.followup.send("Error checking claim: %s" % result.get("error", "Unknown"), ephemeral=True)
        return
    
    text = result["text"]
    sources = result["sources"]
    
    verdict = "Unknown"
    if "False" in text[:100]:
        verdict = "False"
        emoji, color = "❌", 0xE74C3C
    elif "True" in text[:100]:
        verdict = "True"
        emoji, color = "✅", 0x27AE60
    elif "Mixed" in text[:100]:
        verdict = "Mixed"
        emoji, color = "🟡", 0xF1C40F
    else:
        verdict = "Unverified"
        emoji, color = "❓", 0x95A5A6
    
    embed = discord.Embed(title="%s %s" % (emoji, verdict), color=color)
    embed.description = text[:1000]
    
    for i, source in enumerate(sources[:3]):
        embed.add_field(name=source.get("title", "Source %d" % (i+1)), value="[Link](%s)" % source["url"], inline=True)
    
    embed.set_footer(text="Powered by Gemini | Claim: %s" % claim[:80])
    embed.timestamp = discord.utils.utcnow()
    
    history = load_factcheck_history()
    history.append({"timestamp": datetime.now().isoformat(), "claim": claim[:200], "user_id": interaction.user.id, "verdict": verdict})
    save_factcheck_history(history)
    
    await interaction.followup.send(embed=embed)

def setup(bot):
    tree = bot.tree
    @tree.command(name="factcheck", description="AI-powered fact-check with web sources.")
    @discord.app_commands.describe(claim="Claim to verify.")
    async def factcheck_slash(interaction: discord.Interaction, claim: str):
        await interaction.response.defer()
        await factcheck(interaction, claim)
