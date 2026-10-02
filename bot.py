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

# --- CONFIGURARE SERVER WEB (Necesar pentru ca Render să țină botul pornit) ---
app = Flask('')

@app.route('/')
def home():
    return "Botul IJJ este online și baza de date funcționează!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIGURARE BOT DISCORD ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Preluăm ID-ul grupului de Roblox setat în Render
ROBLOX_GROUP_ID = os.environ.get('ROBLOX_GROUP_ID')

@bot.event
async def on_ready():
    print(f'Botul s-a logat ca {bot.user}')
    print(f'Grupul de Roblox configurat: {ROBLOX_GROUP_ID}')

# Funcție pentru salvarea/actualizarea membrilor în baza de date
def salveaza_membru(roblox_id, discord_id, nume_ingame, grad, call_sign, rank_id):
    conn = sqlite3.connect('ijj_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO membri (roblox_id, discord_id, nume_ingame, grad, call_sign, rank_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (roblox_id, discord_id, nume_ingame, grad, call_sign, rank_id))
    conn.commit()
    conn.close()

@bot.command()
async def baza_date(ctx):
    conn = sqlite3.connect('ijj_database.db')
    cursor = conn.cursor()
    
    # Extragem membrii ordonați după rank_id (de la cel mai mare la cel mai mic)
    # Dacă vrei doar de la un anumit grad în sus (ex: rank_id >= 5), poți adăuga WHERE rank_id >= 5
    cursor.execute("SELECT nume_ingame, grad, call_sign FROM membri ORDER BY rank_id DESC")
    membri = cursor.fetchall()
    conn.close()

    if not membri:
        await ctx.send("❌ Baza de date este goală momentan. Niciun membru înregistrat.")
        return

    # Afișarea sub formă de Embed pe Discord
    embed = discord.Embed(
        title="📋 Baza de Date Oficială - IJJ",
        description="Lista curentă a cadrelor înregistrate:",
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

    embed.set_footer(text=f"Total membri înregistrați: {len(membri)}")
    await ctx.send(embed=embed)

# Pornirea serverului web și a botului în paralel
if __name__ == "__main__":
    t = threading.Thread(target=run_web)
    t.start()
    
    TOKEN = os.environ.get('DISCORD_TOKEN')
    bot.run(TOKEN)
  
