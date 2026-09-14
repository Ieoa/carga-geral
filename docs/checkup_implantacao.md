# Checkup de implantação do LOGGERAL

Data da vistoria local: **12/09/2026**.

Este documento separa o que foi validado no ambiente de desenvolvimento do que ainda depende da
infraestrutura da empresa. “Aprovado localmente” não significa homologado no servidor corporativo.

## Resultado local

| Área | Estado | Evidência |
|---|---|---|
| Banco obrigatório | Aprovado localmente | MySQL Community 8.4.11 como único backend de dados. |
| Esquema e migrations | Aprovado localmente | Banco criado do zero, 19 tabelas gerenciadas e `historico_useraccess` presente. |
| Charset e consistência | Aprovado localmente | `utf8mb4`, collation `utf8mb4_0900_ai_ci` e modo SQL estrito. |
| LOGGERAL Insight | Aprovado localmente | Regras, estatística e `IsolationForest` com 105 dados sintéticos; resultado determinístico e sem rede externa. |
| Login e permissões | Aprovado localmente | Bloqueio de tentativas, acesso por proprietário/gestor e mídia privada cobertos por testes. |
| Uploads | Aprovado localmente | Limites, extensões e assinaturas mínimas de PDF, imagem e vídeo validados. |
| Active Directory | Simulado | Fluxo LDAPS, validação de CA, usuário inativo e limpeza de senha temporária testados com mocks. |
| Servidor web | Aprovado localmente | Waitress respondeu a 20 cenários simultâneos de login + Insight + health. |
| Executável Windows | Aprovado localmente | Pacote final iniciou com MySQL, serviu login/arquivos estáticos, autenticou usuário e abriu o Insight; health 200 e página inexistente 404. |
| Falha do banco | Aprovado localmente | `/health/` mudou de HTTP 200 para 503 durante a parada do MySQL e voltou a 200 após reinício. |
| Segurança de dependências | Aprovado localmente | `pip check` sem inconsistências e `pip-audit` sem vulnerabilidades conhecidas na data da vistoria. |
| Configuração Django | Aprovado localmente | `manage.py check`, `check --deploy`, compilação e migrations pendentes sem erros. |
| Suíte automatizada | Aprovado localmente | 65/65 testes aprovados no MySQL, incluindo migrations, AD simulado, uploads, permissões, inicializador do executável, login único, streaming, página 404 e Insight. |

No ensaio concorrente, **20/20** cenários retornaram login 302, Insight 200 e health 200. A latência
total observada teve p95 de **2,221 s** e máxima de **2,222 s** no computador de desenvolvimento;
isso inclui login, análise e verificação do banco e não substitui a medição na rede da empresa.

A suíte automatizada final desta vistoria aprovou **65/65 testes**. Ela deve ser repetida no pacote
exato entregue e o resultado registrado na ordem de serviço da implantação.

## Pendências obrigatórias da empresa

| Item | Estado | Responsável sugerido |
|---|---|---|
| Host, porta, banco, usuário e senha do MySQL real | Pendente | DBA/TI |
| Regra de firewall LOGGERAL → MySQL | Pendente | Redes/TI |
| TLS e CA do MySQL, se exigidos | Pendente | DBA/TI |
| DNS/IP fixo e `PUBLIC_BASE_URL` | Pendente | Redes/TI |
| HTTPS e certificado corporativo | Pendente | Infraestrutura/TI |
| Base DN, conta de serviço, filtro e CA do AD | Pendente | Administrador AD |
| Mapeamento de grupos AD para perfis LOGGERAL | Decisão pendente | Gestor + TI |
| SMTP para avisos de certificados | Pendente | E-mail/TI |
| Pasta `MEDIA_ROOT`, backup e restauração | Pendente | Infraestrutura/Backup |
| Conta local administrativa de contingência | Pendente | Responsável do sistema |
| Teste com usuários reais e critérios de aceite | Pendente | Gestor operacional |

O `.env` atualmente usado no computador de desenvolvimento **não está pronto para a empresa**: o
validador recusou localhost, `DEBUG=True`, ausência de `PUBLIC_BASE_URL`, modo de mídia de rede
desativado e chave padrão. Use `.env.rede.example` somente como modelo e forneça os valores reais por
canal seguro.

## Roteiro de homologação

1. Fazer backup do banco existente e de `MEDIA_ROOT`.
2. Instalar Python/dependências no servidor LOGGERAL, conectado ou pelo `wheelhouse` offline.
3. Preencher `.env` com os dados fornecidos pela TI.
4. Executar `manage.py verificar_rede` antes de qualquer migration.
5. Executar `manage.py migrate`, `verificar_banco`, `verificar_insight` e `check --deploy`.
6. Criar/reprovisionar a conta local de contingência e trocar a senha temporária.
7. Testar cadastro, edição, pesquisa, PDF, uploads, estoque, QR Code, certificados e auditoria.
8. Validar que usuário comum não acessa registros ou arquivos de outro usuário.
9. Interromper e restaurar o MySQL em janela de teste, observando `/health/` e os logs.
10. Ativar AD apenas depois do login local funcionar; validar LDAPS/StartTLS e usuários permitidos,
    negados, inativos e sem atributos opcionais.
11. Testar SMTP, backup/restauração e reinício automático do serviço.
12. Repetir o ensaio com 20 usuários a partir de máquinas da intranet e registrar latência e erros.

## Parecer

O código está **apto para homologação na infraestrutura da empresa**, não para ser declarado em
produção sem as pendências acima. O MySQL portátil confirma compatibilidade do aplicativo e das
migrations; ele não confirma credenciais, certificados, latência, firewall, AD, SMTP nem política de
backup corporativos.

Consulte [DEPLOY.md](../DEPLOY.md) para a instalação e
[loggeral_insight.md](loggeral_insight.md) para funcionamento, limites e apresentação do Insight.
