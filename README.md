# Projeto Historico de Navios e Estoque

Sistema desenvolvido em Django para registrar historico de navios, midias, documentos e equipamentos de estoque.

O projeto tem duas areas principais:

- Historico de navios: cadastro de navios, midias, documentos e relatorios em PDF.
- Estoque: cadastro de colaboradores, equipamentos, QR Codes e certificacoes.

## Tecnologias

- Python 3.12 ou superior
- Django 5.2.5
- SQLite para desenvolvimento local
- ReportLab para geracao de PDFs
- qrcode e Pillow para QR Codes e imagens
- requests e BeautifulSoup para consulta/scraping auxiliar

## Como rodar localmente

1. Clone o repositorio:

```bash
git clone https://github.com/Ieoa/carga-geral.git
cd carga-geral
```

2. Crie e ative o ambiente virtual:

```bash
python -m venv venv
venv\Scripts\activate
```

No Linux ou macOS:

```bash
python -m venv venv
source venv/bin/activate
```

3. Instale as dependencias:

```bash
pip install -r requirements.txt
```

4. Crie um arquivo `.env` na raiz do projeto, no mesmo nivel do `manage.py`:

```env
DJANGO_SECRET_KEY=uma_chave_secreta_grande_e_unica
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
```

5. Aplique as migrations:

```bash
python manage.py migrate
```

6. Crie um superusuario para acessar o admin:

```bash
python manage.py createsuperuser
```

7. Inicie o servidor:

```bash
python manage.py runserver
```

## URLs principais

- Historico: http://127.0.0.1:8000/
- Estoque: http://127.0.0.1:8000/estoque/
- Admin Django: http://127.0.0.1:8000/admin/

## Estrutura

```text
carga-geral/
|-- config/          # Configuracoes principais do Django
|-- historico/       # App de historico de navios, midias e PDFs
|-- estoque/         # App de estoque, equipamentos e certificacoes
|-- navios/          # App reservado/legado
|-- static/          # Arquivos estaticos globais
|-- staticfiles/     # Arquivos gerados pelo collectstatic
|-- media/           # Uploads locais, ignorados pelo Git
|-- manage.py
|-- requirements.txt
`-- requeriments.txt # Mantido por compatibilidade com o nome antigo
```

## Observacoes de seguranca

- Nao versione `.env`, `db.sqlite3`, `media/` ou `venv/`.
- Em producao, use `DEBUG=False` e configure `ALLOWED_HOSTS`.
- Para producao, prefira PostgreSQL ou outro banco gerenciado em vez de SQLite.
