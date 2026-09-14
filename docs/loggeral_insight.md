# LOGGERAL Insight

O LOGGERAL Insight é um módulo de apoio à conferência de operações portuárias. Ele combina regras
determinísticas, estatística robusta e, quando há dados suficientes, o algoritmo `IsolationForest`
do scikit-learn. Todo o processamento ocorre no servidor LOGGERAL: não existe chave de API, custo
por consulta nem envio dos registros para serviços externos.

O resultado chama-se **índice de atenção do registro**. Ele não prevê acidentes, fraude, desempenho
futuro ou causa operacional e não substitui a decisão do responsável.

## Funcionamento por quantidade de dados

Somente registros com duração positiva, pelo menos quatro indicadores aproveitáveis e sem erro de
alta severidade entram na base estatística.

| Amostra válida | Modo | Resultado |
|---:|---|---|
| 0 a 29 | Regras explicáveis | Confere cronologia, valores, dimensões, duração, duplicidade e campos ausentes. |
| 30 a 99 | Regras + estatística robusta | Compara cada indicador com mediana e desvio absoluto mediano do histórico visível. |
| 100 ou mais | Regras + modelo local | Usa `IsolationForest`, com semente fixa, para destacar combinações incomuns. |

Os limites são configuráveis por `INSIGHT_STATISTICAL_MIN_SAMPLES` e
`INSIGHT_ML_MIN_SAMPLES`. `INSIGHT_CONTAMINATION` controla a fração esperada de padrões atípicos e
deve ser calibrada com o responsável operacional. A configuração não altera os dados originais.

## Indicadores analisados

- diferença entre ETA e POB;
- espera entre POB e início;
- duração calculada entre início e término;
- quantidade de ternos;
- LOA e boca;
- peso total movimentado;
- produtividade por hora;
- produtividade por terno/hora.

O parser aceita números comuns no padrão brasileiro, como `1.234,50`. Volume é exibido para
conferência, mas não participa do modelo até a empresa padronizar sua unidade e significado.

## Regras explicáveis

Entre as conferências estão:

- início anterior ao POB ou término anterior ao início;
- diferença excessiva entre ETA e POB;
- duração informada incompatível com a duração calculada;
- peso ou volume não numérico ou negativo;
- quantidade de ternos menor ou igual a zero;
- LOA menor ou igual à boca;
- possível registro duplicado do mesmo navio em uma janela de seis horas;
- operação aberta ou com dados temporais incompletos.

Antecipação em relação à ETA não é tratada automaticamente como erro. Um alerta aparece apenas
quando a diferença absoluta ultrapassa 24 horas e sua mensagem mostra a evidência encontrada.

## Pontuação e explicação

Alertas de alta, média e baixa severidade contribuem para uma pontuação de 0 a 100. Quando o modelo
local identifica um padrão atípico, a tela mostra até três indicadores que mais se afastaram do
histórico, por exemplo duração, peso total e produtividade. As faixas apresentadas são:

- 0 a 34: atenção baixa;
- 35 a 69: atenção média;
- 70 a 100: atenção alta.

Um registro pode ser incomum e ainda estar correto. Por isso, a ação recomendada é conferir os
campos e o contexto, nunca alterar um dado apenas para reduzir a pontuação.

## Privacidade, permissões e API interna

A tela fica em `/insight/` e exige login. O usuário comum analisa somente navios que pode consultar;
gestores e administradores usam a visão ampla prevista pelas regras do sistema. A rota JSON
`/insight/api/navios/<id>/` é interna, também exige login e aplica o mesmo escopo. Ela existe para
demonstração, auditoria técnica e futuras integrações locais, não para exposição na internet.

O motor não importa `requests`, não chama OpenAI, Gemini ou outro provedor e funciona sem acesso à
internet depois que as dependências foram instaladas. Se o scikit-learn não puder ser carregado, as
regras continuam funcionando e a tela informa a degradação em vez de impedir o uso do LOGGERAL.

## Configuração

```env
INSIGHT_ML_ENABLED=True
INSIGHT_STATISTICAL_MIN_SAMPLES=30
INSIGHT_ML_MIN_SAMPLES=100
INSIGHT_CONTAMINATION=0.10
```

Valide o módulo no servidor da aplicação:

```powershell
.\venv\Scripts\python.exe manage.py verificar_insight
```

O treinamento é determinístico para a mesma amostra e fica em cache na memória do processo. Ao
reiniciar o serviço ou alterar os dados, ele é recalculado. Para bases muito maiores, recomenda-se
evoluir para treinamento agendado e artefato versionado, medindo antes tempo e consumo de memória.

## Como apresentar no TCC

O ponto não convencional é aplicar aprendizado não supervisionado local a dados operacionais que
não possuem rótulo de “certo” ou “errado”, mantendo privacidade, explicabilidade e custo recorrente
zero. A demonstração deve comparar os três modos, inserir um caso sintético fora do padrão e mostrar
como a mesma tela explica o alerta e mantém a decisão final com o usuário.

Registre também as limitações: qualidade da entrada, unidades ainda textuais, amostra mínima,
possíveis falsos positivos e necessidade de validação com especialistas da operação.
