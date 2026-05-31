# Visao Geral do Projeto para TCC

## Titulo sugerido

Sistema de Gestao de Historico de Navios e Controle de Materiais em Terminais Portuarios utilizando Python, Django e Banco de Dados Relacional.

## Contexto

O setor portuario depende do registro organizado de informacoes sobre navios, operacoes, documentos, midias, equipamentos e materiais de apoio. Quando esse controle e realizado manualmente ou por ferramentas pouco integradas, podem ocorrer perda de historico, retrabalho, dificuldade de consulta e baixa rastreabilidade das acoes realizadas.

Este projeto propoe um sistema web desenvolvido em Python com Django para centralizar o cadastro de navios, o armazenamento de documentos e midias operacionais, o controle de equipamentos de estoque e o acompanhamento de certificacoes. O sistema tambem possui autenticacao, perfis de acesso, auditoria de alteracoes, geracao de relatorios em PDF, leitura de QR Code e possibilidade de uso local por executavel Windows.

## Problema de pesquisa

Como desenvolver um sistema computacional capaz de organizar o historico de navios e controlar materiais operacionais em um terminal portuario, melhorando a rastreabilidade, a consulta de informacoes e o apoio a tomada de decisao?

## Objetivo geral

Desenvolver um sistema de informacao para gerenciamento do historico de navios de carga geral e controle de materiais em um terminal portuario.

## Objetivos especificos

- Implementar o cadastro de navios e dados operacionais.
- Permitir o armazenamento de fotos, videos e documentos vinculados aos navios.
- Criar recursos de busca e filtragem para consulta do historico operacional.
- Implementar modulo de controle de colaboradores, equipamentos e certificacoes.
- Gerar QR Codes para acesso rapido aos detalhes de equipamentos.
- Registrar auditoria de criacao, alteracao e exclusao de registros.
- Gerar relatorios em PDF para apoio a analise operacional.
- Permitir execucao local do sistema em ambiente Windows por meio de arquivo executavel.

## Justificativa

A organizacao do historico operacional e dos materiais utilizados em terminais portuarios contribui para maior controle, reducao de retrabalho e melhor disponibilidade de informacoes. O sistema desenvolvido aplica conceitos de programacao, banco de dados, engenharia de software, seguranca de acesso e interface web em um contexto pratico relacionado a operacoes portuarias.

## Escopo do sistema

O sistema possui dois modulos principais:

- Historico de navios: cadastro de navios, upload de midias e documentos, consulta por filtros, visualizacao de detalhes e geracao de PDF.
- Estoque: cadastro de colaboradores, equipamentos, certificacoes, controle resumido/detalhado e QR Code para consulta rapida.

## Tecnologias utilizadas

- Python: linguagem principal de desenvolvimento.
- Django: framework web utilizado no backend, rotas, views, templates, autenticacao e ORM.
- SQLite: banco local para desenvolvimento e uso desktop.
- PostgreSQL: opcao recomendada para ambiente de producao.
- HTML, CSS e Bootstrap: construcao da interface.
- ReportLab: geracao de relatorios em PDF.
- qrcode e Pillow: geracao de QR Codes de equipamentos.
- WhiteNoise: publicacao de arquivos estaticos.
- PyInstaller: empacotamento do sistema como executavel Windows.

