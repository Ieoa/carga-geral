# Plano de Testes

## Objetivo

Validar se as principais funcionalidades do sistema atendem aos requisitos definidos para o TCC, garantindo cadastro, consulta, rastreabilidade e funcionamento local.

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

## Testes automatizados recomendados

- Testar geracao de QR Code com `PUBLIC_BASE_URL`.
- Testar fallback de scraping/cache da consulta auxiliar.
- Testar permissao de edicao por dono do registro.
- Testar restricao de exclusao para usuario sem perfil de gestor.
- Testar criacao de auditoria em cadastro, alteracao e exclusao.

## Comandos de validacao

```powershell
.\venv\Scripts\python.exe .\manage.py check
.\venv\Scripts\python.exe .\manage.py test
.\build_windows.ps1
```

## Evidencias para a monografia

Durante a apresentacao do TCC, recomenda-se registrar:

- Prints do dashboard de historico.
- Prints do cadastro de navio.
- Prints da pesquisa de midias.
- Prints do cadastro de equipamento.
- Print do QR Code gerado.
- Exemplo de relatorio PDF.
- Resultado do comando `manage.py check`.
- Evidencia do executavel Windows em funcionamento.

