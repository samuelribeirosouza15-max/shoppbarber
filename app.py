from flask import Flask, request, jsonify, render_template, session, redirect
import sqlite3
import urllib.parse
import datetime
import os
import uuid
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'shoppbarber_super_secreta_2026')

SENHA_SUPER_ADMIN = 'shopp2026'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def conectar_db():
    conn = sqlite3.connect('barbearia.db')
    conn.row_factory = sqlite3.Row
    return conn


def salvar_arquivo_unico(arquivo):
    if arquivo and arquivo.filename != '':
        extensao = os.path.splitext(secure_filename(arquivo.filename))[1]
        nome_unico = f"{uuid.uuid4().hex}{extensao}"
        arquivo.save(os.path.join(app.config['UPLOAD_FOLDER'], nome_unico))
        return f'/static/uploads/{nome_unico}'
    return ''


def hora_para_minutos(hora_str):
    h, m = map(int, hora_str.split(':'))
    return h * 60 + m


def minutos_para_hora(minutos):
    h = minutos // 60
    m = minutos % 60
    return f"{h:02d}:{m:02d}"


def get_barbearia_atual():
    barbearia_id = session.get('barbearia_id', 1)
    conn = conectar_db()
    c = conn.cursor()
    c.execute("SELECT * FROM barbearias WHERE id = ?", (barbearia_id,))
    barbearia = c.fetchone()
    if not barbearia:
        c.execute("SELECT * FROM barbearias ORDER BY id ASC LIMIT 1")
        barbearia = c.fetchone()
    conn.close()
    if barbearia:
        session['barbearia_id'] = barbearia['id']
        session['barbearia_slug'] = barbearia['slug']
        session['barbearia_nome'] = barbearia['nome']
    return barbearia


def barbearia_esta_bloqueada(barbearia):
    if not barbearia:
        return True
    if barbearia['status_pagamento'] == 'bloqueado':
        return True
    if barbearia['plano'] != 'vitalicio' and barbearia['data_vencimento']:
        try:
            venc = datetime.datetime.strptime(barbearia['data_vencimento'], "%Y-%m-%d").date()
            if venc < datetime.date.today():
                return True
        except:
            pass
    return False


def tela_bloqueio(barbearia):
    nome = barbearia['nome'] if barbearia else 'Esta barbearia'
    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sistema Indisponível | ShoppBarber</title>
        <style>
            body {{ background:#0f172a; color:#f8fafc; font-family:'Segoe UI',sans-serif; display:flex; align-items:center; justify-content:center; height:100vh; margin:0; text-align:center; padding:20px; }}
            .box {{ background:#1e293b; border:1px solid #ef4444; border-radius:16px; padding:32px; max-width:440px; }}
            h1 {{ color:#ef4444; margin-bottom:12px; font-size:1.5rem; }}
            p {{ color:#cbd5e1; line-height:1.5; margin-bottom:20px; }}
            a {{ display:inline-block; padding:12px 20px; background:#f59e0b; color:#0f172a; text-decoration:none; border-radius:10px; font-weight:700; }}
        </style>
    </head>
    <body>
        <div class="box">
            <h1>⚠️ Sistema Temporariamente Indisponível</h1>
            <p>O acesso da <strong>{nome}</strong> está suspenso no momento por pendência na assinatura do <strong>ShoppBarber</strong>.</p>
            <a href="/super_admin">Acesso do Gestor</a>
        </div>
    </body>
    </html>
    """, 403


def init_db():
    conn = conectar_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS barbearias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    whatsapp_dono TEXT,
                    plano TEXT DEFAULT 'mensal',
                    status_pagamento TEXT DEFAULT 'ativo',
                    data_vencimento TEXT,
                    cor_tema TEXT DEFAULT '#00bfff'
                )''')

    # Garante que a coluna cor_tema exista mesmo em bancos já criados
    try:
        c.execute("ALTER TABLE barbearias ADD COLUMN cor_tema TEXT DEFAULT '#00bfff'")
    except:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    barbearia_id INTEGER DEFAULT 1,
                    nome TEXT,
                    email TEXT,
                    telefone TEXT,
                    senha TEXT,
                    tipo TEXT,
                    foto TEXT
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS servicos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    barbearia_id INTEGER DEFAULT 1,
                    nome TEXT,
                    preco REAL,
                    duracao INTEGER
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS profissionais (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    barbearia_id INTEGER DEFAULT 1,
                    nome TEXT,
                    especialidade TEXT,
                    status TEXT DEFAULT 'Disponivel',
                    foto TEXT
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS agendamentos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    barbearia_id INTEGER DEFAULT 1,
                    cliente_id INTEGER,
                    cliente_nome TEXT,
                    profissional TEXT,
                    data TEXT,
                    hora TEXT,
                    servico TEXT,
                    avaliacao INTEGER DEFAULT 0
                )''')

    c.execute("SELECT * FROM barbearias WHERE slug='king'")
    king = c.fetchone()
    if not king:
        c.execute(
            """INSERT INTO barbearias (nome, slug, whatsapp_dono, plano, status_pagamento, data_vencimento, cor_tema)
               VALUES ('King Barbearia', 'king', '5562994016649', 'vitalicio', 'ativo', NULL, '#00bfff')"""
        )
        king_id = c.lastrowid
    else:
        king_id = king['id']

    c.execute("SELECT * FROM usuarios WHERE tipo='barbeiro' AND barbearia_id=?", (king_id,))
    if not c.fetchone():
        senha_hash = generate_password_hash('123')
        c.execute(
            "INSERT INTO usuarios (barbearia_id, nome, email, telefone, senha, tipo) VALUES (?, 'Admin', 'admin@barbearia.com', '62994016649', ?, 'barbeiro')",
            (king_id, senha_hash)
        )

    c.execute("SELECT * FROM servicos WHERE barbearia_id=?", (king_id,))
    if not c.fetchone():
        servicos = [
            (king_id, 'Sobrancelha', 15.00, 15),
            (king_id, 'Corte Rápido', 35.00, 25),
            (king_id, 'Corte', 40.00, 30),
            (king_id, 'Barba', 30.00, 30),
            (king_id, 'Corte + Barba', 60.00, 60),
            (king_id, 'Pigmentação', 50.00, 30)
        ]
        c.executemany("INSERT INTO servicos (barbearia_id, nome, preco, duracao) VALUES (?, ?, ?, ?)", servicos)

    c.execute("SELECT * FROM profissionais WHERE barbearia_id=?", (king_id,))
    if not c.fetchone():
        profissionais = [
            (king_id, 'Gestão (Dono)', 'Mestre', 'Disponivel', ''),
            (king_id, 'Gustavo', 'Cabelo', 'Disponivel', ''),
            (king_id, 'Japa', 'Barba', 'Disponivel', '')
        ]
        c.executemany("INSERT INTO profissionais (barbearia_id, nome, especialidade, status, foto) VALUES (?, ?, ?, ?, ?)", profissionais)

    conn.commit()
    conn.close()


# ================= ROTAS DE PÁGINAS =================

@app.route('/')
def home():
    barbearia = get_barbearia_atual()
    if barbearia_esta_bloqueada(barbearia):
        return tela_bloqueio(barbearia)
    nome_cliente = session.get('user_nome', None)
    return render_template('index.html', nome_cliente=nome_cliente, barbearia=barbearia)


@app.route('/tela_agendamento')
def tela_agendamento():
    barbearia = get_barbearia_atual()
    if barbearia_esta_bloqueada(barbearia):
        return tela_bloqueio(barbearia)
    if 'user_id' not in session:
        session['destino_pos_login'] = '/tela_agendamento'
        return redirect('/login')
    nome_cliente = session.get('user_nome', None)
    return render_template('agendar.html', nome_cliente=nome_cliente, barbearia=barbearia)


@app.route('/login')
def pagina_login():
    barbearia = get_barbearia_atual()
    if barbearia_esta_bloqueada(barbearia):
        return tela_bloqueio(barbearia)
    return render_template('login.html', barbearia=barbearia)


@app.route('/login_admin')
def login_admin():
    barbearia = get_barbearia_atual()
    if barbearia_esta_bloqueada(barbearia):
        return tela_bloqueio(barbearia)
    if session.get('user_tipo') == 'barbeiro':
        return redirect('/painel')
    return render_template('login_admin.html', barbearia=barbearia)


@app.route('/painel')
def painel():
    barbearia = get_barbearia_atual()
    if barbearia_esta_bloqueada(barbearia):
        return tela_bloqueio(barbearia)
    if 'user_id' not in session or session.get('user_tipo') != 'barbeiro':
        return redirect('/login_admin')
    return render_template('painel.html', barbearia=barbearia)


@app.route('/logout')
def logout():
    barbearia_id = session.get('barbearia_id', 1)
    barbearia_slug = session.get('barbearia_slug', 'king')
    barbearia_nome = session.get('barbearia_nome', 'King Barbearia')
    session.clear()
    session['barbearia_id'] = barbearia_id
    session['barbearia_slug'] = barbearia_slug
    session['barbearia_nome'] = barbearia_nome
    return redirect('/')


# ================= AUTENTICAÇÃO =================

@app.route('/admin_secreto', methods=['POST'])
def admin_secreto():
    barbearia = get_barbearia_atual()
    if barbearia_esta_bloqueada(barbearia):
        return jsonify({"erro": "Assinatura bloqueada."}), 403
    dados = request.json
    senha_digitada = dados.get('senha', '')

    conn = conectar_db()
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios WHERE tipo='barbeiro' AND barbearia_id=?", (barbearia['id'],))
    admin = c.fetchone()
    conn.close()

    if admin and check_password_hash(admin['senha'], senha_digitada):
        session['user_id'] = admin['id']
        session['user_tipo'] = admin['tipo']
        session['user_nome'] = admin['nome']
        return jsonify({"sucesso": True})

    return jsonify({"erro": "Senha incorreta"}), 401


@app.route('/cadastro', methods=['POST'])
def cadastro():
    barbearia = get_barbearia_atual()
    nome = request.form.get('nome')
    email = request.form.get('email')
    telefone = request.form.get('telefone')
    senha = request.form.get('senha')
    foto = request.files.get('foto')

    if not nome or not telefone or not senha:
        return jsonify({"erro": "Preencha os campos obrigatórios (Nome, Celular e Senha)."}), 400

    if email and ("@" not in email or "." not in email):
        return jsonify({"erro": "Insira um e-mail válido ou deixe em branco."}), 400

    caminho_foto = salvar_arquivo_unico(foto)

    conn = conectar_db()
    c = conn.cursor()

    c.execute("SELECT * FROM usuarios WHERE telefone=? AND barbearia_id=?", (telefone, barbearia['id']))
    if c.fetchone():
        conn.close()
        return jsonify({"erro": "Este celular já está cadastrado nesta barbearia."}), 400

    senha_hash = generate_password_hash(senha)
    email_final = email if email else 'sem_email@barbearia.com'

    c.execute(
        "INSERT INTO usuarios (barbearia_id, nome, email, telefone, senha, tipo, foto) VALUES (?, ?, ?, ?, ?, 'cliente', ?)",
        (barbearia['id'], nome, email_final, telefone, senha_hash, caminho_foto)
    )
    conn.commit()
    conn.close()
    return jsonify({"mensagem": "Conta criada com sucesso!"})


@app.route('/login', methods=['POST'])
def fazer_login():
    barbearia = get_barbearia_atual()
    dados = request.json
    conn = conectar_db()
    c = conn.cursor()

    c.execute(
        "SELECT * FROM usuarios WHERE (nome=? OR telefone=?) AND barbearia_id=?",
        (dados['login'], dados['login'], barbearia['id'])
    )
    user = c.fetchone()
    conn.close()

    if user:
        if check_password_hash(user['senha'], dados['senha']):
            session['user_id'] = user['id']
            session['user_tipo'] = user['tipo']
            session['user_nome'] = user['nome']
            destino = session.pop('destino_pos_login', '/')
            return jsonify({"sucesso": True, "tipo": user['tipo'], "destino": destino})
        else:
            return jsonify({"erro": "Senha incorreta."}), 401
    return jsonify({"erro": "Usuário não encontrado."}), 401


# ================= APIs DE COMODIDADES, SERVIÇOS E PROFISSIONAIS =================

@app.route('/api/comodidades', methods=['GET'])
def get_comodidades():
    comodidades = [
        {"icone": "📶", "nome": "Wi-Fi Grátis", "descricao": "Internet de alta velocidade para clientes."},
        {"icone": "❄️", "nome": "Ambiente Climatizado", "descricao": "Ar-condicionado para seu máximo conforto."},
        {"icone": "☕", "nome": "Café & Água", "descricao": "Café fresco e água gelada cortesia."},
        {"icone": "🎮", "nome": "Área de Espera", "descricao": "TV e entretenimento enquanto aguarda."},
        {"icone": "🅿️", "nome": "Estacionamento", "descricao": "Fácil acesso e vagas próximas."}
    ]
    return jsonify(comodidades)


@app.route('/api/servicos', methods=['GET'])
def get_servicos():
    barbearia = get_barbearia_atual()
    conn = conectar_db()
    c = conn.cursor()
    c.execute("SELECT * FROM servicos WHERE barbearia_id=?", (barbearia['id'],))
    dados = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(dados)


@app.route('/api/servicos', methods=['POST'])
def add_servico():
    if session.get('user_tipo') != 'barbeiro':
        return jsonify({"erro": "Acesso negado"}), 401

    barbearia = get_barbearia_atual()
    dados = request.json
    if not dados.get('nome') or not dados.get('preco') or not dados.get('duracao'):
        return jsonify({"erro": "Preencha todos os campos do serviço."}), 400

    conn = conectar_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO servicos (barbearia_id, nome, preco, duracao) VALUES (?, ?, ?, ?)",
        (barbearia['id'], dados['nome'], dados['preco'], dados['duracao'])
    )
    conn.commit()
    conn.close()
    return jsonify({"sucesso": True})


@app.route('/api/servicos/<int:id>', methods=['DELETE'])
def delete_servico(id):
    if session.get('user_tipo') != 'barbeiro':
        return jsonify({"erro": "Acesso negado"}), 401

    barbearia = get_barbearia_atual()
    conn = conectar_db()
    c = conn.cursor()
    c.execute("DELETE FROM servicos WHERE id=? AND barbearia_id=?", (id, barbearia['id']))
    conn.commit()
    conn.close()
    return jsonify({"sucesso": True})


@app.route('/api/profissionais', methods=['GET'])
def get_profissionais():
    barbearia = get_barbearia_atual()
    conn = conectar_db()
    c = conn.cursor()
    c.execute("SELECT * FROM profissionais WHERE barbearia_id=?", (barbearia['id'],))
    dados = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(dados)


@app.route('/api/profissionais', methods=['POST'])
def add_profissional():
    if session.get('user_tipo') != 'barbeiro':
        return jsonify({"erro": "Acesso negado"}), 401

    barbearia = get_barbearia_atual()
    nome = request.form.get('nome')
    especialidade = request.form.get('especialidade')
    foto = request.files.get('foto')

    if not nome or not especialidade:
        return jsonify({"erro": "Preencha nome e especialidade."}), 400

    caminho_foto = salvar_arquivo_unico(foto)

    conn = conectar_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO profissionais (barbearia_id, nome, especialidade, status, foto) VALUES (?, ?, ?, 'Disponivel', ?)",
        (barbearia['id'], nome, especialidade, caminho_foto)
    )
    conn.commit()
    conn.close()
    return jsonify({"sucesso": True})


@app.route('/api/profissionais/<int:id>/status', methods=['PUT'])
def mudar_status_profissional(id):
    if session.get('user_tipo') != 'barbeiro':
        return jsonify({"erro": "Acesso negado"}), 401

    barbearia = get_barbearia_atual()
    dados = request.json
    conn = conectar_db()
    c = conn.cursor()
    c.execute("UPDATE profissionais SET status=? WHERE id=? AND barbearia_id=?", (dados['status'], id, barbearia['id']))
    conn.commit()
    conn.close()
    return jsonify({"sucesso": True})


# ================= AGENDAMENTOS E HORÁRIOS INTELIGENTES =================

@app.route('/api/horarios_ocupados')
def horarios_ocupados():
    barbearia = get_barbearia_atual()
    profissional = request.args.get('profissional')
    data = request.args.get('data')

    conn = conectar_db()
    c = conn.cursor()

    c.execute("""
        SELECT a.hora, COALESCE(s.duracao, 30) as duracao
        FROM agendamentos a
        LEFT JOIN servicos s ON a.servico = s.nome AND s.barbearia_id = a.barbearia_id
        WHERE a.profissional = ? AND a.data = ? AND a.barbearia_id = ?
    """, (profissional, data, barbearia['id']))

    agendamentos = c.fetchall()
    conn.close()

    intervalos = []
    for ag in agendamentos:
        inicio = hora_para_minutos(ag['hora'])
        fim = inicio + ag['duracao']
        intervalos.append({"inicio": inicio, "fim": fim})

    return jsonify(intervalos)


@app.route('/agendar', methods=['POST'])
def agendar():
    if 'user_id' not in session:
        return jsonify({"erro": "Precisa estar logado"}), 401

    barbearia = get_barbearia_atual()
    dados = request.json
    data = dados.get('data')
    hora = dados.get('hora')
    profissional = dados.get('profissional')
    servico_nome = dados.get('servico')

    try:
        data_hora = datetime.datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M")
        if data_hora < datetime.datetime.now():
            return jsonify({"erro": "Não é possível agendar para um horário que já passou."}), 400
    except:
        return jsonify({"erro": "Data ou hora inválida."}), 400

    conn = conectar_db()
    c = conn.cursor()

    c.execute("SELECT * FROM agendamentos WHERE cliente_id=? AND data=? AND barbearia_id=?", (session['user_id'], data, barbearia['id']))
    if c.fetchone():
        conn.close()
        return jsonify({"erro": "Você já possui um agendamento neste dia."}), 400

    c.execute("SELECT duracao FROM servicos WHERE nome=? AND barbearia_id=?", (servico_nome, barbearia['id']))
    srv = c.fetchone()
    duracao_nova = srv['duracao'] if srv else 30
    inicio_novo = hora_para_minutos(hora)
    fim_novo = inicio_novo + duracao_nova

    c.execute("""
        SELECT a.hora, COALESCE(s.duracao, 30) as duracao
        FROM agendamentos a
        LEFT JOIN servicos s ON a.servico = s.nome AND s.barbearia_id = a.barbearia_id
        WHERE a.data=? AND a.profissional=? AND a.barbearia_id=?
    """, (data, profissional, barbearia['id']))

    for ag in c.fetchall():
        inicio_existente = hora_para_minutos(ag['hora'])
        fim_existente = inicio_existente + ag['duracao']

        if inicio_novo < fim_existente and fim_novo > inicio_existente:
            conn.close()
            return jsonify({"erro": "Este horário conflita com outro atendimento."}), 400

    c.execute(
        "INSERT INTO agendamentos (barbearia_id, cliente_id, cliente_nome, profissional, data, hora, servico) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (barbearia['id'], session['user_id'], session['user_nome'], profissional, data, hora, servico_nome)
    )
    conn.commit()

    nome_loja = barbearia['nome'] if barbearia else 'King Barbearia'
    whats_loja = barbearia['whatsapp_dono'] if (barbearia and barbearia['whatsapp_dono']) else '5562994016649'
    texto = f"Olá! Acabei de agendar na {nome_loja}:\n✂️ *Serviço:* {servico_nome} ({duracao_nova} min)\n💈 *Barbeiro:* {profissional}\n📅 *Data:* {data} às {hora}"
    link_whatsapp = f"https://wa.me/{whats_loja}?text={urllib.parse.quote(texto)}"
    conn.close()

    return jsonify({
        "mensagem": "Agendado com sucesso!",
        "link_wa": link_whatsapp,
        "detalhes": f"{servico_nome} ({duracao_nova} min) com {profissional} dia {data} às {hora}"
    })


# ================= PAINEL DO BARBEIRO E ASSISTENTE =================

@app.route('/api/agendamentos_barbeiro')
def agendamentos_barbeiro():
    if 'user_id' not in session or session.get('user_tipo') != 'barbeiro':
        return jsonify({"erro": "Acesso negado"}), 401
    barbearia = get_barbearia_atual()
    conn = conectar_db()
    c = conn.cursor()
    c.execute("""SELECT a.*, u.email, u.telefone, u.foto 
                 FROM agendamentos a 
                 LEFT JOIN usuarios u ON a.cliente_id = u.id 
                 WHERE a.barbearia_id = ?
                 ORDER BY a.data, a.hora""", (barbearia['id'],))
    dados = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(dados)


@app.route('/api/grafico')
def grafico():
    if 'user_id' not in session or session.get('user_tipo') != 'barbeiro':
        return jsonify({"erro": "Acesso negado"}), 401
    barbearia = get_barbearia_atual()
    conn = conectar_db()
    c = conn.cursor()
    dados = []
    for i in range(6, -1, -1):
        dia = datetime.datetime.now() - datetime.timedelta(days=i)
        data_str = dia.strftime("%Y-%m-%d")
        c.execute("""SELECT SUM(s.preco) as total FROM agendamentos a 
                     JOIN servicos s ON a.servico = s.nome AND s.barbearia_id = a.barbearia_id
                     WHERE a.data = ? AND a.barbearia_id = ?""", (data_str, barbearia['id']))
        res = c.fetchone()
        dados.append({"data": dia.strftime("%d/%m"), "total": res['total'] if res['total'] else 0.0})
    conn.close()
    return jsonify(dados)


@app.route('/api/avaliar', methods=['POST'])
def avaliar():
    if 'user_id' not in session:
        return jsonify({"erro": "Faça login para avaliar"}), 401
    barbearia = get_barbearia_atual()
    dados = request.json
    nota = int(dados.get('nota', 0))
    if nota < 1 or nota > 5:
        return jsonify({"erro": "Nota inválida."}), 400
    conn = conectar_db()
    c = conn.cursor()
    c.execute("UPDATE agendamentos SET avaliacao=? WHERE id=? AND cliente_id=? AND barbearia_id=?", (nota, dados['agendamento_id'], session['user_id'], barbearia['id']))
    conn.commit()
    conn.close()
    return jsonify({"mensagem": "Avaliação registrada!"})


@app.route('/api/assistente', methods=['POST'])
def assistente():
    if 'user_id' not in session or session.get('user_tipo') != 'barbeiro':
        return jsonify({"erro": "Acesso negado"}), 401
    barbearia = get_barbearia_atual()
    dados = request.json
    pergunta = dados.get('pergunta', '').lower()
    conn = conectar_db()
    c = conn.cursor()
    resposta = ""

    if "hoje" in pergunta and ("cliente" in pergunta or "agendamento" in pergunta):
        hoje_str = datetime.datetime.now().strftime("%Y-%m-%d")
        c.execute("SELECT cliente_nome, hora, servico FROM agendamentos WHERE data=? AND barbearia_id=? ORDER BY hora", (hoje_str, barbearia['id']))
        agenda = c.fetchall()
        if len(agenda) == 0:
            resposta = "Você não tem nenhum cliente agendado para hoje."
        else:
            resposta = f"Você tem {len(agenda)} cliente(s) hoje:\n"
            for a in agenda:
                resposta += f"⏰ {a['hora']} - {a['cliente_nome']} ({a['servico']})\n"

    elif "dados" in pergunta or "telefone" in pergunta or "email" in pergunta or "contato" in pergunta:
        nome_busca = pergunta.replace("?", "").split()[-1].capitalize()
        c.execute("SELECT nome, email, telefone FROM usuarios WHERE nome LIKE ? AND barbearia_id=?", ('%' + nome_busca + '%', barbearia['id']))
        u = c.fetchone()
        if u:
            resposta = f"Dados de {u['nome']}:\n📧 E-mail: {u['email']}\n📱 Telefone: {u['telefone']}"
        else:
            resposta = f"Não encontrei ninguém com o nome '{nome_busca}'."

    elif "faturamento" in pergunta or "lucro" in pergunta:
        hoje_str = datetime.datetime.now().strftime("%Y-%m-%d")
        c.execute("SELECT s.preco FROM agendamentos a JOIN servicos s ON a.servico = s.nome AND s.barbearia_id = a.barbearia_id WHERE a.data=? AND a.barbearia_id=?", (hoje_str, barbearia['id']))
        precos = c.fetchall()
        total = sum([p['preco'] for p in precos])
        resposta = f"O faturamento de hoje é R$ {total:.2f}."
    else:
        resposta = "Sou seu assistente. Você pode perguntar:\n- 'Tem cliente hoje?'\n- 'Qual o telefone do João?'\n- 'Qual o faturamento?'"

    conn.close()
    return jsonify({"resposta": resposta})


# ================= CADASTRO DE NOVAS BARBEARIAS =================

@app.route('/nova_barbearia')
def pagina_nova_barbearia():
    return render_template('cadastrar_barbearia.html')


@app.route('/api/cadastrar_barbearia', methods=['POST'])
def cadastrar_barbearia():
    dados = request.json
    nome = (dados.get('nome') or '').strip()
    slug = (dados.get('slug') or '').strip().lower()
    whatsapp = (dados.get('whatsapp') or '').strip()
    cor_tema = (dados.get('cor_tema') or '#00bfff').strip()
    senha = (dados.get('senha') or '').strip()

    reservados = ['login', 'login_admin', 'painel', 'logout', 'agendar', 'tela_agendamento',
                  'cadastro', 'admin_secreto', 'nova_barbearia', 'super_admin', 'api', 'static']

    if not nome or not slug or not whatsapp or not senha:
        return jsonify({"erro": "Preencha todos os campos."}), 400

    if slug in reservados or len(slug) < 2:
        return jsonify({"erro": "Esse link não está disponível. Escolha outro."}), 400

    somente_numeros = ''.join(filter(str.isdigit, whatsapp))
    if not somente_numeros.startswith('55'):
        somente_numeros = '55' + somente_numeros

    conn = conectar_db()
    c = conn.cursor()

    c.execute("SELECT id FROM barbearias WHERE slug = ?", (slug,))
    if c.fetchone():
        conn.close()
        return jsonify({"erro": "Esse link já está em uso por outra barbearia."}), 400

    vencimento = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")

    c.execute(
        """INSERT INTO barbearias (nome, slug, whatsapp_dono, plano, status_pagamento, data_vencimento, cor_tema)
           VALUES (?, ?, ?, 'mensal', 'ativo', ?, ?)""",
        (nome, slug, somente_numeros, vencimento, cor_tema)
    )
    nova_barbearia_id = c.lastrowid

    senha_hash = generate_password_hash(senha)
    c.execute(
        "INSERT INTO usuarios (barbearia_id, nome, email, telefone, senha, tipo) VALUES (?, 'Admin', ?, ?, ?, 'barbeiro')",
        (nova_barbearia_id, f'admin@{slug}.com', somente_numeros, senha_hash)
    )

    servicos_iniciais = [
        (nova_barbearia_id, 'Corte', 35.00, 30),
        (nova_barbearia_id, 'Barba', 25.00, 30)
    ]
    c.executemany("INSERT INTO servicos (barbearia_id, nome, preco, duracao) VALUES (?, ?, ?, ?)", servicos_iniciais)

    c.execute(
        "INSERT INTO profissionais (barbearia_id, nome, especialidade, status, foto) VALUES (?, 'Barbeiro Principal', 'Corte e Barba', 'Disponivel', '')",
        (nova_barbearia_id,)
    )

    conn.commit()
    conn.close()

    return jsonify({"mensagem": "Barbearia criada com sucesso!", "slug": slug})


# ================= PAINEL SUPER-ADMIN (GESTOR DO SHOPPBARBER) =================

@app.route('/super_admin')
def super_admin():
    autenticado = session.get('is_super_admin', False)
    return render_template('super_admin.html', autenticado=autenticado)


@app.route('/api/super_admin/login', methods=['POST'])
def super_admin_login():
    dados = request.json
    if dados.get('senha') == SENHA_SUPER_ADMIN:
        session['is_super_admin'] = True
        return jsonify({"sucesso": True})
    return jsonify({"erro": "Senha mestra incorreta."}), 401


@app.route('/api/super_admin/logout', methods=['POST'])
def super_admin_logout():
    session.pop('is_super_admin', None)
    return jsonify({"sucesso": True})


@app.route('/api/super_admin/barbearias', methods=['GET'])
def listar_barbearias():
    if not session.get('is_super_admin'):
        return jsonify({"erro": "Acesso negado"}), 401

    conn = conectar_db()
    c = conn.cursor()
    c.execute("SELECT * FROM barbearias ORDER BY id ASC")
    rows = c.fetchall()
    conn.close()

    hoje = datetime.date.today()
    lista = []
    for r in rows:
        item = dict(r)
        if item['plano'] == 'vitalicio':
            item['dias_restantes'] = None
        elif item['data_vencimento']:
            try:
                venc = datetime.datetime.strptime(item['data_vencimento'], "%Y-%m-%d").date()
                item['dias_restantes'] = (venc - hoje).days
            except:
                item['dias_restantes'] = 0
        else:
            item['dias_restantes'] = 0
        lista.append(item)

    return jsonify(lista)


@app.route('/api/super_admin/barbearias/<int:id>/renovar', methods=['POST'])
def renovar_barbearia(id):
    if not session.get('is_super_admin'):
        return jsonify({"erro": "Acesso negado"}), 401

    conn = conectar_db()
    c = conn.cursor()
    c.execute("SELECT * FROM barbearias WHERE id = ?", (id,))
    b = c.fetchone()
    if not b:
        conn.close()
        return jsonify({"erro": "Barbearia não encontrada"}), 404

    hoje = datetime.date.today()
    base = hoje
    if b['data_vencimento']:
        try:
            venc_atual = datetime.datetime.strptime(b['data_vencimento'], "%Y-%m-%d").date()
            if venc_atual > hoje:
                base = venc_atual
        except:
            pass

    nova_data = (base + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    c.execute(
        "UPDATE barbearias SET plano='mensal', status_pagamento='ativo', data_vencimento=? WHERE id=?",
        (nova_data, id)
    )
    conn.commit()
    conn.close()
    return jsonify({"sucesso": True, "nova_data": nova_data})


@app.route('/api/super_admin/barbearias/<int:id>/vitalicio', methods=['POST'])
def tornar_vitalicio(id):
    if not session.get('is_super_admin'):
        return jsonify({"erro": "Acesso negado"}), 401

    conn = conectar_db()
    c = conn.cursor()
    c.execute(
        "UPDATE barbearias SET plano='vitalicio', status_pagamento='ativo', data_vencimento=NULL WHERE id=?",
        (id,)
    )
    conn.commit()
    conn.close()
    return jsonify({"sucesso": True})


@app.route('/api/super_admin/barbearias/<int:id>/status', methods=['POST'])
def alterar_status_barbearia(id):
    if not session.get('is_super_admin'):
        return jsonify({"erro": "Acesso negado"}), 401

    dados = request.json
    novo_status = dados.get('status', 'ativo')
    conn = conectar_db()
    c = conn.cursor()
    c.execute("UPDATE barbearias SET status_pagamento=? WHERE id=?", (novo_status, id))
    conn.commit()
    conn.close()
    return jsonify({"sucesso": True})


@app.route('/api/super_admin/barbearias/<int:id>', methods=['DELETE'])
def excluir_barbearia(id):
    if not session.get('is_super_admin'):
        return jsonify({"erro": "Acesso negado"}), 401
    if id == 1:
        return jsonify({"erro": "A King Barbearia padrão não pode ser excluída."}), 400

    conn = conectar_db()
    c = conn.cursor()
    c.execute("DELETE FROM agendamentos WHERE barbearia_id=?", (id,))
    c.execute("DELETE FROM servicos WHERE barbearia_id=?", (id,))
    c.execute("DELETE FROM profissionais WHERE barbearia_id=?", (id,))
    c.execute("DELETE FROM usuarios WHERE barbearia_id=?", (id,))
    c.execute("DELETE FROM barbearias WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"sucesso": True})


# ================= ROTA DINÂMICA DE LINK DA BARBEARIA (EX: /king) =================

@app.route('/<slug>')
def entrar_barbearia(slug):
    conn = conectar_db()
    c = conn.cursor()
    c.execute("SELECT * FROM barbearias WHERE slug = ?", (slug.lower(),))
    barbearia = c.fetchone()
    conn.close()

    if not barbearia:
        return "Barbearia não encontrada no ShoppBarber.", 404

    if session.get('barbearia_id') != barbearia['id']:
        session.clear()
        session['barbearia_id'] = barbearia['id']
        session['barbearia_slug'] = barbearia['slug']
        session['barbearia_nome'] = barbearia['nome']

    return redirect('/')


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)