# Retrieval eval report — sample-corpus-retrieval

- Cases: 25 (top_k=3)
- Hit rate: **100.0%**

| # | Question | Expected source | Hit |
|---|----------|-----------------|-----|
| 1 | What is prompt injection? | prompt-injection-basics.md | ✅ |
| 2 | What is the difference between direct and indirect prompt injection? | prompt-injection-basics.md | ✅ |
| 3 | Why do large language models fall for instructions hidden in data? | prompt-injection-basics.md | ✅ |
| 4 | Which OWASP risk number is prompt injection? | prompt-injection-basics.md | ✅ |
| 5 | How can an attacker poison a retrieval-augmented generation knowledge base? | indirect-injection-rag-poisoning.md | ✅ |
| 6 | What is RAG poisoning? | indirect-injection-rag-poisoning.md | ✅ |
| 7 | How can hidden instructions be planted in a PDF or markdown document? | indirect-injection-rag-poisoning.md | ✅ |
| 8 | Does citation enforcement help against indirect prompt injection? | indirect-injection-rag-poisoning.md | ✅ |
| 9 | What is excessive agency in LLM applications? | owasp-llm-top-10.md | ✅ |
| 10 | What does improper output handling mean in the OWASP LLM Top 10? | owasp-llm-top-10.md | ✅ |
| 11 | What is the OWASP risk about unbounded consumption? | owasp-llm-top-10.md | ✅ |
| 12 | What is system prompt leakage? | owasp-llm-top-10.md | ✅ |
| 13 | Which OWASP risk covers supply chain problems for LLMs? | owasp-llm-top-10.md | ✅ |
| 14 | What is a jailbreak in the context of large language models? | jailbreaks-and-guardrails.md | ✅ |
| 15 | What role-play framing tricks do jailbreaks use? | jailbreaks-and-guardrails.md | ✅ |
| 16 | How do multi-turn escalation jailbreaks work? | jailbreaks-and-guardrails.md | ✅ |
| 17 | What defenses exist against jailbreaking a model? | jailbreaks-and-guardrails.md | ✅ |
| 18 | What is an adversarial example? | adversarial-machine-learning.md | ✅ |
| 19 | What is the difference between poisoning and evasion attacks? | adversarial-machine-learning.md | ✅ |
| 20 | How does a model extraction attack work? | adversarial-machine-learning.md | ✅ |
| 21 | What is MITRE ATLAS? | mitre-atlas-overview.md | ✅ |
| 22 | How does MITRE ATLAS relate to the ATT&CK framework? | mitre-atlas-overview.md | ✅ |
| 23 | How should retrieved content be treated to mitigate prompt injection in RAG? | secure-rag-design.md | ✅ |
| 24 | When should a RAG system refuse to answer? | secure-rag-design.md | ✅ |
| 25 | Why is continuous retrieval evaluation important for RAG security? | secure-rag-design.md | ✅ |