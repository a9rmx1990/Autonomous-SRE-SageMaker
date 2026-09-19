# Judge Demo Script (3-5 Minutes)

## Setup

Before the demo:
1. Start backend: `SIMULATION_MODE=true uvicorn main:app --port 8000`
2. Start frontend: `npm run dev` (or open deployed URL)
3. Open browser to http://localhost:3000
4. Have the Architecture page ready in a second tab

---

## 0:00 — Introduce the Problem (30 seconds)

**Say:**

> "Traditional monitoring tells you something is broken. You get a PagerDuty alert at 3am, SSH into servers, grep through logs, try a fix, check if it worked, and write a post-mortem the next day. We built a system that does all of that autonomously."

**Show:** The dashboard. Point out the system status, service health grid, and incident history.

---

## 0:30 — Trigger the Incident (15 seconds)

**Click:** "Simulate Payment API Incident" button on the dashboard.

**Say:**

> "This simulates a real-world scenario: the payment API's CPU spikes to 95%, ECS containers start crash-looping, 5xx errors spike, and a CloudWatch alarm fires."

The browser navigates to the incident detail page.

---

## 0:45 — Watch the Pipeline (60 seconds)

**Show:** The incident detail page as events stream in real time.

**Point out each stage as it appears:**

1. **Orchestrator** receives the incident and retrieves historical context from AgentCore Memory
2. **Log Analyst** investigates CloudWatch logs and identifies CPU saturation + container crash loops
3. **Remediator** proposes scaling the ECS service from 2 to 4 tasks
4. **Remediator** executes the approved action
5. **Verifier** checks health: CPU drops to 42%, 5xx rate to 0.3%, zero restarts
6. **System** resolves the incident and stores the post-mortem

**Say:**

> "Notice that each agent has a specific job. The orchestrator delegates, it doesn't do everything itself. The Log Analyst investigates, the Remediator acts, and the Verifier confirms. This is a real multi-agent supervisor pattern, not a single LLM chain."

---

## 1:45 — Show Agent Swarm Visualization (15 seconds)

**Point to:** The agent swarm diagram on the incident detail page.

**Say:**

> "This visualization reflects the actual execution state. The connections light up as agents communicate."

---

## 2:00 — Show Safety (30 seconds)

**Point to:** The remediation panel showing the proposed action details.

**Say:**

> "The LLM doesn't execute arbitrary AWS commands. Every action must match an allowlist: restart, scale, flush cache, restart container, or clear queue. In production mode, this pauses for human approval before executing. The system also enforces a retry limit to prevent infinite remediation loops."

---

## 2:30 — Show Memory (30 seconds)

**Navigate to:** the Memory page (`/memory`).

**Point out:**

1. The post-mortem with root cause, remediation, verification, and lessons learned
2. The stored pattern about payment-api peak traffic
3. The preference about choosing scale_up over restart when CPU > 90%

**Say:**

> "This uses Amazon Bedrock AgentCore Memory. Before investigating the next incident on payment-api, the orchestrator will retrieve this context. It learns from every incident."

---

## 3:00 — Show Observability (30 seconds)

**Navigate to:** the Observability page (`/observability`).

**Select** the incident from the dropdown.

**Point out:**

1. The trace timeline with each agent span
2. Duration of each stage
3. The pipeline diagram showing the flow

**Say:**

> "Every agent decision is traced with OpenTelemetry. In production, these traces export to AWS X-Ray. Judges, ops engineers, or auditors can inspect exactly what the agents did, why, and how long each step took. Nothing is a black box."

---

## 3:30 — Show Architecture (30 seconds)

**Navigate to:** the Architecture page (`/architecture`).

**Scroll through** the 8-stage pipeline explanation.

**Point to** the architecture diagram and tech stack.

**Say:**

> "The architecture is modular. Strands Agents SDK for the AI layer, FastAPI for the control plane, Next.js for the dashboard, AgentCore for memory, and OpenTelemetry for observability. Each component can be independently scaled or replaced."

---

## 4:00 — Wrap Up (30 seconds)

**Say:**

> "To summarize: we built an autonomous SRE system that can detect, investigate, remediate, verify, and learn from cloud incidents. It uses AWS Strands Agents for multi-agent orchestration, Amazon Bedrock for reasoning, AgentCore Memory for cross-incident learning, and OpenTelemetry for full observability. The key difference from a chatbot is that this system acts autonomously through controlled, auditable, safe actions on real infrastructure."

---

## If Judges Ask

**"Is this using real AWS?"**
> "In this demo, simulation mode generates realistic synthetic data. In production mode, every tool makes real boto3 API calls. The architecture is identical; only the data source changes."

**"How do you prevent the LLM from doing something dangerous?"**
> "Three layers: action allowlisting (only 5 approved actions), human approval in production mode, and a retry limit to prevent runaway loops. The LLM proposes; the application validates and executes."

**"What if AgentCore Memory is unavailable?"**
> "The system falls back to a local in-memory store. The pipeline runs identically; it just loses cross-session context. No errors, no crashes."

**"How does this differ from a simple LLM chain?"**
> "The orchestrator delegates to specialist agents, each with their own tools and reasoning. The Log Analyst doesn't remediate; the Remediator doesn't verify. This mirrors how real SRE teams work: different roles, shared context."
