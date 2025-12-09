# Pro checkout applies the wrong contract

Pro customers should receive a 10% discount. Free shipping eligibility is based
on the subtotal before discounts, but the final total should still include the
discount. The current implementation charges the wrong amount and sometimes adds
shipping when a cart has reached the $50 threshold.

Acceptance criteria:

- A $40 Pro cart receives a $4 discount.
- A $50 Pro cart has free shipping and a $45 total.
- Existing checkout tests pass without changing their assertions.

