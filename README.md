# Projeto Historico de Navios e Estoque

Sistema desenvolvido em Django para registrar historico de navios, midias, documentos e equipamentos de estoque.

O projeto tem duas areas principais:

- Historico de navios: cadastro de navios, midias, documentos e relatorios em PDF.
- Estoque: cadastro de colaboradores, equipamentos, QR Codes e certificacoes.

## Documentacao tecnica

- [Requisitos do sistema](docs/requisitos.md)
- [Casos de uso](docs/casos_de_uso.md)
- [Modelo de dados](docs/modelo_de_dados.md)
- [Arquitetura](docs/arquitetura.md)
- [Plano de testes](docs/plano_de_testes.md)
- [Manual do usuario](docs/manual_do_usuario.md)

## Tecnologias

- Python 3.12 ou superior
- Django 5.2.5
- SQLite para desenvolvimento local
- ReportLab para geracao de PDFs
- qrcode e Pillow para QR Codes e imagens
- requests e BeautifulSoup para consulta/scraping auxiliar
- WhiteNoise para servir arquivos estaticos em producao

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
ALLOWED_HOSTS=127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=
PUBLIC_BASE_URL=
```

5. Aplique as migrations:

```bash
python manage.py migrate
```

6. Crie um superusuario para acessar o admin:

```bash
python manage.py createsuperuser
```

Novos colaboradores recebem uma senha temporaria aleatoria e devem altera-la no primeiro acesso. Para reprovisionar um acesso existente, execute `python manage.py provisionar_acesso MATRICULA`.

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
|-- docs/            # Documentacao tecnica do sistema
|-- historico/       # App de historico de navios, midias e PDFs
|-- estoque/         # App de estoque, equipamentos e certificacoes
|-- static/          # Arquivos estaticos globais
|-- media/           # Uploads locais, ignorados pelo Git
|-- manage.py
`-- requirements.txt
```

## Observacoes de seguranca

- Nao versione `.env`, `db.sqlite3`, `media/` ou `venv/`.
- Em producao, use `DEBUG=False`, configure `ALLOWED_HOSTS` com o dominio real e use uma `DJANGO_SECRET_KEY` forte.
- Para producao, prefira PostgreSQL ou outro banco gerenciado em vez de SQLite.
- Configure `PUBLIC_BASE_URL` com a URL publica do sistema para que QR Codes apontem para o dominio online correto.
- Configure HTTPS no provedor e ative `SECURE_SSL_REDIRECT=True`, `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True` e `SECURE_HSTS_SECONDS=31536000`.

## Uso offline

- As bibliotecas de interface usadas pelas telas ficam em `static/vendor/`, entao Bootstrap, Bootstrap Icons, jQuery, DataTables, Chart.js e html5-qrcode nao dependem de CDN.
- A consulta auxiliar da Praticagem salva um cache em `media/cache/praticagem_navios.json`. Sem internet, o sistema usa o ultimo cache disponivel.
- Para transportar uma instalacao offline completa, leve junto o banco `db.sqlite3` e a pasta `media/`, pois eles contem os dados e uploads locais.

## Validacao funcional

Para validar os principais fluxos do sistema, recomenda-se verificar:

- Cadastro de navio com dados operacionais.
- Upload e consulta de midias/documentos.
- Geracao de relatorio em PDF.
- Cadastro de equipamentos e QR Code.
- Controle de certificacoes.
- Regras de permissao por perfil.
- Registro de auditoria das acoes.
- Execucao local por `HistoricoNavios.exe`.

Os resultados podem ser associados aos requisitos descritos em [docs/requisitos.md](docs/requisitos.md) e ao plano de testes em [docs/plano_de_testes.md](docs/plano_de_testes.md).

## Deploy online

Variaveis minimas recomendadas:

```env
DJANGO_SECRET_KEY=gere-uma-chave-longa-e-aleatoria
DEBUG=False
DATABASE_URL=postgres://usuario:senha@host:5432/banco
ALLOWED_HOSTS=seudominio.com,www.seudominio.com
CSRF_TRUSTED_ORIGINS=https://seudominio.com,https://www.seudominio.com
PUBLIC_BASE_URL=https://seudominio.com
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
```

Antes de subir:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
```

## Avisos de certificados

Cada certificado pode ser editado ou renovado. A renovacao cria um novo registro e mantem o documento anterior disponivel no historico para rastreabilidade.

Tambem e possivel definir um destinatario e ativar o aviso por e-mail. O sistema envia uma unica notificacao quando o vencimento entra na janela de tres meses e libera um novo envio se a data de vencimento for alterada.

Configure as variaveis `EMAIL_*` do arquivo `.env.production.example` e agende a execucao diaria:

```bash
python manage.py notificar_certificados
```

No Windows, o comando pode ser cadastrado no Agendador de Tarefas. Em Linux, use cron ou um timer do systemd.

## Verificacoes automatizadas

O repositorio possui pipelines para GitHub Actions e GitLab CI. Elas verificam configuracao, migracoes pendentes e testes automatizados a cada envio de codigo.

## Executavel Windows

Para gerar um executavel local do sistema:

```powershell
.\build_windows.ps1
```

O arquivo final fica em:

```text
dist\HistoricoNavios.exe
```

Como usar em outra maquina Windows:

1. Copie `HistoricoNavios.exe` para a maquina.
2. Execute o arquivo.
3. O sistema cria os dados locais em `%LOCALAPPDATA%\HistoricoNavios`.
4. O navegador abre automaticamente em `http://127.0.0.1:8000/` ou na proxima porta livre.

Na primeira execucao, o executavel copia o banco `db.sqlite3` e a pasta `media` embutidos como dados iniciais. Depois disso, cada maquina usa sua propria pasta local em `%LOCALAPPDATA%\HistoricoNavios`.
