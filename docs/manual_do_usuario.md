# Manual do Usuario

## Acesso ao sistema

1. Abra o sistema pelo navegador ou execute `HistoricoNavios.exe`.
2. Informe usuario e senha.
3. Acesse o dashboard principal.

## Modulo Historico de Navios

### Cadastrar navio

1. Acesse a opcao de cadastro de navio.
2. Preencha os dados da embarcacao e da operacao.
3. Informe datas, volumes, pesos e observacoes relevantes.
4. Anexe documentos ou midias quando necessario.
5. Salve o registro.

### Pesquisar midias

1. Acesse a tela de pesquisa de midias.
2. Utilize os filtros disponiveis.
3. Abra o detalhe da midia desejada.
4. Edite, exclua ou gere PDF conforme permissao do usuario.

### Gerar PDF

1. Abra uma midia/documento.
2. Clique na opcao de gerar PDF.
3. O sistema retornara o arquivo com as informacoes do registro.

## Modulo Estoque

### Cadastrar equipamento

1. Acesse o cadastro de equipamentos.
2. Informe nome, identificador, tipo, localizacao, quantidade e descricao.
3. Salve o registro.
4. O sistema gera automaticamente um QR Code para o equipamento.

### Consultar equipamento por QR Code

1. Acesse o leitor de QR Code.
2. Escaneie o codigo do equipamento.
3. O sistema abrira a tela de detalhe correspondente.

### Cadastrar certificacao

1. Acesse o cadastro ou detalhe do equipamento.
2. Informe os dados da certificacao.
3. Anexe arquivo, se necessario.
4. Salve o registro.

## Perfis e permissoes

- Administrador: possui acesso ampliado e pode gerenciar usuarios.
- Gestor: pode editar e excluir registros operacionais conforme regra do sistema.
- Colaborador: pode cadastrar e consultar dados, com restricoes para edicao e exclusao.

## Execucao local no Windows

1. Execute `HistoricoNavios.exe`.
2. Aguarde o servidor local iniciar.
3. O navegador abrira automaticamente.
4. Os dados locais ficam em `%LOCALAPPDATA%\HistoricoNavios`.

