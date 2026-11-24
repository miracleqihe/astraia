// A stable distribution key, not a security hash. Integrity is checked with SHA-256.
export function shardKey(id, count = 64) {
  let hash = 2166136261;
  for (let i = 0; i < id.length; i++) hash = Math.imul(hash ^ id.charCodeAt(i), 16777619);
  return (hash >>> 0) % count;
}
