# Money Changer Web API – Technical Assessment (Python)

## Overview
A single money changer store wants to digitalize manual recording of foreign exchange (FX) transactions. Each time a transaction is completed at the counter, the system should record it via a web API.

The system must:
- Record exchange transactions **without storing customer details**.
- Store the **exact exchange rate used at the time of transaction** (rate snapshot).
- Maintain a database of **daily exchange rates** for each supported currency pair.
- Apply commonly understood money changer business logic.
- Demonstrate **inheritance and/or polymorphism** in the domain design.

### Guidelines and Suggestions
* Candidates are encouraged to exercise critical thinking and clarify any assumptions any time during the evaluation.
* The use of AI has to be declared before the technical assessment commence.
    * AI is a powerful tool, but only you can work on complex production issues.
* Balance between 'solving the problem' and 'coding best practices'. 
    * Clean code, observability and documentation are valued greatly but...
    * It is more important to demonstrate design thinking and have a working API for the assessment.
    * Best practices can be articulated along the way.

---

## Business Context & Common Logic
### 1) Daily Rates and Transaction Rate Snapshot
- The store sets a **daily rate** for each currency pair (e.g., `USD/PHP`) and potentially direction (`BUY` vs `SELL`).
- When a transaction is recorded, the system must:
  1. Find the applicable daily rate for the **transaction date**.
  2. Apply any necessary rules (spread, rounding, fees).
  3. Store the **effective rate** used in the transaction record (snapshot), even if daily rates are changed later.

### 2) No Customer PII
- Do not store any of the following:
  - Customer name, ID/passport, phone, address, etc.
- A transaction is identified by an internal `transaction_id` and timestamp.

### 3) Typical Money Changer Concepts
- `BUY`: store buys foreign currency from customer (customer gives foreign currency; store gives base currency).
- `SELL`: store sells foreign currency to customer (customer gives base currency; store gives foreign currency).
- Rates may differ for `BUY` and `SELL` for the same currency pair.
- Rounding rules are typically applied to the amount given to the customer (e.g., round to 0.05 for cash).

---

## Requirements

### Core Features
1. **Daily Exchange Rates**
   - CRUD endpoints to manage daily rates.
   - Each rate has:
     - `rate_date` (date)
     - `base_currency` (e.g., PHP)
     - `quote_currency` (e.g., USD)
     - `side` (`BUY` or `SELL`)
     - `rate` (decimal)

2. **FX Transactions**
   - Create an exchange transaction.
   - Must store:
     - `transaction_timestamp`
     - `base_currency`, `quote_currency`
     - `side` (`BUY` or `SELL`)
     - `foreign_amount` and/or `base_amount` (see input options below)
     - `effective_rate` (snapshot)
     - any derived values (rounded amounts, fees, etc.)

3. **No Customer Storage**
   - The database schema and API payload must not include customer details.

4. **Inheritance + Polymorphism**
   - The design must include a domain model where inheritance/polymorphism **naturally applies**.
   - Example: different transaction types behave differently when computing totals, rounding, and fees.

---

## Inheritance & Polymorphism: Why it matters?

- Adding a new type (e.g., `OnlineTransaction`, `WholesaleTransaction`, `PromoTransaction`) should require minimal changes within the system and existing integration points.

---

## API Requirements and Implementation Suggestions

### 1) Daily Rates

#### Create/Upsert Daily Rate
`POST /rates`
```json
{
  "rate_date": "2026-02-02",
  "base_currency": "PHP",
  "quote_currency": "USD",
  "side": "SELL",
  "rate": "1.3550"
}
```

### 2) Transactions
#### Create Daily Rate
Rules:  

* Exactly one of foreign_amount or base_amount must be provided (unless you support both, then define precedence).

The API must:

* Look up the daily rate for the transaction date (timestamp date part).
* Apply business rules (fees/rounding if implemented).
* Store effective_rate snapshot in the transaction record.
* Return the computed amounts and effective rate.

`POST /transaction`

Payload Variant A (customer provides foreign amount, system computes base amount):
```json
{
  "timestamp": "2026-02-02T10:15:00+08:00",
  "base_currency": "PHP",
  "quote_currency": "USD",
  "side": "SELL",
  "foreign_amount": "1000.00"
}
```

Payload Variant B (customer provides base amount, system computes foreign amount):
```json
{
  "timestamp": "2026-02-02T10:15:00+08:00",
  "base_currency": "PHP",
  "quote_currency": "USD",
  "side": "BUY",
  "foreign_amount": "2000.00"
}
```

Sample Response from Payload Variant A
```json
{
  "transaction_id": "TXN-20260202-000001",
  "timestamp": "2026-02-02T10:15:00+08:00",
  "base_currency": "PHP",
  "quote_currency": "USD",
  "side": "SELL",
  "foreign_amount": "1000.00",
  "base_amount": "58894",
  "effective_rate": "0.017",
  "fee_amount": "0.00",
  "rounding_adjustment": "0.48"
}
```

---

## Validation & Error Handling

### Missing daily rate for the transaction date:

* Return 409 Conflict or 422 Unprocessable Entity with a clear message.

### Currency code validation:

* Use ISO-style 3-letter codes (e.g., USD, SGD, EUR).

### Amount validation:

* Must be positive.

* Use Decimal, not float.

### Side validation:

* Only BUY or SELL.

## Non-Functional Expectations

### Use a mainstream Python web framework:

* FastAPI preferred, Flask acceptable.

### Use a relational database:

* SQLite for simplicity is fine; Postgres is a plus.

* Use migrations (Alembic recommended).

### Provide unit tests for:

* Rate lookup

* Transaction calculation rules

### Polymorphic behavior (BUY vs SELL differences)

* Provide API docs (OpenAPI/Swagger auto-generated is fine).
* You may also propose alternate API docs methodology.