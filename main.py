import os
import disnake
from disnake.ext import commands, tasks
from flask import Flask
from threading import Thread
import asyncio
import aiohttp

# Flask pra manter vivo no Render
app = Flask('')

@app.route('/')
def home():
    return "Bot de anúncios online v3.1"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# Bot
intents = disnake.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Guarda dados: {guild_id: {nome_anuncio: {canal, cor, titulo, desc, imagem, msg_id, task, tempo}}}
anuncio_data = {}

async def baixar_imagem(url):
    """Baixa imagem do Discord/CDN e retorna URL pro embed"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return url # Discord já hospeda, só usar URL
    return None

class PainelAnunciosView(disnake.ui.View):
    def __init__(self, guild_id, nome):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.nome = nome

        # Select de cor - 12 cores
        self.add_item(disnake.ui.Select(
            placeholder="1. Escolha a cor do embed",
            custom_id=f"cor_select_{nome}",
            options=[
                disnake.SelectOption(label="Vermelho", value="ff0000"),
                disnake.SelectOption(label="Verde", value="00ff00"),
                disnake.SelectOption(label="Azul", value="0000ff"),
                disnake.SelectOption(label="Amarelo", value="ffff00"),
                disnake.SelectOption(label="Roxo", value="800080"),
                disnake.SelectOption(label="Cinza", value="808080"),
                disnake.SelectOption(label="Rosa", value="ff69b4"),
                disnake.SelectOption(label="Marrom", value="8b4513"),
                disnake.SelectOption(label="Preto", value="000"),
                disnake.SelectOption(label="Laranja", value="ff8c00"),
                disnake.SelectOption(label="Ciano", value="00ffff"),
                disnake.SelectOption(label="Branco", value="ffffff"),
            ]
        ))

        # Select de tempo
        self.add_item(disnake.ui.Select(
            placeholder="4. Auto-renovação: escolha o tempo",
            custom_id=f"tempo_select_{nome}",
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
        modal = AnuncioModal(self.guild_id, self.nome)
        await inter.response.send_modal(modal)

    @disnake.ui.button(label="3. Enviar Agora", style=disnake.ButtonStyle.success, emoji="📢", custom_id="enviar")
    async def enviar(self, button, inter):
        data = anuncio_data.get(self.guild_id, {}).get(self.nome)
        if not data or not data.get('titulo'):
            await inter.response.send_message("Preenche o anúncio primeiro!", ephemeral=True)
            return

        canal = bot.get_channel(data['canal'])
        cor = int(data.get('cor', '2b2d31'), 16)

        # Apaga msg antiga se existir
        if data.get('msg_id'):
            try:
                msg_antiga = await canal.fetch_message(data['msg_id'])
                await msg_antiga.delete()
            except:
                pass

        embed = disnake.Embed(
            title=f"📢 {data['titulo']}",
            description=data['desc'],
            color=cor
        )
        if data.get('imagem'):
            embed.set_image(url=data['imagem'])
        embed.set_footer(text=f"Anúncio: {self.nome} | Bot FFZ v3.1", icon_url=bot.user.avatar.url)

        msg = await canal.send(embed=embed)
        data['msg_id'] = msg.id
        await inter.response.send_message(f"Anúncio '{self.nome}' enviado ✅", ephemeral=True)

    @disnake.ui.button(label="5. Ativar Auto-Renovação", style=disnake.ButtonStyle.success, emoji="🔄", custom_id="ativar")
    async def ativar(self, button, inter):
        data = anuncio_data.get(self.guild_id, {}).get(self.nome)
        if not data or not data.get('tempo'):
            await inter.response.send_message("Escolha o tempo primeiro!", ephemeral=True)
            return

        if data.get('task'):
            data['task'].cancel()

        guild_id = self.guild_id
        nome = self.nome

        @tasks.loop(seconds=int(data['tempo']))
        async def renovar():
            canal = bot.get_channel(data['canal'])
            if not canal or not data.get('titulo'):
                return

            cor = int(data.get('cor', '2b2d31'), 16)

            if data.get('msg_id'):
                try:
                    msg_antiga = await canal.fetch_message(data['msg_id'])
                    await msg_antiga.delete()
                except:
                    pass

            embed = disnake.Embed(
                title=f"📢 {data['titulo']}",
                description=data['desc'],
                color=cor
            )
            if data.get('imagem'):
                embed.set_image(url=data['imagem'])
            embed.set_footer(text=f"Auto-renovação | {nome} | Bot FFZ v3.1", icon_url=bot.user.avatar.url)

            msg = await canal.send(embed=embed)
            data['msg_id'] = msg.id

        data['task'] = renovar
        renovar.start()
        horas = int(data['tempo'])/3600
        await inter.response.send_message(f"Auto-renovação '{nome}' ativada a cada {horas}h ✅", ephemeral=True)

    @disnake.ui.button(label="6. Upar Imagem", style=disnake.ButtonStyle.secondary, emoji="🖼️", custom_id="upar_img")
    async def upar_imagem(self, button, inter):
        modal = ImagemModal(self.guild_id, self.nome)
        await inter.response.send_modal(modal)

    @disnake.ui.button(label="Parar Auto-Renovação", style=disnake.ButtonStyle.danger, emoji="⏹️", custom_id="parar")
    async def parar(self, button, inter):
        data = anuncio_data.get(self.guild_id, {}).get(self.nome)
        if data and data.get('task'):
            data['task'].cancel()
            data['task'] = None
            await inter.response.send_message(f"Auto-renovação '{self.nome}' parada ✅", ephemeral=True)
        else:
            await inter.response.send_message("Nenhuma renovação ativa", ephemeral=True)

class AnuncioModal(disnake.ui.Modal):
    def __init__(self, guild_id, nome):
        self.guild_id = guild_id
        self.nome = nome
        if guild_id not in anuncio_data:
            anuncio_data[guild_id] = {}
        if nome not in anuncio_data[guild_id]:
            anuncio_data[guild_id][nome] = {'canal': None, 'cor': '2b2d31', 'task': None, 'msg_id': None, 'imagem': None, 'tempo': None}

        components = [
            disnake.ui.TextInput(label="Título", custom_id="titulo", max_length=256, required=True),
            disnake.ui.TextInput(label="Descrição", custom_id="desc", style=disnake.TextInputStyle.paragraph, max_length=2000, required=True),
        ]
        super().__init__(title=f"Preencher: {nome}", components=components)

    async def callback(self, inter):
        anuncio_data[self.guild_id][self.nome]['titulo'] = inter.text_values['titulo']
        anuncio_data[self.guild_id][self.nome]['desc'] = inter.text_values['desc']
        await inter.response.send_message(f"Anúncio '{self.nome}' preenchido ✅", ephemeral=True)

class ImagemModal(disnake.ui.Modal):
    def __init__(self, guild_id, nome):
        self.guild_id = guild_id
        self.nome = nome
        if guild_id not in anuncio_data:
            anuncio_data[guild_id] = {}
        if nome not in anuncio_data[guild_id]:
            anuncio_data[guild_id][nome] = {'canal': None, 'cor': '2b2d31', 'task': None, 'msg_id': None, 'imagem': None, 'tempo': None}

        components = [
            disnake.ui.TextInput(
                label="URL da imagem ou anexe na mensagem",
                custom_id="url_img",
                required=False,
                placeholder="https://i.imgur.com/xxx.png"
            ),
        ]
        super().__init__(title=f"Upar Imagem: {nome}", components=components)

    async def callback(self, inter):
        url = inter.text_values['url_img']

        # Se anexou imagem na mensagem do modal
        if inter.message and inter.message.attachments:
            url = inter.message.attachments[0].url

        if not url:
            await inter.response.send_message("Manda URL ou anexa imagem junto do modal!", ephemeral=True)
            return

        anuncio_data[self.guild_id][self.nome]['imagem'] = url
        await inter.response.send_message(f"Imagem do '{self.nome}' atualizada ✅", ephemeral=True)

@bot.event
async def on_ready():
    print(f'✅ Bot online como {bot.user}')

    # PRA TESTE: cola ID de vários servidores aqui
    GUILD_IDS = [
        1511910291825492090, # Server 1 - teu principal
        1509287732063637646, # Server 2 - do amigo
        1465329771696361546,
        1512223172554919997 # Server 3 - server teste
    ]
    await bot.sync_commands(guild_ids=GUILD_IDS)
    print(f"Comandos sincronizados em {len(GUILD_IDS)} servidores")

    # Registra views pra não morrer no restart
    for guild_id, anuncios in anuncio_data.items():
        for nome in anuncios.keys():
            bot.add_view(PainelAnunciosView(guild_id, nome))

@bot.slash_command(description="Cria um painel de anúncio novo")
async def criar_anuncio(inter, nome: str, canal: disnake.TextChannel):
    if not inter.author.guild_permissions.administrator:
        await inter.response.send_message("Só admin pode usar", ephemeral=True)
        return

    if inter.guild.id not in anuncio_data:
        anuncio_data[inter.guild.id] = {}

    anuncio_data[inter.guild.id][nome] = {
        'canal': canal.id,
        'cor': '2b2d31',
        'task': None,
        'msg_id': None,
        'imagem': None,
        'tempo': None,
        'titulo': None,
        'desc': None
    }

    embed = disnake.Embed(
        title=f"📢 Painel: {nome}",
        description="""**1.** Escolha a cor
**2.** Preencha o anúncio
**3.** Envie agora
**4.** Escolha o tempo
**5.** Ative a renovação
**6.** Upar imagem

✨ 100% por painel | Auto-delete | Multi-anúncios""",
        color=0x2b2d31
    )
    embed.set_footer(text=f"Anúncio: {nome} | Servidor: {inter.guild.name}")

    view = PainelAnunciosView(inter.guild.id, nome)
    await inter.response.send_message(embed=embed, view=view)

@bot.event
async def on_select_option(inter: disnake.MessageInteraction):
    custom_id = inter.component.custom_id
    if custom_id.startswith("cor_select_"):
        nome = custom_id.replace("cor_select_", "")
        anuncio_data[inter.guild.id][nome]['cor'] = inter.values[0]
        await inter.response.send_message(f"Cor do '{nome}' definida ✅", ephemeral=True)
    elif custom_id.startswith("tempo_select_"):
        nome = custom_id.replace("tempo_select_", "")
        anuncio_data[inter.guild.id][nome]['tempo'] = inter.values[0]
        await inter.response.send_message(f"Tempo do '{nome}' definido ✅", ephemeral=True)

# FIX PRO RENDER - TROCA O BOT.RUN
if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("ERRO: DISCORD_TOKEN não encontrado nas variáveis de ambiente!")
    else:
        asyncio.run(bot.start(token))
