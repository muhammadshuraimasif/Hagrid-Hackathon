<!-- Page 1 -->
Amaanat: Hackathon Solution & Flow 
Blueprint
 Nov 21, 2026  ·  @jawwad malik
PROTOTYPE ONLY. Amaanat is a hackathon prototype, not an official government service.
Every identity, payment, messaging and data service is mocked. No real personal data is
used anywhere.
1. Executive summary
Amaanat (Urdu for something held in trust) is a multi-tenant case platform that takes one
mock relief-grant claim from "I got a message about money" to "money safely on hold in
the right account" or "a person is checking your case". It decides only when the measured
cost of being wrong is lower than the cost of asking a human.
The sentence the brief asks for: We help a low-literacy citizen, alone or through a
community helper on a shared phone, claim a mock government relief grant even though
they cannot read the forms, have a weak signal, and are surrounded by fake "relief
payment" messages.
One task, all three personas. All three people in the brief touch the same claim, so one
deep flow serves everyone:
Seven design principles
1. AI proposes, rules decide, humans own the risky cases. No model ever approves
money or rejects a person. A versioned rule engine plus a cost-derived policy decides;
officers decide everything else.
2. Three exits, no fourth. Every case ends in AUTO (approve onto a reversible hold), ASK
(one specific, cheap piece of evidence) or HUMAN (with a hand-off packet). There is
no silent path and no auto-reject.
Persona Their barrier Where Amaanat meets them
Widow Cannot read, weak
signal
Voice-and-icon claim, offline queue, digit-by-digit
read-back
Shopkeeper Fake relief messages Scam Shield with a verifiable official code, then
the genuine claim
Helper 40 families, one phone Helper Mode: per-family consent, scoped tokens,
wiped on switch
Amaanat: Hackathon Solution & Flow Blueprint
Page 1 of 34

<!-- Page 2 -->
3. Confidence is earned, not stated. It comes from agreement between independent
checks, capped by the weakest one, then calibrated on labelled data. A model's self-
reported confidence is ignored.
4. One decision record, three views. The citizen's plain reason, the officer's packet and
the auditor's trace are rendered from the same stored record.
5. Everything that can change is data. Rules, thresholds, cost weights, required
documents and reason texts live in versioned, immutable rule sets.
6. One gate for personal data. Every read, by a screen, API key, webhook or AI agent,
passes one consent check at the moment of reading.
7. Measure, don't claim. Every number shown to judges comes from a seeded
evaluation run, with its sample size and its limits printed beside it.
What judges will see in eight minutes
A fake relief SMS flagged with reasons, a genuine one verified by its code, and an
ambiguous one routed to a person.
The widow's claim completed by voice and icons on a throttled, then dropped,
connection with no duplicate on sync.
A clean case auto-approved onto a 60-second reversible hold, and an edited CNIC
sent to an officer with the tampered region highlighted.
An admin changing a rule, previewing its effect on past cases in the Digital Twin,
publishing it, and an old decision still showing its old rule version.
A citizen withdrawing a helper's consent and the helper's next request returning 403,
visible in a hash-chained audit log.
The mock identity service switched off live, and the system saying "I cannot verify
right now" instead of guessing.
2. Analysis of the brief and the rubric
The brief scores judgment under failure, not feature count. At least 38 of 100 points
(Safety 15, Accessibility 10, End-to-end completion 7, Output quality 6) are earned only by
behaviour judges watch live: bad photos, low confidence, dropped signal, withdrawn
consent, changed rules. A polished happy path alone cannot earn them.
2.1 What the brief really asks for
A platform, not a chatbot. Users, roles, cases, rules and audit trails are explicitly
required. A chat window as the main product is a stated anti-pattern.
Amaanat: Hackathon Solution & Flow Blueprint
Page 2 of 34

<!-- Page 3 -->
One task, finished end to end. "A deep solution for one task beats a thin solution for
many." End-to-end completion is the single largest rubric line in its category (7
points).
Asymmetric cost. "Wrong approvals cost more than slow approvals. Show how …
Show the numbers." Judges expect a written cost model and a threshold derived from
it, not a hard-coded 0.8.
Abstention is a feature. "Silent guessing earns zero." Low confidence must stop the
flow and hand over with notes attached.
Behaviour over claims. Judges will poke the live system: wrong role, withdrawn
consent, bad photo, dead service. Server-side enforcement is named explicitly.
Honesty is scored. "Show false alarms honestly", "tell the judges what is real and what
is simulated", "explain system limitations".
2.2 Where the 100 points are, and what earns them
Category (pts) Sub-criteria (pts) What actually earns full
marks
AI Implementation
(30)
Functional AI features 12 ·
Workflow integration 8 · Output
quality 6 · Model selection 4
3+ AI features that work live
(we ship 8), all inside one
decision pipeline rather than
side demos; measured
accuracy on screen; a
different, justified tool per
job
SaaS & Architecture
(20)
Core features 8 · API design 5 ·
Database 4 · Deploy/test/monitor
3
Every core feature (RBAC,
cases, public API + Swagger,
audit, consent, mocks);
versioned REST with API
keys; migrations; live URL, CI
tests, health and logs
Real-World Problem
Solving (15)
Understanding 5 · End-to-end
completion 7 · Impact 3
The one claim runs from
message to payment or
human with no dead ends;
grounded in real Pakistani
DPI patterns (CNIC, Raast,
scam SMS)
Amaanat: Hackathon Solution & Flow Blueprint
Page 3 of 34

<!-- Page 4 -->
2.3 The hidden tests judges are likely to run
1. Log in as a citizen and call an officer endpoint directly. Expect 403 from the server, not
a hidden button.
2. Upload a blurry or edited CNIC. Expect a retake request or a human hand-off, never an
approval.
3. Type "Mohammad" where the record says "Muhammad". Expect a careful match, not a
crash or a wrong merge.
4. Ask "why was I approved?" Expect a plain answer and an auditor trace with rule
version and confidence.
5. Change a rule and immediately run a case. Expect the new rule, with no redeploy.
6. Withdraw consent and retry access. Expect denial plus audit entries.
7. Pull the network cable mid-claim. Expect saved progress and clean sync.
8. Paste a genuine government-style message. Expect it not to be flagged, or the false
alarm to be shown honestly.
2.4 Traps to avoid
Invented metrics. Any number not produced by your own run will be questioned. Both
earlier drafts contained illustrative figures; this blueprint replaces them with formulas
and a measurement plan.
LLM as decider. An LLM approving money is unauditable and uncalibrated. Judges
with ML background will ask.
Category (pts) Sub-criteria (pts) What actually earns full
marks
Accessibility (10) Voice & regional language 4 · Low
literacy 3 · Weak internet 3
Urdu voice in and out; a flow
completable without reading;
offline queue proven by
toggling the network live
Safety, Privacy &
Reliability (15)
Uncertainty & handoff 5 ·
Consent 4 · Explain & audit 3 ·
Risk & reliability 3
Cost-based abstention;
withdrawal that produces a
real 403; two explanation
views; chaos switches on
mock services
Innovation (10) Originality 4 · Creative feature 4 ·
Technical creativity 2
One bonus feature fully
working (Digital Twin), plus
original mechanisms judges
have not seen elsewhere
Amaanat: Hackathon Solution & Flow Blueprint
Page 4 of 34

<!-- Page 5 -->
Feature sprawl. Four half-done bonus features score less than one that works.
A single "god" demo session. Switching roles must swap real tokens, or judges will
assume RBAC is cosmetic.
Live-demo fragility. Venue Wi-Fi, cold starts and API quotas end demos. A local
fallback is mandatory.
Auto-rejection. Blocking a real person is a named cost. The AI must never reject.
3. How this replaces Sahara and Rasta
Both earlier proposals picked the right task and the right skeleton (versioned rules, three
routes, consent gateway, hash-chained audit). Amaanat keeps that skeleton, removes
their contradictions, and adds six mechanisms neither had.
3.1 Kept from both
Relief-grant claim as the single task · FastAPI + Postgres modular monolith · JSONLogic
rule sets, immutable once published · AI never rejects · release hold on payments · hash-
chained, insert-only audit log · one consent gate checked at read time · pre-recorded Urdu
clips and chained digit audio · Postgres job queue (no Redis) · Digital Twin and Helper
Mode as bonus features · docker-compose fallback for the live demo.
3.2 Fixed
Issue in the earlier
drafts
Sahara Rasta Amaanat
Cost model and
threshold disagree
with each other
Review cost 2,
threshold 0.98
Review cost 10,
break-even 0.90,
then 0.95 "with
margin"
One cost table in PKR
terms; threshold =
break-even, then
tightened only by a
stated statistical risk
bound (section 8)
"Ask more" band
chosen by gut
0.80–0.98 0.70–0.95 Ask only when the
specific missing
evidence can plausibly
move the case past the
threshold and is worth
its cost (value of
information)
Amaanat: Hackathon Solution & Flow Blueprint
Page 5 of 34

<!-- Page 6 -->
3.3 New in Amaanat
1. Account-title check before payout. Before money moves, the mock Raast service
returns the account holder's name for the destination account, and it must match the
verified claimant. This blocks the single most common real-world relief fraud: a
correct claimant with a scammer's account.
2. Risk-bounded auto-approval. The auto threshold must satisfy a 95% upper
confidence bound on the wrong-approval rate, not just a point estimate.
3. Next-Best-Evidence asker. ASK picks the one cheapest piece of evidence that would
most reduce expected cost, and says it in one Urdu sentence.
4. Capability-gated agent tools. The agent cannot call the payment tool unless it holds a
short-lived, signed decision token minted by the policy engine for that case.
5. Actionable reasons. Every non-approval tells the user exactly what would change the
outcome ("a clearer photo of the back of your card").
6. Fairness slice on the evaluation dashboard. Escalation and false-alarm rates are split
by channel (self, helper, voice) and by name-variant group, so the system can show it
does not quietly punish the people it was built for.
Issue in the earlier
drafts
Sahara Rasta Amaanat
Illustrative numbers
presented in tables
Yes, labelled Yes, labelled No numbers before
measurement; formulas
plus an evaluation plan
Evaluation size 1,200 cases 600 cases About 1,600 generated
cases with fixed train /
calibration / test splits
and confidence intervals
Meta-content not
meant for judges
Version
history, review
notes
Approval status Clean, judge-facing
document
Raw SQL DDL in a
design doc
No Yes Entities and
relationships only; no
code
Separate "BLOCK"
route
No Yes (a fourth route) Fraud signals feed
HUMAN with a fraud
tag; still exactly three
exits
Amaanat: Hackathon Solution & Flow Blueprint
Page 6 of 34

<!-- Page 7 -->
4. Personas, the task and the roles
The task is the mock Relief Support Grant: PKR 25,000, one per household, paid to a
Raast-style account held in the claimant's own name. All five roles from the brief are built,
because judges test permission boundaries.
4.1 Personas (all synthetic)
4.2 Claim lifecycle (case states)
DRAFT → SUBMITTED → CHECKING → one of { NEEDS_INFO (ASK) · IN_REVIEW
(HUMAN) · APPROVED_ON_HOLD (AUTO) } → PAID or REVERSED or
REJECTED_BY_OFFICER → CLOSED. A case can also enter WAITING_FOR_SERVICE
when a mock dependency is down; it resumes automatically and never decides while
waiting.
Persona Context What success looks like
Zainab, widow, 58, Lyari Cannot read; prepaid phone
with 2G in her lane; record
spells her husband's name
"Mohd."
Claims by voice and photos,
hears her status in Urdu, never
has to type
Akram, shopkeeper, 41,
Korangi
Receives three fake "relief
payment" SMS a week; one
asked for an OTP
Checks a message in one tap,
learns how to spot a real one,
then claims safely
Shazia, community
helper, 33
Serves 40 families from one
Android phone; frequent
switching
Switches families in two taps;
each family's data stays
separate and consented
Officer Bilal, Provincial
Relief Dept
60 cases a day A queue sorted by stakes and
uncertainty, with a packet that
explains each case
Admin Sana Policy changes arrive by
notification letter
Edits a rule, sees its effect on
past cases, publishes without
engineers
Auditor Farah Quarterly review Replays any decision and
verifies nothing was altered
Amaanat: Hackathon Solution & Flow Blueprint
Page 7 of 34

<!-- Page 8 -->
4.3 Roles and permissions (enforced on the server)
Tenants. Two seeded workspaces, the Provincial Relief Department and the Municipal Aid
Office, each with its own rule set, officers, API keys and analytics. A row-level tenant id
plus Postgres row-level security keeps them apart.
5. End-to-end flow
Every claim follows one pipeline of 13 steps (0 to 12). Each step writes a case event and an
audit entry, and each has a defined failure behaviour, because that behaviour is what
judges score.
Capability Citizen Helper Officer Admin Auditor
Start, upload, submit a
claim
Own For consenting
families only
— — —
See case status Own Consented
families
Own
tenant
Counts only Read-only
Approve, reject,
request info, reverse a
hold
— — Yes — —
Manage consent Full
control
Request only — — View
ledger
Edit rules, run Digital
Twin, publish
— — — Draft + publish (second
admin approves if
enabled)
View
versions
Users, API keys, mock-
service chaos switches
— — — Yes —
Audit log, AI traces,
chain verification
Own
history
— Own
decisions
— Full, read-
only
# Step What happens AI / tech If it fails
0 Enter Login (or helper
picks "acting for"
a family),
language choice,
Urdu voice
greeting
JWT + RBAC,
cached audio
Offline: cached app opens;
actions queue locally
Amaanat: Hackathon Solution & Flow Blueprint
Page 8 of 34

<!-- Page 9 -->
# Step What happens AI / tech If it fails
1 Check a
message
(optional)
Paste, forward or
photograph a
suspicious SMS;
enter or scan its
verification code
Scam Shield:
rules + classifier
+ LLM voter +
signed-code
check
Unsure → "do not act, ask a
person" and route to
helpline queue; never a
silent block
2 Consent Icon screen, read
aloud: what data,
to whom, for
what, until when;
tap or say "haan"
Consent ledger,
spoken receipt
No consent → nothing
moves; flow pauses
3 Capture Photograph
CNIC front, back
and the claim
form; live blur
and glare
warnings
Client-side
compression,
chunked
resumable
upload
Upload resumes from last
chunk; draft saved on
device and server
4 Read the
documents
Fields extracted
into a fixed
schema;
deterministic
checks in parallel
Vision LLM +
Tesseract + QR
decode +
forensics;
Pydantic
Poor photo → ASK retake;
sources disagree →
HUMAN; model down →
Tesseract, else HUMAN
5 Read-back System speaks
the name and
CNIC digit by
digit; user
confirms with ✔  /
✖  or voice
Recorded digit
clips,
constrained STT
Mismatch → correction
loop, max 2 rounds, then
HUMAN
6 Identity &
duplicates
Mock NADRA
lookup, name
normalisation
and fuzzy match,
duplicate search
Identity resolver Service down →
WAITING_FOR_SERVICE;
never guesses
Amaanat: Hackathon Solution & Flow Blueprint
Page 9 of 34

<!-- Page 10 -->
# Step What happens AI / tech If it fails
7 Eligibility Active rule-set
version
evaluated; each
rule returns pass,
fail or unknown;
"why" questions
answered with
cited sources
JSONLogic
engine, RAG
Any "unknown" blocks
AUTO
8 Risk Repeat claims,
shared accounts,
burst patterns,
helper-device
awareness
Isolation Forest +
rules
A flag means HUMAN,
never a block
9 Decide Expected-cost
policy picks
AUTO, ASK or
HUMAN; hard
guards checked
Decision policy
(pure function),
calibrated
confidence
Any exception → HUMAN
(fail closed)
10 Act AUTO: account-
title check, then
payment
authorised onto a
release hold.
HUMAN: officer
case with hand-
off packet
Capability-gated
agent,
idempotent
mock Raast
Retries with idempotency
key; never pays twice
11 Explain &
notify
Plain reason by
voice and icon;
simulated SMS /
WhatsApp / in-
app; signed
webhook
Reason-code
templates, job
queue
Retry with backoff; failures
visible to admin
12 Close &
learn
Officer decision,
hold release or
reversal,
analytics;
outcome added
to the evaluation
set
Review queue,
eval harness
Ageing cases rise in priority
automatically
Amaanat: Hackathon Solution & Flow Blueprint
Page 10 of 34

<!-- Page 11 -->
6. Architecture and stack
Amaanat is a modular monolith: one deployable API with strict internal module
boundaries, plus a worker and separately-addressed mock services. In 48 hours with 3–4
people this gives clean APIs and clear ownership without microservice overhead; modules
can be split later.
6.1 Layers
6.2 Stack choices and why
Layer Contents
Clients One React PWA with five role areas (citizen, helper,
officer, admin, auditor), a Judge Console, and
external API clients
Edge Request id → rate limit → auth (JWT or API key) →
RBAC → tenant scope → uniform error envelope →
audit hook
Domain modules Cases and events · documents · identity resolver ·
rules · decision policy · consent gate · notifications ·
webhooks · analytics
AI services Document reader, forensics, voice, Scam Shield,
RAG, anomaly detector, explanation builder, claim
agent, evaluation harness
Mock services mock-NADRA (identity), mock-Raast (payments +
account-title lookup), mock-exchange (other
departments), mock-SMS/WhatsApp; each with
chaos switches
Data Postgres with migrations, pgvector, object storage
for images, jobs table as the queue
Concern Choice Why this, not the alternative
Frontend React + TypeScript (Vite) PWA,
Tailwind, Workbox service worker,
Dexie (IndexedDB)
Static bundle caches cleanly
offline; small pages; easy Urdu RTL;
one codebase for all roles. Keep
Next.js only if already built
Amaanat: Hackathon Solution & Flow Blueprint
Page 11 of 34

<!-- Page 12 -->
Concern Choice Why this, not the alternative
API Python FastAPI + Pydantic v2 Same language as OpenCV, scikit-
learn, Tesseract and Whisper;
OpenAPI / Swagger generated
from the schemas
Database Postgres (Supabase or plain) +
Alembic migrations + pgvector +
row-level security
One store for relational data,
vectors and tenant isolation;
migrations are a stated
requirement
Queue Postgres jobs table, workers use
SKIP LOCKED
No Redis to host or break; handles
OCR, notifications, webhooks,
evaluation runs
Auth JWT access (15 min) + rotating
refresh, argon2 hashes, hashed
scoped API keys
Meets "secure login" and "public
API with keys"
Rules JSONLogic expressions stored as
versioned JSON
Proven library, no eval, pure
function: the Digital Twin falls out
for free
Document
reading
Vision-capable LLM (Claude or
Gemini) behind one adapter,
JSON-schema output,
temperature 0; Tesseract (urd +
eng) as offline fallback
LLMs read mixed Urdu/English
cards far better than OCR alone;
the fallback keeps the demo alive
Forensics & QR OpenCV (blur, glare, error-level
analysis, copy-move), pyzbar for
QR
Deterministic, explainable, fast; a
vision model only ever raises
suspicion
Voice Speech-to-text: faster-whisper
(small, Urdu) or Google Speech,
constrained to intents; speech
out: pre-recorded Urdu clips +
digit clips
Urdu TTS quality and browser
support vary; recorded clips work
offline on every phone
Classifiers scikit-learn: char n-gram TF-IDF +
logistic regression (scams),
Isolation Forest (anomalies),
isotonic calibration
Small, fast, explainable, trainable in
minutes on synthetic data
Matching rapidfuzz (Jaro-Winkler, token-
set), custom Roman-Urdu
phonetic key, variant dictionary
Handles Muhammad / Mohammad /
Muhammed / Mohd. without false
merges
Amaanat: Hackathon Solution & Flow Blueprint
Page 12 of 34

<!-- Page 13 -->
7. AI layer
Amaanat ships eight AI features in depth and three in support, and every one of them
feeds the same decision pipeline. That integration is what the 8-point "AI Workflow
Integration" criterion rewards; isolated AI demos do not earn it.
7.1 Features
Concern Choice Why this, not the alternative
RAG pgvector + Postgres full-text
(hybrid), multilingual embeddings,
10–12 mock policy documents
No extra vector database; citations
are mandatory
Agent LangGraph state machine with a
tool allowlist per state
Explicit, testable steps; no free-
roaming agent near money
Observability Structured JSON logs with
request ids, /health and /ready,
Langfuse (or a model_calls table)
for every AI call
Required monitoring; every AI call
is costed and timed
Deploy Web on Vercel or Netlify; API,
worker, mocks, Postgres on
Render / Railway / Fly; docker-
compose fallback on a laptop
Live link plus a demo that survives
venue Wi-Fi
# AI feature (brief) What it does in
Amaanat
Tool Guardrail and
fallback
How quality is
shown
1 Classification &
routing (Jev-
style)
Scores every
message, claim
and request;
returns label,
calibrated
confidence and
route (auto / ask /
human) through
one typed
Decision contract
scikit-learn +
rules + LLM
voter; Jev if
available
Unsure band
always routes to a
human
Confusion matrix,
reliability curve
2 Computer vision Reads CNIC and
claim form;
checks blur, glare,
QR signature,
edits and pasted
regions
Vision LLM,
Tesseract,
OpenCV, pyzbar
Model's own
confidence
ignored; poor
image → retake
Field accuracy,
forgery recall,
false-alarm rate
Amaanat: Hackathon Solution & Flow Blueprint
Page 13 of 34

<!-- Page 14 -->
# AI feature (brief) What it does in
Amaanat
Tool Guardrail and
fallback
How quality is
shown
3 Voice Urdu speech-to-
text for answers,
names and digits;
Urdu audio for
every prompt and
reason
faster-whisper /
Google Speech;
recorded clips
Low STT
confidence →
read-back with ✔
/ ✖  icons
Word error rate on
a recorded test set
4 Structured
outputs
Every extraction,
intake form and
decision is a
validated schema
Pydantic, JSON
schema
Invalid → one
retry → HUMAN
Schema-failure
count
5 Guardrails +
human approval
Blocks unsafe
output, redacts
PII before LLM
calls, treats
document text as
untrusted, gates
payment behind a
decision token
Custom
validators (or
Guardrails AI)
Any guardrail trip
→ HUMAN,
logged
Guardrail trips per
100 cases
6 Explainability Plain Urdu reason
with an actionable
next step; full
auditor trace
Reason-code
templates + rule
trace; optional
LLM paraphrase
checked for new
facts
Paraphrase adds
a fact → template
used
Trace
completeness
check in tests
7 Anomaly
detection
Repeat claims,
one account for
many CNICs,
bursts from one
device, odd hours
Isolation Forest +
rules
Escalates only;
helper devices
exempt from the
"one device" rule
Precision on
seeded fraud rings
8 Autonomous
agent + tool
calling
Runs the claim
step by step: calls
mock identity,
eligibility,
account-title,
payment,
notification and
complaint APIs
LangGraph state
machine
Tool allowlist per
state, step and
time budget,
payment needs a
signed decision
token
Step success and
timeout rates
9 RAG Answers "what
documents do I
need?" and "why
was I asked for
more?" from mock
policy documents,
with sources
pgvector + full-
text hybrid
Low retrieval
score → "I am not
sure" + human;
never decides
eligibility
Answer-with-
citation rate on a
question set
Amaanat: Hackathon Solution & Flow Blueprint
Page 14 of 34

<!-- Page 15 -->
7.2 Rules for every model call
One adapter for all LLM, STT and vision calls: timeout, one retry, fallback, cost and
latency logged with model name and prompt version.
PII is minimised before any external call: CNIC digits are tokenised, only the crop
needed is sent.
Text found inside images or messages is data, never instructions; prompt-injection
strings are a seeded test case.
Temperature 0 and a fixed JSON schema wherever output is consumed by code.
8. The decision engine (Challenges 01 and 02)
Amaanat auto-approves only when two things hold: the expected cost of approving is
lower than the cost of a human review, and the measured wrong-approval rate at that
threshold is provably below 1%. Everything else is asked or handed over, never guessed.
# AI feature (brief) What it does in
Amaanat
Tool Guardrail and
fallback
How quality is
shown
10 Memory &
context
Resumes a claim
across sessions
and devices;
remembers what
was already asked
Case events in
Postgres
Cleared on helper
switch; per-
citizen isolation
—
11 Evaluation
dashboard
Accuracy, false
alarms, latency,
cost, failures,
fairness slice
Custom page
over eval and
model-call tables
Shows sample
sizes and
confidence
intervals
Itself
Amaanat: Hackathon Solution & Flow Blueprint
Page 15 of 34

<!-- Page 16 -->
Evidence is scored, calibrated, then tested twice: once for safe automatic approval, once
for whether one more item is worth asking for. Everything else, including every error, goes
to a person.
8.1 Cost model (editable, stored in the rule set)
One cost unit = PKR 250, so the PKR 25,000 grant is 100 units.
decision routing · 2 questions, 3 exits, fail-closed
Outcome Cost
(units)
Reasoning
Wrong approval: money to an
ineligible person or a wrong account
100 The full grant is lost; recovery is rare;
the rightful household may be
crowded out
Human review of a case that was
actually fine
4 About 10 officer minutes plus roughly
two days of waiting for the citizen
Amaanat: Hackathon Solution & Flow Blueprint
Page 16 of 34

<!-- Page 17 -->
8.2 Deriving the threshold
Let p be the calibrated probability that approving this case is correct. Approving costs (1
− p) × 100 in expectation; sending it to a human costs 4. Approving is cheaper only when:
(1 - p) \cdot 100 < 4 \;\Rightarrow\; p > 0.96
So the break-even threshold is τ  = 0.96. Two refinements turn this into a defensible rule:
1. Risk bound. A point estimate is not enough on synthetic data. On the held-out
calibration split, τ  is raised until the 95% upper confidence bound (Clopper–Pearson)
on the wrong-approval rate among cases with p ≥ τ  is at most 1%. With zero errors
this needs at least 300 auto-approved calibration cases (rule of three), which sets the
evaluation size in section 11.
2. Cost sweep. The harness reports expected cost per case at τ  = 0.90, 0.93, 0.96, 0.98,
0.99 using the formula below, and the dashboard plots it. The chosen τ  is the cheapest
value that also satisfies the risk bound.
E[\text{cost per case}] = 100 \cdot W(\tau) + 4 \cdot H(\tau) + 1 \cdot 
A(\tau)
W = wrong approvals per case, H = human-review rate, A = ask rounds per case, all
measured on the test split. The line to say to judges: "We accept fewer automatic
approvals because each extra point of automation costs more in wrong payments than it
saves in officer time, and here is the curve."
8.3 Where p comes from
No model's self-reported confidence is used. Four independent component scores are
combined so the weakest evidence caps the decision, then calibrated:
c = \min(c_{identity},\, c_{document},\, c_{rules},\, c_{account}) \times (1 
- r_{fraud})
c_identity: match strength from the identity resolver (section 9.1).
Outcome Cost
(units)
Reasoning
One "ask more" round 1 One more photo or answer; some low-
literacy users drop off
Wrongly tagging a genuine person as
fraud
20 Weeks of delay, stigma, lost trust; this
is why the AI never rejects
Amaanat: Hackathon Solution & Flow Blueprint
Page 17 of 34

<!-- Page 18 -->
c_document: agreement between vision LLM, OCR, QR payload and registry, times
the authenticity score.
c_rules: 1 if every rule passed, 0 if any rule returned "unknown".
c_account: 1 if the account-title lookup matches the verified name exactly, lower for
partial matches, 0 for a mismatch.
r_fraud: anomaly and duplicate risk.
The raw score c is mapped to p by isotonic regression fitted on the calibration split. A
reliability chart on the dashboard shows that "0.96" really means about 96% correct.
8.4 The three routes
Never auto-reject. When a rule clearly fails, the system writes a recommendation ("not
eligible under rule R-07, version 3") and an officer confirms it. Every screen has an "ask a
person" button.
8.5 Next-Best-Evidence: when to ASK
ASK is not a confidence band; it is a purchase. For each candidate piece of evidence e
(retake photo, back of CNIC, father's name by voice, a utility bill), the evaluation data
gives q_e, the share of similar cases where that evidence resolved the gap. The system
asks for the single e with the highest net value, and only if it is positive:
\text{VOI}(e) = q_e \cdot (4 - \text{cost after}) - 1 > 0
In plain terms, asking is worth it when the evidence will often turn a human review (cost
4) into a clean decision, and the user is asked for exactly one thing, in one sentence, by
voice.
Route When What the user hears
AUTO (approve
onto hold)
p ≥ τ  and every hard guard
passes
"Your payment is approved. It will
reach your account ending 4321
tomorrow."
ASK (one item) p < τ , a specific fixable gap exists,
its value of information exceeds
its cost (8.5), and fewer than 2
ask rounds so far
"Your card photo is blurry. Please
take it again in good light."
HUMAN (with
packet)
Everything else: low p, any failed
guard, any conflict, any service
down after retries, any exception,
2 ask rounds used
"A person will check your case
within 2 days. You do not need to
do anything."
Amaanat: Hackathon Solution & Flow Blueprint
Page 18 of 34

<!-- Page 19 -->
8.6 Hard guards (all must pass for AUTO)
Amount at or below the tenant's auto-approval cap.
Identity match is Exact (section 9.1); no duplicate or anomaly flag.
Every required field present and confirmed by read-back; no rule returned "unknown".
Document authenticity above the forgery limit; QR payload agrees with printed fields.
Account title matches the verified claimant; the account is not newly changed for this
CNIC.
The active rule set is published, and every mock service answered healthily.
8.7 Safety nets after AUTO
Release hold: 24 hours in the story, 60 seconds in the demo; an officer can reverse
with one click.
Random audit sample: 5% of AUTO cases also go to an officer, which measures real-
world error and catches drift.
Idempotency keys on every payment call: a retry can never pay twice.
8.8 "I am not sure": the hand-off packet
Every HUMAN case arrives with: a three-line plain summary and the reason for escalation;
extracted fields with per-field confidence and which checks failed or were unknown;
image thumbnails with suspect regions boxed; what the citizen was already asked and
answered; the system's suggested action, labelled as a suggestion; and a priority score.
Officer queue order: priority = amount × (1 − p) × vulnerability weight × age factor, so the
highest-stakes, least-certain, longest-waiting cases of the most vulnerable people come
first. Vulnerability flags are set from the channel (voice-only, helper-assisted, low
connectivity), never from protected attributes.
9. Designs for Challenges 03 to 08
Each challenge has one mechanism, one failure behaviour and one live demo moment.
9.1 Bad data and identity (Challenge 03)
A false match is worse than a missed match, so matching is asymmetric: high thresholds,
ties go to a human, and nothing is ever merged automatically.
Tolerant schemas. Every field carries a state: missing, low-confidence, conflicting or
confirmed. A completeness score drives one targeted question ("Please say your
father's name"). Missing data never crashes the flow and is never imputed.
Amaanat: Hackathon Solution & Flow Blueprint
Page 19 of 34

<!-- Page 20 -->
Name normalisation pipeline: Unicode normalisation → strip honorifics (Syed, Mst.,
Bibi, Haji) → Urdu-script to Roman transliteration → variant dictionary (Muhammad /
Mohammad / Muhammed / Mohd / Md / M.) → Roman-Urdu phonetic key → Jaro-
Winkler and token-set similarity.
CNIC is validated, not trusted: 13-digit format, check against QR payload, check
against mock NADRA; transposed digits are a seeded test case.
Duplicates: blocking keys (CNIC hash, phone, account, canonical name + father + date of
birth) produce candidate pairs; scored pairs above a limit raise a "possible duplicate" for
an officer with a side-by-side view.
9.2 Rules that change, and the Digital Twin (Challenge 04 + bonus)
A rule set is data: eligibility expressions, required documents, thresholds, cost
weights, auto cap and reason texts, stored with version, status (draft / published /
retired), author, effective time and content hash. Published versions are immutable.
Instant effect: the decision service reads the tenant's active version on every
decision (a tiny cache keyed by version number). Publishing version 4 changes the
very next decision with no redeploy.
Required documents drive the flow: the next ASK is generated from the active rule
set's document list, so a newly required proof appears in the citizen's flow the
moment it is published.
Old decisions stay honest: each decision stores rule version id and hash; the auditor
can "replay under original version" and get the same outcome.
Rule editor: form-based (fact, operator, value), plain-language preview ("Household
income must be below PKR 40,000"), schema validation and built-in test cases before
publishing; optional second-admin approval.
Match
outcome
Condition Action
Exact CNIC matches, name similarity ≥ 0.92,
father's name and date of birth consistent
Eligible for AUTO
Probable CNIC matches; name 0.75–0.92, or one
secondary field missing
Read-back + ASK for one
more proof
Conflict CNIC belongs to someone else, or same
name with a different CNIC
HUMAN with side-by-side
view
No record Nothing in the mock registry ASK once, then HUMAN
Amaanat: Hackathon Solution & Flow Blueprint
Page 20 of 34

<!-- Page 21 -->
Digital Twin. Every decision stores a normalised input snapshot. The admin edits a draft
and presses "Test on past cases"; the same pure engine replays the last N cases under the
draft. The report shows how many outcomes move and in which direction (newly AUTO,
newly HUMAN, newly ineligible), the change in expected cost per case, and lists every
case newly moved into AUTO as a risk to review. Publishing is disabled until the report has
been opened.
9.3 Explain and audit (Challenge 05)
Audit log: append-only; the application's database role can insert but not update or
delete. Each entry stores the previous entry's hash, and the auditor's "Verify chain"
button recomputes it.
AI call log: every LLM, STT, OCR and classifier call with model, version, input hash,
output, latency and cost.
9.4 Consent and take-back (Challenge 06)
Consent ledger: subject, grantee (helper, department, API client), scope (identity,
contact, documents, payment, status), purpose, expiry, receipt id. Append-only.
One gate: every read of personal data goes through one data-access function that
checks active consent from the database at that moment, returns only allowed fields,
masks CNIC by default and logs denials. Row-level security repeats the check in
Postgres as defence in depth.
"My Data" screen (icons + audio): who has my data, what exactly, since when; toggle
each scope; withdraw one or all; request a correction (opens an officer case);
download my data.
Citizen view Auditor view
Form One or two short Urdu sentences, an
icon, audio
Full structured trace
Content What happened, why, and what would
change it: "A person will check your
case because the name on your card
and the record are slightly different.
Nothing else is needed from you."
Input hash and field values with
confidence; rule version and hash;
model and prompt versions;
component scores; calibrated p; τ  and
cost weights; route; timings; who
acted (user, AI, agent, system, API key,
"acting as")
Source Reason-code templates in the rule set,
so new rules explain themselves
The decision record and its trace
Amaanat: Hackathon Solution & Flow Blueprint
Page 21 of 34

<!-- Page 22 -->
Withdrawal truly stops access: status flips and a consent epoch increments in one
transaction; helper tokens for that citizen become invalid; queued webhooks and jobs
carrying the data are cancelled; derived personal data is purged or anonymised where
policy allows; the next read returns 403 CONSENT_WITHDRAWN and is logged.
Stated limit: the department keeps a minimal decision record for legal accountability
after documents are purged. A withdrawal made offline stops local sharing at once
but takes effect on the server only at sync, and the screen says so.
9.5 Works for everyone (Challenge 07)
Low literacy, voice first
Seven screens, one question each, a big icon answer, a five-dot progress path, ✔  and
✖  for every confirmation.
Every prompt auto-plays in Urdu from about 60 pre-recorded clips cached by the
service worker; a replay button on every screen.
Numbers are read back digit by digit by chaining recorded digit clips; voice input is
constrained to intents (yes / no, digits, a name) with a large keypad fallback.
Photograph the form instead of filling it; on-screen camera frame with live blur and
glare warnings.
Urdu (RTL) and English from dictionary files; Sindhi or Pashto is a new dictionary plus
clips, no code.
Weak or no signal
App shell under 150 KB of JavaScript; citizen pages under 60 KB; "lite mode" with no
images below a measured bandwidth.
Images compressed on the phone (grayscale, ~1200 px, < 200 KB) and uploaded in
resumable chunks.
Every action is an event with a client-generated UUID in an IndexedDB outbox; the
server de-duplicates by that id, so sync never loses or duplicates.
Progress saved at every step on device and server; resume on any device.
Status by simulated SMS as the fallback channel, so a citizen without data still learns
the outcome.
Helper Mode (bonus: one phone, 40 families)
Family list as large picture cards with status badges.
First use per family requires that person's consent by voice phrase or 4-digit PIN, with
a spoken receipt.
Switching issues a short-lived token scoped to that one citizen; a coloured "acting for"
banner is always visible; every action logs "acting as".
Amaanat: Hackathon Solution & Flow Blueprint
Page 22 of 34

<!-- Page 23 -->
On switch, the previous family's on-screen and local data is wiped; each family's
offline data is encrypted with its own key; idle timeout returns to the helper home.
9.6 Scams and fake documents (Challenge 08)
Scam Shield, three voters plus a trust anchor
1. Rules: non-government domain, URL shortener, urgency words, requests for PIN, OTP,
CNIC or a "processing fee", unregistered sender.
2. Classifier: char n-gram TF-IDF + logistic regression on a self-written English, Urdu
and Roman-Urdu set.
3. LLM voter: structured output with a one-line reason.
4. Trust anchor: every genuine Amaanat message carries a short signed verification
code (HMAC). The user enters or scans it; a valid code proves the message is real
regardless of wording. A "relief" message without a valid code is suspicious by
construction.
Outcomes: Likely scam (warn, explain in voice, show the red flags), Unsure ("do not act;
ask your helper or the official line") or Verified (code checked). The system warns; it
never blocks, because blocking a real person is a cost. Stored message text is redacted,
and classified messages feed an optional Scam Map.
Document forensics
Quality gate: blur (variance of Laplacian), glare, crop; failing means a retake, not a
guess.
QR on the mock CNIC carries a signed payload; printed fields must match it. This is
the strongest forgery signal.
Edit checks: error-level analysis, copy-move detection, font and box consistency of
OCR lines, metadata and re-save traces. A vision model's opinion of tampering may
only raise suspicion, never clear a document.
Output: authenticity score, reasons and highlighted regions; low score → HUMAN
with the boxes drawn.
Honest false alarms. The evaluation page shows precision, recall, false-positive rate and
the confusion matrix on a held-out set that includes hard genuine messages, plus three
real false-positive examples with their reasons. Known weakness, stated on screen: edit
detection is weaker on heavily re-compressed WhatsApp images.
Amaanat: Hackathon Solution & Flow Blueprint
Page 23 of 34

<!-- Page 24 -->
10. Platform: data, API, security, reliability
All seven core platform features from the brief are built, plus six optional ones: multi-
tenant workspaces, admin rule editor, notifications, webhooks, officer review queue with
priority and confidence sorting, and low-bandwidth / offline mode. Rate limiting and
background jobs come along because the design needs them.
10.1 Data model (entities, not code)
Entity Holds Notes
Tenant, User Department workspace; login,
role, language
Citizens are "person" records
so a helper can serve many
Person Beneficiary: CNIC (encrypted +
hash), name, canonical name,
phonetic key, father's name,
date of birth, field states
Indexed by CNIC hash and
phonetic key
Helper grant Helper ↔  person, consent
receipt, scope
Revocable
Case, Case event Status, route, priority,
confidence, current step;
append-only events with client
UUID
Events power timeline, audit
and offline sync
Document, Document
analysis
Image hash and path; extracted
fields, per-field confidence,
blur, authenticity, QR result
Images purged on withdrawal
Decision Route, outcome, p, rule version
and hash, model versions,
thresholds and cost weights
applied, citizen explanation,
auditor trace, input snapshot
Immutable; the input snapshot
feeds the Digital Twin
Rule set, Rule version Definition, required
documents, thresholds, cost
weights, reason texts, status,
author, hash
Immutable after publish
Consent, Consent
event
Grants and withdrawals with
scope, purpose, expiry, epoch,
receipt
Append-only
Amaanat: Hackathon Solution & Flow Blueprint
Page 24 of 34

<!-- Page 25 -->
10.2 Public REST API (/api/v1, Swagger at /docs)
Entity Holds Notes
Duplicate candidate,
Anomaly flag
Pairs and scores; risk flags Resolved only by officers
Audit log Actor type, action, entity,
acting-as, request id, previous
hash, hash
Insert-only role
Scam message Redacted text, label,
confidence, route, area, time
Feeds Scam Map
Policy document, chunk Mock policy text and
embeddings
For RAG citations
Job, Notification,
Webhook delivery
Queue rows and delivery
attempts
Retries with backoff
Model call, Eval run,
Eval result
Every AI call; every evaluation
run and its metrics
Feeds the dashboard
Mock tables Synthetic registry, accounts,
payments, message log
Owned by mock services only
Area Main operations
Auth Login, refresh, logout, me
Cases Create, list, get, submit, assign, escalate, close,
timeline, save step
Documents Upload (chunked), get analysis
Decisions Evaluate a case; citizen explanation; auditor trace;
replay under original version
Review queue List sorted by priority and confidence; officer
decision (approve, reject, request info, reverse
hold)
Scam Shield Scan a message, verify a code, give feedback, scam
map
Consent List, grant, withdraw, access log, request
correction
Rules List versions, create draft, run Digital Twin, publish
Amaanat: Hackathon Solution & Flow Blueprint
Page 25 of 34

<!-- Page 26 -->
Public API-key scopes: scan a message, read minimal case status, ask the policy assistant.
Errors use one envelope (code, message, request id); every key and IP is rate-limited with
429 and Retry-After; webhooks (case.decided, case.escalated) are HMAC-signed.
10.3 Security checklist (judges will test these)
RBAC enforced in server-side dependencies on every route, with an automated role ×
endpoint test matrix.
Tenant isolation by tenant id on every row plus Postgres row-level security.
Short-lived JWT, rotating refresh tokens, argon2, hashed API keys, secrets only in
environment variables, login lockout.
Upload validation by magic bytes and size; files hashed; no executable content.
CNIC masked by default everywhere; unmasked only through the consent gate when
necessary.
Prompt-injection defence: text from documents and messages is data; PII minimised
before any external model call.
10.4 Reliability and chaos
Each mock service has admin-controlled failure injection: added latency, 500 errors,
timeouts and stale data. Callers use timeouts, retries with backoff and a circuit breaker.
When the identity service is down the case moves to WAITING_FOR_SERVICE and the
citizen hears "We cannot check your card right now; we will continue automatically." Fail
closed: any exception means HUMAN, never AUTO.
Area Main operations
RAG, Voice Ask with sources; speech-to-text with intent and
confidence; prompt manifest
Sync Push a batch of idempotent events; pull changes
since a cursor
Admin Users, API keys, webhooks, mock-service chaos
switches
Audit, Eval Search log, verify chain; metrics, sweep, fairness
slice
Ops Health, readiness
Amaanat: Hackathon Solution & Flow Blueprint
Page 26 of 34

<!-- Page 27 -->
10.5 Real versus simulated (README and a slide)
11. Evaluation and proof
Every number judges see comes from one seeded, re-runnable harness over about 1,560
generated claim cases and 800 messages, split into train (40%), calibration (30%) and
test (30%). Build it first on Saturday, because thresholds, calibration and the dashboard
all depend on it.
11.1 Test sets
Component Real in the prototype Simulated
Identity (NADRA-
style)
API contract, matching logic, QR
signature check
Registry of synthetic people with
Pakistani name variants
Payments (Raast-
style)
Authorise, hold, release, reverse,
account-title lookup,
idempotency
No money moves; ledger is a table
Data exchange Request / response contracts
gated by consent
Other departments' data is
synthetic
SMS / WhatsApp Pipeline, templates, retries,
signed codes
Messages logged, not sent
AI models OCR, STT, classifiers, forensics,
rule engine, policy, anomaly
detection, RAG
Training and test data are
synthetic; real-world accuracy will
differ
Documents Forensics and verification code Mock CNICs generated with a
fake signing key
Set Cases What it proves
Clean eligible 600 Auto rate and wrong approvals on
the easy path
Clean ineligible 200 Rule failures become officer
recommendations, not rejections
Name variants and
transliterations
150 Matching without wrong merges
Missing fields 100 Targeted questions, no crashes, no
imputation
Amaanat: Hackathon Solution & Flow Blueprint
Page 27 of 34

<!-- Page 28 -->
The generator is re-run with new seeds until the calibration split holds at least 300 auto-
approved cases, the minimum for the 1% risk bound in section 8.2.
11.2 Dashboard metrics
Primary: wrong-approval rate among AUTO with its 95% upper bound; expected cost
per case.
Route mix (AUTO / ASK / HUMAN), ask rounds per case, and the τ  sweep curve.
Reliability chart (predicted p vs observed accuracy) and expected calibration error.
Scam Shield and forgery: precision, recall, false-positive rate, confusion matrices,
three worst false positives.
Fairness slice: human-review rate and false-alarm rate by channel (self / helper /
voice-only) and by name-variant group; a gap larger than 5 points is shown in red.
Operations: p50 and p95 latency per step, AI cost per case, failures by type, guardrail
trips.
Set Cases What it proves
Duplicates and fraud rings 100 Duplicate and anomaly escalation
Forged or edited CNICs 120 Forgery recall and highlighted
evidence
Blurry, glare, cropped
photos
80 Retake requests, no silent reads
Wrong destination
account
80 Account-title check stops the payout
Rule-change replays 60 Version correctness and Digital Twin
diff
Service failures 50 WAITING_FOR_SERVICE, no guesses
Prompt-injection text in
documents
20 Guardrails hold
Scam and genuine
messages
800 (400 + 400, incl.
100 hard genuine)
Precision, recall, false-positive rate
Recorded Urdu
utterances by the team
50 Speech-to-text accuracy for digits
and yes / no
Amaanat: Hackathon Solution & Flow Blueprint
Page 28 of 34

<!-- Page 29 -->
11.3 Automated tests (CI on every push)
Pure functions with many cases: rule engine, decision policy (including "AI never
rejects" and "exception means HUMAN"), name matcher, calibration mapping.
Consent gate: read after withdrawal returns 403 and writes an audit entry.
RBAC matrix: every role against every endpoint.
Audit chain: tampering with one row fails verification.
Payments: replaying the same idempotency key pays once.
Offline sync: the same event pushed twice is stored once.
A scripted browser run of the demo path before every deploy.
11.4 Honest limits (say them out loud)
Labels come from our own generator, so calibration is partly circular and real accuracy will
be lower. Urdu speech coverage is limited to a few speakers and Karachi accents. Forgery
checks are tuned to our mock CNIC design. Training sets are small. Every threshold is
admin-editable precisely because these numbers would need re-measuring on real data.
12. Build plan, demo and defence
About 30 hours remain (Sat 21 Nov, 12:00 PM to Sun 22 Nov, 6:00 PM PKT). The plan is a
vertical slice first, depth second, proof third, and a hard feature freeze at Sunday noon.
Keep anything that already works; adopt this design where it is additive.
Amaanat: Hackathon Solution & Flow Blueprint
Page 29 of 34

<!-- Page 30 -->
12.1 Team
With three people, D's work splits between A and C.
12.2 Remaining-time plan
Person Owns Deliverables
A: Platform Backend core, database,
security
Migrations, auth, RBAC, cases and
events, consent gate, audit chain, public
API, deploy
B: AI Pipeline and evaluation Document reader and forensics, identity
resolver, Scam Shield, decision policy and
calibration, RAG, voice, eval harness
C: Experience Citizen and helper app Seven-screen voice flow, Urdu clips,
offline outbox, Helper Mode, explanation
screens
D: Integration &
QA
Mocks, consoles, demo Mock services with chaos switches,
officer queue, rule editor + Digital Twin,
auditor view, tests, README, video
Phase When (PKT) Goal Exit criterion
1. Lock Sat 12:00–
13:30
Freeze schemas and the decision
contract; confirm model quota
and latency; start data
generators
One written list: done /
partial / not started
2. Slice Sat 13:30–
19:00
One ugly claim travels login →
upload → extract → match →
rules → policy → officer →
payment hold, deployed
Runs on the live URL
3.
Depth
Sat 19:00–Sun
02:00
Hand-off packet and queue, rule
editor + Twin, consent take-
back, Helper Mode, offline
outbox, Scam Shield, Swagger +
API keys
Every Must item works in
the UI
4.
Prove
Sun 02:00–
09:00
Run eval, fit calibration, pick τ
from the sweep, chaos tests, CI
green; sleep in shifts
Real numbers on the
dashboard
Amaanat: Hackathon Solution & Flow Blueprint
Page 30 of 34

<!-- Page 31 -->
12.3 Cut list
Must: five roles with server-side RBAC; case flow end to end; decision policy with
three routes and hand-off packet; account-title check; versioned rules with instant
effect; consent with real withdrawal; audit chain; name matching; document reading +
QR check; Scam Shield with signed codes; two explanation views; Urdu voice prompts
and read-back; offline outbox; eval numbers; Swagger + API keys; live URL.
Should: Digital Twin, Helper Mode, RAG with sources, anomaly detection, webhooks,
analytics per tenant, fairness slice.
Could: Scam Map, WhatsApp simulation, second regional language, second-admin
publishing approval.
12.4 Eight-minute live demo
Run from a Judge Console: a phone-sized citizen view on the left, live back-office panels
on the right. Role switches swap real tokens, so a 403 is a real 403.
Phase When (PKT) Goal Exit criterion
5.
Freeze
Sun 09:00–
12:00
Bug fixes only; test docker-
compose fallback; record Urdu
clips if still missing
Demo script runs twice
without error
6. Ship Sun 12:00–
17:00
README, demo video (public
Drive link), optional 5 slides,
rehearsal; submit by 17:00
Everything submitted with
an hour to spare
# Do Judges see Proves
1 State the sentence, the
prototype label, the real-vs-
simulated table
Scope and honesty Rules, judgment
2 Akram pastes a fake relief SMS,
a genuine one with its code,
and an odd one
Scam with red flags; Verified;
Unsure → person
Ch. 08, Ch. 02
3 Shazia switches to Zainab;
consent by voice; network
throttled, then offline, then
back
Urdu prompts, saved
progress, clean sync, no
duplicates
Ch. 07, Helper
Mode
Amaanat: Hackathon Solution & Flow Blueprint
Page 31 of 34

<!-- Page 32 -->
12.5 Submission checklist
Live URL pre-warmed; docker-compose fallback tested on the demo laptop with
seeded data.
GitHub repository whose history shows work inside the build window.
README: the sentence, architecture, how to run, seeded logins per role, real vs
simulated, evaluation results, limitations, link to /docs.
Demo video on a public Google Drive link; optional slides (five at most).
Prototype label on every screen; no real personal data anywhere, including
screenshots and logs.
# Do Judges see Proves
4 Zainab's card reads
"Muhammed", registry says
"Mohd."
Read-back by voice, Probable
→ one ASK
Ch. 03
5 A clean case; then the same
claimant with a scammer's
account
AUTO onto a 60-second hold;
account-title mismatch →
HUMAN
Ch. 01, new
mechanism
6 An edited CNIC HUMAN with the tampered
region boxed and the hand-off
packet
Ch. 02, Ch. 08
7 Show the cost table and τ
sweep
The numbers behind τ Ch. 01
8 Admin adds a required
document; Twin preview;
publish; new case; open an old
decision
New rule live at once; old
decision shows its old version
Ch. 04, Digital
Twin
9 Zainab withdraws Shazia's
consent; Shazia retries
403; audit shows grant, read,
withdrawal, denial
Ch. 06
10 Auditor opens a trace and
verifies the chain
Full trace; chain verified Ch. 05
11 Admin kills mock-NADRA; run a
case
"Cannot verify right now";
case waits
Reliability
12 Close: limits and what comes
next
Mature judgment Judging notes
Amaanat: Hackathon Solution & Flow Blueprint
Page 32 of 34

<!-- Page 33 -->
12.6 Judge questions, ready answers
12.7 Requirement traceability
Question Answer
Why not let the LLM decide? Its confidence is uncalibrated and its reasoning
is not reproducible. Rules are versioned and
replayable; the LLM only reads documents and
votes.
How did you pick τ ? Break-even from the cost table gives 0.96; we
keep the cheapest τ  whose 95% upper bound
on wrong approvals stays under 1%; the sweep
is on the dashboard.
Why ask instead of escalate? Only when one specific piece of evidence has
positive value of information; at most two
rounds.
What if a rule changes mid-case? The case is decided under the version active at
decision time, which the decision records; the
Twin shows the effect before publishing.
How do you know withdrawal works? One gate checks consent at read time with no
cache; a test and the demo show the 403 and its
audit entries.
Doesn't anomaly detection punish
helpers?
Shared helper devices are exempt from device-
based rules, and the fairness slice shows
escalation by channel.
Why a monolith? Clean module boundaries and real HTTP
contracts to mocks, without operating
microservices in 48 hours.
What are the limits? Synthetic data, mock services, limited Urdu
speakers, forgery checks tuned to our mock
card, small training sets.
Brief requirement Mechanism Demo step
Wrong approvals cost more Cost model, risk-bounded τ , hard
guards, release hold, account-title
check, no auto-reject
5, 7
Amaanat: Hackathon Solution & Flow Blueprint
Page 33 of 34

<!-- Page 34 -->
Brief requirement Mechanism Demo step
Weak internet PWA, small pages, compression,
resumable upload, event outbox, SMS
fallback
3
Low literacy Voice and icons, one question per
screen, digit read-back
3, 4
Rules change Versioned rule sets, instant load, Digital
Twin
8
Bad data Field states, name pipeline, asymmetric
matching, duplicate review
4
Explainable decisions Reason codes with next step; full trace;
hash-chained log
6, 10
User control Consent ledger, one gate, My Data
screen
9
"I am not sure" Three routes, hand-off packet,
WAITING_FOR_SERVICE
2, 6, 11
Scams and fake documents Scam Shield with signed codes; QR and
forensics; honest false alarms
2, 6
Core features (RBAC, dashboard,
cases, API, audit, consent, mocks)
Sections 4, 10 Throughout
3+ optional features Multi-tenant, rule editor, notifications,
webhooks, review queue, offline mode
3, 6, 8
3+ AI features Eight in depth (section 7) Throughout
Bonus Digital Twin, Helper Mode 3, 8
Amaanat: Hackathon Solution & Flow Blueprint
Page 34 of 34