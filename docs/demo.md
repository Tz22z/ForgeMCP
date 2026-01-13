# Demo walkthrough

The bundled demo is deterministic, offline, and uses real file, index, dispatcher, Git,
and test components. Only the LLM is replaced by a recorded sequence of typed decisions.

## Issue

The checkout domain contains two interacting defects:

1. the Pro tier receives a 5% discount instead of its contractual 10%; and
2. free shipping is checked against the discounted amount instead of the pre-discount
   subtotal.

For a $50 Pro cart the correct result is a $5 discount, no shipping charge, and a $45
total. A second assertion checks the $40 discount independently.

## Run it

```bash
forge demo
```

The trace performs six model turns:

| Turn | Action | Runtime behavior |
| ---: | --- | --- |
| 1 | Read `shop/pricing.py` | Policy-check and bounded observation |
| 2 | Read `shop/checkout.py` | Reuse selected repository context |
| 3 | Replace the Pro rate | Invalidate and reparse pricing index entry |
| 4 | Replace the shipping basis | Invalidate checkout and dependent context |
| 5 | Run focused checkout tests | Record passing mutation generation |
| 6 | Return final summary | Accept only because current generation is verified |

The CLI prints status, call/token counters, test status, and the full Git patch.

## Interview focus

The useful discussion is not that an LLM can replace two strings. Focus on the runtime
properties around that edit:

- A final answer before turn 5 would trigger automatic verification.
- A failure would produce another planning turn with failure-local context.
- Repeating the same read past policy would exhaust the repetition budget.
- A traversal path or unknown tool would fail before handler execution.
- Changing the product code invalidates the incremental index immediately.
- The same demo can run with Docker test execution by changing `execution_mode`.

Then show `docs/evaluation.md` to explain how the mechanism is compared without swapping
models or allowing test tampering.

