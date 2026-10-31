# Problem statement

## Challenge

Large volumes of security logs can conceal attacks behind disconnected events. Analysts need to correlate evidence across systems and time to understand an incident as a whole.

KillChain AI aims to answer:

- Where did the attack begin?
- What actions did the attacker perform?
- How did the attack progress across systems?
- Which hosts, users, and systems were affected?
- Which systems and resources could the attacker potentially reach next?

## INC-01: 2013 Retail Data Breach

A stolen third-party vendor credential, followed by weeks of ignored security alerts, contributed to a major retail breach affecting up to 110 million customers.

This motivating use case is supplied in the project brief. No additional incident details are asserted. It highlights the importance of connecting alerts into an attack narrative, making kill chain progression visible, and recognizing suspicious activity early enough to support investigation.

## Intended outcome

The proposed platform will help analysts move from isolated events to evidence-linked attack paths and explanations of potential reachability. Future-path analysis must expose its assumptions and distinguish possible access from observed compromise.

## Scope and current limits

The repository currently contains a health API, dashboard shell, storage configuration and planning documentation. Processing 15 GB, 30 GB, and 50 GB datasets is a future goal, not an implemented capability. There are no detection results, benchmarks, incident logs, or prevention claims.
