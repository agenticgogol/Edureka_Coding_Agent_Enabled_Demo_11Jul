"""Dummy knowledge base for the retrieval_techniques notebook.

Scenario: "Aurora Robotics" is a fictional company that sells consumer
drones. Its internal knowledge base has three shapes of data on purpose,
because different retrieval techniques exist to handle different shapes:

1. HANDBOOK_SECTIONS - one long, structured policy document (warranty +
   returns), broken into parent sections and child paragraphs. Used for
   parent-child retrieval and neighbor expansion, where the answer to a
   question lives across more than one small chunk.
2. KB_DOCUMENTS - ~20 short, independent passages (FAQs, product specs,
   support notes) spanning several topics/departments, with metadata
   (topic, doc_type, department, date). Includes a couple of
   near-duplicate passages on purpose, to make deduplication visible.
   Used for dense/sparse/hybrid search, metadata filtering, reranking,
   MMR, query rewriting/multi-query/decomposition, relevance grading,
   iterative retrieval, and the experimental techniques.
3. PRODUCT_CATALOG - a small structured table (product, category, price,
   stock, warehouse) loaded into an in-memory SQLite DB. Used for SQL
   retrieval, and for compound questions that need both KB text and SQL.

QUERIES maps each technique to a representative user question so every
section of the notebook runs against a concrete, realistic query instead
of an abstract one.
"""

# ---------------------------------------------------------------------------
# 1. Long structured document: parent sections -> child paragraphs
# ---------------------------------------------------------------------------
HANDBOOK_SECTIONS = [
    {
        "section_id": "sec1",
        "heading": "Warranty Coverage",
        "paragraphs": [
            "Aurora Robotics drones are covered by a standard 12-month "
            "limited warranty starting from the date of purchase, not the "
            "date of first flight. The warranty covers manufacturing "
            "defects in the motors, flight controller, and battery cells.",
            "The warranty does NOT cover crash damage, water damage, "
            "damage from unauthorized firmware modifications, or normal "
            "wear items such as propellers and landing gear skids.",
            "Customers who purchase the Aurora Care+ add-on at checkout "
            "receive an extended 24-month warranty that also covers up to "
            "two accidental crash incidents per year.",
        ],
    },
    {
        "section_id": "sec2",
        "heading": "Warranty Claim Process",
        "paragraphs": [
            "To file a warranty claim, a customer must first register "
            "their drone's serial number in the Aurora app and describe "
            "the defect. This opens a support ticket with a claim ID.",
            "Aurora support reviews the claim within 3 business days. If "
            "approved, the customer receives a prepaid shipping label to "
            "send the drone to the Austin repair facility.",
            "Repaired or replacement units are shipped back within 10 "
            "business days of the drone arriving at the repair facility. "
            "Aurora Care+ customers get expedited 5-business-day service.",
        ],
    },
    {
        "section_id": "sec3",
        "heading": "Return Policy",
        "paragraphs": [
            "Unopened drones may be returned for a full refund within 30 "
            "days of delivery. Opened drones may be returned within 15 "
            "days as long as all original accessories are included.",
            "Refunds are issued to the original payment method within 5-7 "
            "business days after Aurora receives the returned unit at "
            "its Austin fulfillment center.",
            "Custom-configured drones (special paint, engraved plates) "
            "are final sale and are not eligible for return, only for "
            "warranty repair under Section 1.",
        ],
    },
]

# ---------------------------------------------------------------------------
# 2. Short independent KB passages (with two intentional near-duplicates:
#    kb_003 and kb_017 both restate the return window, in different words)
# ---------------------------------------------------------------------------
KB_DOCUMENTS = [
    {"id": "kb_001", "text": "The Aurora Nimbus X200 is a consumer camera drone with a 4K 60fps camera, 31-minute flight time, and a 6 km video transmission range.", "metadata": {"topic": "product_specs", "doc_type": "spec_sheet", "department": "product", "date": "2025-11-02"}},
    {"id": "kb_002", "text": "The Aurora Nimbus X200 Pro adds obstacle avoidance sensors on all six sides and a larger 5000 mAh battery for a 38-minute flight time.", "metadata": {"topic": "product_specs", "doc_type": "spec_sheet", "department": "product", "date": "2025-11-02"}},
    {"id": "kb_003", "text": "You can return an unopened Nimbus drone within 30 days of delivery for a complete refund, no questions asked.", "metadata": {"topic": "returns", "doc_type": "faq", "department": "support", "date": "2026-01-15"}},
    {"id": "kb_004", "text": "Firmware version 3.2 for the Nimbus X200 fixed a GPS drift bug and improved obstacle avoidance latency by 40ms.", "metadata": {"topic": "firmware", "doc_type": "release_notes", "department": "engineering", "date": "2026-03-10"}},
    {"id": "kb_005", "text": "The Aurora app supports flight logs, live telemetry overlay, and no-fly-zone warnings pulled from an FAA database updated weekly.", "metadata": {"topic": "software", "doc_type": "faq", "department": "product", "date": "2025-09-20"}},
    {"id": "kb_006", "text": "Propellers on the Nimbus line are rated for approximately 100 flight hours before Aurora recommends replacing them.", "metadata": {"topic": "maintenance", "doc_type": "faq", "department": "support", "date": "2025-08-05"}},
    {"id": "kb_007", "text": "Aurora's warranty explicitly excludes crash damage and water damage unless the customer purchased the Aurora Care+ add-on.", "metadata": {"topic": "warranty", "doc_type": "policy", "department": "support", "date": "2026-01-15"}},
    {"id": "kb_008", "text": "Batteries should be stored at 40-60% charge if the drone will not be flown for more than two weeks, to preserve battery health.", "metadata": {"topic": "maintenance", "doc_type": "faq", "department": "support", "date": "2025-08-05"}},
    {"id": "kb_009", "text": "The EU warehouse in Rotterdam handles all returns and warranty shipments for customers in the European Union.", "metadata": {"topic": "logistics", "doc_type": "faq", "department": "support", "date": "2025-10-01"}},
    {"id": "kb_010", "text": "Aurora Robotics was founded in 2019 and is headquartered in Austin, Texas, with a secondary office in Rotterdam.", "metadata": {"topic": "company", "doc_type": "about", "department": "marketing", "date": "2025-01-10"}},
    {"id": "kb_011", "text": "The Nimbus X200 uses a 1/1.3-inch CMOS sensor, noticeably larger than the 1/2-inch sensor in Aurora's older Sprite line.", "metadata": {"topic": "product_specs", "doc_type": "spec_sheet", "department": "product", "date": "2025-11-02"}},
    {"id": "kb_012", "text": "Aurora Care+ extends the warranty to 24 months and covers up to two accidental crash incidents per year at no extra cost.", "metadata": {"topic": "warranty", "doc_type": "policy", "department": "support", "date": "2026-01-15"}},
    {"id": "kb_013", "text": "Support tickets for warranty claims are typically reviewed within 3 business days, per Aurora's internal SLA.", "metadata": {"topic": "warranty", "doc_type": "policy", "department": "support", "date": "2026-01-15"}},
    {"id": "kb_014", "text": "The Aurora app is available on iOS 15+ and Android 11+, and requires a account login to activate flight telemetry.", "metadata": {"topic": "software", "doc_type": "faq", "department": "product", "date": "2025-09-20"}},
    {"id": "kb_015", "text": "Custom-configured drones with engraved plates or special paint jobs are final sale and cannot be returned.", "metadata": {"topic": "returns", "doc_type": "policy", "department": "support", "date": "2026-01-15"}},
    {"id": "kb_016", "text": "Aurora's customer support team can be reached via in-app chat, email, or phone, Monday-Saturday, 8am-8pm Central Time.", "metadata": {"topic": "support", "doc_type": "faq", "department": "support", "date": "2025-07-12"}},
    {"id": "kb_017", "text": "As long as the drone box has not been opened, customers get a full 30-day return window from the delivery date.", "metadata": {"topic": "returns", "doc_type": "faq", "department": "support", "date": "2026-01-20"}},
    {"id": "kb_018", "text": "The Sprite Mini is Aurora's entry-level indoor drone, designed for beginners and priced under $100.", "metadata": {"topic": "product_specs", "doc_type": "spec_sheet", "department": "product", "date": "2025-06-18"}},
    {"id": "kb_019", "text": "Replacement propellers, batteries, and props guards can be purchased directly from the Aurora online store.", "metadata": {"topic": "maintenance", "doc_type": "faq", "department": "support", "date": "2025-08-05"}},
    {"id": "kb_020", "text": "Aurora publishes quarterly sustainability reports covering e-waste recycling programs for returned drone batteries.", "metadata": {"topic": "company", "doc_type": "about", "department": "marketing", "date": "2025-12-01"}},
]

# ---------------------------------------------------------------------------
# 3. Structured product catalog -> loaded into SQLite for SQL retrieval
# ---------------------------------------------------------------------------
PRODUCT_CATALOG = [
    # (product_name, category, price_usd, stock_units, warehouse)
    ("Nimbus X200", "camera_drone", 599.00, 42, "Austin"),
    ("Nimbus X200 Pro", "camera_drone", 899.00, 17, "Austin"),
    ("Nimbus X200", "camera_drone", 599.00, 30, "Rotterdam"),
    ("Nimbus X200 Pro", "camera_drone", 899.00, 8, "Rotterdam"),
    ("Sprite Mini", "indoor_drone", 89.00, 210, "Austin"),
    ("Sprite Mini", "indoor_drone", 89.00, 95, "Rotterdam"),
    ("Aurora Care+ (1yr)", "warranty_addon", 79.00, 9999, "Austin"),
    ("Replacement Propeller Set", "accessory", 14.00, 500, "Austin"),
    ("Replacement Battery (Nimbus)", "accessory", 59.00, 120, "Austin"),
    ("Replacement Battery (Nimbus)", "accessory", 59.00, 40, "Rotterdam"),
]

# ---------------------------------------------------------------------------
# 4. Representative user queries, one per technique
# ---------------------------------------------------------------------------
QUERIES = {
    "dense": "How do I take care of my drone battery so it lasts longer?",
    "sparse_bm25": "firmware version 3.2 GPS drift",
    "hybrid": "Nimbus X200 warranty crash damage",
    "metadata_filter": "What does the support team say about returns?",
    "parent_child": "Walk me through the entire warranty claim process from filing to getting my drone back.",
    "neighbor_expansion": "What happens after Aurora approves my warranty claim?",
    "rrf": "Nimbus X200 obstacle avoidance",
    "cross_encoder_rerank": "Can I get a refund if I already opened the box?",
    "dedup": "What is Aurora's return window?",
    "mmr": "Tell me about Aurora's drones and policies.",
    "query_rewriting": "ret window 4 unopened nimbus??",
    "multi_query": "How does Aurora's warranty work and how is it different from the return policy?",
    "query_decomposition": "If my Nimbus X200 Pro breaks after 6 months, is it covered, and how long would a repair take?",
    "relevance_grading": "What is the capital of France?",
    "iterative_retrieval": "How long does the whole process take if my drone breaks and I want it fixed under warranty?",
    "sql_retrieval": "How many Nimbus X200 Pro units are in stock in Rotterdam, and what do they cost?",
    "web_fallback": "What are the latest FAA drone regulation changes announced in 2026?",
    "experimental": "What's the difference between the Nimbus X200 and the Sprite Mini?",
}
