# Relatório do sistema de caixas personalizadas

Julho de 2026

## O que a gente observou

O sistema foi criado para automatizar a parte mais demorada da venda de caixa personalizada: receber os dados da pizzaria (telefone, Instagram, frase e logo), montar a arte sozinho e mostrar uma prévia na hora para o cliente aprovar. A ideia sempre foi o sistema fazer uns 80% do trabalho e o designer entrar só no final, para o acabamento antes da impressão.

O problema é que hoje o sistema trabalha em cima do arquivo original do Photoshop, aquele arquivo pesado de quase 500 MB. Toda vez que um cliente pede uma prévia, o sistema precisa abrir esse arquivo inteiro, editar e salvar uma cópia completa. E isso acontece de novo a cada revisão. Na prática fica tudo lento, a memória do servidor não aguenta e o disco enche rápido.

Tem um segundo problema, que é menos visível mas importante. Mesmo pagando esse preço todo, o sistema não consegue reproduzir a arte com fidelidade total. Sombras, contornos, efeitos e as fontes especiais que o designer usa acabam se perdendo quando o sistema mexe no arquivo. Ou seja, o arquivo que sai do sistema teria que ser retrabalhado pelo designer de qualquer jeito.

E ainda tem o trabalho de preparação: para cada modelo novo de caixa, o designer precisa remontar o arquivo no Photoshop com camadas nomeadas de um jeito exato, seguindo uma lista de regras. É manual e chato de fazer.

## O que vai mudar nos formatos

A mudança principal é essa: o arquivo pesado do Photoshop sai do sistema por completo. Ele fica onde sempre deveria ficar, no computador do designer, intacto.

No lugar dele, o sistema passa a usar apenas uma imagem leve da arte, tipo uma foto em boa qualidade de poucos MB, uma para cada fundo disponível (kraft e premium). É só isso que o sistema precisa para montar as prévias, porque os textos e a logo ele desenha por cima dessa imagem, nas posições que já ficam salvas na ferramenta de calibração que o sistema já tem hoje.

E quando o cliente aprova, em vez de gerar mais um arquivo gigante, o sistema monta um pacote de produção para o designer. Esse pacote tem a prévia que o cliente aprovou, a logo já tratada com o fundo removido, os textos exatos e a posição de cada elemento na arte. Nada de arquivo pesado indo e voltando.

## O que vai mudar no fluxo de trabalho

Para o cliente da pizzaria, nada muda, só melhora. Ele manda os dados, recebe a prévia em segundos em vez de esperar, pede os ajustes que quiser e aprova.

Para quem cadastra modelos novos, fica muito mais simples. Em vez de preparar o arquivo no Photoshop com todas aquelas camadas e nomes obrigatórios, basta exportar uma imagem da arte de cada fundo e posicionar os campos na tela, arrastando as caixinhas na ferramenta que já existe. Coisa de minutos.

Para o designer, o trabalho muda de natureza. Hoje ele recebe pedidos soltos e um arquivo degradado que precisa refazer. Com a mudança, ele recebe uma especificação pronta: a imagem aprovada pelo cliente mostrando exatamente como deve ficar, a logo tratada e os textos com as posições certas. Ele abre a arte original dele, que nunca saiu da máquina dele, aplica esses elementos com as fontes e efeitos de verdade, ajusta o que achar necessário e fecha o arquivo para a fábrica. O toque final continua sendo dele, que é justamente onde ele agrega valor. A diferença é que ele não perde mais tempo interpretando pedido de WhatsApp nem refazendo texto por causa de fonte errada.

## Resumindo

O sistema continua fazendo o que já faz de melhor: atender, montar a arte, mostrar prévia e colher aprovação. A parte do atendimento, do catálogo e das revisões não muda nada. O que muda é por dentro: sai o arquivo de 500 MB e entra uma imagem leve mais um pacote de produção bem organizado para o designer. Resultado prático: prévias em segundos, servidor folgado, cadastro de modelo simples e o designer partindo sempre da arte original sem perda de qualidade.
