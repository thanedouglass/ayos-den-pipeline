---
name: youtube-metadata-generator
description: Generate optimized YouTube metadata, SEO-dense descriptions, comma-separated tags, and strategy classifications (Feed Fuel vs SEO Artifact) from raw text or Reddit scrapers. Use when structuring video uploads or automating distribution pipelines.
---

# YouTube Metadata Generator

A systematic skill for transforming raw text, community discussions, or scraped Reddit data into a structured distribution payload optimized for YouTube algorithms and search indexing.

## When to Use

Use this skill when:
- Processing raw text or scraped social media data into upload-ready assets.
- Generating double-layer titles, SEO descriptions, and comma-separated tags.
- Classifying content into the Two-Tier Distribution Stack (*Shorts Feed Fuel* vs *SEO Intent Artifacts*).

## Processing Pipeline

When invoked, process the input data through the following JSON schema specification:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "YouTubeMetadataPayload",
  "type": "object",
  "properties": {
    "viral_title": {
      "type": "string",
      "description": "Double-layer title pairing high-velocity cultural hooks with long-tail search intent."
    },
    "description": {
      "type": "string",
      "description": "SEO-dense description formatted with key context breakdown and primary ecosystem links."
    },
    "tags": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Comma-separated search tags optimized for YouTube search indexing."
    },
    "strategy_tier": {
      "type": "string",
      "enum": ["FEED_FUEL", "SEO_ARTIFACT", "SOVEREIGN_BEACON"]
    }
  },
  "required": ["viral_title", "description", "tags", "strategy_tier"]
}
```

## Execution Steps

1. **Extract Input:** Analyze the provided raw text, topic, or scraped dataset.
2. **Classify Strategy:** Determine whether the asset functions as high-retention Feed Fuel, long-tail SEO Intent, or a Sovereign Beacon.
3. **Construct Payload:** Generate the title, SEO description, and tag array adhering strictly to the schema above.
