# TenderLens — Product requirements

## Summary

TenderLens reads an RFP and returns six things: a requirements checklist, an evidence-linked compliance matrix, the gaps, a cited draft response, the claims nobody can back up, and a bid/no-bid recommendation. Under the hood, five LangGraph agents on Amazon Nova each do one job. Step Functions orchestrates them, with two human checkpoints. Everything is serverless on AWS.

**Problem.** Companies lose bids because answering long RFPs is slow, requirements get missed, and proposal claims aren't backed by evidence.

**Demo moment.** The user uploads a real city IT-services RFP. Within minutes the screen shows:

- every mandatory requirement
- the evidence behind each answer
- the gaps
- the claims nobody can back up
- a bid/no-bid call with its reasons

## Users and journey

The bid manager is the primary user. The subject-matter expert and the approver work from the same run.

| Persona | Their job in a bid | What they need from TenderLens |
| --- | --- | --- |
| Bid manager (primary) | Owns the response and the go/no-go call | A requirements checklist, coverage, a first draft fast, and a bid/no-bid call with reasons |
| Subject-matter expert | Answers technical, security and staffing sections | The requirements assigned to them, the evidence found, and the gaps to fill |
| Approver (sales head, legal) | Signs off before submission | Critical gaps, unsupported claims, and an audit trail of every decision |

**Journey, from upload to decision:**

1. The bid manager signs in and uploads the RFP PDF.
2. TenderLens parses it and extracts requirements, with live progress per step.
3. The bid manager reviews the requirements checklist and can correct a requirement's type or criticality (checkpoint 1).
4. The compliance matrix shows each requirement's status (Met, Partial, Not met, No evidence) and links to the exact passage and page in the evidence.
5. The gap register lists what the company can't meet, with a suggested mitigation for each: a teaming partner, a clarification question to the buyer, or a reason to walk away.
6. The draft response follows the RFP's own section structure. Every claim cites its evidence, and unsupported claims are highlighted.
7. The bid/no-bid card shows the recommendation and its score breakdown. The approver accepts it, or overrides it with a reason (checkpoint 2).
8. The user exports the compliance matrix (XLSX) and the draft (DOCX).

## Features and modules

| # | Module | What it does | Output | Priority |
| --- | --- | --- | --- | --- |
| 1 | Document ingestion | pdfplumber reads text and tables page by page, keeping page numbers for citations. Bedrock Guardrails screens the text for prompt attacks. | Page-aware sections and tables | Must |
| 2 | Requirement extraction | The RFP Analyst agent (Nova Pro) extracts atomic requirements: a verbatim quote, page, section, mandatory or desirable, category, and critical (pass/fail). Its shall/must scan tool catches anything the model skipped. | Requirements checklist | Must |
| 3 | Capability library | The bidder's documents are embedded with Titan Text Embeddings V2 into an index in S3. Search combines vectors and keywords and filters by ontology category. | Searchable evidence | Must |
| 4 | Evidence mapping and assessment | The Compliance Analyst agent chooses its own searches, up to three per requirement. It judges the status and cites passages, and every citation is checked against the source text. | Compliance matrix | Must |
| 5 | Gap analysis | Groups the gaps by severity, flags critical mandatory gaps, and suggests a mitigation for each. | Gap register | Must |
| 6 | Draft response | The Proposal Writer agent writes section by section, in the RFP's required order. Every factual sentence cites evidence, and unknown facts become SME placeholders. | Draft response | Must |
| 7 | Claim verification | The Claim Verifier agent checks every claim with the Guardrails contextual grounding check. Unsupported claims go back to the Writer, for at most two rounds, then get flagged. | Unsupported-claims list | Must |
| 8 | Bid/no-bid | The Bid Strategist agent applies the knock-out rules, computes the score in code from the bid policy, and writes the rationale. | Recommendation + score breakdown | Must |
| 9 | Human checkpoints | The bid manager confirms the requirements after extraction. The approver accepts the decision or overrides it with a reason. | Confirmed list, approval + audit trail | Must |
| 10 | Run trace and KPIs | Every agent step, tool call, token count, cost and latency, plus the four business KPIs | Trace tab + KPI panel | Must |
| 11 | Exports | Downloads the compliance matrix as XLSX and the draft as DOCX. | Files, served by download link | Should |
| 12 | Evaluation harness | Runs the hand-labelled gold set, plus team-level orchestration metrics, on demand. | Eval report | Must |
| 13 | Sign-in and usage limits | Cognito login with no self sign-up. Live runs are capped per day and can be switched off. | Secure URL at $0 idle cost | Must |

## Business KPIs

Each run measures the four KPIs automatically. On the primary RFP, they are also checked against hand-labelled ground truth.

| KPI | Definition | Formula | How it's measured | Target |
| --- | --- | --- | --- | --- |
| Time to first draft | Time from upload until the cited draft is ready | draft-ready time − upload time − time waiting at the confirm checkpoint | Step Functions execution timestamps, stored on the run | Under 15 min for a 50-page RFP |
| Requirement coverage | Share of extracted requirements that the draft answers with at least one cited claim | requirements answered ÷ requirements extracted | Mapping from claims to requirement IDs | 100% of mandatory, 90% or more overall |
| Evidence-backed claim rate | Share of factual claims in the draft that their cited evidence supports | supported claims ÷ all factual claims | Claim-verification step (module 7) | 95% or more; the rest are flagged, never hidden |
| Critical requirements missed | Critical pass/fail requirements that were never extracted, or that the run didn't flag when they were Not met | count | Comparison against the gold set (primary RFP); the shall/must scan on any other RFP | 0 |

Two operational metrics are tracked alongside: cost per RFP run in USD, and latency per pipeline step.

## Bid/no-bid rules

1. **Knock-outs first.** Mandatory pass/fail requirements are checked one by one. Each is met (with evidence), fixable before submission (for example by a teaming partner or more insurance), or fatal. Any fatal knock-out means no-bid.
2. **Expected score.** Each evaluation criterion in the RFP is weighted by its own points. Met counts 100%, Partial 50%, Not met 0%, Unknown 50%.
3. **Decision.** Bid at 70% or more. Bid with conditions at 55–70%, listing the fixes. No-bid below 55%.

The thresholds live in the bid policy, not in code. The model writes the rationale; it doesn't make the call. A what-if shows how the score moves when a gap is fixed.

## Scope, demo data and assumptions

v1 covers one bidder, English text-based PDF RFPs of up to 60 pages, and the modules marked Must above.

**Out of scope (non-goals):** pricing volumes, proposal design and graphics, other languages, scanned PDFs, CRM or SharePoint integrations, learning from past bids, and any real company's data. The [production upgrade path](HLD.md#production-upgrade-path) lists the AWS services that would add these.

**Demo data:**

| Role in demo | Document | Source |
| --- | --- | --- |
| Primary RFP, hand-labelled for KPIs | City of Belle Isle, FL, RFP 2026-04, Information Technology Services | [belleislefl.gov](https://www.belleislefl.gov/sites/default/files/fileattachments/finance/page/10736/rfp_2026-04_information_technology_services_final.pdf) |
| Unseen RFP, uploaded live | City of Dawsonville, GA, 25-RFP-001, IT Managed Services | [dawsonville-ga.gov](https://dawsonville-ga.gov/sites/default/files/fileattachments/city_clerk/page/10387/25-rfp-001_it_managed_services_final.pdf) |
| Bidder's capability library | Cobalt Harbor IT Services, a **fictional** managed IT provider: company profile, service catalogue and SLAs, certifications, security policies, past performance, key staff, insurance, help-desk operations, transition plan | Written for this project |

Belle Isle has real knock-outs. It requires attendance at a mandatory on-site walkthrough, CJIS Level 4 certification for systems and technicians (10 of 75 evaluation points), NIST 800-53 compliance, a 24×7 service desk, and at least $1M each in errors-and-omissions and cyber insurance.

The fictional bidder attended the walkthrough and carries $2M of E&O cover, but only $500k of cyber cover. It has no CJIS Level 4 technicians, and it follows the NIST Cybersecurity Framework rather than 800-53. These planted gaps give the demo real findings with known answers.

**Assumptions:**

- The AWS account runs in ap-southeast-2 (Sydney) with Bedrock access to Amazon Nova, through APAC cross-region inference profiles, and Titan embeddings.
- Every service costs nothing while idle.
- Live runs are capped per day; one parameter makes the app replay-only.
