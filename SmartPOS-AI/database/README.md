# Database

- schema/      — table definitions (products, transactions, users, stores,
  fraud_alerts, reorder_suggestions)
- migrations/  — versioned schema changes

The MVP has no real database; state lives in Streamlit's session memory
(see docs/Database Design.md — to be drafted).
