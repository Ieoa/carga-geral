# Plano de Testes

## Objetivo

Validar se as principais funcionalidades do sistema atendem aos requisitos operacionais, garantindo cadastro, consulta, rastreabilidade e funcionamento local.

## Testes funcionais manuais

| Codigo | Cenario | Resultado esperado |
| --- | --- | --- |
| T01 | Realizar login com usuario valido. | Usuario acessa o dashboard. |
| T02 | Realizar login com usuario invalido. | Sistema exibe mensagem de erro. |
| T03 | Cadastrar colaborador. | Colaborador e usuario associado sao criados. |
| T04 | Cadastrar navio com dados operacionais. | Navio aparece nas consultas. |
| T05 | Anexar foto, video ou documento a um navio. | Arquivo fica vinculado ao registro. |
| T06 | Pesquisar midias por filtros. | Sistema retorna resultados compativeis. |
| T07 | Gerar PDF de uma midia/documento. | Arquivo PDF e retornado ao usuario. |
| T08 | Editar registro de navio. | Alteracoes sao persistidas e auditadas. |
| T09 | Excluir midia com usuario autorizado. | Midia e removida e acao e registrada. |
| T10 | Cadastrar equipamento. | Equipamento aparece na listagem. |
| T11 | Gerar QR Code do equipamento. | QR Code aponta para a tela de detalhe. |
| T12 | Cadastrar certificacao de equipamento. | Certificacao aparece vinculada ao equipamento. |
| T13 | Consultar estoque resumido e detalhado. | Quantidades e agrupamentos sao exibidos corretamente. |
| T14 | Executar `HistoricoNavios.exe`. | Sistema inicia servidor local e abre no navegador. |
| T15 | Tentar login AD com matricula ausente da lista local. | Credencial e recusada sem abrir conexao com o AD. |
| T16 | Autorizar matricula e entrar com credencial corporativa. | Bind `glibra\\matricula` ocorre por StartTLS e o acesso e liberado. |
| T17 | Abrir o cadastro de usuario. | Formulario nao solicita nem armazena CPF ou e-mail. |
| T18 | Abrir a lista de usuarios como administrador. | Contas autorizadas, perfil, tipo de autenticacao e status sao exibidos. |
| T19 | Abrir a lista como colaborador comum ou gestor. | Acesso negado e nenhuma matricula cadastrada e exibida. |
| T20 | Inspecionar o menu como colaborador comum ou gestor. | Links de autorizacao e lista de usuarios permanecem ocultos. |

## Testes automatizados recomendados

- Testar geracao de QR Code com `PUBLIC_BASE_URL`.
- Testar permissao de edicao por dono do registro.
- Testar restricao de exclusao para usuario sem perfil de gestor.
- Testar criacao de auditoria em cadastro, alteracao e exclusao.
- Testar que o backend local rejeita qualquer conta ausente de `UserAccess`.
- Testar que LDAP sem StartTLS/LDAPS e recusado antes da conexao.

## Comandos de validacao

```powershell
.\venv\Scripts\python.exe .\manage.py check
.\venv\Scripts\python.exe .\manage.py test
.\build_windows.ps1
```

## Evidencias de validacao

Durante a homologacao, recomenda-se registrar:

- Prints do dashboard de historico.
- Prints do cadastro de navio.
- Prints da pesquisa de midias.
- Prints do cadastro de equipamento.
- Print do QR Code gerado.
- Exemplo de relatorio PDF.
- Resultado do comando `manage.py check`.
- Evidencia do executavel Windows em funcionamento.
