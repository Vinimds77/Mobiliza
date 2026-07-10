from flask import Flask, render_template, request, redirect
import secrets
import requests
import tzdata
from datetime import datetime
from zoneinfo import ZoneInfo
from user_agents import parse

from config import Config
from database import db

from models.segmento import Segmento
from models.campanha import Campanha
from models.clique import Clique
from models.contato import Contato
from models.campanha_contato import CampanhaContato

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

# ===========================
# DASHBOARD
# ===========================

@app.route("/")
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
def segmentos():

    if request.method == "POST":

        novo = Segmento(
            nome=request.form["nome"]
        )

        db.session.add(novo)
        db.session.commit()

        return redirect("/segmentos")

    lista = Segmento.query.all()

    return render_template(
        "segmentos.html",
        segmentos=lista
    )


# ===========================
# CONTATOS
# ===========================

@app.route("/contatos", methods=["GET", "POST"])
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

    return render_template(
        "contatos.html",
        contatos=lista_contatos,
        segmentos=lista_segmentos
    )


# ===========================
# CAMPANHAS
# ===========================

@app.route("/campanhas", methods=["GET", "POST"])
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

    # Detecta dispositivo e navegador
    user_agent_string = request.headers.get("User-Agent", "")
    user_agent = parse(user_agent_string)

    # IP real do visitante
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    if "," in ip:
        ip = ip.split(",")[0].strip()

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

    dispositivo = "Desktop"

    if user_agent.is_mobile:
        dispositivo = "Celular"
    elif user_agent.is_tablet:
        dispositivo = "Tablet"
    elif user_agent.is_pc:
        dispositivo = "Computador"

    navegador = user_agent.browser.family

    eh_bot = (
        navegador == "WhatsApp"
        or "facebookexternalhit" in user_agent_string.lower()
        or "telegram" in user_agent_string.lower()
        or "slackbot" in user_agent_string.lower()
        or "discordbot" in user_agent_string.lower()
    )
        
    print(
        f"""
=========================
USER AGENT:
{user_agent_string}

BOT: {eh_bot}
IP: {ip}
DISPOSITIVO: {dispositivo}
NAVEGADOR: {navegador}
=========================
""",
        flush=True
        ) 
    if not eh_bot:

        relacionamento.clicou = True
        relacionamento.total_cliques += 1

        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))

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
# HISTÓRICO DE CLIQUES
# ===========================

@app.route("/cliques")
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
# START
# ===========================

if __name__ == "__main__":

    with app.app_context():
        db.create_all()

    app.run(debug=True)