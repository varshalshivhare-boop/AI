# Redis Stream Contract

Owner: contract changes are reviewed by all three PCs. Producers and consumers are listed below.

## Naming

| Stream | Producer | Consumers | Schema | MAXLEN (approx.) |
|---|---|---|---|---|
| `ticks.normalized` | PC 1 market-data | PC 3 gateway (optional live view) | `tick.normalized.v1` | `TICKS_STREAM_MAXLEN` |
| `candles.closed.1m` | PC 1 | PC 2 engine, PC 3 gateway | `candle.closed.v1` | `CANDLES_STREAM_MAXLEN` |
| `candles.closed.5m` | PC 1 | PC 2, PC 3 | `candle.closed.v1` | `CANDLES_STREAM_MAXLEN` |
| `candles.closed.15m` | PC 1 | PC 2, PC 3 | `candle.closed.v1` | `CANDLES_STREAM_MAXLEN` |
| `candles.closed.30m` | PC 1 | PC 2, PC 3 | `candle.closed.v1` | `CANDLES_STREAM_MAXLEN` |
| `candles.closed.1d` | PC 1 | PC 2, PC 3 | `candle.closed.v1` | `CANDLES_STREAM_MAXLEN` |
| `signals.generated` | PC 2 quant-engine | PC 3 gateway and alerts | `signal.generated.v1` | 50000 |
| `provider.health` | PC 1 | PC 3 gateway, PC 3 monitoring | `provider_health.v1` | 5000 |
| `dlq.<stream>` | PC 3 gateway | PC 3 operator tools | original payload + error | 10000 |

Rules:
- Stream names use dots, never slashes or spaces.
- One stream per message type. Do not multiplex schemas on one stream.
- The `timeframe` for candles is encoded in the stream name AND in the payload. Consumers may rely on either. Payload is authoritative if they disagree, and disagreement is a producer bug.
- `dlq.<stream>` holds messages that failed schema validation, with the validation error attached.

## Message envelope

Each stream entry has a single field `payload` containing the UTF-8 JSON document that validates against the named schema. No other fields are used in v1, so consumers can parse with one code path.

```
XADD candles.closed.1m MAXLEN ~ 10000 * payload '{"schema_version":1,"symbol":"RELIANCE",...}'
```

## Consumer groups

| Stream | Group | Consumer naming |
|---|---|---|
| `candles.closed.*` | `quant-engine` | `quant-engine-<host>-<pid>` |
| `candles.closed.*` | `gateway` | `gateway-<n>` |
| `signals.generated` | `gateway` | `gateway-<n>` |
| `signals.generated` | `alerts` | `alerts-<n>` |
| `provider.health` | `gateway` | `gateway-<n>` |

Every consumer ACKs explicitly with `XACK` after successful processing. Failed messages are moved to `dlq.<stream>` and then ACKed, so a poison message cannot block a group.

## Versioning

- `schema_version` is a constant in every payload.
- v1 schemas are frozen. Any additive or breaking change creates `<name>.v2.json`.
- Producers publish the new version on the same stream only after all consumers have a release that understands it. Until then, the old version keeps being published.
- Deprecated versions are removed only after two release cycles with zero consumers on them.
