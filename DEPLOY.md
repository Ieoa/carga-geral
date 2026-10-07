# Implantacao do LOGGERAL na intranet

Este guia descreve uma instalacao sem Docker, adequada ao teste em rede da empresa. Uma unica
maquina atua como servidor da aplicacao e executa Django pelo Waitress; os usuarios usam apenas o
navegador. O banco permanece em um servidor MySQL da rede.

Os exemplos nao contem credenciais reais. Guarde o `.env`, certificados, backups e senhas fora do
Git e limite o acesso a eles à equipe autorizada.

## Topologia

```mermaid
flowchart LR
    U["Navegadores dos usuarios"] -->|"HTTPS recomendado"| P["Proxy reverso ou entrada HTTPS"]
    P -->|"HTTP local/rede protegida"| A["Servidor LOGGERAL\nWaitress + Django"]
    A -->|"MySQL/TLS"| D["Servidor MySQL da rede"]
    A --> M["MEDIA_ROOT protegido"]
    A -.->|"LDAPS ou StartTLS"| AD["Active Directory opcional"]
    A -.->|"SMTP/TLS"| E["Servidor de e-mail opcional"]
```

- Somente o servidor LOGGERAL se conecta ao MySQL. Estacoes de usuario nao precisam de Python,
  Git, MySQL ou Docker.
- A porta 3306 deve aceitar conexoes apenas do IP do servidor LOGGERAL.
- O Waitress escuta na porta 8000. Durante uma homologacao isolada ele pode ser acessado
  diretamente; na implantacao, prefira HTTPS por um proxy aprovado pela TI.
- `MEDIA_ROOT` deve estar no servidor LOGGERAL ou em armazenamento privado acessivel por ele.
  Replique essa pasta no backup junto com o banco.

## O que precisa ser fornecido pela TI

- nome DNS ou IP fixo do servidor LOGGERAL;
- hostname, porta, banco, usuario e senha do MySQL;
- certificado da CA do MySQL, quando o servidor exigir TLS;
- regra de firewall entre servidor LOGGERAL e MySQL;
- certificado HTTPS e forma aprovada de terminacao TLS;
- para AD: URI LDAPS ou StartTLS, Base DN, conta de servico somente-leitura, filtro de usuario e
  CA corporativa;
- para notificacoes: host, porta, TLS, remetente e credenciais SMTP;
- diretorio de backup e politica de retencao.

Esses itens devem ser homologados na infraestrutura real. O teste com um MySQL local portatil nao
comprova conectividade, certificado, permissao, latencia, AD ou SMTP da empresa.

## Preparar o MySQL de rede

Execute as instrucoes com uma conta administrativa do MySQL, substituindo os valores de exemplo:

```sql
CREATE DATABASE historico_navios
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

CREATE USER 'historico_navios'@'IP_DO_SERVIDOR_LOGGERAL'
    IDENTIFIED BY 'SENHA_FORTE_E_EXCLUSIVA';

GRANT ALL PRIVILEGES ON historico_navios.*
    TO 'historico_navios'@'IP_DO_SERVIDOR_LOGGERAL';
FLUSH PRIVILEGES;
```

O usuario precisa criar e alterar tabelas durante as migrations. Depois da implantacao, a TI pode
separar uma credencial de deploy da credencial de execucao, desde que teste todas as permissoes
necessarias. Se a politica exigir TLS, configure o MySQL para exigi-lo e forneca a CA ao LOGGERAL.

No servidor da aplicacao, valide primeiro a rota:

```powershell
Test-NetConnection mysql-servidor.empresa.local -Port 3306
```

Esse comando testa apenas TCP. A autenticacao, o esquema, as migrations e o TLS sao verificados
posteriormente por `manage.py verificar_banco`.

## Instalacao conectada

No servidor Windows com Python 3.12 ou superior:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

O script `iniciar_rede.bat` tambem cria ou repara o ambiente virtual e instala as dependencias.

## Instalacao sem internet

Em um computador Windows com internet, usando a mesma arquitetura e uma versao compativel do
Python do servidor de destino, execute:

```powershell
.\preparar_pacote_offline.ps1
```

O comando baixa os pacotes binarios para `wheelhouse`. Copie para a empresa:

- todo o projeto;
- a pasta `wheelhouse` completa;
- um `.env` preparado por canal seguro, ou crie-o diretamente no destino;
- certificados corporativos necessarios.

Quando `wheelhouse` existe, `iniciar_rede.bat` usa `--no-index` e nao consulta a internet. Nao
versione essa pasta; ela e um artefato de entrega e deve ser refeita quando `requirements.txt` mudar.

## Configurar o `.env`

Copie `.env.rede.example` para `.env` e substitua todos os marcadores. Exemplo resumido:

```env
DJANGO_SECRET_KEY=GERE_UMA_CHAVE_LONGA_ALEATORIA_E_EXCLUSIVA
DEBUG=False
DESKTOP_MODE=False
SERVE_MEDIA_LOCALLY=True

DATABASE_URL=mysql://historico_navios:SENHA_CODIFICADA@mysql-servidor.empresa.local:3306/historico_navios
MYSQL_CONNECT_TIMEOUT=10
MYSQL_READ_TIMEOUT=30
MYSQL_WRITE_TIMEOUT=30
MYSQL_SSL_CA=C:\certificados\ca-mysql.pem

ALLOWED_HOSTS=loggeral-servidor,loggeral.empresa.local,192.168.1.50
PUBLIC_BASE_URL=https://loggeral.empresa.local
CSRF_TRUSTED_ORIGINS=https://loggeral.empresa.local

SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=False

INSIGHT_ML_ENABLED=True
INSIGHT_STATISTICAL_MIN_SAMPLES=30
INSIGHT_ML_MIN_SAMPLES=100
INSIGHT_CONTAMINATION=0.10
LOGIN_FAILURE_LIMIT=5
LOGIN_FAILURE_WINDOW_SECONDS=900
```

Observacoes:

- codifique caracteres reservados do usuario ou senha em `DATABASE_URL` no formato percentual;
- nao use `ALLOWED_HOSTS=*`;
- `PUBLIC_BASE_URL` deve ser o endereco que os usuarios e QR Codes realmente utilizarao;
- no teste HTTP direto em `:8000`, mantenha os quatro ajustes de HTTPS desativados como no
  `.env.rede.example`; ative-os somente quando o acesso HTTPS estiver funcionando;
- `MYSQL_SSL_CA` vazio significa que o cliente nao solicitara uma CA. Confirme a politica com a TI;
- `SERVE_MEDIA_LOCALLY=True` autoriza o modo de homologacao, mas `/media/` continua protegido pela
  autenticacao e pelas permissoes do Django.

## Ativar Active Directory

Primeiro valide a conta administrativa local e o backup da configuracao. Depois acrescente ao `.env`:

```env
AD_AUTH_ENABLED=True
AD_SERVER_URI=ldap://glibra.corp:389
AD_DIRECT_BIND=True
AD_DOMAIN=glibra
AD_START_TLS=True
AD_TLS_VALIDATE=True
AD_CA_CERT_FILE=C:\certificados\ca-corporativa.pem
AD_CONNECT_TIMEOUT=5
AD_RECEIVE_TIMEOUT=10
```

Cadastre primeiro cada matricula na lista local de usuarios autorizados. Contas ausentes nessa lista
nao provocam nenhuma conexao ao AD. O bind direto usa `glibra\\matricula`, nao cria usuarios a partir
do diretorio e nao coleta e-mail, CPF, departamento, cargo ou grupos.

Antes de reiniciar com o AD ativo, promova de forma controlada ao menos uma matricula corporativa que
administrara a lista (o comando tambem garante sua inclusao em `UserAccess`):

```powershell
python manage.py preparar_acesso_inicial --username MATRICULA_AD --skip-migrate --promote-existing
```

Na porta 389, `AD_START_TLS=True` e obrigatorio. A alternativa e `ldaps://glibra.corp:636` com
`AD_START_TLS=False`. LDAP sem protecao e recusado. Mantenha `AD_TLS_VALIDATE=True` e instale a CA
correta; desativar a validacao de certificado nao e uma solucao de producao.

Com o AD ativo, nao existe fallback silencioso para senha local. A contingencia exige desativar o AD
no `.env` e reiniciar o servico de forma controlada. O diretorio nao cria contas nem sincroniza
atributos: o perfil minimo e mantido na base local. Homologue, no minimo:

1. usuario AD valido;
2. senha incorreta e usuario inexistente;
3. usuario desativado;
4. usuario presente no AD, mas ausente da lista local, confirmando que nenhuma conexao LDAP e aberta;
5. indisponibilidade do controlador de dominio;
6. validade e nome do certificado;
7. perfis locais de usuario comum, gestor e administrador.

## Configurar SMTP

Para que avisos de certificados sejam realmente entregues:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DEFAULT_FROM_EMAIL=Carga Geral <nao-responda@empresa.com.br>
EMAIL_HOST=smtp.empresa.local
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=USUARIO_SMTP
EMAIL_HOST_PASSWORD=SENHA_SMTP
```

O backend de console e util apenas no desenvolvimento e nao entrega mensagens. Teste recebimento,
remetente, antispam e indisponibilidade do SMTP antes de agendar:

```powershell
.\venv\Scripts\python.exe manage.py notificar_certificados
```

## Primeira inicializacao

Com o `.env` configurado, execute:

```powershell
.\iniciar_rede.bat
```

O script:

1. cria ou repara `venv`;
2. instala dependencias pela internet ou por `wheelhouse`;
3. valida o modo de rede e exige um host MySQL nao local;
4. aplica migrations e prepara o acesso administrativo inicial;
5. verifica todas as tabelas gerenciadas, migrations, charset e estado do TLS do MySQL;
6. valida o motor local do LOGGERAL Insight;
7. coleta arquivos estaticos;
8. inicia o Waitress em `0.0.0.0:8000`.

Na primeira execucao, anote a senha temporaria de `admin_inicial` em canal seguro. Ela aparece uma
unica vez e deve ser trocada no primeiro acesso. Se o nome ja pertencer a uma conta sem privilegio,
o comando interrompe em vez de promove-la silenciosamente; escolha outro `--username` ou avalie
conscientemente `--promote-existing`.

Para executar cada validacao de forma controlada:

```powershell
.\venv\Scripts\python.exe manage.py verificar_rede
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py regenerar_qrcodes
.\venv\Scripts\python.exe manage.py verificar_banco
.\venv\Scripts\python.exe manage.py verificar_insight
.\venv\Scripts\python.exe manage.py collectstatic --noinput
.\venv\Scripts\python.exe manage.py check --deploy
```

O comando `regenerar_qrcodes` atualiza os códigos existentes para o destino que abre o PDF ativo
mais recente do material. Depois de executá-lo, substitua as etiquetas impressas antigas pelas novas.
O endereço gravado vem de `PUBLIC_BASE_URL` e precisa ser acessível pelo dispositivo leitor.

O endpoint `GET /health/` retorna HTTP 200 quando a aplicacao alcanca o banco e HTTP 503 quando o
banco esta indisponivel. Ele nao substitui testes funcionais e nao expoe credenciais.

## HTTPS e proxy reverso

Na homologacao isolada, a TI pode liberar a porta TCP 8000 apenas para a sub-rede autorizada e usar
`http://SERVIDOR:8000`. Credenciais, AD e a camera do leitor de QR Code justificam HTTPS mesmo na
intranet.

O proxy pode servir `/static/` diretamente, mas deve encaminhar `/media/` ao Django. Exemplo Nginx
em um host aprovado pela empresa:

```nginx
server {
    listen 443 ssl;
    server_name loggeral.empresa.local;

    ssl_certificate     /etc/ssl/loggeral/fullchain.pem;
    ssl_certificate_key /etc/ssl/loggeral/private.key;
    client_max_body_size 110M;

    location /static/ {
        alias /var/www/loggeral/staticfiles/;
    }

    # Nao crie "location /media/ { alias ...; }". A rota precisa chegar ao Django.
    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://IP_DO_SERVIDOR_LOGGERAL:8000;
    }
}
```

Se futuramente arquivos grandes forem entregues com `X-Accel-Redirect` ou recurso equivalente, a
autenticacao e a autorizacao devem continuar sendo decididas pelo Django antes da entrega. Nunca
exponha `MEDIA_ROOT` como alias publico ou compartilhamento anonimo.

## Recuperar acessos afetados pela migration 0009

A migration `historico/0009_invalidate_predictable_passwords` tornou inutilizaveis as senhas locais
de contas ligadas a perfis de colaborador e da antiga conta `admin`. Isso foi intencional porque uma
versao anterior possuia credenciais previsiveis/publicadas. A senha anterior nao pode ser recuperada;
ela precisa ser redefinida.

Antes de migrar um banco existente, gere backup. Depois de `migrate`, liste as contas sem senha local
utilizavel:

```powershell
.\venv\Scripts\python.exe manage.py shell -c "from django.contrib.auth import get_user_model; U=get_user_model(); print('\n'.join(u.username for u in U.objects.all() if not u.has_usable_password()))"
```

Para cada conta que deve continuar com login local, gere uma senha temporaria:

```powershell
.\venv\Scripts\python.exe manage.py provisionar_acesso NOME_DO_USUARIO
```

Entregue a senha por canal seguro; ela deve ser trocada no primeiro acesso. Para uma nova conta
administrativa de contingencia:

```powershell
.\venv\Scripts\python.exe manage.py preparar_acesso_inicial --username admin_contingencia --skip-migrate
```

Uma conta destinada somente ao AD pode permanecer sem senha local: o primeiro login AD valido
sincroniza o usuario e libera o fluxo normal. Nao rode apenas `preparar_acesso_inicial` esperando que
ele redefina uma conta administrativa existente, pois por seguranca esse comando preserva a senha;
use `provisionar_acesso` explicitamente.

## Uploads, backup e restauracao

- `MEDIA_ROOT` contem fotos, videos, documentos, certificados e QR Codes; ele nao fica dentro do
  MySQL.
- `/media/` e uma rota autenticada do Django. Nao use alias publico no Nginx nem compartilhamento
  anonimo no Windows.
- Faca backup consistente do MySQL e de `MEDIA_ROOT` no mesmo ponto logico da operacao.
- Teste periodicamente a restauracao em ambiente isolado.
- Restrinja permissoes de sistema de arquivos à conta que executa o LOGGERAL e aos operadores de
  backup.

Exemplo de backup logico do banco, ajustado à politica da TI:

```powershell
mysqldump --single-transaction --routines --triggers -h mysql-servidor.empresa.local -u historico_navios -p historico_navios > historico_navios.sql
```

## Criterios de aceite na empresa

A implantacao so deve ser considerada homologada depois de registrar evidencias de:

- conexao do servidor LOGGERAL ao MySQL real, com TLS quando exigido;
- migrations completas e `verificar_banco` aprovado;
- login local de contingencia e, se ativado, login AD por LDAPS/StartTLS;
- HTTPS, cookies seguros, CSRF, DNS e firewall;
- cadastro, edicao, pesquisa, permissao por proprietario/gestor, PDF e auditoria;
- upload e reproducao/download de arquivos sem acesso anonimo;
- LOGGERAL Insight nos tres estados de amostra aplicaveis;
- QR Code usando o endereco oficial;
- entrega SMTP e agendamento de notificacoes;
- reinicio automatico do servico, concorrencia esperada e recuperacao de falha do banco;
- backup e restauracao do MySQL e de `MEDIA_ROOT`.

Use [docs/checkup_implantacao.md](docs/checkup_implantacao.md) como registro dessa homologacao e
[docs/loggeral_insight.md](docs/loggeral_insight.md) para interpretar os alertas do Insight.
