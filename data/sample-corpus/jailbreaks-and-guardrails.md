# Jailbreaks and Guardrails

A jailbreak is a prompt designed to make a language model bypass its safety training — its refusals to produce harmful, illegal, or dangerous content. Where prompt injection redirects what a model does, jailbreaking targets what a model is willing to say.

Common jailbreak techniques include role-play framing (pretend you are an AI without restrictions), hypothetical or fictional wrappers (write a story where a character explains how to...), token smuggling (asking for output in code, tables, or ciphers that evade output filters), and multi-turn escalation, where the model is walked gradually across the line it would refuse in one step.

Defenses come in layers. Safety training teaches the base model to refuse harmful requests. System-level guardrails — input classifiers and output classifiers around the model — catch many bypass attempts. Constrained decoding limits what tokens the model can emit. Red-teaming, both human and automated, probes for new jailbreak classes before attackers find them.

The arms race is asymmetric: a jailbreak that works once can be shared instantly, while defenses must generalize to all variants. Researchers therefore measure robustness statistically, with benchmarks of many attack prompts, and treat jailbreak resistance as a moving target rather than a solved property. Reporting mechanisms and coordinated disclosure now exist for serious model vulnerabilities.
