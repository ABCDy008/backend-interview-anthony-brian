# Money Changer Web API

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
    - I put in a total of 172 currency pairs between PHP and other currencies as test data, but doubled them to 344 since I would have a separate exchange rate for BUY and SELL and wanted them to be configurable.
    - For the test data, I just put a spread of 1% (0.99 and 1.01) but the daily exchange rate pipeline could just as easily pass in different pre-configured numbers.
    - I imagine this feature will be useful since there are currencies that are rarer/more regulated than others and therefore we can have different margins for them.
5. [DONE] Provide CRUD operations for daily exchange rates.
    - Created CRUD operations, and also batch versions of operations which make sense. For example, if we want to update/delete exchange rates, it would be normally to correct something wrong with the ingestion. So, it should be doable through a batch call. Also, added specific CRUD operations based on resource and one based on the business context (currencies, side, date).
6. [DONE] Look up the applicable rate using:
    a. Transaction date
    b. Base currency
    c. Quote currency
    d. Transaction side
    - This is how the transactions will get the exchange rate for a specific call. This applies to buy, sell, and cross-sell. Look for the `get_exchange_rate_by_key` function inside the `services.py` file.
7. [DONE] Require exactly one of foreign_amount or base_amount as transaction input.
    - For this one, I implemented a bi-directional setup for BUY and SELL. If the caller specifies a foreign_amount, then the assumption is that the store will buy or sell that amount of foreign currency. If the caller specifies base_amount instead, then the store will buy or sell foreign currency up to that amount of base_currency.
    - Example: Imagine a USD target_currency on a BUY transaction. If the `foreign_amount` is 100, then the interpretation is that the store is buying 100 USD and will give the equivalent PHP for that side of the exchange rate. But if instead of `foreign_amount` the system uses `base_amount`, then what will happen is it would give USD up to 100 PHP, still using the BUY exchange rate.
    - For cross-sell, since there is a pre-defined direction, what we did is implement a similar logic where it will now ask for either a `source_amount` or `target_amount` and use that as a constraint based on the source and target currency respectively.
8. [DONE] Calculate the missing amount using the applicable rate.
    - 
9. [DONE] Apply business rules such as fees, rounding, and adjustments.
10. [DONE] Store the exact effective rate used as a transaction snapshot.
    - There is an effective_rate column in the foreign_exchange_transactions table. This will directly store the exchange_rate of the specific side depending on the transaction_date.
11. [DONE] Preserve the transaction’s effective rate if daily rates change later.
    - Even if someone changes the daily rates after it has been ingested and after a transaction happened, the `effective_rate` of that specific transaction will not change in the transactions table. Only newer transactions after the change will get that new rate applied.
12. [DONE] Validate currency codes as three-letter ISO-style codes.
    - We use pycountry, a third-party python library to enforce ISO 2417 checks. For a normal ISO-style check that we can configure (3 chars), something like XYZ can still pass. This makes it so only proper currencies can pass our checks in `schemas.py`
13. [DONE] Validate that amounts are positive decimal values.
    - We do this check on all amount fields in `schemas.py` file:
    - Decimal = Field(
        gt=0,
        max_digits=20,
        decimal_places=10,
    )
14. [DONE] Reject unsupported transaction sides.
    - This is already inherent with the decision to separate out the buy, sell, and cross-sell API endpoints.
    - Personally, I like this more because now the system will have to be intentional on what it wants to do, rather than abstracting three different logic flows inside it.
15. [DONE] Return a clear conflict or validation error when no daily rate exists.
    - Look into `_transaction_conflict` function on `transactions.py` file.
    - We can see this function used in the buy, sell, and cross-sell api endpoints.
16. [DONE] Demonstrate inheritance or polymorphism, such as different calculation behavior for BUY and SELL.
    - 
17. [TODO] Provide API documentation through OpenAPI/Swagger.

## Non-Functional Requirements
1. [DONE] Use a mainstream Python web framework, preferably FastAPI.
    - This project uses FastAPI. You can check the `main.py` file or everything under the `app` folder
2. [DONE] Use a relational database; SQLite is acceptable, while PostgreSQL is preferred for stronger deployments.
    - This project uses PostgreSQL but for ease of testing, deployed locally in the same container. You can check `docker-compose.yml` file under `db` service.
3. [DONE] Use Decimal rather than floating-point values for financial calculations.
    - This project uses Numeric data type in SQL Alchemy for these kinds of values like the `exchange_rate` column in the `exchange_rates` table.
4. [DONE] Use database migrations, preferably Alembic.
    - This project uses Alembic to track database schema structure over time.
5. [DONE] Separate responsibilities into maintainable components such as routes, schemas, services, domain logic, and persistence models.
6. [DONE] Provide unit tests for rate lookup and transaction calculation rules.
    - The unit tests in `tests/test_transaction_operations.py` covers exact rate-key lookup, missing rates, BUY/SELL calculations, rounding, signed adjustments, fees, and effective-rate snapshots.
7. [DONE] Keep the API behavior and business rules clearly documented.
    - We generated a swagger documentation.
8. [TODO] Make the system extensible so new transaction types can be added with minimal changes to existing integration points.
9. [TODO] Provide a straightforward local development setup.
10. [DONE] Support containerized execution through Docker Compose.
    - This project is using docker and the different services are defined in the `docker-compose.yml` file.

## Assumptions
1. To start, the assumption here is that I will get the exchange rates from a separate area and will have an ingestion pipeline for adding the exchange rates to the database. I have elected to use the values that can be fetched from https://github.com/fawazahmed0/exchange-api, a free currency exchange rates API. For the purposes of this exam, I will assume these are correct (I will not verify the correctness). I will also ask AI to trim down the coins and the cryptocurrency as they are not requirements for the functional requirements (FRs) and the non-functional requirements (NFRs). Again, I will assume that the end result of this is a proper list of exchange rates.
2. I will use PHP as the base currency. If the Money Changer store is here, then it makes sense for PHP to be the base currency as the store will probably have that in the largest quantities.

## Future Considerations
1. In terms of both technical and business aspect, it would be good for the store to cater to popular exchanges outside of the base currency like USD to JPY or something like that with a direct trade rather than a cross sell. This means identifying these popular exchanges and creating rows for them explicitly. Nominating these types of exchanges can be done after analyzing demand. This would make the store's pricing on these specific conversions become more competitive with other stores, potentially. This would also lessen the impact of rounding errors as you only do one rounding instead of two.
2. I'm thinking there may be a way to game the system here, like if you choose specific trades in a chain and exploit how rounding is done, you can loop back to a state where you end up with more (or less) money than you had before. There should be a way or validation that we can do here to prevent this specific scenario but I still need to think of how to check if this is possible and implement safeguards around it.
3. I think it would be needed to implement some level of authentication and authorization here, even if it would most likely be in the store's point of sale system. For example, posting daily rates to the DB should be done by the ingestion pipeline, and fetching them can be done by the system itself via service principals or something to denote identity. But the updates and deletes most likely can only be done by a separate identity that has more administrative roles.
4. A single store wouldn't need something like scaling but in the future if this becomes a central hub of multiple stores or multiple companies, we can implement a worker setup. Essentially, you can have X number of workers setup to process the computations and logs. With that change, a pub-sub model can be considered. There will be a messaging queue (i.e. redis stream, rabbitmq) that will take in the requests and then the workers listen to the queue and take what they can. This setup will introduce more things to add though, like dead-letter queues as well to handle the messages that error out.
5. Related above to supporting high concurrency setups with higher likelihood of failing due to multiple reasons, retries would probably have to be implemented and will also have to be idempotent. We wouldn't want several retries to potentially put multiple rows on the DB or to contribute to more workload for the server or for the workers. In this case, implementing a cache and putting an idempotency key there referencing the result of the first successful call will be useful so that multiple post requests that trigger for the same transaction will not add multiple rows. This can be implemented as a redis cache.
6. Consider retention policies for the DB and put them in cold storage based on some business threshold so the DB does not grow without bound.