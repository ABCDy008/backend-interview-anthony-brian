# Money Changer Web API

# Functional Requirements
Functional Requirements

1. Record foreign exchange transactions without storing customer PII.
    - This should be inherent with the design, a transaction will be treated as only a transaction, with the only identifier being the transaction_id.
2. Generate an internal transaction ID and store the transaction timestamp.
    - Yes, this is a core consideration in the DB table design. Additionally, I feel there would be things I might add which I will talk about in later sections.
3. [DONE] Maintain daily exchange rates for currency pairs.
    - Yes, there will be both a transactions table and a exchange rates table.
4. Support BUY and SELL transaction sides with potentially different rates.
5. [DONE] Provide CRUD operations for daily exchange rates.
    - Created CRUD operations, and also batch versions of operations which make sense. For example, if we want to update/delete exchange rates, it would be normally to correct something wrong with the ingestion. So, it should be doable through a batch call. Also, added specific CRUD operations based on resource and one based on the business context (currencies, side, date).
6. Look up the applicable rate using:
    a. Transaction date
    b. Base currency
    c. Quote currency
    d. Transaction side
7. Require exactly one of foreign_amount or base_amount as transaction input.
8. Calculate the missing amount using the applicable rate.
9. Apply business rules such as fees, rounding, and adjustments.
10. Store the exact effective rate used as a transaction snapshot.
11. Preserve the transaction’s effective rate if daily rates change later.
12. Validate currency codes as three-letter ISO-style codes.
13. Validate that amounts are positive decimal values.
14. Reject unsupported transaction sides.
15. Return a clear conflict or validation error when no daily rate exists.
16. Demonstrate inheritance or polymorphism, such as different calculation behavior for BUY and SELL.
17. Provide API documentation through OpenAPI/Swagger.

## Non-Functional Requirements
1. Use a mainstream Python web framework, preferably FastAPI.
    - This project uses FastAPI. You can check the `main.py` file or everything under the `app` folder
2. Use a relational database; SQLite is acceptable, while PostgreSQL is preferred for stronger deployments.
    - This project uses PostgreSQL but for ease of testing, deployed locally in the same container. You can check `docker-compose.yml` file under `db` service.
3. Use Decimal rather than floating-point values for financial calculations.
    - This project uses Numeric data type in SQL Alchemy for these kinds of values like the `exchange_rate` column in the `exchange_rates` table.
4. Use database migrations, preferably Alembic.
    - This project uses Alembic to track database schema structure over time.
5. Separate responsibilities into maintainable components such as routes, schemas, services, domain logic, and persistence models.
6. Provide unit tests for rate lookup and transaction calculation rules.
7. Keep the API behavior and business rules clearly documented.
8. Make the system extensible so new transaction types can be added with minimal changes to existing integration points.
9. Provide a straightforward local development setup.
10. Support containerized execution through Docker Compose.
    - This project is using docker and the different services are defined in the `docker-compose.yml` file.

## Starting Assumptions
1. To start, the assumption here is that I will get the exchange rates from a separate area and will have an ingestion pipeline for adding the exchange rates to the database. I have elected to use the values that can be fetched from https://github.com/fawazahmed0/exchange-api, a free currency exchange rates API. For the purposes of this exam, I will assume these are correct (I will not verify the correctness). I will also ask AI to trim down the coins and the cryptocurrency as they are not requirements for the functional requirements (FRs) and the non-functional requirements (NFRs). Again, I will assume that the end result of this is a proper list of exchange rates.
2. I will use PHP as the base currency. If the Money Changer store is here, then it makes sense for PHP to be the base currency as the store will probably have that in the largest quantities.
3. I am going to assume that there would be no direct trades other than when PHP is the base or quote currency. Direct trades of this nature would make it necessary to store rows specific to conversions between currencies outside of the "base currency". Brute forcing this would mean tens of thousands of rows per batch of exchange rates. This would not be scalable in terms of the storage.

## Future Considerations
1. In terms of both technical and business aspect, it would be good for the store to cater to popular exchanges outside of the base currency like USD to JPY or something like that with a direct trade. This means identifying these popular exchanges and creating rows for them explicitly. Nominating these types of exchanges can be done after analyzing demand. This would make the store's pricing on these specific conversions become more competitive with other stores, potentially. This would also lessen the impact of rounding errors as you only do one rounding instead of two.
2. I'm thinking there may be a way to game the system here, like if you choose specific trades in a chain and exploit how rounding is done, you can loop back to a state where you end up with more (or less) money than you had before. There should be a way or validation that we can do here to prevent this specific scenario but I still need to think of how to implement this.