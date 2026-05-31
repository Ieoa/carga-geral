# Roteiro para Evoluir a Monografia

Este roteiro conecta o sistema implementado com os capitulos da monografia.

## 1. Introducao

Apresente o contexto portuario, a necessidade de rastreabilidade e os problemas causados por controles manuais ou descentralizados.

## 2. Problema de pesquisa

Use uma formulacao objetiva:

Como desenvolver um sistema computacional capaz de organizar o historico de navios e controlar materiais operacionais em um terminal portuario, melhorando a rastreabilidade, a consulta de informacoes e o apoio a tomada de decisao?

## 3. Objetivos

O objetivo geral pode permanecer alinhado ao PDF atual. Nos objetivos especificos, inclua as funcionalidades ja implementadas:

- Cadastro de navios.
- Registro de midias e documentos.
- Pesquisa por filtros.
- Controle de equipamentos.
- Geracao de QR Code.
- Auditoria de alteracoes.
- Geracao de PDF.
- Distribuicao por executavel Windows.

## 4. Referencial teorico

Topicos recomendados:

- Sistemas de informacao.
- Gestao portuaria.
- Terminal Operating Systems.
- Banco de dados relacional.
- Desenvolvimento web com Django.
- Rastreabilidade e auditoria.
- Controle de estoque.

## 5. Metodologia

Descreva uma metodologia aplicada:

1. Levantamento de requisitos.
2. Modelagem de dados.
3. Desenvolvimento incremental.
4. Implementacao dos modulos.
5. Testes funcionais.
6. Empacotamento e validacao local.

## 6. Desenvolvimento do sistema

Inclua:

- Arquitetura MTV do Django.
- Estrutura dos apps `historico` e `estoque`.
- Modelo de dados.
- Telas principais.
- Regras de permissao.
- Auditoria.
- Relatorios e QR Code.

## 7. Resultados

Mostre evidencias:

- Prints das telas.
- Tabela comparando objetivos e funcionalidades entregues.
- Resultado dos testes.
- Funcionamento do executavel.

Exemplo de tabela:

| Objetivo especifico | Funcionalidade implementada | Status |
| --- | --- | --- |
| Cadastrar navios | Tela e model `Navio` | Atendido |
| Controlar materiais | Modulo `estoque` e model `Equipamento` | Atendido |
| Gerar relatorios | PDF com ReportLab | Atendido |
| Facilitar rastreabilidade | `AuditLog` e perfis de acesso | Atendido |

## 8. Conclusao

Explique que o sistema atingiu o objetivo principal ao centralizar informacoes operacionais, melhorar consultas e permitir controle de materiais. Tambem cite limitacoes, como necessidade futura de implantacao em servidor real, dashboards analiticos mais avancados e validacao com usuarios finais.

## 9. Trabalhos futuros

- Exportacao de relatorios em Excel.
- Dashboard com indicadores operacionais.
- API REST para integracao com outros sistemas.
- Controle de manutencao preventiva de equipamentos.
- Historico de validade de certificacoes.
- Hospedagem em servidor cloud com PostgreSQL.

