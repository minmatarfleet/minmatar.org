# CONVERSION
Tools for the Loyalty Point (LP) Conversion team.

## Functionality
Initial functionality is providing access to data about recently traded volumes for a set of specific MinMil loyalty store items, in CSV format.

This data can then be incorporated into the Google Sheets that the conversion team use to identify the best items to use for converting LP into ISK.

## Implementation
The initial implementation is very unsophisticated, to get something up and running as quickly as possible without having to learn lots of different framework technologies.

## To-do

1. Replace the `refresh` endpoint with a Celery scheduled task
2. Cache the data in Redis or the database so that it can survive a server restart
3. Add unit tests
4. Lookup and cache the current Jita price from the market API
5. Extend the item IDs list to include all TLF LP store items