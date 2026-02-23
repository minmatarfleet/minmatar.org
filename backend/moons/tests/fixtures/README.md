# Moon paste fixtures

## sample_3h58r_paste.txt

Sample scan paste for system 3H58-R (SolarSystemID 30002325), used to debug parser and ESI behaviour.

**Known issue (why “processing is off”):** One row has a **typo in MoonID**:

- **Line:** `3H58-R V - Moon 10` block, Zeolites row  
- **Wrong:** `4014800` (7 digits)  
- **Correct:** `40148004` (8 digits)

ESI returns 404 for moon ID `4014800` because it doesn’t exist. The parser now reports this in `result.errors` instead of crashing, with a hint to check for a missing digit.

To process the paste successfully, fix that row in the source (e.g. change `4014800` to `40148004`) before pasting.
