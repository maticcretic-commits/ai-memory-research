"""Phase 1 Batch 1 — synthetic fixtures only.

Every record below is invented for testing. No real email, prompt, task,
or person is represented. Labels are the expected outcome for the
rule-based prototype, not a measured result on real data.
"""

CONVENTIONS_V1 = {
    "version": 1,
    "name": "prototype-conventions-v1",
    "rules": [
        {"id": "title_verb", "description": "Title starts with a capitalised verb from the allowed list."},
        {"id": "context_bullets", "description": "Body contains at least one bullet line starting with '- '."},
        {"id": "no_secrets", "description": "Body contains no secret-shaped word from the block list."},
        {"id": "title_length", "description": "Title is 80 characters or fewer."}
    ],
    "allowed_verbs": ["Build", "Review", "Draft", "Check", "Send", "Fix"],
    "secret_words": ["api_key", "password", "token"]
}

PROMPTS_SEED = [
    {"id": "syn-001", "type": "workplace", "use_case": "weekly_review",
     "output_format": "text", "app": "chatgpt",
     "text": "Summarise this week's synthetic notes into three actions.",
     "example": "Input: three synthetic notes. Output: three numbered actions."},
    {"id": "syn-002", "type": "workplace", "use_case": "email_draft",
     "output_format": "text", "app": "chatgpt",
     "text": "Draft a short reply in a plain, direct voice from these synthetic points.",
     "example": "Input: two synthetic points. Output: one short paragraph."}
]

INBOX_MESSAGES = [
    {"id": "msg-01", "subject": "Help, my synthetic order did not arrive",
     "body": "Hello support, my synthetic order SYN-100 is late. Please help.",
     "expected": "support"},
    {"id": "msg-02", "subject": "Quote for synthetic dashboard work",
     "body": "Please send a quote for building a synthetic dashboard. Budget is fictional.",
     "expected": "lead"},
    {"id": "msg-03", "subject": "Weekly synthetic newsletter",
     "body": "Unsubscribe link below. This week's synthetic news roundup.",
     "expected": "newsletter"},
    {"id": "msg-04", "subject": "Lunch on Friday?",
     "body": "Are you free for lunch on Friday? No work attached.",
     "expected": "personal"},
    {"id": "msg-05", "subject": "Refund request for synthetic item",
     "body": "I would like a refund for synthetic item SYN-200, it arrived broken.",
     "expected": "support"},
    {"id": "msg-06", "subject": "Proposal: synthetic automation pilot",
     "body": "We would like a proposal for an automation pilot. Please share pricing and timeline.",
     "expected": "lead"},
    {"id": "msg-07", "subject": "Your synthetic digest",
     "body": "Here is your daily digest. Manage preferences or unsubscribe.",
     "expected": "newsletter"},
    {"id": "msg-08", "subject": "Mixed synthetic message",
     "body": "Hello, I need help and also a quote, and here is a newsletter link.",
     "expected": "review"}
]
