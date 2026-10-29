# Adversarial Machine Learning

Adversarial machine learning studies how machine-learning systems can be attacked and how to defend them. The field predates large language models: adversarial examples — inputs perturbed with tiny, often imperceptible changes that flip a classifier's decision — were first demonstrated against image models.

Three broad attack families are standard. Evasion attacks happen at inference time: an attacker crafts input that the model misclassifies, such as a stop sign modified so a vision system reads it as a speed limit. Poisoning attacks happen at training time: corrupting training data so the learned model itself contains a vulnerability or backdoor. Extraction attacks steal the model itself: querying an API systematically enough to reconstruct a copy of the model, or its training data through memorization.

The NIST AI Risk Management Framework and NIST's taxonomy of adversarial machine learning attacks organize these threats for practitioners. MITRE ATLAS plays the same role for ML that the classic ATT&CK matrix plays for enterprise networks: a public knowledge base of real-world tactics and techniques adversaries use against AI systems.

Defenses include adversarial training (learning on attack examples), input sanitization and anomaly detection, differential privacy to limit memorization, watermarking and rate limiting against extraction, and rigorous data provenance against poisoning. No single defense is sufficient; the field's consensus is layered mitigation plus monitoring, because attack surfaces evolve with the models.
