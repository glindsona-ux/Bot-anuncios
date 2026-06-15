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
    return "Bot de anúncios v5.0 - Multi Anúncios ONLINE", 200

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    print(f"Flask iniciando na porta {port}")
    serve(app, host='0.0.0.0', port=port, threads=6)

intents = disnake.Intents.default()
intents.message_content = True
intents.guilds = True

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

bot = commands.Bot(command_prefix='!', intents=intents)

# { guild_id: { nome: { canal, cor, titulo, desc, imagem, tempo, msg_id, task } } }
anuncio_data = {}


class CorSelect(disnake.ui.Select):
    def __init__(self, nome):
        options = [
            disnake.SelectOption(label="Vermelho",  value="ff0000"),
            disnake.SelectOption(label="Verde",     value="00ff00"),
            disnake.SelectOption(label="Azul",      value="0000ff"),
            disnake.SelectOption(label="Amarelo",   value="ffff00"),
            disnake.SelectOption(label="Roxo",      value="800080"),
            disnake.SelectOption(label="Cinza",     value="808080"),
            disnake.SelectOption(label="Rosa",      value="ff69b4"),
            disnake.SelectOption(label="Marrom",    value="8b4513"),
            disnake.SelectOption(label="Preto",     value="000000"),
            disnake.SelectOption(label="Laranja",   value="ff8c00"),
            disnake.SelectOption(label="Ciano",     value="00ffff"),
            disnake.SelectOption(label="Branco",    value="ffffff"),
        ]
        super().__init__(placeholder="1. Cor da Embed", custom_id=f"cor_{nome}", options=options)

    async def callback(self, inter):
        nome = self.custom_id.replace("cor_", "")
        anuncio_data[inter.guild.id][nome]['cor'] = self.values[0]
        await inter.response.send_message("Cor definida ✅", ephemeral=True)


class TempoSelect(disnake.ui.Select):
    def __init__(self, nome):
        options = [
            disnake.SelectOption(label="30 minutos", value="1800"),
            disnake.SelectOption(label="1 hora",     value="3600"),
            disnake.SelectOption(label="6 horas",    value="21600"),
            disnake.SelectOption(label="12 horas",   value="43200"),
            disnake.SelectOption(label="24 horas",   value="86400"),
        ]
        super().__init__(placeholder="3. Tempo de renovação", custom_id=f"tempo_{nome}", options=options)

    async def callback(self, inter):
        nome = self.custom_id.replace("tempo_", "")
        anuncio_data[inter.guild.id][nome]['tempo'] = self.values[0]
        await inter.response.send_message("Tempo definido ✅", ephemeral=True)


class PainelView(disnake.ui.View):
    def __init__(self, guild_id, nome):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.nome = nome
        self.add_item(CorSelect(nome))
        self.add_item(TempoSelect(nome))

    @disnake.ui.button(label="2. Preencher Embed", style=disnake.ButtonStyle.primary, emoji="✏️", row=2)
    async def preencher(self, button, inter):
        await inter.response.send_modal(AnuncioModal(self.guild_id, self.nome))

    @disnake.ui.button(label="4. Upar Imagem", style=disnake.ButtonStyle.secondary, emoji="🖼️", row=2)
    async def upar_imagem(self, button, inter):
        await inter.response.send_modal(ImagemModal(self.guild_id, self.nome))

    @disnake.ui.button(label="5. Enviar Anúncio", style=disnake.ButtonStyle.success, emoji="📢", row=2)
    async def enviar(self, button, inter):
        await inter.response.defer(ephemeral=True)
        data = anuncio_data.get(self.guild_id, {}).get(self.nome)
        if not data or not data.get('titulo'):
            await inter.edit_original_response(content="Preenche a embed primeiro!")
            return

        canal = bot.get_channel(data['canal'])
        if not canal:
            await inter.edit_original_response(content="Canal não encontrado!")
            return

        # Apaga mensagem antiga se existir
        if data.get('msg_id'):
            try:
                msg_antiga = await canal.fetch_message(data['msg_id'])
                await msg_antiga.delete()
            except:
                pass

        cor = int(data.get('cor', '2b2d31'), 16)
        embed = disnake.Embed(title=f"📢 {data['titulo']}", description=data['desc'], color=cor)
        if data.get('imagem'):
            embed.set_image(url=data['imagem'])
        embed.set_footer(text=f"{self.nome} | v5.0", icon_url=bot.user.avatar.url)

        msg = await canal.send(embed=embed)
        data['msg_id'] = msg.id
        await inter.edit_original_response(content=f"Anúncio **{self.nome}** enviado ✅")

    @disnake.ui.button(label="6. Ativar Renovação", style=disnake.ButtonStyle.success, emoji="🔄", row=3)
    async def ativar(self, button, inter):
        await inter.response.defer(ephemeral=True)
        data = anuncio_data.get(self.guild_id, {}).get(self.nome)
        if not data or not data.get('tempo'):
            await inter.edit_original_response(content="Escolha o tempo primeiro!")
            return
        if not data.get('titulo'):
            await inter.edit_original_response(content="Preenche a embed primeiro!")
            return

        if data.get('task'):
            data['task'].cancel()

        guild_id = self.guild_id
        nome = self.nome

        @tasks.loop(seconds=int(data['tempo']))
        async def renovar():
            d = anuncio_data.get(guild_id, {}).get(nome)
            if not d or not d.get('titulo'):
                return
            canal = bot.get_channel(d['canal'])
            if not canal:
                return

            if d.get('msg_id'):
                try:
                    msg_antiga = await canal.fetch_message(d['msg_id'])
                    await msg_antiga.delete()
                except:
                    pass

            cor = int(d.get('cor', '2b2d31'), 16)
            embed = disnake.Embed(title=f"📢 {d['titulo']}", description=d['desc'], color=cor)
            if d.get('imagem'):
                embed.set_image(url=d['imagem'])
            embed.set_footer(text=f"Auto | {nome} | v5.0", icon_url=bot.user.avatar.url)

            msg = await canal.send(embed=embed)
            d['msg_id'] = msg.id

        data['task'] = renovar
        renovar.start()
        horas = int(data['tempo']) / 3600
        await inter.edit_original_response(content=f"Renovação ativada a cada {horas}h ✅")

    @disnake.ui.button(label="Parar Renovação", style=disnake.ButtonStyle.danger, emoji="⏹️", row=3)
    async def parar(self, button, inter):
        data = anuncio_data.get(self.guild_id, {}).get(self.nome)
        if data and data.get('task'):
            data['task'].cancel()
            data['task'] = None
            await inter.response.send_message("Renovação parada ✅", ephemeral=True)
        else:
            await inter.response.send_message("Nenhuma renovação ativa", ephemeral=True)

    @disnake.ui.button(label="🗑️ Apagar Anúncio", style=disnake.ButtonStyle.danger, row=3)
    async def apagar(self, button, inter):
        await inter.response.send_modal(ApagarModal(self.guild_id))


class AnuncioModal(disnake.ui.Modal):
    def __init__(self, guild_id, nome):
        self.guild_id = guild_id
        self.nome = nome
        components = [
            disnake.ui.TextInput(label="Título", custom_id="titulo", max_length=256, required=True),
            disnake.ui.TextInput(label="Descrição", custom_id="desc", style=disnake.TextInputStyle.paragraph, max_length=2000, required=True),
        ]
        super().__init__(title=f"Preencher: {nome}", components=components)

    async def callback(self, inter):
        anuncio_data[self.guild_id][self.nome]['titulo'] = inter.text_values['titulo']
        anuncio_data[self.guild_id][self.nome]['desc']   = inter.text_values['desc']
        await inter.response.send_message("Embed preenchida ✅", ephemeral=True)


class ImagemModal(disnake.ui.Modal):
    def __init__(self, guild_id, nome):
        self.guild_id = guild_id
        self.nome = nome
        components = [
            disnake.ui.TextInput(label="URL da Imagem", custom_id="url_img", required=False, placeholder="https://i.imgur.com/xxx.png"),
        ]
        super().__init__(title=f"Imagem: {nome}", components=components)

    async def callback(self, inter):
        url = inter.text_values['url_img'].strip()
        if not url:
            await inter.response.send_message("Manda uma URL válida!", ephemeral=True)
            return
        anuncio_data[self.guild_id][self.nome]['imagem'] = url
        await inter.response.send_message("Imagem atualizada ✅", ephemeral=True)


class ApagarModal(disnake.ui.Modal):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        anuncios = anuncio_data.get(guild_id, {})
        lista = ", ".join(anuncios.keys()) if anuncios else "Nenhum anúncio"
        components = [
            disnake.ui.TextInput(
                label="Nome do anúncio para apagar",
                custom_id="nome_apagar",
                placeholder=f"Criados: {lista}",
                max_length=100,
                required=True
            ),
        ]
        super().__init__(title="🗑️ Apagar Anúncio", components=components)

    async def callback(self, inter):
        nome = inter.text_values['nome_apagar'].strip()
        guild_anuncios = anuncio_data.get(self.guild_id, {})

        if nome not in guild_anuncios:
            lista = ", ".join(guild_anuncios.keys()) if guild_anuncios else "nenhum"
            await inter.response.send_message(
                f"❌ **{nome}** não encontrado!\nDisponíveis: `{lista}`",
                ephemeral=True
            )
            return

        data = guild_anuncios[nome]

        if data.get('task'):
            data['task'].cancel()

        canal = bot.get_channel(data['canal'])
        if canal and data.get('msg_id'):
            try:
                msg = await canal.fetch_message(data['msg_id'])
                await msg.delete()
            except:
                pass

        del anuncio_data[self.guild_id][nome]
        await inter.response.send_message(f"✅ Anúncio **{nome}** apagado!", ephemeral=True)


@bot.event
async def on_ready():
    print(f'✅ Bot online como {bot.user}')
    print('v5.0 - Multi Anúncios carregado')
    for guild_id, anuncios in anuncio_data.items():
        for nome in anuncios.keys():
            bot.add_view(PainelView(guild_id, nome))


@bot.slash_command(description="Cria um novo anúncio com auto-renovação")
async def criar_anuncio(inter, nome: str, canal: disnake.TextChannel):
    if not inter.author.guild_permissions.administrator:
        await inter.response.send_message("Só admin pode usar!", ephemeral=True)
        return

    await inter.response.defer(ephemeral=False)

    if inter.guild.id not in anuncio_data:
        anuncio_data[inter.guild.id] = {}

    if nome in anuncio_data[inter.guild.id]:
        await inter.edit_original_response(content=f"❌ Já existe um anúncio com o nome **{nome}**!")
        return

    anuncio_data[inter.guild.id][nome] = {
        'canal': canal.id, 'cor': '2b2d31', 'titulo': None,
        'desc': None, 'imagem': None, 'tempo': None,
        'msg_id': None, 'task': None
    }

    embed = disnake.Embed(
        title=f"📢 Anúncio: {nome}",
        description=(
            "**1.** Escolha a cor\n"
            "**2.** Preencha o conteúdo\n"
            "**3.** Escolha o tempo de renovação\n"
            "**4.** Upar imagem (opcional)\n"
            "**5.** Enviar no canal\n"
            "**6.** Ativar renovação automática"
        ),
        color=0x2b2d31
    )
    embed.set_footer(text=f"Canal: #{canal.name} | ID: {nome}")
    view = PainelView(inter.guild.id, nome)
    await inter.edit_original_response(embed=embed, view=view)


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("ERRO: DISCORD_TOKEN não encontrado!")
        exit(1)

    Thread(target=run_flask, daemon=True).start()
    time.sleep(2)

    bot.run(token)
                  
