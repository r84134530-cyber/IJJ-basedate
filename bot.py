import os
import discord
from discord.ext import commands
from flask import Flask
import threading
import requests
import sqlite3

# --- CONFIGURARE BAZĂ DE DATE SQLITE ---
def init_db():
    conn = sqlite3.connect('ijj_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS membri (
            roblox_id TEXT PRIMARY KEY,
            discord_id TEXT,
            nume_ingame TEXT,
            grad TEXT,
            call_sign TEXT,
            rank_id INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- CONFIGURARE SERVER WEB (Pentru Render) ---
app = Flask('')

@app.route('/')
def home():
    return "Botul IJJ este online!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIGURARE BOT DISCORD ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

ROBLOX_GROUP_ID = int(os.environ.get('ROBLOX_GROUP_ID', 0))

@bot.event
async def on_ready():
    print(f'Botul s-a logat ca {bot.user}')

# Funcție ajutătoare: Obține Roblox ID după username
def obtine_roblox_id(username):
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [username], "excludeBannedUsers": True}
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json().get("data", [])
        if data:
            return data[0]["id"], data[0]["name"]
    return None, None

# Funcție ajutătoare: Verifică gradul în grupul IJJ
def verifica_grup_roblox(roblox_id):
    url = f"https://groups.roblox.com/v1/users/{roblox_id}/groups/roles"
    response = requests.get(url)
    if response.status_code == 200:
        for item in response.json().get("data", []):
            if item["group"]["id"] == ROBLOX_GROUP_ID:
                return {
                    "in_grup": True,
                    "grad": item["role"]["name"],
                    "rank_id": item["role"]["rank"]
                }
    return {"in_grup": False}

# --- 1. COMANDA /inregistrare ---
@bot.command()
async def inregistrare(ctx, nume_roblox: str, call_sign: str = "N/A"):
    await ctx.send(f"🔍 Verific contul de Roblox **{nume_roblox}**...")
    
    roblox_id, nume_corect = obtine_roblox_id(nume_roblox)
    if not roblox_id:
        await ctx.send("❌ Nu am găsit niciun jucător de Roblox cu acest nume!")
        return

    rezultat_grup = verifica_grup_roblox(roblox_id)
    if not rezultat_grup["in_grup"]:
        await ctx.send(f"❌ Jucătorul **{nume_corect}** nu este în grupul oficial IJJ!")
        return

    grad = rezultat_grup["grad"]
    rank_id = rezultat_grup["rank_id"]
    discord_id = str(ctx.author.id)

    # Salvăm în baza de date
    conn = sqlite3.connect('ijj_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO membri (roblox_id, discord_id, nume_ingame, grad, call_sign, rank_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (str(roblox_id), discord_id, nume_corect, grad, call_sign, rank_id))
    conn.commit()
    conn.close()

    await ctx.send(f"✅ Înregistrare reușită!\n👤 **Nume:** {nume_corect}\n⭐ **Grad:** {grad}\n📞 **Call Sign:** {call_sign}")

# --- 2. COMANDA /update ---
@bot.command()
async def update(ctx):
    discord_id = str(ctx.author.id)
    
    conn = sqlite3.connect('ijj_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT roblox_id, nume_ingame FROM membri WHERE discord_id = ?", (discord_id,))
    membru = cursor.fetchone()
    conn.close()

    if not membru:
        await ctx.send("❌ Nu ești înregistrat în baza de date! Folosește mai întâi `/inregistrare <nume_roblox> <call_sign>`")
        return

    roblox_id, nume_ingame = membru
    await ctx.send(f"🔄 Verific actualizările pentru **{nume_ingame}** pe grupul de Roblox...")

    rezultat_grup = verifica_grup_roblox(int(roblox_id))
    if not rezultat_grup["in_grup"]:
        await ctx.send("❌ Nu mai ești în grupul IJJ de Roblox!")
        return

    grad_nou = rezultat_grup["grad"]
    rank_nou = rezultat_grup["rank_id"]

    # Actualizăm gradul în baza de date
    conn = sqlite3.connect('ijj_database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE membri SET grad = ?, rank_id = ? WHERE roblox_id = ?", (grad_nou, rank_nou, roblox_id))
    conn.commit()
    conn.close()

    await ctx.send(f"✅ Update finalizat! Gradul tău actualizat este: **{grad_nou}** (Rank ID: {rank_nou})")

# --- 3. COMANDA /baza_date ---
@bot.command()
async def baza_date(ctx):
    conn = sqlite3.connect('ijj_database.db')
    cursor = conn.cursor()
    
    # Selectăm doar de la rank_id 5 în sus (după cum ai cerut: IJJ 05 în sus)
    cursor.execute("SELECT nume_ingame, grad, call_sign FROM membri WHERE rank_id >= 5 ORDER BY rank_id DESC")
    membri = cursor.fetchall()
    conn.close()

    if not membri:
        await ctx.send("❌ Niciun membru găsit de la gradul IJJ 05 în sus momentan.")
        return

    embed = discord.Embed(
        title="📋 Baza de Date Oficială - IJJ (IJJ 05+)",
        description="Lista cadrelor înregistrate:",
        color=discord.Color.blue()
    )

    lista_text = ""
    for index, (nume, grad, call_sign) in enumerate(membri, start=1):
        sign = call_sign if call_sign else "N/A"
        lista_text += f"**{index}.** `{nume}` | **Grad:** {grad} | **Call Sign:** `{sign}`\n"
        
        if len(lista_text) > 900:
            embed.add_field(name="Membri (continuare)", value=lista_text, inline=False)
            lista_text = ""

    if lista_text:
        embed.add_field(name="Membri", value=lista_text, inline=False)

    embed.set_footer(text=f"Total membri afișați: {len(membri)}")
    await ctx.send(embed=embed)

# Pornire server web + bot
if __name__ == "__main__":
    t = threading.Thread(target=run_web)
    t.start()
    
    TOKEN = os.environ.get('DISCORD_TOKEN')
    bot.run(TOKEN)
        
