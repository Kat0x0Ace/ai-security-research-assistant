# OWASP Top 10 for LLM Applications

The OWASP Top 10 for LLM Applications is an awareness document listing the most critical security risks specific to systems built on large language models. The 2025 list includes:

1. Prompt Injection — crafting inputs that cause the model to unintentionally follow attacker instructions. The defining risk of LLM systems.
2. Sensitive Information Disclosure — models leaking personal data, credentials, or proprietary training content present in their context or training data.
3. Supply Chain Vulnerabilities — compromised model repositories, poisoned fine-tuning datasets, or vulnerable dependencies in the LLM stack.
4. Data and Model Poisoning — manipulating training or fine-tuning data to plant backdoors or biases that trigger later.
5. Improper Output Handling — downstream systems trusting LLM output as if it were validated code, SQL, or HTML, enabling injection in the classic sense one layer below the model.
6. Excessive Agency — granting the model tools, permissions, or autonomy beyond what its reliability justifies.
7. System Prompt Leakage — revealing the hidden instructions that define the agent's role, rules, and sometimes secrets.
8. Vector and Embedding Weaknesses — attacks against retrieval systems, including unauthorized access to vector stores and cross-modal injection.
9. Misinformation — the model producing confident but false content, hallucination as a security problem.
10. Unbounded Consumption — denial-of-wallet and resource exhaustion through expensive model calls or runaway agents.

The list is maintained by the OWASP GenAI Security Project and updated as the threat landscape evolves. It is the standard starting point for threat-modeling an LLM application.
