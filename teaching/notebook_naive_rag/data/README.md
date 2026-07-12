# Sample data

- `company_handbook.txt` — a small synthetic employee handbook (leave
  policy, remote work, expense reimbursement, performance reviews,
  equipment policy). Used as the default `.txt` input in `notebook.ipynb`
  via `TextLoader`.
- `product_faq.pdf` — a small synthetic product FAQ (battery life, charge
  time, payload capacity, warranty) rendered as a real PDF. Used as the
  default `.pdf` input via `PyPDFLoader`.

Both files are intentionally small and self-contained so the notebook
runs end to end without requiring the user to supply their own documents
first. Swap the `SOURCES` list at the top of `notebook.ipynb` with your
own local file paths and/or URLs to try it on real content.
