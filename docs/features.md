# Feature selection

Core scope remains the accepted product brief: people, organizations, households,
relationships, interactions, context, and commitments. No drop-in features have
been accepted; the initial plan includes none.

The available catalog contains `helper-bot` (In-App Help Agent). It offers a help
panel, evidence-backed answers, scoped log reads, issue drafts requiring human
confirmation, and an evolving FAQ. It requires an application LLM chat loop,
read-only tools, and a source snapshot tied to the deployed build.

Offered to the owner during architecture. Deferred by architectural default because
Common Thread has no chat loop and must be useful without AI; no owner acceptance
was received. This optional selection does not block planning. Do not inject
helper-bot stages unless explicitly accepted. If accepted,
schedule after Stage 0 and core CRM work, with its source-snapshot, scoped log access,
feature flag, redaction, and external-action confirmation requirements included.
