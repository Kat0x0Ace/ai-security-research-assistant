# MITRE ATLAS Overview

MITRE ATLAS (Adversarial Threat Landscape for Artificial-Intelligence Systems) is a publicly available knowledge base that catalogs tactics and techniques used by adversaries against machine-learning systems. It is modeled on MITRE ATT&CK, the widely used framework for describing attacks on enterprise networks, and is maintained by The MITRE Corporation.

ATLAS organizes adversary behavior into tactics — the goals an attacker pursues, such as reconnaissance, initial access, persistence, and impact — and techniques, the concrete ways each goal can be achieved against an ML system. Example techniques include training data poisoning, model inversion, evasion attacks, prompt injection, and exfiltration of model weights through an inference API.

The knowledge base is grounded in real-world case studies and demonstrations, not just theoretical attacks. It maps to the NIST AI Risk Management Framework and is intended to help defenders threat-model AI systems the way security teams threat-model traditional infrastructure: enumerate what an adversary would plausibly do, check which techniques your design enables, and prioritize mitigations.

For LLM applications specifically, ATLAS covers attacks unique to generative systems — jailbreaking, prompt injection, and training-data extraction — alongside classical ML attacks that remain relevant, such as data poisoning and model theft.
