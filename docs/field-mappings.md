# Source field mappings

Status: no mappings defined. No organizer source format, field inventory or sample record is available. This is a mapping-documentation plan, not an approved mapping table.

After inspection, document each source separately with its source identity, format/version, encoding evidence, framing rules and sample coverage. For each observed field, record:

- Exact source column/key/path and observed type, including absent/null/empty behavior.
- Verified semantics and the supporting organizer documentation or private sample reference.
- Approved target field in the versioned canonical contract, or an explicit unmapped disposition.
- Transformation, timestamp/zone interpretation, identifier normalization and any precision loss.
- Validation outcomes, raw-evidence preservation and transformation version.

Document source-only fields and conflicts explicitly. A missing field in one source must not inherit another source's mapping. Do not assume common field names imply common semantics. Keep sensitive source values and absolute private evidence paths out of public documentation.

No example source columns or fictional event mappings are provided. The canonical schema and executable mapping tests are deferred pending actual authorized samples.
