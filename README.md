# Money Changer Web API

# Local Development Quick Reference

1. **Prerequisites:** Install and start Docker Desktop.
2. **Clone and enter the repository:** Change to the repository's root directory, the directory containing `docker-compose.yml`.
3. **Start the application:** Run `docker compose up --build`. The API container automatically runs the database migrations, seeds the exchange rates, and starts Uvicorn. Keep this terminal open while using the application.
4. **Access the application:**
    - Swagger UI: `http://localhost:8000/`
    - API documentation: `http://localhost:8000/docs`
    - Health check: `http://localhost:8000/health`
5. You can now access the different APIs documented on the documentation.
6. **Stop the application:** Press `Ctrl+C` in the terminal running Compose.

# API Endpoints Rationale

## Health

- `GET /health` confirms that the API process is running without checking database connectivity. The purpose of this is as a generic health check for general troubleshooting, and potentially useful for health probes.
- `GET /ready` verifies that the API can connect to the database and reports `503` when it cannot. This is the same expectation for health but for dependencies of the API. If I added redis cache, that would also be something this will flag.

## Exchange Rates

- `GET /exchange-rates` lists exchange-rate snapshots for a required date with optional currency, side, and pagination filters. This is the general exchange rates lookup endpoint. You can list all of the rows to create a full table. You can list all BUY side or SELL side exchange rates for more specific views. Then you can also do specific currency exchange rates.
- `GET /exchange-rates/{rate_date}/{base_currency}/{target_currency}/{side}` retrieves one rate by its complete business key. This is potentially useful to fetch the specific exchange rate to display somewhere during the actual transaction flow in the POS system.
- `POST /exchange-rates/batch` creates the BUY and SELL rates for a daily base-currency rate set. This is a batch post endpoint. This is the only POST endpoint because in my opinion, there would be no reason to POST individual entries. So a POST considers a full daily rate set, instead of individual rows in the exchange_rates table.
- `PUT /exchange-rates/{rate_date}/{base_currency}` replaces every rate in an existing daily rate set. This is a full replace, hence the PUT. So the context is the whole daily rate set as well. This means this will override all rows in a certain date for a specific base_currency.
- `PUT /exchange-rates/{rate_date}/{base_currency}/{target_currency}/{side}` updates only the value of one rate identified by its complete business key. This is for updating a specific exchange rate (row) in the table. This may be useful for operational usage.
- `DELETE /exchange-rates/{rate_date}/{base_currency}` removes all rates in a daily rate set and reports how many records were deleted. This delete also does a full delete of a daily rate set for a base_currency. I didn't see a reason to have a specific delete for a resource since that would mean an inconsistent state that may break some of the APIs. But deleting a full daily rate set can be useful for operational usage.

## Transactions

- `GET /transactions` lists immutable transaction legs with optional logical transaction, date, currency, side, and pagination filters. This is the general transactions lookup. I only added this since I assume there will be some kind of monitoring tool or dashboard that would use the transactions.
- `POST /transactions/purchases` records a BUY transaction for one foreign currency using either a foreign amount or a base-currency amount. I divided the transactions into three different setups so that one transaction POST endpoint will not abstract 3 three different functionalities. I intended to name this as /transactions/buy but that makes this a verb and is not proper naming convention so I changed to purchases.
- `POST /transactions/sales` records a SELL transaction for one foreign currency using either a foreign amount or a base-currency amount. Same considerations above but for the opposite `side`.
- `POST /transactions/exchanges` records linked BUY and SELL legs to convert one foreign currency into another through the home currency. This one is specially for when there are two foreign currencies. It has a separate setup because from how I architected the setup, exchanges will involve a buy and sell instead of a direct trade.

# Running Unit Tests
1. py -3.14 -m venv .venv (create base virtual env)
2. .\.venv\Scripts\Activate.ps1 (activate and go inside virtual env)
3. python -m pip install -e ".[dev]" (do the installs)
4. python -m pytest -q (Run Unit Tests)
5. python -m coverage run -m pytest -q (Run Unit Tests and compile coverage report)
6. python -m coverage report -m (Read the coverage report)

# Functional Requirements
Functional Requirements

1. [DONE] Record foreign exchange transactions without storing customer PII.
    - This should be inherent with the design, a transaction will be treated as only a transaction.
    - I thought about having the user supply a transaction ID that will link the transaction to their end but that seems like it's outside the scope of this.
    - I still did add a `transaction_id` column that is used for something else, but not user generated.
2. [DONE] Generate an internal transaction ID and store the transaction timestamp.
    - Yes, this is a core consideration in the DB table design.
    - I actually have an `id` and `transaction_id` column.
    - The former is basically the unique identifier, then the latter supports the cross-sell functionality where you want to make your USD into JPY or vice-versa (i.e. your home currency is not directly involved).
3. [DONE] Maintain daily exchange rates for currency pairs.
    - Yes, there will be both a transactions table and a exchange rates table.
    - For this one, I assumed there is a ingestion pipeline that will run daily to input all entries for the day that will use my API.
    - So I added a batch version of the CRUD to accommodate for that. Something to note is that we only expect currency pairs between a home currency and the foreign currency.
    - Supporting direct trades between two non-home currencies will make us put a permutation/combination of all currencies, which is tens of thousands of rows a day.
    - In this case, I just assumed that since this is a single store (from the README), it will be in the PH and will use PHP as the base currency.
4. [DONE] Support BUY and SELL transaction sides with potentially different rates.
    - For this one, yes the application supports BUY and SELL as well as a cross-sell functionality if we want to convert two non-home currencies (i.e. USD to JPY).
    - The rates being different for BUY and SELL is something that is inherent with the initial seed of the `exchange_rates` table.
    - I put in a total of 167 currency pairs between PHP and other currencies as test data, but doubled them to 334 since I would have a separate exchange rate for BUY and SELL and wanted them to be configurable.
    - For the test data, I just put a spread of 1% (0.99 and 1.01) but the daily exchange rate pipeline could just as easily pass in different pre-configured numbers.
    - I imagine this feature will be useful since there are currencies that are rarer/more regulated than others and therefore we can have different margins for them.
5. [DONE] Provide CRUD operations for daily exchange rates.
    - Created CRUD operations, and also batch versions of operations which make sense. For example, if we want to update/delete exchange rates, it would be normally to correct something wrong with the ingestion. So, it should be doable through a batch call. Also, added specific CRUD operations based on resource and one based on the business context (currencies, side, date).
6. [DONE] Look up the applicable rate using:
    a. Transaction date
    b. Base currency
    c. Quote currency
    d. Transaction side
    - This is how the transactions will get the exchange rate for a specific call. This applies to buy, sell, and cross-sell. Look for the `get_exchange_rate_by_key` function inside `app/services/exchange_rates.py`.
7. [DONE] Require exactly one of foreign_amount or base_amount as transaction input.
    - For this one, I implemented a bi-directional setup for BUY and SELL. If the caller specifies a foreign_amount, then the assumption is that the store will buy or sell that amount of foreign currency. If the caller specifies base_amount instead, then the store will buy or sell foreign currency up to that amount of base_currency.
    - Example: Imagine a USD target_currency on a BUY transaction. If the `foreign_amount` is 100, then the interpretation is that the store is buying 100 USD and will give the equivalent PHP for that side of the exchange rate. But if instead of `foreign_amount` the system uses `base_amount`, then what will happen is it would give USD up to 100 PHP, still using the BUY exchange rate.
    - For cross-sell, since there is a pre-defined direction, what we did is implement a similar logic where it will now ask for either a `source_amount` or `target_amount` and use that as a constraint based on the source and target currency respectively.
8. [DONE] Calculate the missing amount using the applicable rate.
    - This is shown in the `domain.py` file with the logic of `BuyCalculation` and `SellCalculation` classes.
9. [DONE] Apply business rules such as fees, rounding, and adjustments.
    - This is similarly shown in the `domain.py` file with the logic of `BuyCalculation` and `SellCalculation` classes. For fees, I don't know what the industry standard is so I just put a random amount like 1 PHP and 0.5 PHP for Buy and Sell fees respectively. The fee is already deducted from the amount specified, and will be deducted before or after the exchange depending on the call.
    - For rounding, we implement banker's rounding or round half even. This lessens the impact overall of the bias of the normal rounding where 5 means round up all the time. Now, it is split depending on the nearest even number. This is from research but I'm not sure if this is the standard.
    - We save both fees and rounding on the DB, and the adjustments happen in realtime for the fees.
10. [DONE] Store the exact effective rate used as a transaction snapshot.
    - There is an effective_rate column in the foreign_exchange_transactions table. This will directly store the exchange_rate of the specific side depending on the transaction_date.
11. [DONE] Preserve the transaction’s effective rate if daily rates change later.
    - Even if someone changes the daily rates after it has been ingested and after a transaction happened, the `effective_rate` of that specific transaction will not change in the transactions table. Only newer transactions after the change will get that new rate applied.
12. [DONE] Validate currency codes as three-letter ISO-style codes.
    - We use pycountry, a third-party Python library to enforce ISO 4217 checks, so alphabetic values such as XYZ are rejected and only recognized currency codes pass validation in `app/schemas/exchange_rates.py`.
13. [DONE] Validate that amounts are positive decimal values.
    - We do this check on all amount fields in `app/schemas/transactions.py` and the exchange-rate schema files:
    - Decimal = Field(
        gt=0,
        max_digits=20,
        decimal_places=10,
    )
14. [DONE] Reject unsupported transaction sides.
    - This is already inherent with the decision to separate out the buy, sell, and cross-sell API endpoints.
    - Personally, I like this more because now the system will have to be intentional on what it wants to do, rather than abstracting three different logic flows inside it.
15. [DONE] Return a clear conflict or validation error when no daily rate exists.
    - Look into the `_transaction_conflict` function in `app/api/transactions.py`.
    - We can see this function used in the buy, sell, and cross-sell api endpoints.
16. [DONE] Demonstrate inheritance or polymorphism, such as different calculation behavior for BUY and SELL.
    - BuyCalculation and SellCalculation, come from the same base class. They expose different behaviors like different directions for the fees. I would imagine that if we were to add other types of transactions, there would just be other classes extending from the base class but would expose other features like discounts, rebates, promos, convenience fees, etc.
17. [DONE] Provide API documentation through OpenAPI/Swagger.
    - This can be accessed with http://localhost:8000. It is an auto-generated swagger docs from the API endpoints.

## Non-Functional Requirements
1. [DONE] Use a mainstream Python web framework, preferably FastAPI.
    - This project uses FastAPI. You can check the `main.py` file or everything under the `app` folder
2. [DONE] Use a relational database; SQLite is acceptable, while PostgreSQL is preferred for stronger deployments.
    - This project uses PostgreSQL but for ease of testing, deployed locally in the same container. You can check `docker-compose.yml` file under `db` service.
3. [DONE] Use Decimal rather than floating-point values for financial calculations.
    - This project uses Numeric data type in SQL Alchemy for these kinds of values like the `exchange_rate` column in the `exchange_rates` table.
4. [DONE] Use database migrations, preferably Alembic.
    - This project uses Alembic to track database schema structure over time. We can see this under the `versions` folder under `alembic` folder.
5. [DONE] Separate responsibilities into maintainable components such as routes, schemas, services, domain logic, and persistence models.
    - This project uses all of the items here. They should all be aptly named, except for the routes, which are split into different files to split the endpoint definitions.
6. [DONE] Provide unit tests for rate lookup and transaction calculation rules.
    - The unit tests in the `tests/` directory cover exact rate-key lookup, missing rates, BUY/SELL calculations, rounding, signed adjustments, fees, effective-rate snapshots, schemas, and OpenAPI documentation.
    - The current overall test coverage is 88%.
7. [DONE] Keep the API behavior and business rules clearly documented.
    - We generated a swagger documentation for the project. They clearly show the description of each endpoint, the expected schema, and the expected response.
8. [DONE] Make the system extensible so new transaction types can be added with minimal changes to existing integration points.
    - The models.py and domain.py files respectively show that we use inheritance and polymorphism to think about the components of this application. This should make it easy to add more transaction types in the future.
9. [DONE] Provide a straightforward local development setup.
    - Added in this markdown file at the very top is the setup for local development.
10. [DONE] Support containerized execution through Docker Compose.
    - This project is using docker and the different services are defined in the `docker-compose.yml` file.

## Assumptions
1. To start, the assumption here is that I will get the exchange rates from a separate area and will have an ingestion pipeline for adding the exchange rates to the database. I have elected to use the values that can be fetched from https://github.com/fawazahmed0/exchange-api, a free currency exchange rates API. For the purposes of this exam, I will assume these are correct (I will not verify the correctness). I will also ask AI to trim down the coins and the cryptocurrency as they are not requirements for the functional requirements (FRs) and the non-functional requirements (NFRs). Again, I will assume that the end result of this is a proper list of exchange rates.
2. I will use PHP as the base currency. If the Money Changer store is here, then it makes sense for PHP to be the base currency as the store will probably have that in the largest quantities.
3. Transactions are treated as immutable financial records. The API exposes the three creation endpoints, logical transaction reads, and business-day collection reads. Corrections should be handled through a controlled administrative or reversal workflow rather than changing or deleting historical rows.

## Future Considerations
1. In terms of both technical and business aspect, it would be good for the store to cater to popular exchanges outside of the base currency like USD to JPY or something like that with a direct trade rather than a cross sell. This means identifying these popular exchanges and creating rows for them explicitly. Nominating these types of exchanges can be done after analyzing demand. This would make the store's pricing on these specific conversions become more competitive with other stores, potentially. This would also lessen the impact of rounding errors as you only do one rounding instead of two.
2. I'm thinking there may be a way to game the system here, like if you choose specific trades in a chain and exploit how rounding is done, you can loop back to a state where you end up with more (or less) money than you had before. There should be a way or validation that we can do here to prevent this specific scenario but I still need to think of how to check if this is possible and implement safeguards around it.
3. I think it would be needed to implement some level of authentication and authorization here, even if it would most likely be in the store's point of sale system. For example, posting daily rates to the DB should be done by the ingestion pipeline, and fetching them can be done by the system itself via service principals or something to denote identity. But the updates and deletes most likely can only be done by a separate identity that has more administrative roles.
4. A single store wouldn't need something like scaling but in the future if this becomes a central hub of multiple stores or multiple companies, we can implement a worker setup. Essentially, you can have X number of workers setup to process the computations and logs. With that change, a pub-sub model can be considered. There will be a messaging queue (i.e. redis stream, rabbitmq) that will take in the requests and then the workers listen to the queue and take what they can. This setup will introduce more things to add though, like dead-letter queues as well to handle the messages that error out.
5. Related above to supporting high concurrency setups with higher likelihood of failing due to multiple reasons, retries would probably have to be implemented and will also have to be idempotent. We wouldn't want several retries to potentially put multiple rows on the DB or to contribute to more workload for the server or for the workers. In this case, implementing a cache and putting an idempotency key there referencing the result of the first successful call will be useful so that multiple post requests that trigger for the same transaction will not add multiple rows. This can be implemented as a redis cache.
6. Consider retention policies for the DB and put them in cold storage based on some business threshold so the DB does not grow without bound.