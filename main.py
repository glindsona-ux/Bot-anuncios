import os
import disnake
from disnake.ext import commands, tasks
from flask import Flask
from threading import Thread
import asyncio

# Flask pra manter vivo no Render
app = Flask('')

@app.route('/')
def home():
    return "Bot de anúncios online"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# Bot
intents = disnake.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Guarda dados dos painéis em memória
anuncio_data = {} # {guild_id: {canal, cor, titulo, desc, imagem, msg_id, task}}

class PainelAnunciosView(disnake.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

        # Select de cor
        self.add_item(disnake.ui.Select(
            placeholder="1. Escolha a cor do embed",
            custom_id="cor_select",
            options=[
                disnake.SelectOption(label="Vermelho", value="ff0000"),
                disnake.SelectOption(label="Verde", value="00ff00"),
                disnake.SelectOption(label="Azul", value="0000ff"),
                disnake.SelectOption(label="Amarelo", value="ffff00"),
                disnake.SelectOption(label="Roxo", value="800080"),
            ]
        ))

        # Select de tempo
        self.add_item(disnake.ui.Select(
            placeholder="4. Auto-renovação: escolha o tempo",
            custom_id="tempo_select",
            options=[
                disnake.SelectOption(label="30 minutos", value="1800"),
                disnake.SelectOption(label="1 hora", value="3600"),
                disnake.SelectOption(label="6 horas", value="21600"),
                disnake.SelectOption(label="12 horas", value="43200"),
                disnake.SelectOption(label="24 horas", value="86400"),
            ]
        ))

    @disnake.ui.button(label="2. Preencher Anúncio", style=disnake.ButtonStyle.primary, emoji="🎨", custom_id="preencher")
    async def preencher(self, button, inter):
        modal = AnuncioModal(self.guild_id)
        await inter.response.send_modal(modal)

    @disnake.ui.button(label="3. Enviar Agora", style=disnake.ButtonStyle.success, emoji="📢", custom_id="enviar")
    async def enviar(self, button, inter):
        data = anuncio_data.get(self.guild_id)
        if not data or not data.get('titulo'):
            await inter.response.send_message("Preenche o anúncio primeiro!", ephemeral=True)
            return

        canal = bot.get_channel(data['canal'])
        cor = int(data.get('cor', '2b2d31'), 16)
        embed = disnake.Embed(title=data['titulo'], description=data['desc'], color=cor)
        if data.get('imagem'):
            embed.set_image(url=data['imagem'])

        msg = await canal.send(embed=embed)
        data['msg_id'] = msg.id
        await inter.response.send_message("Anúncio enviado ✅", ephemeral=True)

    @disnake.ui.button(label="5. Ativar Auto-Renovação", style=disnake.ButtonStyle.success, emoji="🔄", custom_id="ativar")
    async def ativar(self, button, inter):
        data = anuncio_data.get(self.guild_id)
        if not data or not data.get('tempo'):
            await inter.response.send_message("Escolha o tempo primeiro!", ephemeral=True)
            return

        if data.get('task'):
            data['task'].cancel()

        @tasks.loop(seconds=int(data['tempo']))
        async def renovar():
            canal = bot.get_channel(data['canal'])
            cor = int(data.get('cor', '2b2d31'), 16)
            embed = disnake.Embed(title=data['titulo'], description=data['desc'], color=cor)
            if data.get('imagem'):
                embed.set_image(url=data['imagem'])
            await canal.send(embed=embed)

        data['task'] = renovar
        renovar.start()
        await inter.response.send_message(f"Auto-renovação ativada a cada {int(data['tempo'])/3600}h ✅", ephemeral=True)

    @disnake.ui.button(label="Parar Auto-Renovação", style=disnake.ButtonStyle.danger, emoji="⏹️", custom_id="parar")
    async def parar(self, button, inter):
        data = anuncio_data.get(self.guild_id)
        if data and data.get('task'):
            data['task'].cancel()
            data['task'] = None
            await inter.response.send_message("Auto-renovação parada ✅", ephemeral=True)
        else:
            await inter.response.send_message("Nenhuma renovação ativa", ephemeral=True)

class AnuncioModal(disnake.ui.Modal):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        components = [
            disnake.ui.TextInput(label="Título", custom_id="titulo", max_length=256, required=True),
            disnake.ui.TextInput(label="Descrição", custom_id="desc", style=disnake.TextInputStyle.paragraph, max_length=2000, required=True),
            disnake.ui.TextInput(label="Imagem URL (opcional)", custom_id="imagem", required=False),
        ]
        super().__init__(title="Preencher Anúncio", components=components)

    async def callback(self, inter):
        anuncio_data[self.guild_id]['titulo'] = inter.text_values['titulo']
        anuncio_data[self.guild_id]['desc'] = inter.text_values['desc']
        anuncio_data[self.guild_id]['imagem'] = inter.text_values['imagem']
        await inter.response.send_message("Anúncio preenchido ✅", ephemeral=True)

@bot.event
async def on_ready():
    print(f'✅ Bot online como {bot.user}')

@bot.slash_command(description="Configura o painel de anúncios")
async def setup_anuncio(inter, canal: disnake.TextChannel):
    if not inter.author.guild_permissions.administrator:
        await inter.response.send_message("Só admin pode usar", ephemeral=True)
        return

    anuncio_data[inter.guild.id] = {'canal': canal.id, 'cor': '2b2d31', 'task': None}

    embed = disnake.Embed(
        title="📢 Painel de Anúncios",
        description="""**1.** Escolha a cor
**2.** Preencha o anúncio
**3.** Envie agora
**4.** Escolha o tempo
**5.** Ative a renovação

Use `/setup_anuncio` primeiro pra definir onde vai postar!""",
        color=0x2b2d31
    )

    view = PainelAnunciosView(inter.guild.id)
    await inter.response.send_message(embed=embed, view=view)

@bot.event
async def on_dropdown(inter):
    if inter.component.custom_id == "cor_select":
        anuncio_data[inter.guild.id]['cor'] = inter.values[0]
        await inter.response.send_message(f"Cor definida ✅", ephemeral=True)
    elif inter.component.custom_id == "tempo_select":
        anuncio_data[inter.guild.id]['tempo'] = inter.values[0]
        await inter.response.send_message(f"Tempo definido ✅", ephemeral=True)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    token = os.getenv("DISCORD_TOKEN")
    bot.run(token)
