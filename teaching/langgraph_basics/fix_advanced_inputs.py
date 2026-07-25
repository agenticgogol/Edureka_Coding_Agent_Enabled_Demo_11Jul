import json
from pathlib import Path

p = Path("teaching/langgraph_basics/langgraph_advanced.ipynb")
nb = json.loads(p.read_text())
for cell in nb["cells"]:
    if cell.get("cell_type") == "code":
        text = "".join(cell["source"])
        text = text.replace('"steps": 0}', '"steps": 0, "max_steps": 4}')
        text = text.replace('"steps": 0, "max_steps": 4, "max_steps": 4', '"steps": 0, "max_steps": 4')
        cell["source"] = text.splitlines(True)
p.write_text(json.dumps(nb, indent=1) + "\n")
print("fixed agent inputs")
