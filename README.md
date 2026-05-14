# 📖 Projeto Histórico de Navios

Sistema desenvolvido em **Django** para registro e gerenciamento de informações históricas de navios.  
O projeto inclui autenticação de usuários, geração de relatórios em PDF com **ReportLab** e interface administrativa via painel padrão do Django.

---

## 🚀 Tecnologias utilizadas
- [Python 3.12+](https://www.python.org/)
- [Django 6.0](https://www.djangoproject.com/)
- [ReportLab](https://www.reportlab.com/) (para geração de PDFs)
- Banco de dados **SQLite** (padrão, pode ser trocado por PostgreSQL/MySQL)

---

## 📦 Instalação

1. Clone o repositório:
   ```bash
   git clone <URL_DO_REPOSITORIO>
   cd historico_navios-main
2. Criar e ativar um ambiente virtual
   python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate # Linux/Mac
3. instale as dependências
   pip install -r requirements.txt

4. Crie um arquivo .env na raiz do projeto (mesmo nível do manage.py):
   ```bash
   dentro do env:
   DJANGO_SECRET_KEY=uma_chave_secreta_grande_e_unica
   DEBUG=True
   DATABASE_URL=sqlite:///db.sqlite3
O .env não deve ser versionado (já está no .gitignore).

6. Execute as migrações:
   ```bash
   python manage.py migrate
Crie um superusuário para acessar o painel admin:

6. crie um superusuário:
   ```bash
   python manage.py createsuperuser

7. rode o programa
   ```bash
   python manage.py runserver


📂 Estrutura de diretórios
```bash
historico_navios-main/
│
├── config/              # Configurações principais do Django
├── historico/           # Aplicação principal (models, views, urls)
├── static/              # Arquivos estáticos (CSS, JS, imagens)
├── media/               # Uploads de arquivos
├── templates/           # Templates HTML
├── db.sqlite3           # Banco de dados local (ignorado no Git)
├── manage.py            # Utilitário de gerenciamento Django
└── requirements.txt     # Dependências do projeto



🔒 Segurança
Nunca versionar db.sqlite3 ou .env.
Em produção, usar DEBUG=False e configurar ALLOWED_HOSTS.
Usar banco de dados robusto (PostgreSQL/MySQL) em vez de SQLite.
