import os
import disnake
import time
import nest_asyncio
from disnake.ext import commands, tasks
from flask import Flask
from threading import Thread

nest_asyncio.apply()

app = Flask('')

@app.route('/')
def home():
    return "Bot de anúncios online v3.1"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, threaded=True)

intents = disnake.Intents.default()
intents.message_content = True
intents.guilds = True
bot = commands.Bot(command_prefix='!', intents=intents, test_guilds=[1511910291825492090]) # <- COLA TEU ID AQUI

anuncio_data = {}

class CorSelect(disnake.ui.Select):
    def __init__(self, nome):
        options = [
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
        super().__init__(placeholder="1. Escolha a cor do embed", custom_id=f"cor_{nome}", options=options)

    async def callback(self, inter):
        anuncio_data[inter.guild.id][self.custom_id.replace("cor_", "")]['cor'] = self.values[0]
        await inter.response.send_message(f"Cor definida ✅", ephemeral=True)

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
        self.add_item(CorSelect(nome))
        self.add_item(TempoSelect(nome))

    @disnake.ui.button(label="2. Preencher Anúncio", style=disnake.ButtonStyle.primary, emoji="🎨")
    async def preencher(self, button, inter):
        await inter.response.send_modal(AnuncioModal(self.guild_id, self.nome))

    @disnake.ui.button(label="3. Enviar Agora", style=disnake.ButtonStyle.success, emoji="📢")
    async def enviar(self, button, inter):
        await inter.response.defer(ephemeral=True) # <- FIX: responde antes dos 3s
        data = anuncio_data.get(self.guild_id, {}).get(self.nome)
        if not data or not data.get('titulo'):
            await inter.edit_original_response(content="Preenche o anúncio primeiro!")
            return

        canal = bot.get_channel(data['canal'])
        cor = int(data.get('cor', '2b2d31'), 16)

        if data.get('msg_id'):
            try:
                msg_antiga = await canal.fetch_message(data['msg_id'])
                await msg_antiga.delete()
            except:
                pass

        embed = disnake.Embed(title=f"📢 {data['titulo']}", description=data['desc'], color=cor)
        if data.get('imagem'):
            embed.set_image(url=data['imagem'])
        embed.set_footer(text=f"Anúncio: {self.nome} | Bot FFZ v3.1", icon_url=bot.user.avatar.url)

        msg = await canal.send(embed=embed)
        data['msg_id'] = msg.id
        await inter.edit_original_response(content=f"Anúncio '{self.nome}' enviado ✅")

    @disnake.ui.button(label="5. Ativar Auto-Renovação", style=disnake.ButtonStyle.success, emoji="🔄")
    async def ativar(self, button, inter):
        await inter.response.defer(ephemeral=True) # <- FIX
        data = anuncio_data.get(self.guild_id, {}).get(self.nome)
        if not data or not data.get('tempo'):
            await inter.edit_original_response(content="Escolha o tempo primeiro!")
            return

        if data.get('task'):
            data['task'].cancel()

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
            embed = disnake.Embed(title=f"📢 {data['titulo']}", description=data['desc'], color=cor)
            if data.get('imagem'):
                embed.set_image(url=data['imagem'])
            embed.set_footer(text=f"Auto-renovação | {self.nome} | Bot FFZ v3.1", icon_url=bot.user.avatar.url)
            msg = await canal.send(embed=embed)
            data['msg_id'] = msg.id

        data['task'] = renovar
        renovar.start()
        horas = int(data['tempo'])/3600
        await inter.edit_original_response(content=f"Auto-renovação ativada a cada {horas}h ✅")

    @disnake.ui.button(label="6. Upar Imagem", style=disnake.ButtonStyle.secondary, emoji="🖼️")
    async def upar_imagem(self, button, inter):
        await inter.response.send_modal(ImagemModal(self.guild_id, self.nome))

    @disnake.ui.button(label="Parar Auto-Renovação", style=disnake.ButtonStyle.danger, emoji="⏹️")
    async def parar(self, button, inter):
        data = anuncio_data.get(self.guild_id, {}).get(self.nome)
        if data and data.get('task'):
            data['task'].cancel()
            data['task'] = None
            await inter.response.send_message(f"Auto-renovação parada ✅", ephemeral=True)
        else:
            await inter.response.send_message("Nenhuma renovação ativa", ephemeral=True)

class AnuncioModal(disnake.ui.Modal):
    def __init__(self, guild_id, nome):
        self.guild_id = guild_id
        self.nome = nome
        if guild_id not in anuncio_data:
            anuncio_data[guild_id] = {}
        if nome not in anuncio_data[guild_id]:
            anuncio_data[guild_id][nome] = {'canal': None, 'cor': '2b2d31', 'task': None, 'msg_id': None, 'imagem': None, 'tempo': None, 'titulo': None, 'desc': None}

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
            anuncio_data[guild_id][nome] = {'canal': None, 'cor': '2b2d31', 'task': None, 'msg_id': None, 'imagem': None, 'tempo': None, 'titulo': None, 'desc': None}

        components = [
            disnake.ui.TextInput(label="URL da imagem", custom_id="url_img", required=False, placeholder="https://i.imgur.com/xxx.png"),
        ]
        super().__init__(title=f"Upar Imagem: {nome}", components=components)

    async def callback(self, inter):
        url = inter.text_values['url_img']
        if inter.message and inter.message.attachments:
            url = inter.message.attachments[0].url
        if not url:
            await inter.response.send_message("Manda URL ou anexa imagem!", ephemeral=True)
            return
        anuncio_data[self.guild_id][self.nome]['imagem'] = url
        await inter.response.send_message(f"Imagem atualizada ✅", ephemeral=True)

@bot.event
async def on_ready():
    print(f'✅ Bot online como {bot.user}')
    print("Comandos sync instantâneo no server de teste")

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
        'canal': canal.id, 'cor': '2b2d31', 'task': None, 'msg_id': None,
        'imagem': None, 'tempo': None, 'titulo': None, 'desc': None
    }

    embed = disnake.Embed(
        title=f"📢 Painel: {nome}",
        description="**1.** Escolha a cor\n**2.** Preencha o anúncio\n**3.** Envie agora\n**4.** Escolha o tempo\n**5.** Ative a renovação\n**6.** Upar imagem",
        color=0x2b2d31
    )
    embed.set_footer(text=f"Anúncio: {nome}")
    view = PainelAnunciosView(inter.guild.id, nome)
    await inter.response.send_message(embed=embed, view=view)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    Thread(target=run_flask, daemon=True).start()
    time.sleep(3)
    print(f"Flask rodando na porta {port}")
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("ERRO: DISCORD_TOKEN não encontrado!")
    else:
        bot.run(token)
