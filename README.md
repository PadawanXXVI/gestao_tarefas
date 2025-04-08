# 🗂️ Gestão de Tarefas - Projeto Flask

Este é um sistema web desenvolvido em **Python + Flask**, com suporte a **MySQL**, para o gerenciamento de projetos, tarefas e execução de progresso. Ele utiliza visualizações interativas, arquitetura modular e banco de dados relacional.

## 🎓 Sobre o Projeto

Este projeto foi desenvolvido como parte da disciplina **Data Visualization**, ministrada pelo professor **Ms. Guilherme Lustosa Ricarte**, no **3º semestre do Curso de Tecnologia em Ciência de Dados** da **Faculdade de Tecnologia e Inovação Senac DF**.

## 🚀 Tecnologias utilizadas

- Python 3.12
- Flask 3.1
- Flask-SQLAlchemy
- Flask-Migrate
- MySQL (via mysqlclient)
- Python-dotenv
- Estrutura com Application Factory

## 📦 Instalação e uso local

1. Clone o repositório:
```bash
git clone https://github.com/seu_usuario/gestao_tarefas.git
cd gestao_tarefas
```

2. Crie um ambiente virtual e ative:
```bash
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure o `.env` a partir do `.env.example`

5. Rode a aplicação:
```bash
export FLASK_APP=run.py
export FLASK_ENV=development
flask run
```

## 🗃️ Banco de dados

O projeto usa MySQL. Para preparar o banco:

```bash
flask db init
flask db migrate -m "Criação inicial"
flask db upgrade
```

## 👨‍💻 Autoria

Desenvolvido por Anderson de Matos Guimarães, aluno do Curso de Ciência de Dados - Faculdade de Tecnologia e Inovação Senac DF.

---

## 📄 Licença

Este projeto é acadêmico e sem fins lucrativos. Uso livre para fins educacionais.
