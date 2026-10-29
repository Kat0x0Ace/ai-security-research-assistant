# Building Secure Retrieval-Augmented Generation Systems

Retrieval-augmented generation (RAG) improves LLM answers by grounding them in documents: a query is embedded into a vector, similar document chunks are retrieved from a vector database, and the model answers using those chunks as context. Security of a RAG system has to be considered at every stage of that pipeline.

At ingestion, risks include poisoning (attacker-controlled documents entering the corpus) and sensitive data leaking into a store that is more widely readable than its source. At retrieval, the vector database itself is an attack surface: vector stores have access controls like any database, and embeddings can sometimes be inverted to approximate the original text. At generation, the retrieved chunks sit in the model's context where indirect prompt injection lives.

Core design principles that improve RAG security:

- Treat all retrieved content as untrusted data: delimit it, instruct the model never to follow instructions inside it, and sanitize or scan chunks for injection payloads.
- Enforce citations. Every claim should trace to a visible source, which makes manipulation auditable.
- Prefer refusal over guessing. When retrieval confidence is low — for example, the best match is still distant in embedding space — the system should decline to answer rather than hallucinate.
- Scope tool permissions. A RAG agent that can also send email or modify records turns a successful injection into a real-world action.
- Evaluate retrieval quality continuously. An eval suite of question/expected-source pairs catches silent regressions when models, chunking strategies, or the corpus change.

These principles echo defense-in-depth from classical security: assume some layer will fail and make each layer limit the damage of the next.
