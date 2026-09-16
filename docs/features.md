# Feature selection

Core scope remains the accepted product brief: people, organizations, households,
relationships, interactions, context, and commitments. No drop-in features have
been accepted; the initial plan includes none.

The available catalog contains `helper-bot` (In-App Help Agent). It offers a help
panel, evidence-backed answers, scoped log reads, issue drafts requiring human
confirmation, and an evolving FAQ. It requires an application LLM chat loop,
read-only tools, and a source snapshot tied to the deployed build.

The owner explicitly chose to defer the help agent and build the useful CRM first.
Common Thread has no chat loop and must be useful without AI. Do not inject
helper-bot stages into the initial plan. If accepted later,
schedule after Stage 0 and core CRM work, with its source-snapshot, scoped log access,
feature flag, redaction, and external-action confirmation requirements included.
