# Website API types come from the backend schema

The website's API types are generated from the backend's OpenAPI document, not copied by hand.

- `frontend/app/src/types/generated/openapi.json` is the backend schema; `backend/app/tests/test_openapi_schema.py` fails when it is stale.
- `frontend/app/src/types/generated/api.d.ts` is generated from it (`npm run gen:api`); `testing/types/generated_api.test.ts` fails when it is stale. Never edit either file by hand.
- After changing a backend endpoint or schema, regenerate both and commit them:

```bash
cd backend && UPDATE_CONTRACTS=1 pipenv run python manage.py test app.tests.test_openapi_schema --settings=app.settings_test
cd frontend/app && npm run gen:api
```

## New types

A new API type is an alias of the generated schema in `src/types/api.minmatar.org.ts`, never a hand-written interface:

```ts
export type Thing = ApiResponse<'ThingResponse'>      // a response: every field present, null when unset
export type ThingPatch = ApiRequest<'ThingPatchRequest'>  // a request body: defaulted fields optional
```

The API sends date-times as ISO strings, so they are `string`, never `Date`. Nullable fields are `| null`: handle the null.

`testing/types/generated_api.test.ts` fails on a new `export interface` in `src/types/api.minmatar.org.ts` or `src/helpers/api.minmatar.org/*.ts`. The interfaces that are still hand-written are listed, with the reason, in `testing/types/hand_written_api_types.json`; when you alias one, remove it from that list. UI view models (`src/types/layout_components.ts`) stay hand-written.

If an endpoint returns an untyped `dict`, give it a Ninja response schema rather than a hand-written frontend type.
