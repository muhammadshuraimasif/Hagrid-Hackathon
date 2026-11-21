<!-- Page 2 -->
CODER'S CUP '26
HAGRID'S HACKATHON  /  AI PROBLEM STATEMENT
ACM NUCES  •  FAST-NUCES KARACHI
01
OFFICIAL CHALLENGE BRIEF / NOVEMBER 2026
The Last Mile: AI on Public Rails
A 48-hour hackathon on digital public infrastructure (DPI)
BUILD WINDOW
Friday, 20 November 2026, 6:00 PM – Sunday, 22 November 2026, 6:00 PM PKT
DEVELOPMENT MODE
Remote • 48 hours
FINAL EVALUATION
Monday, 23 November 2026 • FAST-NUCES Karachi Library • exact time to be
announced
TEAM SIZE
3–4 participants
PROTOTYPE ONLY. Everything you build is a prototype. It is not an official service.
Note to Participants
You are free to use any AI tool and any AI model to help you code. But the judges will not score how fast you
code. They will score your judgment: how your system handles risk, mistakes, and surprises.
You are scored on how your system behaves, not on what you claim.
Use of real personal data will result in disqualification. Mock everything.
All development must take place during the hackathon. Solutions must be original; plagiarism and pre-built
projects are prohibited.
01 Background
Pakistan has developed digital public infrastructure (DPI) through systems for identity verification, digital
payments, and data exchange. Initiatives such as NADRA and Raast demonstrate how these systems form
the foundation of essential digital services.
However, the existence of digital infrastructure does not guarantee that everyone can access or use it
effectively. Many people still face barriers such as low literacy, language difficulties, complicated forms, and
unreliable internet connectivity.
Trust and safety present another challenge. Fraudulent messages, misleading information, and uncertainty
about the legitimacy of digital services can discourage people from using systems designed to help them.
These challenges highlight two critical gaps: accessibility and trust. Bridging the last mile requires making
digital public services not only available, but also understandable, accessible, and safe for the people who
need them most.


<!-- Page 3 -->
CODER'S CUP '26
HAGRID'S HACKATHON  /  AI PROBLEM STATEMENT
ACM NUCES  •  FAST-NUCES KARACHI
02
02 The Challenge
Meet three people. They all depend on the same public services.
 • The widow cannot read forms and has a weak phone signal.
 • The shopkeeper keeps getting fake "relief payment" messages.
 • The helper serves 40 families from one shared phone.
 Their records are incomplete. Their names are spelled in different ways. One wrong approval can cost
someone their savings.
Build one multi-user SaaS platform that serves all three. It must decide, explain, and protect. It must also be
able to say "I am not sure" and hand the case to a human.
This is not a chatbot. It is a working platform with users, roles, cases, rules, and audit trails.
Complete this sentence before you code
We help [specific person] do [one public task] even though [what stops them today].
Pick one task and finish it end to end. A deep solution for one task beats a thin solution for many.
03 Core Requirements
Constraints (your system must handle all of these)
 • Wrong approvals cost more than slow approvals. Show how your system handles this trade-off.
 • Weak internet. The system must work on a slow or dropping connection.
 • Low literacy. The system must be usable by someone who cannot read.
 • Rules change without notice. The system must adapt without code changes.
 • Bad data. Data will be missing, duplicated, or wrong. Do not assume clean input.
 • Explainable decisions. Every AI decision must be explainable to the user and reviewable by an auditor.
 • User control. Users must control what data is shared and be able to take it back.
 • "I am not sure." When confidence is low, the system must stop and hand over to a human.
 

<!-- Page 4 -->
CODER'S CUP '26
HAGRID'S HACKATHON  /  AI PROBLEM STATEMENT
ACM NUCES  •  FAST-NUCES KARACHI
03
User Roles (use at least 3)
Role
What they can do
Citizen
Upload documents, use voice or text, track tasks, control data sharing
Community helper
Assist many citizens, manage cases with proper permissions
Department officer
Review, approve, or reject claims and complaints
Admin
Manage users, roles, rules, and mock services
Auditor
Read-only access to logs, consent records, and AI decisions
Platform Features
Core (all required)
 • Secure login (JWT or OAuth) with role-based access control
 • Dashboard with task progress, status, and history
 • Case management (create, assign, escalate, close)
 • Public REST API with API keys and documentation (Swagger or OpenAPI)
 • Audit log of every user, AI, and agent action
 • Consent management (see, share, withdraw, correct data)
 • Mock identity, payment, and data services behind clean APIs
 
Pick at least 3
 • Multi-tenant workspaces (each department has its own space)
 • Admin rule editor (change eligibility rules without code changes)
 • Notifications (SMS, WhatsApp, email, in-app)
 • Webhooks for outside systems
 • Analytics dashboard per tenant
 • Officer review queue with priority and confidence sorting
 • Subscription plans and usage limits
 • Background jobs and queues
 • Rate limiting and error handling
 • Low-bandwidth or offline mode
 

<!-- Page 5 -->
CODER'S CUP '26
HAGRID'S HACKATHON  /  AI PROBLEM STATEMENT
ACM NUCES  •  FAST-NUCES KARACHI
04
AI Features (use at least 3)
AI feature
What it must do
Example tools
RAG
Answer from official rules, forms, and policies, with sources
shown
LangChain, LlamaIndex, Chroma,
Pinecone
Autonomous agents + tool
calling
Plan and finish a task step by step by calling mock identity,
payment, and complaint APIs
LangGraph, CrewAI, n8n, MCP
Classification and routing
(Jev)
Sort scams, complaints, and requests. Give each a confidence
score and route it
Jev, scikit-learn
Computer vision
Read IDs and forms (OCR), check QR codes, detect forged or
edited documents, handle blurry photos
Tesseract, Google Vision, OpenCV,
pyzbar
Voice
Speech-to-text and text-to-speech in Urdu or a regional
language
Whisper, Google Speech, ElevenLabs
Structured outputs
Fill forms in a fixed format and validate them
Pydantic, JSON schema
Guardrails + human approval
Block unsafe answers, flag unsure cases, require approval for
risky steps
Guardrails AI, NeMo Guardrails
Explainability
Tell users in simple words why a decision was made
Prompting, rule traces
Anomaly detection
Spot suspicious payments, repeated claims, or unusual patterns
scikit-learn, PyOD
Memory and context
Remember progress across steps and sessions
Database, vector store
Evaluation dashboard
Show accuracy, false alarms, speed, cost, and failures
LangSmith, Langfuse, custom
What is Jev? Jev is a type-safe AI decision model. It takes an input, classifies it, gives it a score, and routes it to the right
place (auto-handle, ask more, or send to a human). You may use it, or build the same idea with another tool.
Engineering Basics
 • Database with migrations (Postgres or Supabase)
• Monitoring, logs, and basic tests
04 Technical Challenges
These go beyond a normal app. Show that you understand the problem, not just that the screen
works.
CHALLENGE 01 The Cost of Being Wrong
A wrong approval is worse than a slow one. Define your own rule for when the system acts alone, when it
asks for more proof, and when it sends the case to a human. Show the numbers behind your choice.
• Deployed link

<!-- Page 6 -->
CODER'S CUP '26
HAGRID'S HACKATHON  /  AI PROBLEM STATEMENT
ACM NUCES  •  FAST-NUCES KARACHI
05
The system must know when it does not know. Low confidence must lead to a clear handoff to a human,
with the case notes attached. Silent guessing earns zero.
CHALLENGE 03 Bad Data
Missing fields, duplicate people, and names spelled in many ways (e.g., Muhammad / Mohammad /
Muhammed). Handle them without crashing and without a wrong match.
CHALLENGE 04 Rules That Change
An admin changes an eligibility rule. The system must follow the new rule at once, with no code change and
no redeploy. Old decisions must still show which rule version was used.
CHALLENGE 05 Explain and Audit
Every AI decision needs two views: a simple reason for the user, and a full trace for the auditor (input, rule or
model version, confidence, result).
CHALLENGE 06 Consent and Take-Back
A user can see who has their data, change what is shared, and withdraw it. Withdrawal must truly stop
access, and the audit log must show it.
CHALLENGE 07 Works for Everyone
A person who cannot read, on a weak connection, must still finish the task. Think voice, icons, small pages,
and saved progress.
CHALLENGE 08 Scams and Fake Documents
Catch fake "relief payment" messages and edited or forged documents. Show false alarms honestly. Blocking
a real person is also a cost.
05 Creative Features (Bonus)
These are optional. They reward teams that plan well.
 • Digital Twin: A safe copy of your system where an admin can test a rule change on past cases and see the
 effect before it goes live.
• Helper Mode: One shared phone, 40 families. Fast and safe switching between people, with separate
 consent for each.
• Offline-First Sync: Work with no signal. Sync later without losing or duplicating data.
• Scam Map: A live view of scam patterns by type, area, or time, built from classified messages.
Note: You are not expected to build all four. One bonus feature that really works is worth more than four half-finished
ones.
CHALLENGE 02 Saying "I Am Not Sure"

<!-- Page 7 -->
CODER'S CUP '26
HAGRID'S HACKATHON  /  AI PROBLEM STATEMENT
ACM NUCES  •  FAST-NUCES KARACHI
06
06 Rules
 • Build during the event.
 • Any tools and AI models are allowed.
 • Mock all identity, payment, and data services. No real personal data.
 • Label your project as a prototype, not an official service.
 • Tell the judges what is real and what is simulated.
 
07 What to Submit
 • Functional AI-powered prototype and live demo
 • Code repository (GitHub repository link)
 • A README file
 • Demonstration video (public Google Drive link)
 • Presentation slides (optional)
 
08 Judging Notes
 • Functionality over claims: Judges will evaluate the actual behavior and functionality of the system rather
 than relying solely on presentations or documentation.
• Security and reliability: Implementations must demonstrate appropriate security measures, including
 server-side enforcement of access controls and permissions.
• Live demonstration: A working live demonstration is mandatory. Screenshots and recorded videos cannot
 substitute for demonstrating the actual system.
• Responsible AI behavior: Systems should recognize uncertainty, handle unexpected situations safely, and
 demonstrate appropriate human intervention when necessary.
• Technical judgment: Teams should be prepared to explain and justify their architectural decisions,
 implementation choices, and system limitations.
 THE ORGANIZERS RESERVE THE RIGHT TO CHANGE ANY PART
OF THIS DOCUMENT AT ANY TIME, WITH OR WITHOUT PRIOR
 NOTICE.
