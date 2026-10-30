"""Text shingling, MinHash and LSH banding, plus exact Jaccard similarity. Pure Python, deterministic."""
import hashlib
import re
from collections import defaultdict
from itertools import combinations

PRIME = (1 << 61) - 1
NUM_PERM = 128
BANDS, ROWS = 32, 4  # 32 x 4 = 128; pairs from about 40% similarity upward become candidates


def tokens(text: str) -> list:
    return re.findall(r"[^\W_]+", text.lower())


def shingles(text: str, k: int = 5) -> set:
    words = tokens(text)
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def _h(s: str) -> int:
    return int.from_bytes(hashlib.blake2b(s.encode("utf-8"), digest_size=8).digest(), "big")


# Fixed (a, b) pairs for the hash permutations, derived from a seed string so runs are repeatable.
_PERMS = [(_h(f"a{i}") % (PRIME - 1) + 1, _h(f"b{i}") % PRIME) for i in range(NUM_PERM)]


def minhash(sh: set) -> list:
    if not sh:
        return [PRIME] * NUM_PERM
    hashed = [_h(s) for s in sh]
    return [min((a * x + b) % PRIME for x in hashed) for a, b in _PERMS]


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def candidate_pairs(signatures: dict) -> set:
    """LSH: documents that share any band of their MinHash signature."""
    buckets = defaultdict(list)
    for key, sig in signatures.items():
        for band in range(BANDS):
            buckets[(band, tuple(sig[band * ROWS:(band + 1) * ROWS]))].append(key)
    pairs = set()
    for members in buckets.values():
        if 1 < len(members) <= 500:
            pairs.update(tuple(sorted(p)) for p in combinations(members, 2))
    return pairs


def similar_pairs(docs: dict, threshold: float = 0.5, exhaustive_up_to: int = 300):
    """docs: key -> shingle set. Returns [(a, b, jaccard)] with jaccard >= threshold.

    Small sets are compared pair by pair (exact). Larger sets use MinHash/LSH to find candidates first.
    """
    keys = [k for k, v in docs.items() if v]
    if len(keys) <= exhaustive_up_to:
        pairs = combinations(sorted(keys), 2)
    else:
        pairs = candidate_pairs({k: minhash(docs[k]) for k in keys})
    out = []
    for a, b in pairs:
        j = jaccard(docs[a], docs[b])
        if j >= threshold:
            out.append((a, b, j))
    return sorted(out, key=lambda t: (-t[2], t[0], t[1]))


def clusters(pairs, keys) -> dict:
    """Union-find over the pairs. Returns key -> cluster id (1, 2, ...) for keys that are in a pair."""
    parent = {k: k for k in keys}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b, _ in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    roots, out = {}, {}
    for k in sorted(keys):
        if any(k in (a, b) for a, b, _ in pairs):
            out[k] = roots.setdefault(find(k), len(roots) + 1)
    return out
