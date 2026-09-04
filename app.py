from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    url_for,
    has_request_context
)
import os
import secrets
import requests
import tzdata
import click
from datetime import datetime, timezone, timedelta, time as dt_time
from zoneinfo import ZoneInfo
from user_agents import parse
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import inspect, text, func, event
from sqlalchemy.orm import with_loader_criteria, joinedload
from sqlalchemy.exc import OperationalError

from config import Config
from database import db

from models.segmento import Segmento
from models.campanha import Campanha
from models.clique import Clique
from models.contato import Contato
from models.campanha_contato import CampanhaContato
from models.usuario import Usuario
from models.cliente import Cliente

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

with app.app_context():
    db.create_all()

    colunas_usuarios = [c["name"] for c in inspect(db.engine).get_columns("usuarios")]

    if "criado_em" not in colunas_usuarios:
        db.session.execute(text("ALTER TABLE usuarios ADD COLUMN criado_em TIMESTAMP"))
        db.session.commit()

    colunas_campanhas = [c["name"] for c in inspect(db.engine).get_columns("campanhas")]

    if "criado_em" not in colunas_campanhas:
        db.session.execute(text("ALTER TABLE campanhas ADD COLUMN criado_em TIMESTAMP"))
        db.session.commit()

    colunas_segmentos = [c["name"] for c in inspect(db.engine).get_columns("segmentos")]

    if "tipo" not in colunas_segmentos:
        db.session.execute(text(
            "ALTER TABLE segmentos ADD COLUMN tipo VARCHAR(20) NOT NULL DEFAULT 'regional'"
        ))
        db.session.commit()

    colunas_contatos = [c["name"] for c in inspect(db.engine).get_columns("contatos")]

    if "tamanho_grupo" not in colunas_contatos:
        db.session.execute(text("ALTER TABLE contatos ADD COLUMN tamanho_grupo INTEGER"))
        db.session.commit()

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
# FILTRO AUTOMÁTICO POR CLIENTE
# ===========================

MODELOS_COM_CLIENTE = (Segmento, Contato, Campanha)


@event.listens_for(db.session, "do_orm_execute")
def aplicar_filtro_cliente(execute_state):

    if not execute_state.is_select or not has_request_context():
        return

    if request.endpoint == "abrir_link":
        return

    cliente_id = session.get("cliente_id")

    if cliente_id is None:
        return

    for modelo in MODELOS_COM_CLIENTE:
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(modelo, lambda cls: cls.cliente_id == cliente_id)
        )


@app.before_request
def exigir_cliente_selecionado():

    if not current_user.is_authenticated:
        return

    endpoints_sem_cliente = {
        "login", "logout", "static", "abrir_link",
        "clientes", "selecionar_cliente", "usuarios"
    }

    if request.endpoint in endpoints_sem_cliente or request.endpoint is None:
        return

    if "cliente_id" not in session:
        return redirect(url_for("clientes"))


@app.context_processor
def injetar_cliente_atual():
    cliente_id = session.get("cliente_id")
    return {"cliente_atual": Cliente.query.get(cliente_id) if cliente_id else None}


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
# USUÁRIOS
# ===========================

@app.route("/usuarios", methods=["GET", "POST"])
@login_required
def usuarios():

    erro = None

    if request.method == "POST":

        username = request.form["username"]
        senha = request.form["senha"]

        if Usuario.query.filter_by(username=username).first():
            erro = "duplicado"
        else:
            novo = Usuario(
                username=username,
                senha_hash=generate_password_hash(senha)
            )
            db.session.add(novo)
            db.session.commit()
            return redirect("/usuarios")

    lista = Usuario.query.order_by(Usuario.username).all()

    return render_template("usuarios.html", usuarios=lista, erro=erro)


# ===========================
# CLIENTES
# ===========================

@app.route("/clientes", methods=["GET", "POST"])
@login_required
def clientes():

    if request.method == "POST":

        novo = Cliente(nome=request.form["nome"])

        db.session.add(novo)
        db.session.commit()

        return redirect("/clientes")

    lista = Cliente.query.order_by(Cliente.nome).all()

    return render_template("clientes.html", clientes=lista)


@app.route("/clientes/selecionar/<int:id>")
@login_required
def selecionar_cliente(id):

    cliente = Cliente.query.get_or_404(id)

    session["cliente_id"] = cliente.id

    return redirect("/")


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
    total_campanhas = Campanha.query.filter_by(ativa=True).count()
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
            nome=request.form["nome"],
            cliente_id=session["cliente_id"],
            tipo=request.form.get("tipo", "regional")
        )

        db.session.add(novo)
        db.session.commit()

        return redirect("/segmentos")

    lista = Segmento.query.all()

    erro = request.args.get("erro")

    contagem_contatos = dict(
        db.session.query(
            Segmento.id, func.count(Contato.id)
        ).join(Contato, Contato.segmento_id == Segmento.id)
        .group_by(Segmento.id).all()
    )

    return render_template(
        "segmentos.html",
        segmentos=lista,
        erro=erro,
        contagem_contatos=contagem_contatos
    )


@app.route("/segmentos/tipo/<int:id>", methods=["POST"])
@login_required
def alterar_tipo_segmento(id):

    segmento = Segmento.query.get_or_404(id)

    segmento.tipo = request.form.get("tipo", "regional")

    db.session.commit()

    return redirect("/segmentos")


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
            segmento_id=request.form["segmento"],
            cliente_id=session["cliente_id"]
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


@app.route("/contatos/tamanho/<int:id>", methods=["POST"])
@login_required
def alterar_tamanho_grupo(id):

    contato = Contato.query.get_or_404(id)

    valor = request.form.get("tamanho_grupo", "").strip()

    contato.tamanho_grupo = int(valor) if valor.isdigit() else None

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
            codigo=codigo,
            cliente_id=session["cliente_id"]
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

    mostrar_arquivadas = request.args.get("arquivadas") == "1"

    page = request.args.get("page", 1, type=int)
    busca = request.args.get("busca", "").strip()
    data_inicio = request.args.get("data_inicio", "").strip()
    data_fim = request.args.get("data_fim", "").strip()

    consulta = Campanha.query.filter_by(ativa=not mostrar_arquivadas)

    if busca:
        consulta = consulta.filter(Campanha.titulo.ilike(f"%{busca}%"))

    if data_inicio:
        consulta = consulta.filter(
            Campanha.criado_em >= datetime.strptime(data_inicio, "%Y-%m-%d")
        )

    if data_fim:
        consulta = consulta.filter(
            Campanha.criado_em < datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)
        )

    # Mais recentes primeiro. criado_em pode ser nulo em campanhas antigas
    # (criadas antes desse campo existir) — essas caem pro fim da lista,
    # ordenadas por id como aproximação de recência.
    consulta = consulta.order_by(
        Campanha.criado_em.is_(None),
        Campanha.criado_em.desc(),
        Campanha.id.desc()
    )

    paginacao = consulta.paginate(page=page, per_page=10, error_out=False)

    lista_segmentos = Segmento.query.all()

    contagem_contatos = dict(
        db.session.query(
            CampanhaContato.campanha_id,
            func.count(CampanhaContato.id)
        ).join(
            Campanha, CampanhaContato.campanha_id == Campanha.id
        ).group_by(CampanhaContato.campanha_id).all()
    )

    return render_template(
        "campanhas.html",
        campanhas=paginacao.items,
        paginacao=paginacao,
        segmentos=lista_segmentos,
        contagem_contatos=contagem_contatos,
        mostrar_arquivadas=mostrar_arquivadas,
        busca=busca,
        data_inicio=data_inicio,
        data_fim=data_fim
    )


@app.route("/campanhas/excluir/<int:id>")
@login_required
def arquivar_campanha(id):

    # Arquivamento lógico: a campanha some da listagem normal, mas
    # cliques, campanhas_contatos e o link /r/<codigo> continuam
    # intactos e funcionando (histórico e métricas preservados).
    campanha = Campanha.query.get_or_404(id)

    campanha.ativa = False

    db.session.commit()

    return redirect("/campanhas")


@app.route("/campanhas/restaurar/<int:id>")
@login_required
def restaurar_campanha(id):

    # Só troca ativa de volta pra True. Não recria nada, não mexe em
    # codigo/id/campanhas_contatos/cliques — os links continuam os mesmos.
    campanha = Campanha.query.get_or_404(id)

    campanha.ativa = True

    db.session.commit()

    return redirect("/campanhas")


# ===========================
# LINK RASTREÁVEL
# ===========================

@app.route("/r/<codigo>")
def abrir_link(codigo):

    try:
        relacionamento = CampanhaContato.query.filter_by(
            codigo=codigo
        ).first()

    except OperationalError as erro:

        db.session.rollback()

        print(
            f"[abrir_link] Falha de conexão com o banco ao consultar "
            f"codigo={codigo}: {erro}",
            flush=True
        )

        return "Serviço temporariamente indisponível. Tente novamente em instantes.", 503

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
# RELATÓRIO SEMANAL POR SEGMENTO
# ===========================

def periodo_padrao_semanal():
    """Sexta-feira mais recente ANTERIOR a hoje até hoje, em horário de
    Brasília. Se hoje já é sexta, usa a sexta anterior (últimos 7 dias)."""

    hoje_br = datetime.now(ZoneInfo("America/Sao_Paulo")).date()

    dias_desde_sexta = (hoje_br.weekday() - 4) % 7

    if dias_desde_sexta == 0:
        dias_desde_sexta = 7

    sexta_br = hoje_br - timedelta(days=dias_desde_sexta)

    return sexta_br, hoje_br


def limites_utc_do_periodo(data_inicio, data_fim):
    """Converte um intervalo de datas (calendário de Brasília) nos limites
    naive-UTC equivalentes, pra comparar direto com criado_em."""

    inicio_br = datetime.combine(data_inicio, dt_time.min, tzinfo=ZoneInfo("America/Sao_Paulo"))
    fim_br = datetime.combine(data_fim, dt_time.max, tzinfo=ZoneInfo("America/Sao_Paulo"))

    inicio_utc = inicio_br.astimezone(timezone.utc).replace(tzinfo=None)
    fim_utc = fim_br.astimezone(timezone.utc).replace(tzinfo=None)

    return inicio_utc, fim_utc


@app.route("/relatorios/segmentos")
@login_required
def relatorio_segmentos():

    sexta_padrao, hoje_padrao = periodo_padrao_semanal()

    data_inicio_str = request.args.get("data_inicio")
    data_fim_str = request.args.get("data_fim")

    try:
        data_inicio = (
            datetime.strptime(data_inicio_str, "%Y-%m-%d").date()
            if data_inicio_str else sexta_padrao
        )
        data_fim = (
            datetime.strptime(data_fim_str, "%Y-%m-%d").date()
            if data_fim_str else hoje_padrao
        )
    except ValueError:
        data_inicio, data_fim = sexta_padrao, hoje_padrao

    inicio_utc, fim_utc = limites_utc_do_periodo(data_inicio, data_fim)

    # Todo envio (CampanhaContato) do período, já com o Contato/Segmento
    # pré-carregados via joinedload — sem isso, cada acesso a r.contato e
    # contato.segmento dispara uma query lazy-load por linha (N+1).
    relacionamentos = (
        CampanhaContato.query
        .join(Contato, Contato.id == CampanhaContato.contato_id)
        .join(Campanha, Campanha.id == CampanhaContato.campanha_id)
        .options(joinedload(CampanhaContato.contato).joinedload(Contato.segmento))
        .filter(Campanha.criado_em >= inicio_utc, Campanha.criado_em <= fim_utc)
        .all()
    )

    # IPs distintos por par (campanha, contato) — UMA query agregada pra
    # todos os pares de uma vez, em vez de uma query de Clique por linha
    # dentro do loop (era isso que causava o timeout: ~200 envios na semana
    # = ~200 queries extras de rede pro Neon).
    alcance_por_par = {
        (campanha_id, contato_id): ips_distintos
        for campanha_id, contato_id, ips_distintos in (
            db.session.query(
                Clique.campanha_id,
                Clique.contato_id,
                func.count(func.distinct(Clique.ip))
            )
            .filter(Clique.ip.isnot(None), Clique.ip != "")
            .group_by(Clique.campanha_id, Clique.contato_id)
            .all()
        )
    }

    contagem_segmento = dict(
        db.session.query(
            Segmento.id,
            func.count(Contato.id)
        ).join(Contato, Contato.segmento_id == Segmento.id)
        .group_by(Segmento.id).all()
    )

    segmentos_acc = {}

    for r in relacionamentos:

        contato = r.contato
        segmento = contato.segmento if contato else None

        if segmento is None:
            continue

        ips_distintos = alcance_por_par.get((r.campanha_id, r.contato_id), 0)

        seg_acc = segmentos_acc.setdefault(segmento.id, {
            "segmento": segmento.nome,
            "tipo": segmento.tipo,
            "envios": 0,
            "cliques_diretos": 0,
            "cliques_totais": 0,
            "alcance_ips": 0,
            "campanhas": set(),
            "contatos": {}
        })

        seg_acc["envios"] += 1
        seg_acc["cliques_totais"] += r.total_cliques
        seg_acc["alcance_ips"] += ips_distintos
        seg_acc["campanhas"].add(r.campanha_id)

        if r.clicou:
            seg_acc["cliques_diretos"] += 1

        cont_acc = seg_acc["contatos"].setdefault(contato.id, {
            "nome": contato.nome,
            "tamanho_grupo": contato.tamanho_grupo,
            "envios": 0,
            "cliques_diretos": 0,
            "cliques_totais": 0,
            "alcance_ips": 0
        })

        cont_acc["envios"] += 1
        cont_acc["cliques_totais"] += r.total_cliques
        cont_acc["alcance_ips"] += ips_distintos

        if r.clicou:
            cont_acc["cliques_diretos"] += 1

    regionais = []
    grupos = []

    for seg_id, acc in segmentos_acc.items():

        envios = acc["envios"]

        ctr = round(acc["cliques_diretos"] / envios * 100, 1) if envios else 0
        cliques_por_envio = round(acc["cliques_totais"] / envios, 2) if envios else 0

        linha = {
            "segmento": acc["segmento"],
            "envios": envios,
            "contatos_segmento": contagem_segmento.get(seg_id, 0),
            "cliques_diretos": acc["cliques_diretos"],
            "cliques_totais": acc["cliques_totais"],
            "ctr": ctr,
            "cliques_por_envio": cliques_por_envio,
            "alcance_ips": acc["alcance_ips"],
            "total_campanhas": len(acc["campanhas"])
        }

        if acc["tipo"] == "grupo":

            detalhes = []
            grupos_ativados = 0
            soma_tamanho_conhecido = 0
            soma_alcance_com_tamanho = 0
            algum_sem_tamanho = False

            for cont_acc in acc["contatos"].values():

                if cont_acc["cliques_totais"] > 0:
                    grupos_ativados += 1

                tamanho = cont_acc["tamanho_grupo"]

                if tamanho:
                    taxa_alcance = round(cont_acc["alcance_ips"] / tamanho * 100, 1)
                    soma_tamanho_conhecido += tamanho
                    soma_alcance_com_tamanho += cont_acc["alcance_ips"]
                else:
                    taxa_alcance = None
                    algum_sem_tamanho = True

                detalhes.append({
                    "nome": cont_acc["nome"],
                    "envios": cont_acc["envios"],
                    "cliques_totais": cont_acc["cliques_totais"],
                    "cliques_por_envio": (
                        round(cont_acc["cliques_totais"] / cont_acc["envios"], 2)
                        if cont_acc["envios"] else 0
                    ),
                    "alcance_ips": cont_acc["alcance_ips"],
                    "tamanho_grupo": tamanho,
                    "taxa_alcance": taxa_alcance
                })

            detalhes.sort(key=lambda d: d["alcance_ips"], reverse=True)

            linha["detalhes"] = detalhes
            linha["grupos_ativados"] = grupos_ativados
            linha["total_grupos"] = contagem_segmento.get(seg_id, 0)
            linha["taxa_alcance_agregada"] = (
                round(soma_alcance_com_tamanho / soma_tamanho_conhecido * 100, 1)
                if soma_tamanho_conhecido else None
            )
            linha["algum_sem_tamanho"] = algum_sem_tamanho

            grupos.append(linha)

        else:
            regionais.append(linha)

    regionais.sort(key=lambda l: l["segmento"])
    grupos.sort(key=lambda l: l["segmento"])

    return render_template(
        "relatorio_segmentos.html",
        regionais=regionais,
        grupos=grupos,
        data_inicio=data_inicio,
        data_fim=data_fim,
        gerado_em=datetime.now(timezone.utc).replace(tzinfo=None)
    )


# ===========================
# HISTÓRICO DE CLIQUES
# ===========================

@app.route("/cliques")
@login_required
def listar_cliques():

    cliques = Clique.query.join(Campanha).order_by(
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

    relacionamentos = CampanhaContato.query.join(Campanha).all()

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
