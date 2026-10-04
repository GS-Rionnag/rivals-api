# Provider fallback behavior

Normal overall, hero, and class win rates use aggregate summaries from
RivalsData, RivalsTracker, and Tracker. Available values remain usable when
another source fails. Private sections set `metadata.private_profile` and
`metadata.privacy_warning`: returned values can be stale or inaccurate.
Unknown counts remain unknown, rather than becoming zero.

Player profiles use RivalsData and RivalsTracker. Missing current and lifetime
peak ranks can come from Tracker after verifying the account name. The additive
`rank_summary` describes rank labels, season, source, and private snapshot flags.
Valid primary rank values are preserved. Account search can use both RivalsData
and RivalsTracker.

Successful read responses are stored using provider, endpoint, parameters, and
payload as the cache key. A transient provider failure can return that same
request's last successful response for up to `stale_cache_ttl` seconds (default
86400). Set it to zero to disable this fallback. Responses carry
`provider_metadata.fallback` where their shape supports it; `client.provider_errors`
also records the fallback and its timestamp. Some projected resource models do
not retain all raw metadata, so callers should inspect provider errors too.

This covers eligible read resources, including maps, bans, leaderboards, hero
stats, identity, cosmetics, proficiency, and punishments. It does not establish
an equivalent second provider for each resource. For example, RivalsTracker's
combined map counts cannot replace separate competitive and quickplay counts.
If no equivalent source or previous successful response exists, the function
still reports its failure. Returning invented values would be misleading.

Explicit privacy errors do not use stale-response fallback. Private flags on a
successful response do not discard its available data. Live status, live games,
match history pagination, match details, and forced provider refreshes do not
use this outage fallback. Cached player profiles omit old live status. Stale
season catalogs cannot verify the current season.

Precise win rates retain their separate completed-match cache and incremental
history traversal. Provider pacing, cooldowns, and browser fallback still apply
before using an eligible cached response.
