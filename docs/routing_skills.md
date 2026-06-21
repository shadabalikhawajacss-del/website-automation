# Routing Skills

The assistant must not guess a report after the user asks a question. It follows
this order:

1. Normalize casual wording.
2. Apply high-confidence skills from known report columns/capabilities.
3. Let OpenAI refine only if the skill router is not high confidence.
4. Generate the selected live report(s).
5. Parse exports/page tables and calculate the answer.

## High-confidence skills

### Product stock

Examples:

- `iphone 13 how many stocks`
- `Samsung A16 on hand`
- `REVVL Tab inventory`

Route:

- Inventory Report

Columns used:

- `item`
- `itmdesc`
- `manufacturer`
- `qty`
- `cost`

### Product sales trend

Examples:

- `iphone 13 sold last 30 days`
- `fastest selling phones`
- `slow movers`

Route:

- Phone Trend By Market

Columns used:

- `item`
- `itmdesc`
- `onhand`
- `sale7`
- `sale14`
- `sale30`

### Product stock plus trend

Examples:

- `iphone 13 stock and 30 day sales`
- `which phones have high stock and low 30-day sales`

Route:

- Inventory Report
- Phone Trend By Market

### Employee sales/rankings

Examples:

- `who's number one in phone sales`
- `top 5 employees by accessories`

Route:

- Employee Ranking By Box Sales

### Home dashboard

Examples:

- `how are we doing`
- `top stores right now`

Route:

- Home dashboard

## OpenAI guardrail

If a high-confidence skill route is found, OpenAI cannot replace it with the
generic Employee Performance report. This prevents product questions from being
mistaken for employee questions.
