# FielMedina API

Django + Strawberry GraphQL backend for the Fielmedina apps (`Fielmedina-ios-v3`,
`Fielmedina-Android-v3`, siblings of this directory). Schema lives in `api/schema.py`.

## What clients depend on

- `locations` / `events` resolvers accept `city_id`, `category_id`, `limit`,
  `offset` and are `select_related`/`prefetch_related` (N+1 already avoided). Both
  clients currently use these **only** for the prefetcher's full-catalogue warm-up
  call (`limit: 500`/`200`, no filters) — filtering happens client-side offline-first,
  not via these params, even though the params exist and work. See each client's
  `CLAUDE.md` for why.
- No `totalCount` on any list field — clients detect "last page" by a short page
  (`returned.count < limit`), not an explicit count.
- Introspection is disabled outside `DEBUG` (`NoSchemaIntrospectionCustomRule`).

## Known gaps (not yet addressed, flagged during a client-side audit)

- No GraphQL query depth/cost limiting — a public endpoint without this is a DoS
  surface.
- No max page size cap — a client could request an arbitrarily large `limit`.

## Client offline dependency (read before changing field shapes)

Both mobile apps cache GraphQL responses keyed by exact query+variables. Adding or
renaming a field on a type used by an already-shipped query is safe (additive);
changing what a field *returns* for existing data, or renaming/removing a field a
client already queries, invalidates that client's offline cache and forces a refetch
on next launch — acceptable, but worth knowing before doing it casually. Coordinate
schema changes with whichever client's `queries.graphql` references the field.
