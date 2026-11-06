# Generic deployment settings

The public package does not preselect the user's city or school. Configure it for your environment after installation; examples are not the author's personal runtime configuration.

## Time and weather

```json
{
  "local_timezone": "UTC+08:00",
  "weather_default_city": "",
  "weather_default_country": ""
}
```

- `local_timezone` accepts `UTC`, `UTC±HH:MM`, and IANA timezone names such as `Europe/Paris`. The default remains UTC+08:00 so upgrading an existing installation does not shift all schedules. Use an IANA name for regions observing daylight saving time.
- The timetable, initiative windows, group daily budgets, dynamic-post daily budgets, nightly reflection, local usage statistics, and local speech monthly budgets use this setting. The vision provider's peak/off-peak pricing schedule retains its existing UTC+08:00 rules independently of the user's timezone; it does not identify the user's location.
- Back up and list existing tasks before changing timezone. Reload the plugin afterward and inspect each next execution time. Cron and `at:` timestamps without offsets use the configured timezone; explicitly offset `at:` timestamps retain their absolute instant. Do not recreate tasks merely to change timezone.
- The default weather city is empty: configure one yourself or specify it in a query. The optional country/region code can remain empty to avoid country filtering. All cities use the geocoding service; ambiguous locations require confirmation. Neither IP addresses nor schools determine the location.
- The public package does not overwrite existing local city settings, Canvas bindings, lecture schedules, or memories. Applicable regulations, provider availability, and account permissions remain subject to each service.

## Binding your school's Canvas

The [local binding utility](../tools/canvas_login.py) first asks for the school's HTTPS Canvas origin, for example `https://canvas.example.edu`, then accepts the access token with hidden input. The example domain cannot be used for a real login. When renewing an existing binding, press Enter to reuse its locally saved origin.

The origin and token are stored together locally in `canvas.credentials.json`, never in model arguments or public examples. Tokens are sent only to that origin. Redirects, non-HTTPS URLs, embedded credentials, non-root paths, and query parameters are refused. Only the existing GET endpoints for courses, assignments, and announcements are exposed. Submitting assignments, sending messages, and modifying grades are not supported. Schools that do not offer personal tokens or the relevant APIs cannot use this integration; compatibility with every school instance is not guaranteed.

School names and city-specific references in the current public source, documentation, and examples have been generalized. This update does not rewrite Git history; older commits retain their original file versions.
