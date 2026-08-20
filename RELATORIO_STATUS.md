# Relatório de Status — Projeto CEG Pizza Box

## Visão geral

O **Pizza Box Agent** é a ferramenta de pré-venda para a fábrica de caixas de pizza:
recebe os dados do cliente, gera um **preview de aprovação** por IA para envio ao cliente
(via WhatsApp) e produz os **arquivos de impressão** (CMYK, alta resolução, com faca e
sangria) a partir dos gabaritos. O núcleo do sistema está construído e funcional; a etapa
atual é o **fechamento gráfico** dos modelos junto à gráfica e a **homologação final**.

---

## O que já está pronto (construído e testado)

**Plataforma / fluxo de negócio**
- Ciclo completo de pedido: rascunho → preview → aprovação → produção → entrega
- Catálogo de modelos, cadastro de clientes e histórico de revisões
- Painel web de operação (funil de pedidos, criação de pedido, catálogo, calibração)

**Inteligência artificial**
- Interpretação de mensagens em linguagem natural (extração de telefone, Instagram,
  frase, tema, etc.) via Gemini
- **Preview de aprovação por IA (Nano Banana):** gera um mockup profissional da caixa
  personalizado com a marca do cliente, para aprovação rápida
- Análise de foto de caixa (identifica o modelo e lê os dados já impressos)

**Produção gráfica**
- Geração do arquivo de produção em **CMYK** com perfil de cor **ICC (SWOP)** embutido
- **Resolução de impressão** configurável (300/350 DPI) carimbada na saída
- **Faca em camada separada** e **sangria** aplicadas ao arquivo
- Avisos automáticos quando a arte tem elementos não suportados (para o operador corrigir
  antes da produção) e quando uma fonte não está instalada

**Integração WhatsApp**
- Webhook completo (verificação, recepção e validação de assinatura)
- Conversa ponta a ponta: catálogo → escolha do modelo → coleta de dados → envio do
  preview → aprovação → produção
- Tela de configuração das credenciais (sem necessidade de reiniciar o sistema)

**Qualidade**
- Suíte de testes automatizados cobrindo o fluxo (todos passando)
- Fluxo validado ponta a ponta com gabaritos e pedidos reais

---

## Em andamento

1. **Fechamento gráfico dos modelos (com a gráfica).** Encaixe da arte sobre a faca real
   de cada modelo — proporção, sangria, remoção de fundo branco e ausência de marcas de
   corte na arte. Etapa iterativa, em alinhamento com a gráfica. *(É a fase de "testes"
   em curso.)*
2. **Refinamento dos arquivos de aprovação e de produção** por modelo.
3. **Preparação para publicação do WhatsApp** (deploy).

---

## Dependências (aceleram a conclusão)

Alguns itens dependem de informações externas e destravam o avanço:

- **Credenciais Meta / WhatsApp Business** (do cliente) — necessárias para ligar o envio
  automático das mensagens.
- **Arquivos de faca** de cada modelo (com a gráfica) — necessários para o fechamento
  gráfico preciso de cada caixa.
- **Endereço público / hospedagem** — para o WhatsApp receber e responder mensagens.

---

## Plano de conclusão (por etapas)

**Etapa 1 — Sistema operacional + primeiro modelo fechado**
Plataforma rodando com o fluxo completo de preview e aprovação, e o primeiro modelo de
caixa validado para produção. Marco ideal para uma **demonstração**.

**Etapa 2 — Ativação do WhatsApp**
Ligação do envio/recepção automático (após credenciais e hospedagem), com testes ponta a
ponta.

**Etapa 3 — Homologação e entrega**
Fechamento dos modelos restantes, ajustes finais com o cliente e entrega.

---

## Observações técnicas (transparência)

- **Preview x arquivo de impressão:** o preview por IA é um mockup de **aprovação**
  (RGB, alta qualidade visual). O **arquivo final de impressão** de caixas grandes é
  finalizado em vetor sobre a faca, na gráfica — a IA entrega a direção de arte, a gráfica
  fecha a chapa. Esse é o fluxo padrão do setor.
- **Escopo em pré-venda:** precificação e pagamento estão intencionalmente fora do escopo.
- **Textos e QR nos mockups:** os arquivos de aprovação servem para validar visual e
  posicionamento; textos finais e QR do cardápio são conferidos/refeitos no fechamento
  gráfico.

---

*Relatório de status — sem datas. As etapas podem ser cronometradas conforme as
dependências acima forem destravadas.*
