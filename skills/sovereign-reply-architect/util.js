// Helper utilities for the Sovereign Reply Architect skill
// Reads past entries from queue.json to provide lore continuity checks

import { readFileSync } from "fs";
import path from "path";

/**
 * Load the queue.json file and return an array of past items.
 * @param {string} [queuePath] - Optional custom path; defaults to project root queue.json.
 * @returns {Array<Object>} Parsed queue entries (empty array on error).
 */
export function loadQueue(queuePath = path.resolve(process.cwd(), "queue.json")) {
  try {
    const raw = readFileSync(queuePath, { encoding: "utf-8" });
    const data = JSON.parse(raw);
    if (Array.isArray(data)) return data;
    console.warn("queue.json does not contain an array; returning empty list");
    return [];
  } catch (e) {
    console.error("Failed to read queue.json:", e);
    return [];
  }
}

/**
 * Find the most recent entry that matches a given narrative arc.
 * @param {string} arcId - The narrative_arc identifier to look for.
 * @param {Array<Object>} [queue] - Optional preloaded queue; if omitted we load it.
 * @returns {Object|null} The latest matching entry or null.
 */
export function findLatestArcEntry(arcId, queue) {
  const items = queue ?? loadQueue();
  // Assuming items are ordered by insertion timestamp (id field or similar)
  const matching = items.filter((it) => it.narrative_arc === arcId);
  if (matching.length === 0) return null;
  // Return the entry with the highest id (timestamp) or last element
  return matching.reduce((a, b) => (a.id > b.id ? a : b));
}

/**
 * Example usage within your agent code:
 *   const { loadQueue, findLatestArcEntry } = require("./util.js");
 *   const queue = loadQueue();
 *   const prior = findLatestArcEntry("HYBE_HxG_Tour_Burnout_2026", queue);
 *   // Use `prior` to inform your new script generation.
 */

