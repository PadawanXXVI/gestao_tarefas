from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from markupsafe import Markup
import pandas as pd
import plotly.express as px
from flask_migrate import Migrate
from plotly.subplots import make_subplots

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from flask_migrate import Migrate


app = Flask(__name__)

# Configuração do Banco de Dados
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# 🔁 Modelo de Histórico de Execução
class ExecucaoTarefa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tarefa_id = db.Column(db.Integer, db.ForeignKey('tarefa.id'), nullable=False)
    data = db.Column(db.Date, nullable=False)
    percentual = db.Column(db.Float, nullable=False)

    tarefa = db.relationship('Tarefa', backref=db.backref('execucoes', lazy=True))

# Modelo de Projetos
class Projeto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    prazo_nominal = db.Column(db.Integer, nullable=False)
    data_inicio = db.Column(db.Date, nullable=False)

    # Relacionamento: Um projeto tem várias tarefas através dos tópicos
    def get_tarefas(self):
        return Tarefa.query.join(Topico).filter(Topico.projeto_id == self.id).all()

# Modelo de Tópicos e Subtópicos
class Topico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    projeto_id = db.Column(db.Integer, db.ForeignKey('projeto.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('topico.id'), nullable=True)

    subtitulos = db.relationship('Topico', backref=db.backref('parent', remote_side=[id]), lazy=True)


# Modelo de Tarefas
class Tarefa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    topico_id = db.Column(db.Integer, db.ForeignKey('topico.id'), nullable=False)
    responsavel_id = db.Column(db.Integer, db.ForeignKey('colaborador.id'), nullable=False)

    data_inicio_planejada = db.Column(db.Date, nullable=False)
    data_fim_planejada = db.Column(db.Date, nullable=False)
    horas_planejadas = db.Column(db.Float, default=0.0)

    data_inicio_executada = db.Column(db.Date, nullable=True)
    data_fim_executada = db.Column(db.Date, nullable=True)
    horas_executadas = db.Column(db.Float, default=0.0)

    percentual_execucao = db.Column(db.Float, default=0.0)  # **🔹 Novo campo para indicar a porcentagem de execução**

    # Relacionamento com Colaborador
    responsavel = db.relationship('Colaborador', backref=db.backref('tarefas', lazy=True))

    # 🔹 Adicionando o relacionamento com Topico
    topico = db.relationship('Topico', backref=db.backref('tarefas', lazy=True), overlaps="tarefas")


# Modelo de Colaboradores
class Colaborador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cargo = db.Column(db.String(50), nullable=False)
    custo_hora = db.Column(db.Float, nullable=False)


with app.app_context():
    db.create_all()


# Função para estruturar tópicos e subtópicos
def organizar_topicos(topicos, parent_id=None, nivel=0):
    organizados = []
    filtrados = sorted([t for t in topicos if t.parent_id == parent_id], key=lambda x: x.id)
    for topico in filtrados:
        organizados.append((topico, nivel))
        organizados.extend(organizar_topicos(topicos, topico.id, nivel + 1))
    return organizados


@app.route('/')
def index():
    projetos = Projeto.query.all()
    colaboradores = Colaborador.query.all()
    return render_template('index.html', projetos=projetos, colaboradores=colaboradores)


from datetime import datetime

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from flask import jsonify, render_template
from datetime import datetime


@app.route('/dashboard/<int:projeto_id>')
def dashboard_projeto(projeto_id):
    projeto = Projeto.query.get_or_404(projeto_id)
    tarefas = Tarefa.query.join(Topico).filter(Topico.projeto_id == projeto.id).all()
    hoje = datetime.today().date()
    total_percentual = sum(t.percentual_execucao or 0 for t in tarefas)
    progresso_total = total_percentual / len(tarefas) if tarefas else 0.0

    # 📈 Status das Tarefas
    status_tarefas = {
        'Concluído': sum(1 for t in tarefas if t.percentual_execucao == 100),
        'Em Execução': sum(1 for t in tarefas if 0 < t.percentual_execucao < 100),
        'Atrasado': sum(
            1 for t in tarefas if t.data_fim_planejada and t.data_fim_planejada < hoje and t.percentual_execucao < 100),
        'Não Iniciadas': sum(1 for t in tarefas if (t.percentual_execucao or 0) == 0),
    }

    # 📌 Tempo Nominal
    data_fim_nominal = projeto.data_inicio + timedelta(days=projeto.prazo_nominal)
    datas_nominal = pd.date_range(start=projeto.data_inicio, end=data_fim_nominal)
    nominal = [(i / (len(datas_nominal) - 1)) * 100 for i in range(len(datas_nominal))]

    # 📌 Curva Planejada (baseada nas tarefas)
    progresso_planejado_por_data = {}
    for t in tarefas:
        dias = (t.data_fim_planejada - t.data_inicio_planejada).days + 1
        if dias <= 0:
            continue
        carga_diaria = 100 / dias
        for i in range(dias):
            dia = t.data_inicio_planejada + timedelta(days=i)
            progresso_planejado_por_data[dia] = progresso_planejado_por_data.get(dia, 0) + carga_diaria

    datas_planejado = sorted(progresso_planejado_por_data.keys())
    progresso_planejado = []
    acumulado = 0
    for d in datas_planejado:
        acumulado += progresso_planejado_por_data[d]
        progresso_planejado.append(acumulado / len(tarefas))

    # 📌 Curva Executada (ExecucaoTarefa)
    exec_data = ExecucaoTarefa.query.join(Tarefa).join(Topico).filter(Topico.projeto_id == projeto.id).all()
    if exec_data:
        df_exec = pd.DataFrame([{
            "Data": e.data,
            "Tarefa": e.tarefa_id,
            "Percentual": e.percentual
        } for e in exec_data])

        df_exec["Data"] = pd.to_datetime(df_exec["Data"])
        df_exec = df_exec.sort_values(["Tarefa", "Data"])
        df_exec["Acumulado"] = df_exec.groupby("Tarefa")["Percentual"].cummax()
        df_exec_diario = df_exec.groupby("Data")["Acumulado"].sum().reset_index()
        df_exec_diario["Progresso"] = df_exec_diario["Acumulado"] / len(tarefas)
        df_exec_diario["Linha"] = "Executado"
        df_exec_final = df_exec_diario[["Data", "Progresso", "Linha"]]
    else:
        df_exec_final = pd.DataFrame(columns=["Data", "Progresso", "Linha"])

    # 🔹 Unificação da Curva S
    df_nominal = pd.DataFrame({"Data": datas_nominal, "Linha": "Nominal", "Progresso": nominal})
    df_planejado = pd.DataFrame({"Data": datas_planejado, "Linha": "Planejado", "Progresso": progresso_planejado})
    df_tempo = pd.concat([df_nominal, df_planejado, df_exec_final])

    fig_tempo = px.line(
        df_tempo,
        x="Data",
        y="Progresso",
        color="Linha",
        title="📊 Progresso do Tempo: Nominal vs Planejado vs Executado",
        labels={"Progresso": "Progresso (%)"}
    )
    fig_tempo.update_layout(
        template="simple_white",
        font=dict(size=14),
        title_font=dict(size=18),
        legend=dict(title=None, orientation="h", x=0.5, xanchor="center", y=-0.3),
        margin=dict(t=40, b=60, l=20, r=20)
    )

    # 📉 Burndown Chart
    datas_burndown_nominal = pd.date_range(start=projeto.data_inicio, end=data_fim_nominal)
    df_burndown_nominal = pd.DataFrame({
        "Data": datas_burndown_nominal,
        "Trabalho (%)": [(1 - i / (len(datas_burndown_nominal) - 1)) * 100 for i in range(len(datas_burndown_nominal))],
        "Linha": "Nominal"
    })

    # 🔹 Planejado no Burndown
    total_tarefas = len(tarefas)
    trabalho_total = total_tarefas * 100
    trabalho_restante_planejado = []
    acumulado_planejado = 0
    for d in datas_planejado:
        acumulado_planejado += progresso_planejado_por_data[d]
        restante = max(trabalho_total - acumulado_planejado, 0)
        trabalho_restante_planejado.append(restante / total_tarefas)

    df_burndown_planejado = pd.DataFrame({
        "Data": datas_planejado,
        "Trabalho (%)": trabalho_restante_planejado,
        "Linha": "Planejado"
    })

    # 🔹 Executado no Burndown
    if exec_data:
        df_hist = pd.DataFrame([{
            "Data": e.data,
            "Tarefa": e.tarefa_id,
            "Percentual": e.percentual
        } for e in exec_data])
        df_hist["Data"] = pd.to_datetime(df_hist["Data"])
        df_hist = df_hist.sort_values(["Tarefa", "Data"])
        df_hist["Acumulado"] = df_hist.groupby("Tarefa")["Percentual"].cummax()
        df_diario = df_hist.groupby("Data")["Acumulado"].sum().reset_index()
        df_diario["Trabalho (%)"] = (trabalho_total - df_diario["Acumulado"]) / total_tarefas
        df_diario["Linha"] = "Executado"
        df_burndown_exec = df_diario[["Data", "Trabalho (%)", "Linha"]]
    else:
        df_burndown_exec = pd.DataFrame(columns=["Data", "Trabalho (%)", "Linha"])

    # 🔹 Unir tudo no Burndown
    df_burndown = pd.concat([df_burndown_nominal, df_burndown_planejado, df_burndown_exec])
    fig_burndown = px.line(
        df_burndown,
        x="Data",
        y="Trabalho (%)",
        color="Linha",
        title="📉 Burndown Chart - Trabalho Restante",
        labels={"Trabalho (%)": "Trabalho (%)", "Data": "Data"}
    )
    fig_burndown.update_layout(template="simple_white", font=dict(size=14), title_font=dict(size=18))

    # 👥 Alocação de Recursos
    df_recursos = pd.DataFrame([
        {"Colaborador": t.responsavel.nome, "Horas": t.horas_planejadas}
        for t in tarefas if t.responsavel
    ])
    fig_recursos = px.bar(df_recursos, x="Horas", y="Colaborador", orientation="h",
                          title="👥 Alocação de Recursos por Colaborador")
    fig_recursos.update_layout(template="simple_white", font=dict(size=14), title_font=dict(size=18))

    # 📊 Execução por Tarefa
    df_execucao = pd.DataFrame([
        {"Tarefa": t.nome, "Execução (%)": t.percentual_execucao or 0}
        for t in tarefas
    ])
    fig_execucao = px.bar(
        df_execucao,
        x="Tarefa",
        y="Execução (%)",
        title="📊 Execução por Tarefa"
    )
    fig_execucao.update_layout(
        template="simple_white",
        font=dict(size=14),
        title_font=dict(size=18),
        yaxis=dict(range=[0, 100])
    )

    # 📌 Execução por Tópico
    df_topico_execucao = pd.DataFrame([
        {"Tópico": t.topico.nome, "Execução": t.percentual_execucao or 0}
        for t in tarefas
    ])
    df_topico_resumo = df_topico_execucao.groupby("Tópico", as_index=False).mean()
    fig_topico = px.bar(
        df_topico_resumo,
        x="Tópico",
        y="Execução",
        title="📌 Execução Média por Tópico",
        text="Execução"
    )
    fig_topico.update_layout(
        template="simple_white",
        font=dict(size=14),
        title_font=dict(size=18),
        yaxis=dict(range=[0, 100])
    )

    # 🔺 Cálculo do Caminho Crítico por Tópico
    caminho_critico_topico = None
    maior_duracao_total = 0
    for topico in set(t.topico for t in tarefas):
        tarefas_topico = [t for t in tarefas if t.topico == topico]
        duracao_total_topico = 0
        for tarefa in tarefas_topico:
            if tarefa.data_inicio_executada and tarefa.percentual_execucao > 0:
                dias_exec = (hoje - tarefa.data_inicio_executada).days
                estimativa_total = dias_exec / (tarefa.percentual_execucao / 100)
                duracao_total_topico += estimativa_total
            else:
                duracao_planejada = (tarefa.data_fim_planejada - tarefa.data_inicio_planejada).days + 1
                duracao_total_topico += duracao_planejada
        if duracao_total_topico > maior_duracao_total:
            maior_duracao_total = duracao_total_topico
            caminho_critico_topico = topico.nome if topico else "Indefinido"

    # 🔹 Gráfico do Caminho Crítico
    tarefas_criticas = [t for t in tarefas if t.topico.nome == caminho_critico_topico]
    df_critico = pd.DataFrame([
        {
            "Tarefa": t.nome,
            "Início": t.data_inicio_executada or t.data_inicio_planejada,
            "Fim": t.data_fim_executada or t.data_fim_planejada
        }
        for t in tarefas_criticas
    ])
    fig_caminho_critico = px.timeline(
        df_critico,
        x_start="Início",
        x_end="Fim",
        y="Tarefa",
        title=f"📌 Caminho Crítico - Tópico: {caminho_critico_topico}"
    )
    fig_caminho_critico.update_yaxes(autorange="reversed")
    fig_caminho_critico.update_layout(
        template="simple_white",
        font=dict(size=14),
        title_font=dict(size=18)
    )

    return render_template(
        "dashboard_projeto.html",
        projeto=projeto,
        status_tarefas=status_tarefas,
        fig_tempo=fig_tempo.to_html(full_html=False),
        fig_burndown=fig_burndown.to_html(full_html=False),
        fig_recursos=fig_recursos.to_html(full_html=False),
        fig_execucao=fig_execucao.to_html(full_html=False),
        fig_topico=fig_topico.to_html(full_html=False),
        fig_caminho_critico=fig_caminho_critico.to_html(full_html=False),
        caminho_critico=caminho_critico_topico,
        progresso_total=round(progresso_total, 2)
    )


from datetime import datetime, timedelta


@app.route('/projeto/<int:projeto_id>')
def visualizar_projeto(projeto_id):
    projeto = Projeto.query.get_or_404(projeto_id)
    topicos = Topico.query.filter_by(projeto_id=projeto_id).all()
    tarefas = Tarefa.query.filter(Tarefa.topico_id.in_([t.id for t in topicos])).all()

    total_percentual = sum(t.percentual_execucao or 0 for t in tarefas)
    progresso_total = total_percentual / len(tarefas) if tarefas else 0.0

    # 🧱 DataFrame para o Gantt
    df_gantt = pd.DataFrame([
        {
            "Tarefa": t.nome,
            "Responsável": t.responsavel.nome if t.responsavel else "Sem responsável",
            "Início Planejado": t.data_inicio_planejada,
            "Fim Planejado": t.data_fim_planejada,
            "Duração (dias)": (t.data_fim_planejada - t.data_inicio_planejada).days + 1,
            "Execução (%)": t.percentual_execucao or 0
        } for t in tarefas
    ])
    df_gantt["Início Planejado"] = pd.to_datetime(df_gantt["Início Planejado"])
    df_gantt["Fim Planejado"] = pd.to_datetime(df_gantt["Fim Planejado"])

    # 📊 Gantt Chart
    fig = px.timeline(
        df_gantt,
        x_start="Início Planejado",
        x_end="Fim Planejado",
        y="Tarefa",
        color="Responsável",
        hover_data=["Duração (dias)", "Execução (%)"],
        title=f"Gantt Planejado - {projeto.nome}"
    )
    fig.update_yaxes(autorange="reversed")

    # 🔴 Datas importantes
    inicio_proj = pd.Timestamp(projeto.data_inicio)
    fim_nominal = inicio_proj + pd.Timedelta(days=projeto.prazo_nominal)
    meta_pct = 0.70  # Meta de 70%
    data_meta = inicio_proj + pd.Timedelta(days=int(projeto.prazo_nominal * meta_pct))

    # 🟥 Faixa do prazo contratual
    fig.add_vrect(
        x0=fim_nominal - pd.Timedelta(hours=12),
        x1=fim_nominal + pd.Timedelta(hours=12),
        fillcolor="red",
        opacity=0.15,
        layer="below",
        line_width=0
    )
    fig.add_annotation(
        x=fim_nominal,
        y=1.05,
        xref="x",
        yref="paper",
        text="📌 Prazo Contratual",
        showarrow=False,
        font=dict(color="red", size=12),
        align="center",
        bgcolor="rgba(255,255,255,0.6)"
    )

    # 🟦 Linha vertical da meta
    fig.add_shape(
        type="line",
        x0=data_meta,
        x1=data_meta,
        y0=0,
        y1=1,
        xref="x",
        yref="paper",
        layer="above",  # força a linha a ser visível
        line=dict(color="blue", dash="dash", width=2),
        opacity=0.8
    )
    fig.add_annotation(
        x=data_meta,
        y=1.07,
        xref="x",
        yref="paper",
        text=f"🎯 Meta 70% do Tempo",
        showarrow=False,
        font=dict(color="blue", size=12),
        align="center",
        bgcolor="rgba(255,255,255,0.6)"
    )

    # Ajustar eixo X se necessário
    fig.update_xaxes(range=[
        df_gantt["Início Planejado"].min(),
        max(df_gantt["Fim Planejado"].max(), fim_nominal + pd.Timedelta(days=1))
    ])

    # Layout final
    fig.update_layout(
        template="simple_white",
        font=dict(size=14),
        title_font=dict(size=18),
        margin=dict(t=120, b=60),
        xaxis_title="Data",
        yaxis_title="Tarefa"
    )

    gantt_html = fig.to_html(full_html=False)

    return render_template(
        'projeto.html',
        projeto=projeto,
        topicos=organizar_topicos(topicos),
        tarefas=tarefas,
        progresso_total=round(progresso_total, 2),
        hoje=datetime.today().strftime('%Y-%m-%d'),
        gantt_html=gantt_html
    )


@app.route('/projeto/<int:projeto_id>/adicionar_topico', methods=['GET', 'POST'])
def adicionar_topico(projeto_id):
    if request.method == 'POST':
        nome = request.form['nome']
        parent_id = request.form.get('parent_id')
        parent_id = int(parent_id) if parent_id else None

        # Impedir criação de subtopico se o parent_id já tiver tarefas
        if parent_id:
            tarefas_existentes = Tarefa.query.filter_by(topico_id=parent_id).count()
            if tarefas_existentes > 0:
                return "Erro: Este tópico já possui tarefas e não pode ter sub-tópicos.", 400

        novo_topico = Topico(nome=nome, projeto_id=projeto_id, parent_id=parent_id)
        db.session.add(novo_topico)
        db.session.commit()
        return redirect(url_for('visualizar_projeto', projeto_id=projeto_id))

    topicos = Topico.query.filter_by(projeto_id=projeto_id).all()
    return render_template('adicionar_topico.html', projeto_id=projeto_id, topicos=topicos)


@app.route('/tarefa/<int:tarefa_id>/editar', methods=['GET', 'POST'])
def editar_tarefa(tarefa_id):
    """Edita os detalhes planejados da tarefa"""
    tarefa = Tarefa.query.get_or_404(tarefa_id)
    colaboradores = Colaborador.query.all()

    if request.method == 'POST':
        tarefa.nome = request.form['nome']
        tarefa.responsavel_id = int(request.form['responsavel_id'])
        tarefa.horas_planejadas = float(request.form.get('horas_planejadas', 0.0))
        tarefa.data_inicio_planejada = datetime.strptime(request.form['data_inicio_planejada'], '%Y-%m-%d').date()
        tarefa.data_fim_planejada = datetime.strptime(request.form['data_fim_planejada'], '%Y-%m-%d').date()

        db.session.commit()
        return redirect(url_for('visualizar_projeto', projeto_id=tarefa.topico.projeto_id))  # Agora funciona corretamente

    return render_template('editar_tarefa.html', tarefa=tarefa, colaboradores=colaboradores)

@app.route('/topico/<int:topico_id>/adicionar_tarefa', methods=['GET', 'POST'])
def adicionar_tarefa(topico_id):
    """ Adiciona uma nova tarefa planejada ao projeto """
    topico = Topico.query.get_or_404(topico_id)
    colaboradores = Colaborador.query.all()

    # Bloquear tarefas em tópicos que possuem subtópicos
    subtopicos_existentes = Topico.query.filter_by(parent_id=topico.id).count()
    if subtopicos_existentes > 0:
        return "Erro: Este tópico possui sub-tópicos e não pode ter tarefas.", 400

    if request.method == 'POST':
        nome = request.form['nome']
        responsavel_id = int(request.form['responsavel_id'])
        horas_planejadas = float(request.form.get('horas_planejadas', 0.0))
        data_inicio = datetime.strptime(request.form['data_inicio'], '%Y-%m-%d').date()
        data_fim = datetime.strptime(request.form['data_fim'], '%Y-%m-%d').date()

        nova_tarefa = Tarefa(
            nome=nome, topico_id=topico.id, responsavel_id=responsavel_id,
            horas_planejadas=horas_planejadas, data_inicio_planejada=data_inicio, data_fim_planejada=data_fim
        )
        db.session.add(nova_tarefa)
        db.session.commit()
        return redirect(url_for('visualizar_projeto', projeto_id=topico.projeto_id))

    return render_template('adicionar_tarefa.html', topico=topico, colaboradores=colaboradores)


@app.route('/tarefa/<int:tarefa_id>/atualizar_execucao', methods=['GET', 'POST'])
def atualizar_execucao_tarefa(tarefa_id):
    """Atualiza a execução da tarefa"""
    tarefa = Tarefa.query.get_or_404(tarefa_id)

    if request.method == 'POST':
        if 'data_inicio_executada' in request.form:
            if request.form['data_inicio_executada']:
                tarefa.data_inicio_executada = datetime.strptime(request.form['data_inicio_executada'],
                                                                 '%Y-%m-%d').date()
            else:
                tarefa.data_inicio_executada = None  # ✅ Agora pode ser removida

        # Se a data de fim for enviada vazia, removê-la do banco de dados
        if 'data_fim_executada' in request.form and request.form['data_fim_executada']:
            tarefa.data_fim_executada = datetime.strptime(request.form['data_fim_executada'], '%Y-%m-%d').date()
        else:
            tarefa.data_fim_executada = None  # Define como None se estiver vazia

        if 'horas_executadas' in request.form:
            tarefa.horas_executadas = float(request.form['horas_executadas'])

        if 'percentual_execucao' in request.form:
            tarefa.percentual_execucao = float(request.form['percentual_execucao'])

        db.session.commit()

        # Buscar o projeto associado via Tópico
        topico = Topico.query.get(tarefa.topico_id)
        return redirect(url_for('visualizar_projeto', projeto_id=topico.projeto_id))

    return render_template('atualizar_execucao_tarefa.html', tarefa=tarefa)



@app.route('/adicionar_projeto', methods=['GET', 'POST'])
def adicionar_projeto():
    if request.method == 'POST':
        nome = request.form['nome']
        prazo_nominal = int(request.form['prazo_nominal'])
        data_inicio = datetime.strptime(request.form['data_inicio'], '%Y-%m-%d').date()

        novo_projeto = Projeto(nome=nome, prazo_nominal=prazo_nominal, data_inicio=data_inicio)
        db.session.add(novo_projeto)
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('adicionar_projeto.html')


@app.route('/excluir_projeto/<int:projeto_id>')
def excluir_projeto(projeto_id):
    projeto = Projeto.query.get_or_404(projeto_id)
    db.session.delete(projeto)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/adicionar_colaborador', methods=['GET', 'POST'])
def adicionar_colaborador():
    if request.method == 'POST':
        nome = request.form['nome']
        cargo = request.form['cargo']
        custo_hora = float(request.form['custo_hora'])

        novo_colaborador = Colaborador(nome=nome, cargo=cargo, custo_hora=custo_hora)
        db.session.add(novo_colaborador)
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('adicionar_colaborador.html')


@app.route('/excluir_colaborador/<int:colaborador_id>')
def excluir_colaborador(colaborador_id):
    colaborador = Colaborador.query.get_or_404(colaborador_id)
    db.session.delete(colaborador)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/projeto/<int:projeto_id>/gantt')
def gantt(projeto_id):
    projeto = Projeto.query.get_or_404(projeto_id)
    topicos = Topico.query.filter_by(projeto_id=projeto_id).all()
    tarefas = Tarefa.query.filter(Tarefa.topico_id.in_([t.id for t in topicos])).all()

    df = pd.DataFrame(
        [{"Nome": t.nome, "Início": t.data_inicio_planejada, "Fim": t.data_fim_planejada} for t in tarefas])
    fig = px.timeline(df, x_start="Início", x_end="Fim", y="Nome", title=f'📊 Gantt - {projeto.nome}')

    gantt_html = Markup(fig.to_html(full_html=False))
    return render_template('gantt.html', projeto=projeto, gantt_html=gantt_html)
@app.route('/excluir_topico/<int:topico_id>')
def excluir_topico(topico_id):
    topico = Topico.query.get_or_404(topico_id)
    projeto_id = topico.projeto_id

    # Impedir a exclusão se houver subtópicos
    if Topico.query.filter_by(parent_id=topico.id).count() > 0:
        return "Erro: Não é possível excluir um tópico que possui subtópicos."

    db.session.delete(topico)
    db.session.commit()
    return redirect(url_for('visualizar_projeto', projeto_id=projeto_id))


@app.route('/editar_topico/<int:topico_id>', methods=['GET', 'POST'])
def editar_topico(topico_id):
    topico = Topico.query.get_or_404(topico_id)

    if request.method == 'POST':
        topico.nome = request.form['nome']
        db.session.commit()
        return redirect(url_for('visualizar_projeto', projeto_id=topico.projeto_id))

    return render_template('editar_topico.html', topico=topico)


@app.route('/editar_projeto/<int:projeto_id>', methods=['GET', 'POST'])
def editar_projeto(projeto_id):
    projeto = Projeto.query.get_or_404(projeto_id)

    if request.method == 'POST':
        projeto.nome = request.form['nome']
        projeto.prazo_nominal = int(request.form['prazo_nominal'])
        projeto.data_inicio = datetime.strptime(request.form['data_inicio'], '%Y-%m-%d').date()

        db.session.commit()
        return redirect(url_for('index'))

    return render_template('editar_projeto.html', projeto=projeto)


if __name__ == '__main__':
    app.run(debug=True)
