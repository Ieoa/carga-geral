# Requisitos do Sistema

## Requisitos funcionais

| Codigo | Requisito | Modulo |
| --- | --- | --- |
| RF01 | O sistema deve permitir autenticacao de usuarios. | Geral |
| RF02 | O sistema deve permitir o cadastro de colaboradores. | Historico/Estoque |
| RF03 | O sistema deve permitir o cadastro de navios. | Historico |
| RF04 | O sistema deve permitir registrar dados operacionais do navio, como ETA, POB, inicio e fim de operacao. | Historico |
| RF05 | O sistema deve permitir upload de fotos, videos e documentos vinculados ao navio. | Historico |
| RF06 | O sistema deve permitir consulta e filtragem de midias cadastradas. | Historico |
| RF07 | O sistema deve permitir editar registros de navios e midias conforme perfil de acesso. | Historico |
| RF08 | O sistema deve permitir excluir midias conforme perfil de acesso. | Historico |
| RF09 | O sistema deve gerar relatorio em PDF de midias/documentos. | Historico |
| RF10 | O sistema deve permitir cadastro e listagem de equipamentos. | Estoque |
| RF11 | O sistema deve gerar QR Code para acesso aos detalhes de equipamentos. | Estoque |
| RF12 | O sistema deve permitir cadastro de certificacoes vinculadas a equipamentos. | Estoque |
| RF13 | O sistema deve apresentar visoes resumidas e detalhadas do estoque. | Estoque |
| RF14 | O sistema deve registrar auditoria de acoes relevantes. | Geral |
| RF15 | O sistema deve permitir execucao local por meio de executavel Windows. | Distribuicao |

## Requisitos nao funcionais

| Codigo | Requisito | Descricao |
| --- | --- | --- |
| RNF01 | Usabilidade | A interface deve ser simples, objetiva e adequada ao uso operacional. |
| RNF02 | Rastreabilidade | O sistema deve registrar usuario, perfil e alteracoes realizadas em registros principais. |
| RNF03 | Persistencia | Os dados devem ser armazenados em banco relacional. |
| RNF04 | Portabilidade | O sistema deve poder ser executado localmente em Windows por arquivo `.exe`. |
| RNF05 | Disponibilidade local | O uso local deve funcionar sem depender de CDN para bibliotecas de interface. |
| RNF06 | Seguranca | O acesso deve exigir login e respeitar perfis de permissao. |
| RNF07 | Manutenibilidade | O projeto deve estar organizado em apps Django e documentado em README e pasta `docs`. |

## Perfis de usuario

| Perfil | Permissoes principais |
| --- | --- |
| Administrador | Gerencia usuarios, edita e exclui registros, acessa administracao Django. |
| Gestor | Edita e exclui registros operacionais conforme regras de negocio. |
| Colaborador | Cadastra e consulta informacoes, com restricoes de edicao/exclusao. |

## Regras de negocio

- Cada navio pode possuir multiplas midias e documentos.
- Cada equipamento pode possuir uma ou mais certificacoes.
- Equipamentos recebem QR Code para facilitar acesso ao detalhe do registro.
- Usuarios com perfil operacional limitado nao devem excluir registros de terceiros.
- Acoes de criacao, alteracao e exclusao devem ser registradas em auditoria quando aplicavel.

