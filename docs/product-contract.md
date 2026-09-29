# Customer import product contract

The client imports synthetic customer records using `POST /customers/import` with
an `application/json` request body. Every record must have a nonempty string
`name`. A `nickname` is optional: callers may provide a string, provide `null`, or
omit it. Unknown fields and non-string, non-null nicknames are invalid.

A successful request returns HTTP 200 and a JSON object containing the normalized
customer. The result always includes `name` and `nickname`; a missing or null
nickname is represented as `null` in the response. For example:

```json
{"customer":{"name":"Avery Chen","nickname":"Aves"}}
```

Invalid customer records return HTTP 422 with `{"error":"invalid_customer"}`.
Malformed JSON returns HTTP 400 with `{"error":"invalid_json"}`. Requests larger
than 16 KiB are rejected with HTTP 413. Only JSON objects are valid records.

`GET /health` returns HTTP 200 with `{"status":"ok"}` while the service is running.
`GET /` serves the demo page. Unsupported paths return HTTP 404 with
`{"error":"not_found"}`. Imports are stateless: this demo does not persist data.

Release acceptance requires preserving these response behaviors and rejecting
invalid records. All presentation data is synthetic.
