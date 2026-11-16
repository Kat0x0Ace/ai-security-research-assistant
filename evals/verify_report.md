# Citation-check eval

25 eval questions · grounded answers from the live model, then the same answer with one fabricated cited sentence appended.

- **False flags on grounded answers:** 2 across 25 answers
- **Fabricated cited claims caught:** 24/25 (runs where the verifier's reply didn't parse are excluded and listed as *unverified*)
- **Answers with no citations (check can't help):** 0
- **Refusals (never reach the check):** 0
- **Median check latency:** 2.7s per answer (one batched LLM call)

| Question | Claims | Clean answer | Fabricated claim |
|---|---|---|---|
| What is prompt injection? | 6 | 0 flagged | caught |
| What is the difference between direct and indirect prompt injection? | 2 | 0 flagged | caught |
| Why do large language models fall for instructions hidden in data? | 7 | 1 flagged | caught |
| Which OWASP risk number is prompt injection? | 1 | 0 flagged | caught |
| How can an attacker poison a retrieval-augmented generation knowledge base? | 7 | 0 flagged | caught |
| What is RAG poisoning? | 2 | 0 flagged | caught |
| How can hidden instructions be planted in a PDF or markdown document? | 2 | 0 flagged | caught |
| Does citation enforcement help against indirect prompt injection? | 1 | 0 flagged | caught |
| What is excessive agency in LLM applications? | 1 | 0 flagged | caught |
| What does improper output handling mean in the OWASP LLM Top 10? | 1 | 0 flagged | caught |
| What is the OWASP risk about unbounded consumption? | 1 | 0 flagged | caught |
| What is system prompt leakage? | 1 | 0 flagged | caught |
| Which OWASP risk covers supply chain problems for LLMs? | 1 | 0 flagged | caught |
| What is a jailbreak in the context of large language models? | 2 | 0 flagged | caught |
| What role-play framing tricks do jailbreaks use? | 1 | 0 flagged | caught |
| How do multi-turn escalation jailbreaks work? | 1 | 0 flagged | caught |
| What defenses exist against jailbreaking a model? | 10 | 1 flagged | MISSED |
| What is an adversarial example? | 2 | 0 flagged | caught |
| What is the difference between poisoning and evasion attacks? | 2 | 0 flagged | caught |
| How does a model extraction attack work? | 2 | 0 flagged | caught |
| What is MITRE ATLAS? | 4 | 0 flagged | caught |
| How does MITRE ATLAS relate to the ATT&CK framework? | 3 | 0 flagged | caught |
| How should retrieved content be treated to mitigate prompt injection in RAG? | 9 | 0 flagged | caught |
| When should a RAG system refuse to answer? | 1 | 0 flagged | caught |
| Why is continuous retrieval evaluation important for RAG security? | 3 | 0 flagged | caught |
