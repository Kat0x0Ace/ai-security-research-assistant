# Indirect Prompt Injection and RAG Poisoning

Indirect prompt injection targets systems where the model reads content the attacker can influence. The most exposed class of systems is retrieval-augmented generation: a RAG pipeline fetches documents from a corpus and places them in the model's context. If an attacker can write to that corpus — by uploading a file, editing a shared wiki, or publishing a web page a search tool fetches — they effectively write instructions into the model's context window.

RAG poisoning is the deliberate version of this: seeding the knowledge base with documents whose text contains hidden instructions, for example white-on-white text in a PDF or invisible characters in a markdown file. When a user asks an unrelated question, the poisoned chunk is retrieved, and the injected instruction rides along into the answer.

Known mitigations include: wrapping every retrieved chunk in explicit delimiters and instructing the model that anything inside is data, not instructions; post-retrieval scanning for instruction-like patterns; provenance tracking so users can see which sources produced an answer; and privilege separation, so the model that answers questions cannot also send emails or update records.

Citation enforcement is itself a partial mitigation: when every claim must point to a visible source, an answer influenced by a hidden instruction becomes easier to audit. Refusal behavior helps too — a system that declines to answer when retrieval confidence is low gives an attacker fewer chances to smuggle context in.
