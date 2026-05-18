import disnake
from disnake.ext import commands, tasks
import json
import os
import asyncio
import threading
from flask import Flask

# --- Flask keepalive pra Render não dormir ---
app = Flask('')

@app.route('/')
def home():
    return "Bot online!"

def run_flask():
    port = int(os.getenv("PORT", 10000)) # Render usa PORT 10000
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- Bot config ---
TOKEN = os.getenv("TOKEN")

intents = disnake.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.InteractionBot(intents=intents)
DB_FILE = "anuncios.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

db = load_db()

CORES = {
    "Azul": 0x3498db,
    "Verde": 0x2ecc71,
    "Vermelho": 0xe74c3c,
    "Amarelo": 0xf1c40f,
    "Roxo": 0x9b59b6,
    "Preto": 0x2c2f33
}

INTERVALOS = {
    "25 minutos": 25 * 60,
    "30 minutos": 30 * 60,
    "1 hora": 60 * 60,
    "2 horas": 2 * 60 * 60,
    "3 horas": 3 * 60 * 60,
    "4 horas": 4 * 60 * 60,
    "5 horas": 5 * 60 * 60
}

class PainelAnuncio(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.string_select(
        placeholder="1. Escolha a cor do embed",
        options=[disnake.SelectOption(label=k) for k in CORES.keys()],
        custom_id="select_cor"
    )
    async def select_cor(self, select: disnake.ui.StringSelect, inter: disnake.MessageInteraction):
        db.setdefault(str(inter.guild.id), {}).setdefault("temp", {})
        db[str(inter.guild.id)]["temp"]["cor"] = CORES[select.values[0]]
        save_db(db)
        await inter.response.send_message(f"Cor selecionada: **{select.values[0]}**", ephemeral=True)

    @disnake.ui.button(label="2. Preencher Anúncio", style=disnake.ButtonStyle.primary, emoji="✍️", custom_id="btn_preencher")
    async def preencher(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.send_modal(ModalAnuncio())

    @disnake.ui.button(label="3. Enviar Agora", style=disnake.ButtonStyle.green, emoji="📢", custom_id="btn_enviar")
    async def enviar(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        guild_data = db.get(str(inter.guild.id), {})
        temp = guild_data.get("temp", {})

        if "cor" not in temp or "titulo" not in temp or "descricao" not in temp:
            await inter.response.send_message("Preencha a cor e o anúncio primeiro!", ephemeral=True)
            return

        canal_id = guild_data.get("canal_anuncio")
        if not canal_id:
            await inter.response.send_message("Use `/setcanal` primeiro pra definir onde enviar!", ephemeral=True)
            return

        canal = inter.guild.get_channel(canal_id)
        if not canal:
            await inter.response.send_message("Canal não encontrado. Use `/setcanal` de novo.", ephemeral=True)
            return

        embed = disnake.Embed(
            title=temp["titulo"],
            description=temp["descricao"],
            color=temp["cor"]
        )
        embed.set_footer(text=f"Anúncio por {inter.author.display_name}")

        msg = await canal.send(embed=embed)

        db[str(inter.guild.id)]["temp"] = {}
        db[str(inter.guild.id)]["ultimo_post"] = asyncio.get_event_loop().time()
        db[str(inter.guild.id)]["ultimo_post_msg"] = msg.id
        save_db(db)

        await inter.response.send_message(f"Anúncio enviado em {canal.mention}!", ephemeral=True)

    @disnake.ui.string_select(
        placeholder="4. Auto-renovação: escolha o tempo",
        options=[disnake.SelectOption(label=k) for k in INTERVALOS.keys()],
        custom_id="select_tempo",
        row=1
    )
    async def select_tempo(self, select: disnake.ui.StringSelect, inter: disnake.MessageInteraction):
        db.setdefault(str(inter.guild.id), {}).setdefault("temp", {})
        db[str(inter.guild.id)]["temp"]["tempo"] = INTERVALOS[select.values[0]]
        db[str(inter.guild.id)]["temp"]["tempo_nome"] = select.values[0]
        save_db(db)
        await inter.response.send_message(f"Tempo selecionado: **{select.values[0]}**", ephemeral=True)

    @disnake.ui.button(label="5. Ativar Auto-Renovação", style=disnake.ButtonStyle.success, emoji="🔄", custom_id="btn_ativar", row=2)
    async def ativar_renovacao(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        guild_id = str(inter.guild.id)
        data = db.get(guild_id, {})
        temp = data.get("temp", {})

        if "tempo" not in temp:
            await inter.response.send_message("Escolha o tempo primeiro!", ephemeral=True)
            return
        if "canal_anuncio" not in data:
            await inter.response.send_message("Use `/setcanal` primeiro!", ephemeral=True)
            return
        if "titulo" not in temp:
            await inter.response.send_message("Preencha o anúncio primeiro!", ephemeral=True)
            return

        db[guild_id]["intervalo"] = temp["tempo"]
        db[guild_id]["intervalo_nome"] = temp["tempo_nome"]
        db[guild_id]["ultimo_post"] = asyncio.get_event_loop().time()

        save_db(db)

        if not renovar_painel.is_running():
            renovar_painel.start()

        canal = inter.guild.get_channel(data["canal_anuncio"])
        await inter.response.send_message(f"Auto-renovação ativada! Vai postar a cada **{temp['tempo_nome']}** em {canal.mention}.", ephemeral=True)

        embed = disnake.Embed(
            title=temp["titulo"],
            description=temp["descricao"],
            color=temp["cor"]
        )
        embed.set_footer(text=f"Anúncio automático por {inter.author.display_name}")
        msg = await canal.send(embed=embed)
        db[guild_id]["ultimo_post_msg"] = msg.id
        db[guild_id]["temp"] = {}
        save_db(db)

    @disnake.ui.button(label="Parar Auto-Renovação", style=disnake.ButtonStyle.danger, emoji="⏹️", custom_id="btn_parar", row=2)
    async def parar_renovacao(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        guild_id = str(inter.guild.id)
        if guild_id in db:
            db[guild_id].pop("intervalo", None)
            db[guild_id].pop("intervalo_nome", None)
            save_db(db)
        await inter.response.send_message("Auto-renovação parada.", ephemeral=True)

class ModalAnuncio(disnake.ui.Modal):
    def __init__(self):
        components = [
            disnake.ui.TextInput(
                label="Título",
                placeholder="Título do anúncio",
                max_length=256,
                custom_id="titulo_input"
            ),
            disnake.ui.TextInput(
                label="Descrição",
                style=disnake.TextInputStyle.paragraph,
                placeholder="Descrição do anúncio",
                max_length=4000,
                custom_id="desc_input"
            )
        ]
        super().__init__(title="Criar Anúncio", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        db.setdefault(str(inter.guild.id), {}).setdefault("temp", {})
        db[str(inter.guild.id)]["temp"]["titulo"] = inter.text_values["titulo_input"]
        db[str(inter.guild.id)]["temp"]["descricao"] = inter.text_values["desc_input"]
        save_db(db)
        await inter.response.send_message("Anúncio preenchido! Agora clique em 'Enviar Agora' ou 'Ativar Auto-Renovação'.", ephemeral=True)

@bot.slash_command(name="setup_anuncio", description="Cria o painel de anúncios no canal atual")
@commands.has_permissions(administrator=True)
async def setup_anuncio(inter: disnake.ApplicationCommandInteraction):
    db.setdefault(str(inter.guild.id), {})
    save_db(db)

    embed = disnake.Embed(
        title="📢 Painel de Anúncios",
        description="**1.** Escolha a cor\n**2.** Preencha o anúncio\n**3.** Envie agora\n**4.** Escolha o tempo\n**5.** Ative a renovação\nUse `/setcanal` primeiro pra definir onde vai postar!",
        color=0x3498db
    )
    await inter.response.send_message(embed=embed, view=PainelAnuncio())

@bot.slash_command(name="setcanal", description="Define o canal onde os anúncios serão enviados")
@commands.has_permissions(administrator=True)
async def setcanal(inter: disnake.ApplicationCommandInteraction, canal: disnake.TextChannel):
    db.setdefault(str(inter.guild.id), {})["canal_anuncio"] = canal.id
    save_db(db)
    await inter.response.send_message(f"Canal de anúncios definido para {canal.mention}")

@tasks.loop(seconds=60)
async def renovar_painel():
    for guild_id, data in list(db.items()):
        if "intervalo" not in data or "canal_anuncio" not in data or "ultimo_post" not in data:
            continue

        agora = asyncio.get_event_loop().time()
        if agora - data["ultimo_post"] >= data["intervalo"]:
            guild = bot.get_guild(int(guild_id))
            if not guild:
                continue

            canal = guild.get_channel(data["canal_anuncio"])
            if not canal:
                continue

            try:
                msg_antiga = await canal.fetch_message(data["ultimo_post_msg"])
                await msg_antiga.delete()
            except:
                pass

            temp = data.get("temp", {})
            if not temp and "temp_titulo" in data:
                temp = {
                    "titulo": data["temp_titulo"],
                    "descricao": data["temp_descricao"],
                    "cor": data["temp_cor"]
                }

            if not temp:
                continue

            embed = disnake.Embed(
                title=temp["titulo"],
                description=temp["descricao"],
                color=temp["cor"]
            )
            embed.set_footer(text="Anúncio automático")
            nova_msg = await canal.send(embed=embed)

            db[guild_id]["ultimo_post"] = agora
            db[guild_id]["ultimo_post_msg"] = nova_msg.id
            save_db(db)

@bot.event
async def on_ready():
    print(f"Bot online como {bot.user}")
    bot.add_view(PainelAnuncio())
    if not renovar_painel.is_running():
        renovar_painel.start()

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
