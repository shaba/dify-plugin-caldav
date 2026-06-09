# Privacy Policy

This plugin (`dify-plugin-caldav`) does not collect, store or transmit any
personal data to the plugin author or any third party.

- The configured credentials are `base_url` (the URL of the CalDAV server you
  choose), `username` and `password`. They are stored by your Dify instance, not
  by the plugin author.
- When you invoke a tool, the plugin connects **only** to that `base_url` over
  the CalDAV protocol (HTTP), carrying the calendar name, query, event or task
  data you provided, authenticated with your `username`/`password`.
- No analytics, telemetry or external hosts are involved. The plugin itself
  persists nothing.

Your calendars, events and tasks are subject to the privacy policy of the CalDAV
server configured in `base_url`.
