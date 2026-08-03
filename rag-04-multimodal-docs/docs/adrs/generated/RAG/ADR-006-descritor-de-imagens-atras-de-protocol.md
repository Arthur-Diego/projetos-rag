# ADR-006: Descritor de imagens atrás de Protocol, com modelo local como segunda implementação prevista

- **Status:** aceito
- **Data:** 2026-08-01
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

As imagens extraídas pelo `hi_res` entram no índice como descrição em linguagem
natural, gerada por um modelo de visão. A v1 usa `gpt-4o-mini` em modo visão (base64
numa mensagem `image_url`), que é o caminho do guia. Mas descrever imagem é o único
estágio da ingestão em que o custo por elemento é uma chamada de visão paga, e o
Apêndice C do guia aponta a alternativa local para zerar custo de API. A pergunta
arquitetural: esse ponto de troca merece uma interface, ou o acoplamento direto basta?

O precedente é o ADR-004 do rag-03: o reranker nasceu atrás de `Protocol` prevendo a
Cohere como segunda implementação, e a previsão foi exercida antes do fim do projeto,
quando a validação trocou o modelo por medição.

## Decisão

**O descritor de imagens é um `Protocol`** (`ImageDescriptor`, nome final na
implementação): recebe a referência da imagem, devolve a descrição textual. A
implementação da v1 é a da OpenAI (`gpt-4o-mini` visão). Um modelo de visão local
(via Ollama ou similar) é a segunda implementação prevista, não implementada.

Como todo `Protocol` do projeto, não é verificado em runtime: o mypy é obrigatório na
suíte exatamente por isso (regra herdada da trilha).

## Alternativas consideradas

### Acoplar direto no cliente da OpenAI

Rejeitada. O custo da interface é uma classe de método único; o custo do acoplamento é
reescrever o `ImageDescriptionService` quando a alternativa local for exercitada. O
precedente do rag-03 mostrou que a segunda implementação chega antes do que se espera.

### Protocol também para o resumidor de tabelas

Rejeitada por ora. O resumo de tabela é texto para texto usando o mesmo cliente LLM da
geração; não há segunda implementação plausível distinta do próprio provedor de LLM do
projeto. Interface sem segunda implementação plausível é camada vazia, e a guideline do
workspace manda não criá-la. Se o provedor de LLM inteiro virar ponto de troca, isso é
outra decisão, de outro tamanho.

## Consequências

**Positivas**

- Zerar o custo de visão vira trocar uma linha na composição, num `exp/` de uma tarde.
- Testes do `ImageDescriptionService` usam um descritor dublê sem tocar rede, seguindo
  o escopo de testes da trilha.

**Negativas**

- Uma interface a mais para manter alinhada (assinatura e semântica) entre duas
  implementações que podem divergir em qualidade. A tabela de medição é o instrumento
  para comparar, como foi no rerank do rag-03.

## Referências

- `docs/domains/rag/hld.md`, "Componentes e responsabilidades"
- `../README.md`, Apêndice C (alternativa local) e seção "Projeto 4"
- ADR-004 do rag-03 (precedente do Protocol com segunda implementação prevista)
