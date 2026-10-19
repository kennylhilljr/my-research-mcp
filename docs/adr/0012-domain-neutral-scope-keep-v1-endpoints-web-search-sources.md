# ADR 0012: Domain-neutral scope; every v1 endpoint kept; web search as optional sources

- **Status:** Accepted (owner decision, 2026-10-19)
- **Date:** 2026-10-19
- **Supersedes:** review decision D7 and open decision O1 ([REVIEW v1](../review/REVIEW-v1.md) sections 1 and 7); FR-SRC-17 as written in [PRD-sources v1](../prd/components/PRD-sources-v1.md)

## Context

v1 grew around one subject area: a docs-domain list, six crawl projects and a web-search tool (`search_iam_docs`) built on four providers (Vertex AI Search, Brave, SerpAPI, Google Programmable Search). The first round of v2 requirements removed all four providers and described the docs sources in terms of that subject area.

The owner's direction:

1. The requirements must not be tied to one subject area. Coverage of any area (including the one v1 grew around) comes from configuration, so it can expand without a requirements change.
2. No endpoint v1 calls today is dropped.
3. Vertex AI Search stays available as an option.

## Decision

1. **Domain-neutral requirements.** No requirement, goal or tool names a subject area. Topic coverage is configuration: docs-site instances, named site sets and web-search engines.
2. **Every v1 endpoint stays reachable.** Each upstream endpoint v1 calls has a v2 source. The one substitution, already in the v1 requirements: the undocumented AWS and Microsoft Learn site-search endpoints give way to those vendors' official MCP servers, which cover the same documentation. The v1 docs-domain list ships in the default configuration as the site set `v1_docs`, and the six v1 crawl projects ship as `docs_site_*` instances. Both are data the owner can edit, extend or replace.
3. **Web search is a source group, `web`,** with four optional, metered sources:
   - `vertex_search`, one instance per Vertex AI Search engine (`vertex_<name>`). It authenticates with the owner's Google sign-in (Application Default Credentials), not an API key.
   - `brave_search`, `serpapi` and `google_pse` (Programmable Search). `google_pse` carries its announced shutdown date, 2027-01-01.
4. **Spend stays deliberate.** Every web source is off until configured, has a daily call cap, and is not in the default fan-out. Callers ask for it with `groups=["web"]` or by source id. Within the group, the default strategy is `fallback`: try the configured sources in order (v1's order: Vertex, Brave, SerpAPI, Programmable Search) and stop at the first that answers. `all` fans out to every configured web source.
5. **Google sign-in credentials are not stored by v2.** `gcloud` owns the Application Default Credentials file. v2 asks `google-auth` for a short-lived access token, keeps it in memory only, and sends it only to `discoveryengine.googleapis.com`. This is the one credential that does not live in the Keychain; health reports its state like any other credential.

## Consequences

- G1 and the source catalog grow from 38 to 42 sources. The non-goal "paid search providers" is dropped; paid providers are allowed as optional, capped sources.
- `search` gains an optional `site_set` argument in M1 (restricts Brave, SerpAPI and Programmable Search results to a named set of domains; a Vertex engine's scope is set in Google Cloud). M0 is unchanged: the argument is added with a default, so the M0 tool contract stays valid.
- A new extra, `gcp` (`google-auth`), is needed only by `vertex_search`. Without it the Vertex source shows `unconfigured` with the install command.
- `google-auth` refreshes tokens through its own HTTP call to Google's token endpoint. That call is outside the shared HTTP client, so it is recorded as a call record by the provider and allowed only to `oauth2.googleapis.com`.
- SerpAPI accepts its key only as a query parameter. Query placement is allowed there under the existing rule (FR-PLAT-12): the URL is never logged, and the redactor masks `api_key=`.
- v1 credentials for all four providers are imported at cutover, together with the Vertex project, location and engine id and the Programmable Search engine id (settings, not secrets).
