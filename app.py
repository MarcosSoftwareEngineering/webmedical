import os
from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'chave_local_apenas_para_dev')

# --- CONFIGURAÇÃO DO SUPABASE (via variáveis de ambiente) ---
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL e SUPABASE_KEY precisam estar definidas como variáveis de ambiente. "
        "Localmente, crie um arquivo .env ou defina-as no terminal antes de rodar o app."
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- ROTAS DE AUTENTICAÇÃO ---
@app.route('/')
def login_page():
    if 'usuario' in session:
        return redirect(url_for('painel_triagem'))
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def fazer_login():
    dados = request.json
    login_usuario = dados.get('login')
    senha_usuario = dados.get('senha')

    if not login_usuario or not senha_usuario:
        return jsonify({"status": "error", "message": "Informe celular e senha."}), 400

    try:
        resposta = supabase.table('usuarios').select('*') \
            .eq('login', login_usuario).eq('senha', senha_usuario).execute()
    except Exception as e:
        app.logger.error(f"Erro Supabase (login): {e}")
        return jsonify({"status": "error", "message": "Erro ao consultar o banco de dados."}), 500

    if resposta.data and len(resposta.data) > 0:
        session['usuario'] = login_usuario
        return jsonify({"status": "success", "message": "Login realizado com sucesso!"}), 200
    else:
        return jsonify({"status": "error", "message": "Celular ou Senha incorretos!"}), 401

@app.route('/api/cadastro', methods=['POST'])
def cadastrar_usuario():
    dados = request.json
    if not dados.get('email') or not dados.get('login') or not dados.get('senha'):
        return jsonify({"status": "error", "message": "Preencha todos os campos obrigatórios."}), 400

    novo_usuario = {
        "email": dados.get('email'),
        "login": dados.get('login'),
        "senha": dados.get('senha')
    }
    try:
        supabase.table('usuarios').insert(novo_usuario).execute()
        return jsonify({"status": "success", "message": "Usuário cadastrado com sucesso!"}), 201
    except Exception as e:
        erro_str = str(e)
        app.logger.error(f"Erro Supabase (cadastro): {erro_str}")
        if "duplicate key" in erro_str or "23505" in erro_str:
            return jsonify({"status": "error", "message": "Celular ou e-mail já cadastrados."}), 400
        return jsonify({"status": "error", "message": "Erro interno ao cadastrar. Tente novamente."}), 500

@app.route('/api/recuperar_senha', methods=['POST'])
def recuperar_senha():
    dados = request.json
    email = dados.get('email')

    if not email:
        return jsonify({"status": "error", "message": "Forneça um e-mail válido!"}), 400

    try:
        resposta = supabase.table('usuarios').select('*').eq('email', email).execute()
    except Exception as e:
        app.logger.error(f"Erro Supabase (recuperar_senha): {e}")
        return jsonify({"status": "error", "message": "Erro ao consultar o banco de dados."}), 500

    if resposta.data and len(resposta.data) > 0:
        return jsonify({"status": "success", "message": "Instruções de recuperação enviadas para o e-mail!"}), 200
    else:
        return jsonify({"status": "error", "message": "E-mail não encontrado no sistema!"}), 404

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login_page'))

# --- PAINEL PRINCIPAL ---
@app.route('/dashboard')
def painel_triagem():
    if 'usuario' not in session:
        return redirect(url_for('login_page'))
    return render_template('index.html', usuario=session['usuario'])

# --- ROTAS DA API DE PACIENTES ---
@app.route('/api/v1/pacientes', methods=['GET'])
def get_pacientes():
    try:
        resposta = supabase.table('pacientes').select('*').execute()
        pacientes = resposta.data

        prioridade_triagem = {"Vermelho": 1, "Amarelo": 2, "Verde": 3}
        pacientes_ordenados = sorted(
            pacientes,
            key=lambda p: (prioridade_triagem.get(p.get("triagem"), 4), p.get("id"))
        )
        return jsonify({"status": "success", "data": pacientes_ordenados}), 200
    except Exception as e:
        app.logger.error(f"Erro Supabase (get_pacientes): {e}")
        return jsonify({"status": "error", "message": "Erro ao carregar pacientes da base."}), 500

@app.route('/api/v1/pacientes', methods=['POST'])
def add_paciente():
    dados = request.json
    novo_paciente = {
        "nome": dados.get("nome"),
        "sintoma": dados.get("sintoma"),
        "triagem": dados.get("triagem")
    }
    try:
        resposta = supabase.table('pacientes').insert(novo_paciente).execute()
        return jsonify({"status": "success", "data": resposta.data[0]}), 201
    except Exception as e:
        app.logger.error(f"Erro Supabase (add_paciente): {e}")
        return jsonify({"status": "error", "message": "Erro ao salvar paciente."}), 500

@app.route('/api/v1/pacientes/<int:paciente_id>', methods=['PUT'])
def edit_paciente(paciente_id):
    dados = request.json
    dados_atualizados = {
        "nome": dados.get("nome"),
        "sintoma": dados.get("sintoma"),
        "triagem": dados.get("triagem")
    }
    try:
        resposta = supabase.table('pacientes').update(dados_atualizados).eq('id', paciente_id).execute()
        return jsonify({"status": "success", "data": resposta.data[0]}), 200
    except Exception as e:
        app.logger.error(f"Erro Supabase (edit_paciente): {e}")
        return jsonify({"status": "error", "message": "Erro ao atualizar dados do paciente."}), 500

@app.route('/api/v1/pacientes/<int:paciente_id>', methods=['DELETE'])
def delete_paciente(paciente_id):
    try:
        supabase.table('pacientes').delete().eq('id', paciente_id).execute()
        return jsonify({"status": "success", "message": "Removido"}), 200
    except Exception as e:
        app.logger.error(f"Erro Supabase (delete_paciente): {e}")
        return jsonify({"status": "error", "message": "Erro ao remover paciente da base."}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)