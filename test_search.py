from worker_headless import HeadlessWorker
from nerves._async_utils import run_async_safely

w = HeadlessWorker(headless=True)
for q in ["OpenAI news", "prix Bitcoin EUR", "actualités IA 2026"]:
    r = run_async_safely(w.search_and_extract_leads(q, limit=5))
    print(f"\n=== {q} → {len(r)} résultats ===")
    for item in r[:3]:
        print(f"  - {item['title'][:60]}")
        print(f"    {item['source_url'][:80]}")