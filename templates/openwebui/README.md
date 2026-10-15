# Open WebUI

A managed [Open WebUI](https://openwebui.com) instance — a chat interface for
the platform's language models — with its own PostgreSQL database.

The app is automatically connected to the platform LLM gateway (LiteLLM):
the template requests the `llm` capability, and the platform provisions a
virtual gateway key and injects endpoint and key at deploy time. The models
granted to this app appear in the chat's model selector.

The template consists of two components: `open-webui` (the web UI, persistent
data directory for uploads) and `postgres` (database for users, chats and
settings, persistent volume).
