# User journey: the bid manager

The bid manager owns the go/no-go call on public tenders and the response that goes out. TenderLens takes an RFP from upload to a checked, cited first draft and a bid recommendation. The agents do the reading, searching, drafting and checking. The bid manager makes the two decisions that matter: what the RFP actually requires, and whether to bid.

## At a glance

| Stage | Bid manager does | TenderLens does | Time |
| --- | --- | --- | --- |
| 1. Upload | Signs in and uploads the RFP PDF | Parses pages, screens them with Bedrock Guardrails | Seconds |
| 2. Extract | Waits, or watches the step tracker | The RFP Analyst extracts every requirement and the scored criteria | 2 to 3 minutes |
| 3. Confirm (checkpoint 1) | Reviews the requirements, fixes category or pass/fail flags, confirms | Pauses the workflow until confirmed | The bid manager's call |
| 4. Assess, draft, verify | Waits | Compliance Analyst rules on each requirement; Proposal Writer drafts; Claim Verifier checks every claim | 5 to 8 minutes |
| 5. Approve (checkpoint 2) | Reviews the recommendation, gaps and draft; accepts or overrides with a reason | Pauses the workflow until a decision is recorded | The bid manager's call |
| 6. Publish and use | Downloads the matrix and draft, assigns gaps | Writes the XLSX and DOCX, logs KPIs | Seconds |

## 1. Upload

- Sign in. The runs page lists past runs with status, recommendation, requirement count and cost.
- Choose the RFP PDF and click **Start run**. The PDF goes straight to S3 and the Step Functions workflow starts.
- The step tracker shows the nine stages. The two marked with a person are the bid manager's.
- Parse and screen: every page is checked for injected instructions before any agent reads it. A flagged page is withheld and noted.

If live runs are switched off, or the daily run limit is reached, the upload card says so and past runs stay available.

## 2. Extract

The RFP Analyst reads the RFP one page at a time, four pages in parallel, and lists every requirement the bidder must meet or address:

- each requirement is a word-for-word quote with its page, checked against the PDF;
- marked mandatory or desirable, pass/fail or not, with a category (technical, security and compliance, staffing, service levels, insurance and legal, commercial, submission);
- linked to the RFP's scored evaluation criterion where there is one.

A rule-based shall/must scan runs alongside. Any obligation it finds that no requirement covers is shown as a possible miss.

## 3. Checkpoint 1: confirm the requirements

The run pauses and a banner asks the bid manager to confirm.

- **Requirements** tab: read the list. Each row shows the quote, page, category, obligation and pass/fail flag.
- Correct any category, or tick or untick pass/fail. Corrected rows are highlighted.
- Check the possible misses the scan flagged.
- Click **Confirm requirements**. The corrections are saved, written to the audit log, and used by every agent after this point.

In this deployment the run continues with the extracted list if nobody confirms within two minutes, so a demo never stalls. The window is a deploy setting.

## 4. Assess, draft and verify

No action is needed. The tabs fill in as each agent finishes.

- **Compliance matrix**: each requirement ruled met, partial, not met or no evidence, with a rationale and citations into the bidder's capability library. Filter by status, and click a citation to read the source passage.
- **Gaps**: every shortfall, by severity, with knock-out risks marked and a proposed mitigation (teaming partner, clarification question, exception or remediation).
- **Draft**: the response, written as claims. Every claim is tied to the requirements it answers and the evidence behind it. The Claim Verifier scores each claim's grounding; unsupported claims go back to the writer, at most twice, and anything still unsupported is marked.

## 5. Checkpoint 2: approve the decision

The run pauses again with the recommendation: **Bid**, **Bid with conditions** or **No bid**, with the share of available points.

- **Decision** tab: how it was reached. Knock-out checks first (for example a mandatory walkthrough or debarment), then a score weighted by the RFP's own evaluation points. The thresholds come from the bid policy: 70% or more to bid, 55% or more to bid with conditions. It also lists the conditions to meet and what-if scores, such as the effect of closing a gap with a teaming partner.
- **Overview**: coverage of requirements, evidence-backed claim rate, critical requirements and time to first draft.
- Then either **accept** the recommendation, or **override** it by choosing a different decision and giving a reason. Both are written to the audit log with the approver's name.

The decision itself is computed in code from the policy, not by the model, so the same inputs always give the same answer. If no one acts within seven days, the computed decision is recorded and the run completes.

## 6. Publish and use

- **Matrix (XLSX)**: the compliance matrix, a gaps sheet and the decision with its score lines, ready for the bid team.
- **Draft (DOCX)**: the cited first draft. Unsupported claims are shown in red, and gaps the writer could not fill appear as "[SME INPUT NEEDED]" placeholders for a subject expert.
- Typical next steps outside TenderLens: assign each gap an owner, send the clarification questions before the RFP's deadline for questions, approach teaming partners, and have experts finish the draft.

## Looking under the hood

These tabs are for anyone who wants to know how a result was reached or whether to trust it.

- **Architecture**: each workflow stage, the agent and models it uses, and this run's calls, tokens, cost and time.
- **Agent trace**: every model call, tool call (with its arguments) and automatic check, plus a timeline of the agents working in parallel.
- **Quality & controls**: the token budget used, Guardrails screening and grounding scores, the checks that ran, the audit log of human decisions, and, for RFPs with a hand-labelled gold set, an eval scored on demand with **Run eval**.

## Sharing

A finished run can be shared. Shared runs appear on the public read-only demo at `/demo`, where anyone can open them without signing in. Emails are replaced with role names there, and nothing can be started, confirmed or approved.
