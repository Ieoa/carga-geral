# Deploy do Historico de Navios

Este projeto e uma aplicacao Django. Para acessar por dominio na empresa, publique como aplicacao web em um servidor com Python, banco PostgreSQL, HTTPS e um dominio apontando para o servidor.

## Opcao recomendada

Use uma VPS Linux com:

- Python 3.12+
- PostgreSQL
- Gunicorn
- Nginx
- Certbot/Let's Encrypt

Exemplo de dominio:

```text
historiconavios.suaempresa.com.br
```

## Variaveis de ambiente

Crie um `.env` de producao baseado em `.env.production.example`:

```env
DJANGO_SECRET_KEY=gere-uma-chave-longa-e-unica
DEBUG=False
DATABASE_URL=postgres://usuario:senha@localhost:5432/historico_navios
ALLOWED_HOSTS=historiconavios.suaempresa.com.br
CSRF_TRUSTED_ORIGINS=https://historiconavios.suaempresa.com.br
PUBLIC_BASE_URL=https://historiconavios.suaempresa.com.br
MEDIA_ROOT=/var/www/historico_navios/media
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
```

## Comandos no servidor

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
```

Teste o Gunicorn:

```bash
gunicorn config.wsgi:application --bind 127.0.0.1:8000
```

## Servico systemd

Crie `/etc/systemd/system/historico-navios.service`:

```ini
[Unit]
Description=Historico de Navios
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/historico_navios/app
EnvironmentFile=/var/www/historico_navios/app/.env
ExecStart=/var/www/historico_navios/app/venv/bin/gunicorn config.wsgi:application --workers 3 --bind unix:/run/historico-navios.sock
Restart=always

[Install]
WantedBy=multi-user.target
```

Ative:

```bash
sudo systemctl daemon-reload
sudo systemctl enable historico-navios
sudo systemctl start historico-navios
```

## Nginx

Crie `/etc/nginx/sites-available/historico-navios`:

```nginx
server {
    server_name historiconavios.suaempresa.com.br;

    client_max_body_size 50M;

    location /static/ {
        alias /var/www/historico_navios/app/staticfiles/;
    }

    location /media/ {
        alias /var/www/historico_navios/media/;
    }

    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://unix:/run/historico-navios.sock;
    }
}
```

Ative:

```bash
sudo ln -s /etc/nginx/sites-available/historico-navios /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d historiconavios.suaempresa.com.br
```

## Cadastro de usuarios

O sistema ja tem cadastro de usuarios por colaborador:

- Historico: `/colaboradores/cadastrar/`
- Estoque: `/estoque/dashboard/cadastrar-colaborador/`

Nos dois fluxos, a matricula vira o login. A senha inicial e gerada pelos 6 primeiros digitos do CPF.

## Primeiro acesso local confirmado

No banco SQLite local deste projeto, o usuario `admin` foi mantido como superusuario e a senha foi alterada para:

```text
Admin2110
```

A senha antiga `admin` nao autentica mais.
