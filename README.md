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
- MySQL 8.0 ou superior
- ReportLab para geracao de PDFs
- qrcode e Pillow para QR Codes e imagens
- requests e BeautifulSoup para consulta/scraping auxiliar
- WhiteNoise para servir arquivos estaticos em producao

## Como rodar localmente

No Windows, depois de configurar o MySQL e o arquivo `.env`, a forma mais simples e executar
`iniciar_local.bat`. O script instala as dependencias, aplica as migrations, verifica o banco,
cria o administrador inicial quando necessario e abre o sistema no navegador.

1. Clone o repositorio:

```bash
git clone URL_DO_REPOSITORIO_GITLAB
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
DATABASE_URL=mysql://historico_navios:sua_senha@127.0.0.1:3306/historico_navios
ALLOWED_HOSTS=127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=
PUBLIC_BASE_URL=
```

5. Crie o banco e o usuario no MySQL:

```sql
CREATE DATABASE historico_navios CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'historico_navios'@'localhost' IDENTIFIED BY 'sua_senha';
GRANT ALL PRIVILEGES ON historico_navios.* TO 'historico_navios'@'localhost';
```

6. Prepare o banco e o primeiro acesso administrativo:

```bash
python manage.py preparar_acesso_inicial
python manage.py verificar_banco
```

O primeiro comando cria `admin_inicial` com uma senha temporaria aleatoria, exibida uma unica vez no
terminal. Na segunda execucao, o usuario e a senha existentes sao preservados. Se for necessario
redefinir a senha:

```bash
python manage.py provisionar_acesso admin_inicial
```

7. Opcionalmente, somente em desenvolvimento, prepare as contas de demonstracao:

```bash
python manage.py criar_usuarios_demo
```

O terminal exibira uma senha temporaria para cada perfil:

- `admin_demo`: acesso administrativo completo.
- `gestor_demo`: acesso de gestor aos registros operacionais.
- `comum_demo`: acesso de colaborador aos proprios registros.

As senhas nao ficam gravadas no repositorio e devem ser alteradas no primeiro acesso. O comando funciona somente com `DEBUG=True`; execute-o novamente para renovar as credenciais da demonstracao.

Novos colaboradores cadastrados pelo administrador tambem recebem uma senha temporaria aleatoria. Para reprovisionar um acesso existente, execute `python manage.py provisionar_acesso MATRICULA`.

8. Inicie o servidor:

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

- Nao versione `.env`, exportacoes do banco, `media/` ou `venv/`.
- Em producao, use `DEBUG=False`, configure `ALLOWED_HOSTS` com o dominio real e use uma `DJANGO_SECRET_KEY` forte.
- Em producao, prefira uma instancia MySQL gerenciada e mantenha backups automatizados.
- Configure `PUBLIC_BASE_URL` com a URL publica do sistema para que QR Codes apontem para o dominio online correto.
- Configure HTTPS no provedor e ative `SECURE_SSL_REDIRECT=True`, `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True` e `SECURE_HSTS_SECONDS=31536000`.

## Homologacao na rede com MySQL remoto

Para o teste corporativo, use tres papeis separados:

- Servidor MySQL: hospeda somente o banco `historico_navios` na porta 3306.
- Servidor LOGGERAL: executa Django/Waitress e atende a porta 8000.
- Computadores dos usuarios: acessam o LOGGERAL apenas pelo navegador.

Nos computadores dos usuarios nao e necessario instalar Python, Git ou MySQL.

### 1. Preparar o acesso no servidor MySQL

A TI deve permitir a porta 3306 somente a partir do IP do servidor LOGGERAL. No MySQL, crie
uma conta limitada ao banco e ao host da aplicacao:

```sql
CREATE DATABASE historico_navios CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'historico_navios'@'IP_DO_SERVIDOR_LOGGERAL' IDENTIFIED BY 'SENHA_FORTE';
GRANT ALL PRIVILEGES ON historico_navios.*
    TO 'historico_navios'@'IP_DO_SERVIDOR_LOGGERAL';
FLUSH PRIVILEGES;
```

No servidor LOGGERAL, valide a rota antes de instalar a aplicacao:

```powershell
Test-NetConnection NOME_OU_IP_DO_MYSQL -Port 3306
```

### 2. Configurar o servidor LOGGERAL

Copie `.env.rede.example` para `.env` e substitua todos os valores de exemplo. Os campos
principais sao:

```env
DEBUG=False
SERVE_MEDIA_LOCALLY=True
DATABASE_URL=mysql://historico_navios:SENHA@mysql-servidor.empresa.local:3306/historico_navios
ALLOWED_HOSTS=127.0.0.1,localhost,loggeral-servidor,192.168.1.50
PUBLIC_BASE_URL=http://192.168.1.50:8000
```

O IP em `PUBLIC_BASE_URL` deve ser fixo ou reservado no DHCP. Nao use `ALLOWED_HOSTS=*`.
Se a senha do MySQL possuir caracteres reservados de URL, aplique a codificacao percentual.

### 3. Iniciar a homologacao

Execute `iniciar_rede.bat`. O script:

1. instala as dependencias e o servidor Waitress;
2. valida a configuracao de rede e exige um MySQL remoto;
3. aplica as migrations e prepara `admin_inicial`;
4. verifica as tabelas obrigatorias;
5. coleta os arquivos estaticos;
6. inicia o LOGGERAL em `0.0.0.0:8000`.

A TI deve liberar a porta TCP 8000 no Firewall do Windows somente para a rede corporativa.
Os usuarios acessam o endereco definido em `PUBLIC_BASE_URL`.

O modo `SERVE_MEDIA_LOCALLY=True` existe para homologacao controlada. Para implantacao definitiva,
use HTTPS e uma infraestrutura aprovada pela TI para servir e proteger os uploads.

## Uso offline

- As bibliotecas de interface usadas pelas telas ficam em `static/vendor/`, entao Bootstrap, Bootstrap Icons, jQuery, DataTables, Chart.js e html5-qrcode nao dependem de CDN.
- A consulta auxiliar da Praticagem salva um cache em `media/cache/praticagem_navios.json`. Sem internet, o sistema usa o ultimo cache disponivel.
- O sistema requer acesso ao servidor MySQL. A pasta `media/` ainda deve ser copiada ou disponibilizada em armazenamento compartilhado.

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
DATABASE_URL=mysql://usuario:senha@host:3306/historico_navios
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

## Solucao para `historico_useraccess` inexistente

A tabela e criada pela migration `historico/0008_useraccess`. Este repositorio tambem possui a
migration de reparo `0010_ensure_useraccess_table`, para bancos onde a migration antiga foi marcada
como aplicada sem a criacao fisica da tabela.

Depois de atualizar o codigo, execute sempre nesta ordem:

```bash
python manage.py showmigrations historico
python manage.py migrate
python manage.py criar_usuarios_demo
```

Para uma vistoria automatica da conexao e das tabelas essenciais:

```bash
python manage.py verificar_banco
```

Nao use `--fake` para essas migrations. Antes de qualquer reparo em banco da empresa, gere backup.

## Active Directory (opcional)

O login do AD pode ser ativado por variaveis de ambiente. Solicite a TI da empresa: URL LDAPS,
Base DN, DN e senha de uma conta de servico de leitura e o filtro de usuario. Exemplo:

```env
AD_AUTH_ENABLED=True
AD_SERVER_URI=ldaps://ad.empresa.local:636
AD_BIND_DN=CN=svc_loggeral,OU=Contas de Servico,DC=empresa,DC=local
AD_BIND_PASSWORD=senha-da-conta-de-servico
AD_USER_SEARCH_BASE=DC=empresa,DC=local
AD_USER_FILTER=(sAMAccountName={username})
```

Usuarios autenticados no AD sao sincronizados com `auth_user`, mas nao recebem permissoes de
administrador automaticamente. A conta local continua disponivel como contingencia enquanto o
backend padrao estiver configurado.

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

O executavel usa a conexao MySQL definida em `DATABASE_URL`. A pasta de midias continua em `%LOCALAPPDATA%\HistoricoNavios`, salvo se `MEDIA_ROOT` for configurado.
