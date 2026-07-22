# Seguranca

## Comunicacao de vulnerabilidades

Vulnerabilidades, credenciais expostas e incidentes nao devem ser publicados em issues abertas. Comunique o responsavel tecnico pelo canal interno definido pela organizacao.

## Credenciais

- Nunca registre senhas, chaves, tokens ou arquivos `.env` no Git.
- Use senhas temporarias apenas para o primeiro acesso e exija sua alteracao.
- Configure `DJANGO_SECRET_KEY`, banco de dados e SMTP por variaveis de ambiente.
- Revogue imediatamente qualquer credencial que tenha sido exposta.

## Producao

- Execute com `DEBUG=False` e HTTPS.
- Restrinja `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` aos dominios reais.
- Mantenha backups testados do banco e dos arquivos de midia.
- Execute `python manage.py check --deploy` antes da publicacao.
