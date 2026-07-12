# Teaching Brief: Naive RAG End-to-End Pipeline

## Description (as given by user)
Developing a naive RAG end to end pipeline demonstration in notebook.
We will use LangChain wrappers wherever possible.
- Accepts PDF files, URLs, or text files as document input. User can supply one or multiple files/URLs.
- Chunking via RecursiveCharacterTextSplitter.
- OpenAI `text-embedding-3-small` for embeddings.
- In-memory ChromaDB as the vector database (this completes the ingestion pipeline).
- When the user asks a question, the same embedding model converts it into a query vector.
- Similarity search is run against the vector database.
- Top 3 chunks are retrieved.
- Passed to the LLM with a strict instruction to answer using retrieved context only.
- Final answer is provided to the user.

## Steps (in order, each builds on the previous)
a) Ingestion — load PDF/URL/text inputs via LangChain loaders (PyPDFLoader, WebBaseLoader, TextLoader), split with RecursiveCharacterTextSplitter — added 2026-07-13
b) Embed chunks with OpenAI text-embedding-3-small and store in an in-memory ChromaDB collection — added 2026-07-13
c) Query — embed the user's question with the same embedding model, run similarity search, retrieve top 3 chunks — added 2026-07-13
d) Generation — pass retrieved chunks + question to gpt-4o-mini with a strict "answer using retrieved context only" instruction, print the final answer — added 2026-07-13

## Format
notebook

## Happy-path test case (user-approved)
User sets a list of local file paths / URLs in the notebook, runs the ingestion cells (load → recursive-split → embed with text-embedding-3-small → store in in-memory Chroma). User then sets a question string, runs the retrieval cell (top-3 similarity search), then runs the generation cell (gpt-4o-mini, answers strictly from retrieved context) and sees a final answer printed, grounded only in the uploaded documents.

## Observability
none

## Vector store
chromadb (in-memory)

## Constraints
- LangChain wrappers wherever possible (document loaders, text splitter, OpenAI embeddings/chat wrappers, Chroma vector store wrapper).
- OPENAI_API_KEY required (used for both embeddings and generation).
- Loaders: PyPDFLoader (PDF), WebBaseLoader (URL), TextLoader (plain text).
- Input method: file path / URL list variable near the top of the notebook (no upload widget).
- Retrieval: top-3 similarity search; LLM must be instructed to answer strictly from retrieved context only.

## Audience level
intermediate

## Decisions
- LLM for generation: OpenAI gpt-4o-mini (single-provider, alongside embeddings) — user's choice over an Anthropic-for-generation split.
- Document loaders: PyPDFLoader + WebBaseLoader + TextLoader (standard LangChain community loaders) over Unstructured loaders.
- Input method: plain Python list of file paths/URLs over ipywidgets upload widget.
- No Phoenix observability for this demo.

## Checkpoint status
- Description: approved
- Clarifications: approved
- Format: approved
- Happy-path test case: approved
- API key verification: verified (OPENAI_API_KEY, live gpt-4o-mini call succeeded)
- Observability: approved (none)
- Vector store: approved (chromadb, in-memory)
- Ready to generate: approved
- Build: complete
- Verify: complete
