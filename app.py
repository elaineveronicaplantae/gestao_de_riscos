# === app.py - rotas padronizadas para /relatorios (plural) ===
import os
import json
import smtplib
import re  # ✅ necessário para a normalização por regex
from email.mime.text import MIMEText
from flask import Flask, render_template, request, jsonify, send_file, redirect, session, url_for
from io import BytesIO
from datetime import datetime, date  # ✅ inclui 'date'
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
import socket
from typing import Iterable, Dict, Any, List
from functools import wraps

app = Flask(__name__)
app.secret_key = "chave_super_secreta"  # 🔒 troque por algo forte

# Usuários permitidos
usuarios = {
    "admin": "senha123",
    "willian.silva": "plantae2024",
    "elaine.veronica": "_info2018",
    "luan.carlos": "plantae2024",
    "rodrigo.gomes": "plantae2024",
    "elianai.modesto": "plantae2024",
    "caroline.mayumi": "plantae2024",
    "ana.ferrari": "plantae2024",
    "felipe.costa": "plantae2024",
    "murilo.bondezan": "plantae2024",
    "antonio.shiro": "plantae2024",
    "thiago.assis": "plantae2024",
    "lunara.lepre": "plantae2024",
    "liliane.firmo": "plantae2024",
    "gabriel.nogueira": "plantae2024",
    "fernando.lopes": "plantae2024"
}

# ------------------------------
# Decorador de login obrigatório
# ------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# ------------------------------
# Rota de login
# ------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]

        if usuario in usuarios and usuarios[usuario] == senha:
            session["usuario"] = usuario
            # ✅ Correção: após login, vai para a Plataforma GR10 (index)
            return redirect(url_for("index"))
        else:
            return render_template("login.html", erro="Usuário ou senha inválidos")

    return render_template("login.html")

# ------------------------------
# Rota de logout
# ------------------------------
@app.route("/logout")
def logout():
    session.pop("usuario", None)
    return redirect(url_for("login"))

# ------------------------------
# --- Função auxiliar: converter string em date ---
def _to_date(value):
    """Converte string de data para date, aceitando formatos comuns."""
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).date()
        except Exception:
            pass
    return None

# --- Normalização centralizada do número de contrato ---
def _normalize_contrato(value):
    """Remove espaços laterais e mantém apenas dígitos (0-9)."""
    try:
        v = value.strip()
        v = re.sub(r"\D+", "", v)
        return v
    except Exception:
        return value

# ------------------------------
# Rota Index (Plataforma GR10)
# ------------------------------
@app.route("/")
@login_required
def index():
    return render_template("PlataformaGR10.html")

# ------------------------------
# Rota /pesquisar
# ------------------------------
@app.route('/pesquisar', methods=['GET', 'POST'])
@login_required
def pesquisar():
    if request.method == 'POST':
        contrato = _normalize_contrato(request.form.get('contrato', ''))
        if not contrato:
            return "Número do contrato não informado.", 400

        json_path = os.path.join("dados", f"formulario_{contrato}.json")
        if os.path.exists(json_path):
            print(f"✅ Formulário encontrado para contrato {contrato}")
        else:
            print(f"❌ Nenhum formulário encontrado para contrato {contrato}")

        return redirect(f'/formulario?contrato={contrato}')

    return render_template('pesquisar.html')

# ------------------------------
# Rota /formulario
# ------------------------------
@app.route('/formulario', methods=['GET'])
@login_required
def formulario():
    contrato = _normalize_contrato(request.args.get("contrato", ""))
    json_path = os.path.join("dados", f"formulario_{contrato}.json")
    if not os.path.exists(json_path):
        return render_template('formulario.html', dados={}, contrato=contrato)

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            dados = json.load(f)
    except Exception as e:
        print(f"Erro ao ler JSON do contrato {contrato}: {e}")
        return render_template('formulario.html', dados={}, contrato=contrato)

    return render_template('formulario.html', dados=dados, contrato=contrato)

# ------------------------------
# Rota /salvar_json
# ------------------------------
@app.route('/salvar_json', methods=['POST'])
@login_required
def salvar_json():
    try:
        dados_json = request.get_json(force=True)

        contrato = _normalize_contrato(dados_json.get("contrato", ""))
        dados_json["contrato"] = contrato

        caminho_arquivo = os.path.join("dados", f"formulario_{contrato}.json")
        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados_json, f, ensure_ascii=False, indent=4)

        link_proximo = f"/formulario?contrato={contrato}"
        return jsonify({
            "status": "ok",
            "mensagem": "Formulário salvo com sucesso!",
            "link_proximo": link_proximo
        }), 200

    except Exception as e:
        import traceback
        print("❌ Erro ao salvar:", str(e))
        traceback.print_exc()
        return jsonify({"erro": "Erro ao salvar o formulário."}), 500

# ------------------------------
# Rota /visualizar_pdf
# ------------------------------
@app.route("/visualizar_pdf")
@login_required
def visualizar_pdf():
    contrato = _normalize_contrato(request.args.get("contrato", ""))
    json_path = os.path.join("dados", f"formulario_{contrato}.json")
    if not os.path.exists(json_path):
        return "Dados do formulário não encontrados", 404

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            dados = json.load(f)
    except Exception as e:
        print(f"Erro ao ler o JSON: {e}")
        return jsonify({"erro": "Erro ao carregar dados"}), 500

    pdf_buffer = gerar_pdf_formulario(dados)

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f"formulario_{contrato}.pdf",
        mimetype='application/pdf'
    )

# ------------------------------
# Função auxiliar para gerar PDF
# ------------------------------
def gerar_pdf_formulario(dados):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    # ... (sua lógica original do PDF permanece)
    c.save()
    buffer.seek(0)
    return buffer

# ------------------------------
# Iterador de formulários
# ------------------------------
def _iter_formularios(diretorio: str = "dados") -> Iterable[Dict[str, Any]]:
    if not os.path.isdir(diretorio):
        return []
    for nome in os.listdir(diretorio):
        if not nome.startswith("formulario_") or not nome.endswith(".json"):
            continue
        caminho = os.path.join(diretorio, nome)
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                yield json.load(f)
        except Exception as e:
            print(f"⚠️ Erro lendo {caminho}: {e}")

def coletar_dados_relatorio(data_inicio_str: str, data_fim_str: str) -> List[Dict[str, Any]]:
    di = _to_date(data_inicio_str)
    df = _to_date(data_fim_str)
    if not di or not df:
        return []

    resultados: List[Dict[str, Any]] = []

    for raw in _iter_formularios("dados"):
        contrato = _normalize_contrato(str(raw.get("contrato", "")))
        nome_gestor = raw.get("nome_gestor_relacionamento") or raw.get("gestor_relacionamento") or ""
        resp_apont = raw.get("responsavel_apontamento", "")
        resp_preen = raw.get("responsavel_preenchimento", "")
        pareceres_resp = raw.get("pareceres_adicionais_resposta", "")

        dt_apont_str = raw.get("data_apontamento", "")
        dt_preen_str = raw.get("data_preenchimento", "")
        dt_apont = _to_date(dt_apont_str)
        dt_preen = _to_date(dt_preen_str)

        dentro = False
        for d in (dt_apont, dt_preen):
            if d and di <= d <= df:
                dentro = True
                break
        if not dentro:
            continue

        def _fmt(d: date, fallback: str) -> str:
            return d.strftime("%d/%m/%Y") if isinstance(d, date) else (fallback or "")

        resultados.append({
            "contrato": contrato,
            "nome_gestor_relacionamento": nome_gestor,
            "responsavel_apontamento": resp_apont,
            "data_apontamento": _fmt(dt_apont, dt_apont_str),
            "responsavel_preenchimento": resp_preen,
            "data_preenchimento": _fmt(dt_preen, dt_preen_str),
            "pareceres_adicionais_resposta": pareceres_resp
        })

    resultados.sort(key=lambda x: (x.get("contrato", ""), x.get("data_apontamento", "")))
    return resultados

# ------------------------------
# Rota /relatorios
# ------------------------------
@app.route('/relatorios', methods=['GET'])
@login_required
def relatorios():
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    dados = []
    if data_inicio and data_fim:
        dados = coletar_dados_relatorio(data_inicio, data_fim)

    return render_template('relatorios.html',
                           dados=dados,
                           data_inicio=data_inicio,
                           data_fim=data_fim)

# ------------------------------
# Rota /relatorios/pdf
# ------------------------------
@app.route('/relatorios/pdf', methods=['POST'])
@login_required
def relatorios_pdf():
    data_inicio = request.form.get('data_inicio')
    data_fim = request.form.get('data_fim')
    itens = coletar_dados_relatorio(data_inicio, data_fim)

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    y = altura - 40
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, f"Relatório GR10 A07 — Período: {data_inicio} a {data_fim}")
    y -= 20
    c.setFont("Helvetica", 10)

    if not itens:
        c.drawString(40, y, "Nenhum dado encontrado para o período informado.")
    else:
        for item in itens:
            bloco = [
                f"Contrato: {item.get('contrato','')}",
                f"Nome do Gestor: {item.get('nome_gestor_relacionamento','')}",
                f"Responsável pelo Apontamento: {item.get('responsavel_apontamento','')}",
                f"Data do Apontamento: {item.get('data_apontamento','')}",
                f"Responsável pelo Preenchimento: {item.get('responsavel_preenchimento','')}",
                f"Data do Preenchimento: {item.get('data_preenchimento','')}",
                f"Pareceres Adicionais - Resposta: {item.get('pareceres_adicionais_resposta','')}",
                "-" * 90
            ]
            for linha in bloco:
                if y < 60:
                    c.showPage()
                    y = altura - 40
                    c.setFont("Helvetica", 10)
                c.drawString(40, y, linha)
                y -= 16

    c.showPage()
    c.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"relatorio_{data_inicio}a{data_fim}.pdf",
        mimetype='application/pdf'
    )
# Envio de e-mail
# ------------------------------
def enviar_email(remetente, senha, destinatario, contrato, nome_usuario, observacao="", servidor_smtp="smtp.gmail.com", porta=587):
    assunto = "Formulário GR10 A07 - Monitoramento de PLD"
    link = f"https://riscos.plantaeagrocredito.com.br/formulario?contrato={contrato}"
    corpo = (
        f"Olá,\n\n"
        f"Segue o link para preenchimento do formulário GR10 A07 - Monitoramento de PLD:\n"
        f"{link}\n\n"
        f"Lembre-se: o prazo para resposta é de 3 dias úteis.\n"
    )

    if observacao:
        corpo += f"\nObservação: {observacao}\n"

    corpo += (
        f"\nEm caso de dúvidas, acione o time de Compliance.\n\n"
        f"Atenciosamente,\n{nome_usuario}"
    )

    msg = MIMEText(corpo, _charset="utf-8")
    msg["Subject"] = assunto
    msg["From"] = remetente
    msg["To"] = destinatario

    with smtplib.SMTP(servidor_smtp, porta) as server:
        server.starttls()
        server.login(remetente, senha)
        server.sendmail(remetente, [destinatario], msg.as_string())

# ------------------------------
# Rota /enviar_email
# ------------------------------
@app.route("/enviar_email", methods=["GET", "POST"])
def enviar_email_rota():
    if "usuario" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        nome_usuario = request.form.get("email_usuario")
        lista_destinatarios = request.form.get("destinatarios")
        contrato = request.form.get("contrato")
        observacao = request.form.get("observacao")

        if not nome_usuario or not lista_destinatarios or not contrato:
            return "<p><strong>❌ Todos os campos são obrigatórios.</strong></p>"

        try:
            remetente = "formularios@plantaeagrocredito.com.br"
            senha = "tmoa mjvm iwrj gmfd"

            emails = [e.strip() for e in lista_destinatarios.split(';') if e.strip()]
            for email in emails:
                enviar_email(remetente, senha, email, contrato, nome_usuario, observacao)

            return f"""
            <p><strong>✅ E-mails enviados com sucesso!</strong></p>
            <p><a href='/formulario?contrato={contrato}'>Voltar ao formulário</a></p>
            """
        except Exception as e:
            return f"<p><strong>❌ Erro ao enviar e-mails:</strong> {str(e)}</p>"

    return render_template("enviar_email.html")
# ------------------------------
# Inicialização do servidor
# ------------------------------
if __name__ == '__main__':
    try:
        socket.inet_aton("85.25.172.144")
        app.run(host='85.25.172.144', port=5000, debug=True)
    except:
        app.run(host='127.0.0.1', port=5000, debug=True)
