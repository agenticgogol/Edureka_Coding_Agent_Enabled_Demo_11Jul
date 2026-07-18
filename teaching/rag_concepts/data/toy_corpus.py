"""Toy text/documents reused across every step of this notebook.

Keeping this in one shared module means every section (chunking,
embeddings, vector DBs, search, reranking, MMR) operates on the exact
same data, so a student can compare outputs across sections directly.
"""

TOY_PARAGRAPH = """\
The Amazon rainforest is the largest tropical rainforest in the world, covering \
much of northwestern Brazil and extending into Colombia, Peru, and other South \
American countries. It is home to an estimated 400 billion individual trees \
representing 16,000 species. The rainforest plays a critical role in regulating \
the Earth's climate by absorbing large amounts of carbon dioxide and releasing \
oxygen. Scientists often call it the "lungs of the planet" because of this \
role, although the rainforest itself also consumes a large share of the oxygen \
it produces through respiration and decomposition. Deforestation, driven \
largely by cattle ranching, logging, and agriculture, threatens the rainforest's \
biodiversity and its ability to store carbon. Indigenous communities have lived \
in the Amazon for thousands of years and rely on the forest for food, medicine, \
and shelter. Conservation efforts today combine satellite monitoring, \
reforestation projects, and policy changes to slow the rate of forest loss."""

# A small toy "document collection" used for the vector-DB / search /
# reranking / MMR sections — five short passages on related but distinct
# topics, each with metadata for filtering demos.
TOY_DOCUMENTS = [
    {
        "id": "doc1",
        "text": "The Amazon rainforest absorbs large amounts of carbon dioxide and is often called the lungs of the planet.",
        "metadata": {"topic": "climate", "source": "encyclopedia"},
    },
    {
        "id": "doc2",
        "text": "Deforestation in the Amazon is driven mainly by cattle ranching, logging, and agricultural expansion.",
        "metadata": {"topic": "deforestation", "source": "news"},
    },
    {
        "id": "doc3",
        "text": "Indigenous communities have lived in the Amazon rainforest for thousands of years, relying on it for food and medicine.",
        "metadata": {"topic": "culture", "source": "encyclopedia"},
    },
    {
        "id": "doc4",
        "text": "Python is a popular programming language known for its readability and used heavily in data science and AI.",
        "metadata": {"topic": "programming", "source": "blog"},
    },
    {
        "id": "doc5",
        "text": "Machine learning models like neural networks require large datasets and significant compute to train effectively.",
        "metadata": {"topic": "programming", "source": "blog"},
    },
    {
        "id": "doc6",
        "text": "Satellite monitoring and reforestation projects are two key strategies used to slow Amazon deforestation.",
        "metadata": {"topic": "deforestation", "source": "news"},
    },
    {
        "id": "doc7",
        "text": "Vector databases like Qdrant, ChromaDB, and FAISS store embeddings and support fast similarity search.",
        "metadata": {"topic": "programming", "source": "blog"},
    },
    {
        "id": "doc8",
        "text": "Climate change is accelerating the loss of biodiversity in tropical rainforests around the world.",
        "metadata": {"topic": "climate", "source": "news"},
    },
]

TOY_WORD = "rainforest"
TOY_QUERY = "How does deforestation affect the Amazon?"
