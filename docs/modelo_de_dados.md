# Modelo de Dados

## Principais entidades

| Entidade | Finalidade |
| --- | --- |
| User | Conta local previamente autorizada; a senha corporativa permanece no Active Directory. |
| UserAccess | Controle local que define quais contas podem consultar o Active Directory. |
| Colaborador | Perfil operacional minimo, com matricula, nome, area e cargo. |
| Navio | Registro principal de navios e dados operacionais. |
| FotoVideoNavio | Midias vinculadas a um navio. |
| DocumentoNavio | Documentos vinculados a um navio. |
| AuditLog | Registro de auditoria de acoes realizadas no sistema. |
| Equipamento | Cadastro de equipamentos e materiais operacionais. |
| Certificacao | Certificacoes vinculadas a equipamentos. |

## Diagrama entidade-relacionamento simplificado

```mermaid
erDiagram
    USER ||--o| HISTORICO_COLABORADOR : possui
    USER ||--o| ESTOQUE_COLABORADOR : possui
    USER ||--o{ NAVIO : cadastra
    USER ||--o{ FOTOVIDEONAVIO : envia
    USER ||--o{ DOCUMENTONAVIO : envia
    USER ||--o{ EQUIPAMENTO : cadastra
    USER ||--o{ CERTIFICACAO : cadastra
    USER ||--o{ AUDITLOG : realiza

    NAVIO ||--o{ FOTOVIDEONAVIO : possui
    NAVIO ||--o{ DOCUMENTONAVIO : possui
    EQUIPAMENTO ||--o{ CERTIFICACAO : possui

    USER {
        int id
        string username
        string first_name
        string last_name
    }

    NAVIO {
        int id
        string navio
        string armador
        string agencia
        datetime eta
        datetime pob
        datetime inicio_operacao
        datetime fim_operacao
        string volume_descarga
        string peso_descarga
        string volume_embarque
        string peso_embarque
    }

    FOTOVIDEONAVIO {
        int id
        file arquivo
        string tipo_peca
        text observacao
        datetime data_criacao
    }

    EQUIPAMENTO {
        int registro
        string equipamento
        string identificador
        string tipo_equipamento
        int quantidade
        string localizacao
        file foto
        file qrcode
    }

    CERTIFICACAO {
        int id
        string nome_certificado
        date data_certificacao
        date data_vencimento
        string empresa_certificadora
        string codigo_certificado
    }

    AUDITLOG {
        int id
        string actor_role
        string action
        string app_label
        string model_name
        string object_pk
        json changes
        datetime created_at
    }
```

## Observacoes sobre persistencia

- O sistema utiliza o ORM do Django para manipular as tabelas.
- O banco padrao do projeto e MySQL 8.0 ou superior.
- A conexao e configurada por `DATABASE_URL`, no formato `mysql://usuario:senha@host:3306/banco`.
- Arquivos enviados pelo usuario sao armazenados na pasta de midia configurada por `MEDIA_ROOT`.
