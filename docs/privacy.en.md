# Privacy, identity and what may be shared

[中文](privacy.md)

Repository authors are not the bot's owner identity. New deployers must locally configure their own `owners`, AstrBot administrators, platform IDs and session scopes; verify the Bilibili owner's UID separately from the bot's logged-in account. No original-device identity is bound by default.

Do not import another person's main persona, chat history, rolling summaries, vector store, databases, mailbox, Bilibili cookies, QQ login directory, recovery password file or pending review drafts. Even without API keys, memories can cause a model to adopt someone else's identity and experiences.

If the bot identifies the wrong owner, inspect the current persona, global prompt, session summaries, retrieved entries and metadata, tool-injected identity fields, shared caches and third-party plugins. A model's statement does not establish that a web page contains that fact. Preserve provenance and dates, isolate the affected entries, then correct the original entries and summaries; merely appending a denial does not remove old retrieval results.

After retrieval, validate owner-private, group-public and group-member scopes against metadata; prompt labels alone do not provide isolation. The cross-window timeline is owner-private material by default, and public comments still require independent review. Review does not replace data-access boundaries.

Keep WebUIs local; use authenticated tunnels or private networking for remote access. Do not put keys, passwords, cookies or tokens in chats, command arguments, screenshots or Git. Keep local backups outside the repository. Third-party APIs receive the relevant request content, so enable them according to your privacy requirements.

This inspection found no occurrence of the reported private owner nickname in current files or visible Git history. This does not establish anything about external copies or another bot's memories. If sensitive information is later confirmed in Git history, revoke affected credentials first and assess history cleanup; deleting it in a new commit does not mean history has been cleared.
