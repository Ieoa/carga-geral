# Arquitetura do Sistema

## Visao geral

O sistema segue a arquitetura padrao do Django, baseada no padrao MTV:

- Model: representa as entidades e regras de persistencia.
- Template: apresenta as telas HTML ao usuario.
- View: processa requisicoes, aplica regras de negocio e retorna respostas.

## Diagrama de arquitetura

```mermaid
flowchart TD
    Browser["Navegador do usuario"]
    URLs["Rotas Django"]
    Views["Views"]
    Templates["Templates HTML"]
    Models["Models Django"]
    DB["Banco de dados SQL"]
    Media["Arquivos de midia"]
    Static["Arquivos estaticos"]
    Auth["Autenticacao e permissoes"]
    Audit["Auditoria"]
    PDF["Geracao de PDF"]
    QR["Geracao de QR Code"]

    Browser --> URLs
    URLs --> Views
    Views --> Auth
    Views --> Models
    Views --> Templates
    Views --> Audit
    Views --> PDF
    Models --> DB
    Models --> Media
    Models --> QR
    Templates --> Static
    Templates --> Media
    Templates --> Browser
```

## Organizacao dos apps

| Pasta | Responsabilidade |
| --- | --- |
| `config` | Configuracoes gerais do Django, URLs principais, WSGI e ASGI. |
| `historico` | Cadastro de navios, midias, documentos, pesquisa, PDF, auditoria e permissoes. |
| `estoque` | Cadastro de colaboradores, equipamentos, certificacoes, estoque e QR Code. |
| `static` | Bibliotecas e arquivos estaticos utilizados em desenvolvimento. |
| `staticfiles` | Arquivos coletados para publicacao. |
| `media` | Uploads locais de documentos, fotos, videos e QR Codes. |

## Fluxo de uso local por executavel

```mermaid
sequenceDiagram
    participant U as Usuario
    participant EXE as HistoricoNavios.exe
    participant DJ as Django local
    participant DB as SQLite local
    participant NAV as Navegador

    U->>EXE: Executa o arquivo
    EXE->>EXE: Prepara pasta em LOCALAPPDATA
    EXE->>DB: Copia banco inicial se necessario
    EXE->>DJ: Executa migrations
    EXE->>DJ: Inicia servidor local
    EXE->>NAV: Abre URL local
    NAV->>DJ: Acessa sistema
    DJ->>DB: Consulta e salva dados
```

## Decisoes tecnicas

- Django foi escolhido por integrar ORM, autenticacao, templates, admin e estrutura modular.
- SQLite foi mantido para facilitar instalacao local e operacao offline controlada.
- O uso de `DATABASE_URL` permite migrar para PostgreSQL em producao.
- Arquivos estaticos foram mantidos localmente para permitir uso offline.
- PyInstaller foi usado para distribuir o sistema como `.exe`, reduzindo dependencia de instalacao manual de Python no computador do usuario.
