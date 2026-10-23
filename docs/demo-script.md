# TenderLens demo walkthrough (about 8 minutes)

The demo follows one RFP from upload to a signed-off bid decision, then shows the trace and the evals behind it.

## 1. The problem (30 seconds)

Bid teams lose opportunities because long RFPs take days to answer, mandatory requirements get missed, and proposal claims go out without evidence. TenderLens turns an RFP into a checked, cited first draft and a bid/no-bid call in minutes, with a person approving every decision.

## 2. Upload (1 minute)

- Sign in and upload the City of Belle Isle IT-services RFP (26 pages).
- Point at the step tracker: nine Step Functions states, five of them agents, two of them people.
- Parse and screen: pdfplumber keeps page numbers for citations, and Bedrock Guardrails screens every page for injected instructions before any agent reads it.

## 3. Checkpoint 1: confirm the requirements (1.5 minutes)

- Requirements tab: every requirement is a verbatim quote with its page. Quotes are checked word for word against the PDF, and paraphrases are rejected.
- Pass/fail flags: the mandatory walkthrough, CJIS, insurance minimums, debarment.
- Possible misses: a rule-based shall/must scan runs under the agent as a recall safety net.
- Correct one category, then confirm. The run resumes from the Step Functions task token.

## 4. Assessment and gaps (1.5 minutes)

- Compliance matrix: Met, Partial, Not met or No evidence, each with the passage that proves it. Click a citation to show the exact text.
- The agent chose its own searches (hybrid vector + keyword, filtered by the ontology category), at most three per requirement.
- Gaps: no CJIS Level 4 technicians, cyber cover of $500k against a $1M minimum, NIST CSF instead of 800-53. Each comes with a mitigation.

## 5. Draft and verification (1 minute)

- Draft tab: every sentence is an atomic claim with its citations.
- The Claim Verifier checked each claim with the Guardrails contextual grounding check, and unsupported claims went back to the Writer for a rewrite.
- SME placeholders appear where the evidence is silent, instead of invented facts.

## 6. Checkpoint 2: the decision (1 minute)

- Decision tab: knock-outs first (met, fixable or fatal), then a score weighted by the RFP's own evaluation points.
- The decision is computed in code. The Strategist agent only tested what-ifs with the scoring tool and wrote the rationale.
- Approve it, or override it with a reason. Both go into the audit trail.

## 7. Under the hood (1.5 minutes)

- Agent trace: model calls, tool calls, tokens, cost and latency per agent; validation events where code rejected an agent's output.
- Typed hand-offs: every message between agents is an ontology type, checked on write and on read.
- Governance: Cognito sign-in, least-privilege IAM, a daily run cap, token budgets, and a switch that turns live runs off.
- Evals: the gold set measures extraction recall, critical recall, status accuracy and citation validity, plus team-level metrics.
- Upgrade path: the same agents move to AgentCore Runtime, Gateway and Memory, Bedrock Knowledge Bases, or Claude, without a rewrite.
