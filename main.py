import os
import disnake
import time
import asyncio
from disnake.ext import commands, tasks
from flask import Flask
from threading import Thread
from waitress import serve

app = Flask('')

@app.route('/')
def home():
    return "Bot de anúncios v4.5 - 2 Embeds ONLINE", 200

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    print(f"Flask iniciando na porta {port}")
    serve(app, host='0.0.0.0', port=port, threads=6)

intents = disnake.Intents.default()
intents.message_content = True
intents.guilds = True

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

bot = commands.Bot(command_prefix='!', intents=intents, test_guilds=[1511910291825492090])

anuncio_data = {}

class CorSelect(disnake.ui.Select):
    def __init__(self, nome, embed_num):
        options = [
            disnake.SelectOption(label="Vermelho", value="ff0000"),
            disnake.SelectOption(label="Verde", value="00ff00"),
            disnake.SelectOption(label="Azul", value="0000ff"),
            disnake.SelectOption(label="Amarelo", value="ffff00"),
            disnake.SelectOption(label="Roxo", value="800080"),
            disnake.SelectOption(label="Cinza", value="808080"),
            disnake.SelectOption(label="Rosa", value="ff69b4"),
            disnake.SelectOption(label="Marrom", value="8b4513"),
            disnake.SelectOption(label="Preto", value="000000"),
            disnake.SelectOption(label="Laranja", value="ff8c00"),
            disnake.SelectOption(label="Ciano", value="00ffff"),
            disnake.SelectOption(label="Branco", value="ffffff"),
        ]
        super().__init__(placeholder=f"1.{embed_num} Cor Embed {embed_num}", custom_id=f"cor_{nome}_{embed_num}", options=options)

    async def callback(self, inter):
        parts = self.custom_id.replace("cor_", "").rsplit("_", 1)
        nome, num = parts[0], parts[1]
        anuncio_data[inter.guild.id][nome][f'cor{num}'] = self.values[0]
        await inter.response.send_message(f"Cor Embed {num} definida ✅", ephemeral=True)

class TempoSelect(disnake.ui.Select):
    def __init__(self, nome):
        options = [
            disnake.SelectOption(label="30 minutos", value="1800"),
            disnake.SelectOption(label="1 hora", value="3600"),
            disnake.SelectOption(label="6 horas", value="21600"),
            disnake.SelectOption(label="12 horas", value="43200"),
            disnake.SelectOption(label="24 horas", value="86400"),
        ]
        super().__init__(placeholder="4. Auto-renovação", custom_id=f"tempo_{nome}", options=options)

    async def callback(self, inter):
        anuncio_data[inter.guild.id][self.custom_id.replace("tempo_", "")]['tempo'] = self.values[0]
        await inter.response.send_message(f"Tempo definido ✅", ephemeral=True)

class PainelAnunciosView(disnake.ui.View):
    def __init__(self, guild_id, nome):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.nome = nome
        self.add_item(CorSelect(nome, "1"))
        self.add_item(CorSelect(nome, "2"))
        self.add_item(TempoSelect(nome))

    @disnake.ui.button(label="2.1 Preencher Embed 1", style=disnake.ButtonStyle.primary, emoji="1️⃣")
    async def preencher1(self, button, inter):
        await inter.response.send_modal(AnuncioModal(self.guild_id, self.nome, "1"))

    @disnake.ui.button(label="2.2 Preencher Embed 2", style=disnake.ButtonStyle.primary, emoji="2️⃣")
    async def preencher2(self, button, inter):
        await inter.response.send_modal(AnuncioModal(self.guild_id, self.nome, "2"))

    @disnake.ui.button(label="3. Enviar Ambos", style=disnake.ButtonStyle.success, emoji="📢")
    async def enviar(self, button, inter):
        await inter.response.defer(ephemeral=True)
        data = anuncio_data.get(self.guild_id, {}).get(self.nome)
        if not data or not data.get('titulo1'):
            await inter.edit_original_response(content="Preenche o Embed 1 primeiro!")
            return

        canal = bot.get_channel(data['canal'])
        cor1 = int(data.get('cor1', '2b2d31'), 16)
        cor2 = int(data.get('cor2', '2b2d31'), 16)

        for msg_id_key in ['msg_id1', 'msg_id2']:
            if data.get(msg_id_key):
                try:
                    msg_antiga = await canal.fetch_message(data[msg_id_key])
                    await msg_antiga.delete()
                except:
                    pass

        embed1 = disnake.Embed(title=f"📢 {data['titulo1']}", description=data['desc1'], color=cor1)
        if data.get('imagem1'):
            embed1.set_image(url=data['imagem1'])
        embed1.set_footer(text=f"Embed 1 | {self.nome} | v4.5", icon_url=bot.user.avatar.url)
        msg1 = await canal.send(embed=embed1)
        data['msg_id1'] = msg1.id

        if data.get('titulo2'):
            embed2 = disnake.Embed(title=f"📢 {data['titulo2']}", description=data['desc2'], color=cor2)
            if data.get('imagem2'):
                embed2.set_image(url=data['imagem2'])
            embed2.set_footer(text=f"Embed 2 | {self.nome} | v4.5", icon_url=bot.user.avatar.url)
            msg2 = await canal.send(embed=embed2)
            data['msg_id2'] = msg2.id

        await inter.edit_original_response(content=f"Ambos anúncios '{self.nome}' enviados ✅")

    @disnake.ui.button(label="5. Ativar Auto-Renovação", style=disnake.ButtonStyle.success, emoji="🔄")
    async def ativar(self, button, inter):
        await inter.response.defer(ephemeral=True)
        data = anuncio_data.get(self.guild_id, {}).get(self.nome)
        if not data or not data.get('tempo'):
            await inter.edit_original_response(content="Escolha o tempo primeiro!")
            return

        if data.get('task'):
            data['task'].cancel()

        @tasks.loop(seconds=int(data['tempo']))
        async def renovar():
            canal = bot.get_channel(data['canal'])
            if not canal or not data.get('titulo1'):
                return
            cor1 = int(data.get('cor1', '2b2d31'), 16)
            cor2 = int(data.get('cor2', '2b2d31'), 16)

            for msg_id_key in ['msg_id1', 'msg_id2']:
                if data.get(msg_id_key):
                    try:
                        msg_antiga = await canal.fetch_message(data[msg_id_key])
                        await msg_antiga.delete()
                    except:
                        pass

            embed1 = disnake.Embed(title=f"📢 {data['titulo1']}", description=data['desc1'], color=cor1)
            if data.get('imagem1'):
                embed1.set_image(url=data['imagem1'])
            embed1.set_footer(text=f"Auto | Embed 1 | {self.nome}", icon_url=bot.user.avatar.url)
            msg1 = await canal.send(embed=embed1)
            data['msg_id1'] = msg1.id

            if data.get('titulo2'):
                embed2 = disnake.Embed(title=f"📢 {data['titulo2']}", description=data['desc2'], color=cor2)
                if data.get('imagem2'):
                    embed2.set_image(url=data['imagem2'])
                embed2.set_footer(text=f"Auto | Embed 2 | {self.nome}", icon_url=bot.user.avatar.url)
                msg2 = await canal.send(embed=embed2)
                data['msg_id2'] = msg2.id

        data['task'] = renovar
        renovar.start()
        horas = int(data['tempo']) / 3600
        await inter.edit_original_response(content=f"Auto-renovação ativada a cada {horas}h ✅")

    @disnake.ui.button(label="6.1 Upar Imagem 1", style=disnake.ButtonStyle.secondary, emoji="🖼️")
    async def upar_imagem1(self, button, inter):
        await inter.response.send_modal(ImagemModal(self.guild_id, self.nome, "1"))

    @disnake.ui.button(label="6.2 Upar Imagem 2", style=disnake.ButtonStyle.secondary, emoji="🖼️")
    async def upar_imagem2(self, button, inter):
        await inter.response.send_modal(ImagemModal(self.guild_id, self.nome, "2"))

    @disnake.ui.button(label="Parar Auto-Renovação", style=disnake.ButtonStyle.danger, emoji="⏹️", row=2)
    async def parar(self, button, inter):
        data = anuncio_data.get(self.guild_id, {}).get(self.nome)
        if data and data.get('task'):
            data['task'].cancel()
            data['task'] = None
            await inter.response.send_message(f"Auto-renovação parada ✅", ephemeral=True)
        else:
            await inter.response.send_message("Nenhuma renovação ativa", ephemeral=True)

    @disnake.ui.button(label="🗑️ Apagar Anúncio", style=disnake.ButtonStyle.danger, row=2)
    async def apagar_anuncio(self, button, inter):
        await inter.response.send_modal(ApagarAnuncioModal(self.guild_id))

class ApagarAnuncioModal(disnake.ui.Modal):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        anuncios = anuncio_data.get(guild_id, {})
        lista = ", ".join(anuncios.keys()) if anuncios else "Nenhum anúncio criado"
        components = [
            disnake.ui.TextInput(
                label="Nome do anúncio para apagar",
                custom_id="nome_apagar",
                placeholder=f"Anúncios: {lista}",
                max_length=100,
                required=True
            ),
        ]
        super().__init__(title="🗑️ Apagar Anúncio", components=components)

    async def callback(self, inter):
        nome = inter.text_values['nome_apagar'].strip()
        guild_anuncios = anuncio_data.get(self.guild_id, {})

        if nome not in guild_anuncios:
            anuncios_disponiveis = ", ".join(guild_anuncios.keys()) if guild_anuncios else "nenhum"
            await inter.response.send_message(
                f"❌ Anúncio **{nome}** não encontrado!\nDisponíveis: `{anuncios_disponiveis}`",
                ephemeral=True
            )
            return

        data = guild_anuncios[nome]

        # Para a renovação se estiver ativa
        if data.get('task'):
            data['task'].cancel()

        # Apaga as mensagens do canal
        canal = bot.get_channel(data['canal'])
        if canal:
            for msg_id_key in ['msg_id1', 'msg_id2']:
                if data.get(msg_id_key):
                    try:
                        msg = await canal.fetch_message(data[msg_id_key])
                        await msg.delete()
                    except:
                        pass

        # Remove dos dados
        del anuncio_data[self.guild_id][nome]
        await inter.response.send_message(f"✅ Anúncio **{nome}** apagado com sucesso!", ephemeral=True)

class AnuncioModal(disnake.ui.Modal):
    def __init__(self, guild_id, nome, num):
        self.guild_id = guild_id
        self.nome = nome
        self.num = num
        if guild_id not in anuncio_data:
            anuncio_data[guild_id] = {}
        if nome not in anuncio_data[guild_id]:
            anuncio_data[guild_id][nome] = {
                'canal': None, 'cor1': '2b2d31', 'cor2': '2b2d31', 'task': None,
                'msg_id1': None, 'msg_id2': None, 'imagem1': None, 'imagem2': None,
                'tempo': None, 'titulo1': None, 'desc1': None, 'titulo2': None, 'desc2': None
            }
        components = [
            disnake.ui.TextInput(label=f"Título Embed {num}", custom_id="titulo", max_length=256, required=True),
            disnake.ui.TextInput(label=f"Descrição Embed {num}", custom_id="desc", style=disnake.TextInputStyle.paragraph, max_length=2000, required=True),
        ]
        super().__init__(title=f"Preencher Embed {num}: {nome}", components=components)

    async def callback(self, inter):
        anuncio_data[self.guild_id][self.nome][f'titulo{self.num}'] = inter.text_values['titulo']
        anuncio_data[self.guild_id][self.nome][f'desc{self.num}'] = inter.text_values['desc']
        await inter.response.send_message(f"Embed {self.num} preenchido ✅", ephemeral=True)

class ImagemModal(disnake.ui.Modal):
    def __init__(self, guild_id, nome, num):
        self.guild_id = guild_id
        self.nome = nome
        self.num = num
        if guild_id not in anuncio_data:
            anuncio_data[guild_id] = {}
        if nome not in anuncio_data[guild_id]:
            anuncio_data[guild_id][nome] = {
                'canal': None, 'cor1': '2b2d31', 'cor2': '2b2d31', 'task': None,
                'msg_id1': None, 'msg_id2': None, 'imagem1': None, 'imagem2': None,
                'tempo': None, 'titulo1': None, 'desc1': None, 'titulo2': None, 'desc2': None
            }
        components = [
            disnake.ui.TextInput(label=f"URL Imagem {num}", custom_id="url_img", required=False, placeholder="https://i.imgur.com/xxx.png"),
        ]
        super().__init__(title=f"Upar Imagem {num}: {nome}", components=components)

    async def callback(self, inter):
        url = inter.text_values['url_img']
        if inter.message and inter.message.attachments:
            url = inter.message.attachments[0].url
        if not url:
            await inter.response.send_message("Manda URL ou anexa imagem!", ephemeral=True)
            return
        anuncio_data[self.guild_id][self.nome][f'imagem{self.num}'] = url
        await inter.response.send_message(f"Imagem {self.num} atualizada ✅", ephemeral=True)

@bot.event
async def on_ready():
    print(f'✅ Bot online como {bot.user}')
    print('v4.5 - 2 Embeds carregado')
    for guild_id, anuncios in anuncio_data.items():
        for nome in anuncios.keys():
            bot.add_view(PainelAnunciosView(guild_id, nome))

@bot.slash_command(description="Cria painel com 2 embeds")
async def criar_anuncio(inter, nome: str, canal: disnake.TextChannel):
    if not inter.author.guild_permissions.administrator:
        await inter.response.send_message("Só admin pode usar", ephemeral=True)
        return

    if inter.guild.id not in anuncio_data:
        anuncio_data[inter.guild.id] = {}

    anuncio_data[inter.guild.id][nome] = {
        'canal': canal.id, 'cor1': '2b2d31', 'cor2': '2b2d31', 'task': None,
        'msg_id1': None, 'msg_id2': None, 'imagem1': None, 'imagem2': None,
        'tempo': None, 'titulo1': None, 'desc1': None, 'titulo2': None, 'desc2': None
    }

    embed = disnake.Embed(
        title=f"📢 Painel v4.5: {nome}",
        description="**1.1/1.2** Cor Embed 1 e 2\n**2.1** Preencher Embed 1\n**2.2** Preencher Embed 2\n**3** Enviar Ambos\n**4** Tempo\n**5** Ativar Renovação\n**6.1/6.2** Imagem 1 e 2",
        color=0x2b2d31
    )
    embed.set_footer(text=f"Anúncio: {nome}")
    view = PainelAnunciosView(inter.guild.id, nome)
    await inter.response.send_message(embed=embed, view=view)

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("ERRO: DISCORD_TOKEN não encontrado!")
        exit(1)

    Thread(target=run_flask, daemon=True).start()
    time.sleep(2)

    bot.run(token)
    
