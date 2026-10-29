# Mandile SEO — Five-Part AI Employee Starter

This is an independent, safe, **dry-run** adaptation of the five-part AI employee architecture described by Nick Vasilescu. It is **not a native GitHub fork or a full copy** of his Hermes/Orgo template.

## Five components

| Component | Prototype implementation | Future production integration |
| --- | --- | --- |
| Harness | `AgentHarness` validates and routes events | Hermes or another reviewed agent runtime |
| Model | `Model` protocol with deterministic `DemoModel` | Provider-neutral LLM adapter after review |
| Computer | Local Python process | Isolated and supervised worker per client |
| Memory | Tenant-scoped SQLite event/proposal ledger | Protected persistent datastore with retention policy |
| Connectors | `DryRunConnector` queues proposals | Explicitly approved CRM, email, phone, and calendar connectors |

The starter illustrates **missed-call lead recovery**. It drafts a follow-up and queues it for human approval. It **does not** text, email, book, spend, or write to an external CRM. Approval changes state to `approved_not_sent`, never to delivered.

## Try it

Requires Python 3.10+, no dependencies or API keys:

```sh
cd mandile/five-part-agent
python3 agent.py demo
python3 agent.py list
python3 agent.py approve
python3 -m unittest discover -s . -p 'test_*.py'
```

## Before a real client deployment

- Validate signed inbound events, consent, opt-out handling, business hours, rate limits, and local communications law.
- Isolate each client's secrets and data; add access control, encryption/backup, retention limits, and a deletion process.
- Implement delivery with per-recipient allowlists, human approval, retries, receipts, idempotency, and a kill switch.
- Guard against prompt injection and data exfiltration; no financial operations or autonomous messaging.
- Instrument qualification, bookings, closed jobs, operating cost, failure rate, and actual outcomes.

## Credits

Architectural inspiration: Nick Vasilescu, **harness + model + computer + memory + connectors**. Original implementation: [nickvasilescu/nicks-stack](https://github.com/nickvasilescu/nicks-stack), MIT license, © 2026 Nick Vasilescu. This starter does not incorporate Nick's source files. If any upstream code is later copied in, retain its MIT license and notices.

Related [published interview](https://pocketcasts.com/podcast/build-with-ai/123091f0-fdb4-013b-f558-0acc26574db2/how-to-make-5k-per-month-per-client-selling-managed-ai-agents/98d85840-ee49-4b2c-9fd9-8c98c9e570af).
