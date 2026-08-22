# Adversarial retrieval set — what to generate

Ordinary queries mostly test whether retrieval works when it's easy. An
adversarial set tests the failure modes that actually hurt in production —
generate at least a few examples of each:

- **Near-miss distractors.** A query where the corpus contains a document
  that's topically similar but factually wrong for this query (e.g. the
  refund policy for a *different* product tier). The retriever should rank
  the correct doc above the near-miss, not just "some relevant doc" above
  irrelevant noise.
- **Multi-hop.** A query whose answer requires combining facts from two or
  more separate documents, none of which alone contains the full answer.
  Tests whether retrieval surfaces *all* the needed docs, not just the one
  most textually similar to the query.
- **Negation.** A query containing a negation that flips which document is
  relevant (e.g. "policies that do NOT require a receipt" vs. "policies that
  require a receipt") — embedding similarity often ignores negation, so the
  wrong document frequently scores highest.
- **Entity confusion.** A query naming an entity that's easily confused with
  a similarly-named or spelled entity in the corpus (two products with
  overlapping names, two people/companies with similar names) — tests
  whether retrieval keys on the right entity or just topical similarity.

For each generated example, record: the query, the doc_id(s) that are
actually relevant (ground truth), and which adversarial category it belongs
to — the category matters later for diagnosing *why* recall is low on a
given query, not just that it is.
