from flask import Flask, render_template, request, redirect
import os
import secrets
import requests
import tzdata
import click
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from user_agents import parse
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required
)
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from database import db

from models.segmento import Segmento
from models.campanha import Campanha
from models.clique import Clique
from models.contato import Contato
from models.campanha_contato import CampanhaContato
from models.usuario import Usuario

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

with app.app_context():
    db.create_all()

    if Usuario.query.count() == 0:

        admin_username = os.getenv("ADMIN_USERNAME")
        admin_password = os.getenv("ADMIN_PASSWORD")

        if admin_username and admin_password:

            usuario_inicial = Usuario(
                username=admin_username,
                senha_hash=generate_password_hash(admin_password)
            )

            db.session.add(usuario_inicial)
            db.session.commit()

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


# ===========================
# LOGIN
# ===========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        senha = request.form["senha"]

        usuario = Usuario.query.filter_by(username=username).first()

        if usuario and check_password_hash(usuario.senha_hash, senha):

            login_user(usuario)

            next_url = request.args.get("next")

            if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)

            return redirect("/")

        return render_template(
            "login.html",
            erro="Usuário ou senha inválidos."
        )

    return render_template("login.html")


@app.route("/logout")
def logout():
    logout_user()
    return redirect("/login")


# ===========================
# FILTROS DE TEMPLATE
# ===========================

@app.template_filter("brasilia")
def formatar_brasilia(valor, formato="%d/%m/%Y %H:%M:%S"):

    if valor is None:
        return "-"

    horario_utc = valor.replace(tzinfo=timezone.utc)
    horario_brasilia = horario_utc.astimezone(ZoneInfo("America/Sao_Paulo"))

    return horario_brasilia.strftime(formato)


# ===========================
# DASHBOARD
# ===========================

@app.route("/")
@login_required
def dashboard():

    total_segmentos = Segmento.query.count()
    total_contatos = Contato.query.count()
    total_campanhas = Campanha.query.count()
    total_cliques = Clique.query.count()

    return render_template(
        "dashboard.html",
        segmentos=total_segmentos,
        contatos=total_contatos,
        campanhas=total_campanhas,
        cliques=total_cliques
    )


# ===========================
# SEGMENTOS
# ===========================

@app.route("/segmentos", methods=["GET", "POST"])
@login_required
def segmentos():

    if request.method == "POST":

        novo = Segmento(
            nome=request.form["nome"]
        )

        db.session.add(novo)
        db.session.commit()

        return redirect("/segmentos")

    lista = Segmento.query.all()

    erro = request.args.get("erro")

    return render_template(
        "segmentos.html",
        segmentos=lista,
        erro=erro
    )


@app.route("/segmentos/excluir/<int:id>")
@login_required
def excluir_segmento(id):

    segmento = Segmento.query.get_or_404(id)

    tem_contatos = Contato.query.filter_by(
        segmento_id=id
    ).count()

    if tem_contatos > 0:
        return redirect("/segmentos?erro=vinculado")

    db.session.delete(segmento)
    db.session.commit()

    return redirect("/segmentos")


# ===========================
# CONTATOS
# ===========================

@app.route("/contatos", methods=["GET", "POST"])
@login_required
def contatos():

    if request.method == "POST":

        contato = Contato(
            nome=request.form["nome"],
            telefone=request.form["telefone"],
            cargo=request.form["cargo"],
            segmento_id=request.form["segmento"]
        )

        db.session.add(contato)
        db.session.commit()

        return redirect("/contatos")

    lista_contatos = Contato.query.all()
    lista_segmentos = Segmento.query.all()

    erro = request.args.get("erro")

    return render_template(
        "contatos.html",
        contatos=lista_contatos,
        segmentos=lista_segmentos,
        erro=erro
    )


@app.route("/contatos/excluir/<int:id>")
@login_required
def excluir_contato(id):

    contato = Contato.query.get_or_404(id)

    tem_campanhas = CampanhaContato.query.filter_by(
        contato_id=id
    ).count()

    if tem_campanhas > 0:
        return redirect("/contatos?erro=vinculado")

    db.session.delete(contato)
    db.session.commit()

    return redirect("/contatos")


# ===========================
# CAMPANHAS
# ===========================

@app.route("/campanhas", methods=["GET", "POST"])
@login_required
def campanhas():

    if request.method == "POST":

        titulo = request.form["titulo"]
        destino = request.form["destino"]
        segmento_id = request.form["segmento"]

        codigo = secrets.token_hex(3)

        campanha = Campanha(
            titulo=titulo,
            destino=destino,
            codigo=codigo
        )

        db.session.add(campanha)
        db.session.commit()

        contatos = Contato.query.filter_by(
            segmento_id=segmento_id
        ).all()

        for contato in contatos:

            codigo_individual = secrets.token_hex(3)

            relacionamento = CampanhaContato(
                campanha_id=campanha.id,
                contato_id=contato.id,
                codigo=codigo_individual
            )

            db.session.add(relacionamento)

        db.session.commit()

        return redirect("/campanhas")

    lista = Campanha.query.all()
    lista_segmentos = Segmento.query.all()

    return render_template(
        "campanhas.html",
        campanhas=lista,
        segmentos=lista_segmentos
    )


@app.route("/campanhas/excluir/<int:id>")
@login_required
def excluir_campanha(id):

    campanha = Campanha.query.get_or_404(id)

    Clique.query.filter_by(campanha_id=id).delete()
    CampanhaContato.query.filter_by(campanha_id=id).delete()

    db.session.delete(campanha)
    db.session.commit()

    return redirect("/campanhas")


# ===========================
# LINK RASTREÁVEL
# ===========================

@app.route("/r/<codigo>")
def abrir_link(codigo):

    relacionamento = CampanhaContato.query.filter_by(
        codigo=codigo
    ).first()

    if not relacionamento:
        return "Link inválido."

    campanha = Campanha.query.get(
        relacionamento.campanha_id
    )

    # User Agent
    user_agent_string = request.headers.get("User-Agent", "")
    user_agent = parse(user_agent_string)

    # IP real
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    if "," in ip:
        ip = ip.split(",")[0].strip()

    # Geolocalização
    cidade = "-"
    estado = "-"
    pais = "-"

    try:
        resposta = requests.get(
            f"http://ip-api.com/json/{ip}",
            timeout=3
        )

        dados = resposta.json()

        if dados.get("status") == "success":
            cidade = dados.get("city", "-")
            estado = dados.get("regionName", "-")
            pais = dados.get("country", "-")

    except Exception:
        pass

    # Dispositivo
    dispositivo = "Desktop"

    if user_agent.is_mobile:
        dispositivo = "Celular"
    elif user_agent.is_tablet:
        dispositivo = "Tablet"
    elif user_agent.is_pc:
        dispositivo = "Computador"

    navegador = user_agent.browser.family

    # Bots (previews de WhatsApp, Facebook, Telegram, crawlers, etc.)
    bots = [
        "facebookexternalhit",
        "WhatsApp",
        "TelegramBot",
        "Slackbot",
        "Twitterbot",
        "LinkedInBot",
        "Googlebot",
        "bingbot",
        "Discordbot"
    ]

    eh_bot = False

    for bot in bots:
        if bot.lower() in user_agent_string.lower():
            eh_bot = True
            break

    if navegador == "WhatsApp":
        eh_bot = True

    print(
        f"""
USER AGENT:
{user_agent_string}

BOT: {eh_bot}
IP: {ip}
PAÍS: {pais}
ESTADO: {estado}
CIDADE: {cidade}
DISPOSITIVO: {dispositivo}
NAVEGADOR: {navegador}
=========================
""", flush=True)

    if not eh_bot:

        relacionamento.clicou = True
        relacionamento.total_cliques += 1

        agora = datetime.now(timezone.utc).replace(tzinfo=None)

        if relacionamento.primeiro_clique is None:
            relacionamento.primeiro_clique = agora

        relacionamento.ultimo_clique = agora

        clique = Clique(
            campanha_id=campanha.id,
            contato_id=relacionamento.contato_id,
            ip=ip,
            dispositivo=dispositivo,
            navegador=navegador,
            cidade=cidade,
            estado=estado,
            pais=pais
        )
        db.session.add(clique)

    db.session.add(relacionamento)
    db.session.commit()

    return redirect(campanha.destino)

# ===========================
# DETALHES DA CAMPANHA
# ===========================

@app.route("/campanha/<int:id>")
@login_required
def detalhes_campanha(id):

    campanha = Campanha.query.get_or_404(id)

    relacionamentos = CampanhaContato.query.filter_by(
        campanha_id=id
    ).all()

    for r in relacionamentos:

        ultimo_clique = Clique.query.filter_by(
            contato_id=r.contato_id,
            campanha_id=id
        ).order_by(
            Clique.data.desc()
        ).first()

        r.ultimo_dispositivo = (
            ultimo_clique.dispositivo if ultimo_clique else "-"
        )

        r.ultimo_navegador = (
            ultimo_clique.navegador if ultimo_clique else "-"
        )

        # Todos os cliques do contato
        cliques = Clique.query.filter_by(
            contato_id=r.contato_id,
            campanha_id=id
        ).all()

        ips = set()
        dispositivos = set()
        navegadores = set()

        for clique in cliques:

            if clique.ip:
                ips.add(clique.ip)

            if clique.dispositivo:
                dispositivos.add(clique.dispositivo)

            if clique.navegador:
                navegadores.add(clique.navegador)

        r.total_ips = len(ips)
        r.total_dispositivos = len(dispositivos)
        r.total_navegadores = len(navegadores)

        indice = 0

        if len(ips) > 1:
            indice += 1

        if len(dispositivos) > 1:
            indice += 1

        if len(navegadores) > 1:
            indice += 1

        if indice == 0:
            r.compartilhamento = "🟢 Normal"

        elif indice == 1:
            r.compartilhamento = "🟡 Baixo"

        elif indice == 2:
            r.compartilhamento = "🟠 Médio"

        else:
            r.compartilhamento = "🔴 Alto"

    return render_template(
        "campanha_detalhes.html",
        campanha=campanha,
        relacionamentos=relacionamentos,
        base_url=request.host_url.rstrip("/")
    )

# ===========================
# RELATÓRIO DA CAMPANHA
# ===========================

@app.route("/campanhas/<int:id>/relatorio")
@login_required
def relatorio_campanha(id):

    campanha = Campanha.query.get_or_404(id)

    relacionamentos = CampanhaContato.query.filter_by(
        campanha_id=id
    ).all()

    total_contatos = len(relacionamentos)
    cliques_diretos = 0

    alcance_ips = 0
    alcance_dispositivos = 0

    detalhado = []

    for r in relacionamentos:

        cliques = Clique.query.filter_by(
            campanha_id=id,
            contato_id=r.contato_id
        ).all()

        ips = {c.ip for c in cliques if c.ip}
        dispositivos = {c.dispositivo for c in cliques if c.dispositivo}

        if r.clicou:
            cliques_diretos += 1

        alcance_ips += len(ips)
        alcance_dispositivos += len(dispositivos)

        detalhado.append({
            "contato_id": r.contato_id,
            "nome": r.contato.nome,
            "cliques_totais": r.total_cliques,
            "ips_distintos": len(ips),
            "dispositivos_distintos": len(dispositivos),
            "primeiro_clique": r.primeiro_clique,
            "ultimo_clique": r.ultimo_clique
        })

    ranking_compartilhamento = sorted(
        detalhado,
        key=lambda d: (d["ips_distintos"], d["dispositivos_distintos"]),
        reverse=True
    )

    ctr = round(cliques_diretos / total_contatos * 100, 1) if total_contatos > 0 else 0

    resumo = {
        "total_contatos": total_contatos,
        "cliques_diretos": cliques_diretos,
        "ctr": ctr,
        "alcance_estimado_ips": alcance_ips,
        "alcance_estimado_dispositivos": alcance_dispositivos
    }

    return render_template(
        "relatorio.html",
        campanha=campanha,
        resumo=resumo,
        ranking_compartilhamento=ranking_compartilhamento,
        detalhado=sorted(detalhado, key=lambda d: d["nome"]),
        gerado_em=datetime.now(timezone.utc).replace(tzinfo=None)
    )


# ===========================
# HISTÓRICO DE CLIQUES
# ===========================

@app.route("/cliques")
@login_required
def listar_cliques():

    cliques = Clique.query.order_by(
        Clique.data.desc()
    ).all()

    return render_template(
        "cliques.html",
        cliques=cliques
    )


# ===========================
# TESTE
# ===========================

@app.route("/teste")
@login_required
def teste():

    relacionamentos = CampanhaContato.query.all()

    texto = ""

    for r in relacionamentos:
        texto += f"""
        Campanha: {r.campanha_id} |
        Contato: {r.contato_id} |
        Código: {r.codigo}<br>
        """

    return texto

@app.route("/historico/<int:campanha_id>/<int:contato_id>")
@login_required
def historico(campanha_id, contato_id):

    campanha = Campanha.query.get_or_404(campanha_id)

    contato = Contato.query.get_or_404(contato_id)

    cliques = Clique.query.filter_by(
        campanha_id=campanha_id,
        contato_id=contato_id
    ).order_by(
        Clique.data.desc()
    ).all()

    return render_template(
        "historico.html",
        campanha=campanha,
        contato=contato,
        cliques=cliques
    )
# ===========================
# CLI
# ===========================

@app.cli.command("criar-usuario")
@click.argument("username")
def criar_usuario(username):

    if Usuario.query.filter_by(username=username).first():
        click.echo("Usuário já existe.")
        return

    senha = click.prompt("Senha", hide_input=True, confirmation_prompt=True)

    usuario = Usuario(
        username=username,
        senha_hash=generate_password_hash(senha)
    )

    db.session.add(usuario)
    db.session.commit()

    click.echo(f"Usuário '{username}' criado.")


# ===========================
# START
# ===========================

if __name__ == "__main__":
    app.run(debug=True)
