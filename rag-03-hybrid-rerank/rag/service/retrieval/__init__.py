"""O funil de recuperação: os três serviços que decidem o que chega ao modelo.

**Esta pasta existe porque ela é o que muda de projeto para projeto na trilha.**
Ingestão, montagem de prompt, geração e citação são praticamente os mesmos nos
dez projetos. A recuperação não: o Projeto 1 faz kNN puro, o 3 (este) faz funil
híbrido com fusão e reordenação, o 4 troca por multi-vector, o 5 por grafo de
estado, o 7 por consulta a grafo de conhecimento.

Agrupar torna a pergunta "o que este projeto faz de diferente?" respondível
olhando um diretório, em vez de garimpando arquivos soltos entre oito irmãos que
não mudaram.

O que está aqui, as quatro etapas do funil mais o orquestrador:

- `dense_search_service` busca por significado. **Delega ao repositório** (ADR-009).
- `keyword_search_service` busca por palavra exata. **Delega ao repositório.**
- `fusion_service` funde os rankings por posição. Função pura, sem dependência.
- `rerank_service` reordena por precisão. `Protocol`, com implementação local.
- `retrieval_service` orquestra os quatro e é dono da política (faixas, `k`,
  `candidates`, `rrf_k`). Orquestra e não calcula.

**Os dois primeiros são repasse hoje, e isso foi decidido de olhos abertos.** A
guideline do workspace chama delegação pura de camada vazia, e ela está certa
enquanto não houver política de caminho. O ADR-009 registra por que foram criados
assim mesmo e qual é o gatilho que os torna necessários: tratamento de query
próprio do BM25, expansão no caminho denso, contagens diferentes por caminho, ou o
docstore que o Projeto 4 acrescenta.

O que NÃO está aqui, e a ausência é deliberada:

- `query_rewrite_service` fica fora, apesar do sufixo `_service` e da aparência
  de vizinho. Ele é o estágio da PERGUNTA, não o da recuperação: o funil recebe
  uma query já resolvida e nunca vê a conversa. Trazê-lo para cá faria a política
  de reescrita ter dois donos.
- Os repositórios continuam em `repository/`. Eles são a fronteira com o motor de
  busca, e essa fronteira é de camada, não de assunto.

Diverge da guideline de arquitetura do workspace, que prescreve `service/` plano.
Ver ADR-008.
"""
