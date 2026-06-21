# RT BDI Site Coverage

## Top navigation areas

The live site top navigation has these major areas:

1. Home
2. Favorites
3. Sales Reports
4. Employee Report
5. Inventory Report

Favorites is a shortcut area that points to reports also present under Sales,
Employee, and Inventory. It is still important because users may expect those
favorite report names to work as aliases.

## Home dashboard coverage

Home was inspected live. It contains:

- Top 10 stores by PPD/accessory sale for the current period.
- Activation by market.
- Activation trend by month plus projected value.
- Accessory trend by month plus projected value.
- Period summary with store count, total activation, accessory, qpay, and conversion.
- Company snapshot for today.
- Previous-day store table with activation, accessory, qpay, invoice, MTD, and trending columns.

The command below extracts those Home tables:

```bash
rtbdi live-home
```

## Reports with validated live exports

See `docs/live_validation_summary.md` for the current validation matrix.

## Remaining work

- Convert Home snapshot data into direct `live-answer` responses for dashboard
  questions like "How are we doing today?" or "Who are the top stores right now?"
- Add more aliases from Favorites labels so casual report names route correctly.
- Finish report-specific export handlers for the remaining edge cases.
