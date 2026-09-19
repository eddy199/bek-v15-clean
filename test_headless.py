from worker_headless import HeadlessWorker
from nerves._async_utils import run_async_safely

w = HeadlessWorker(headless=True)
r = run_async_safely(w.fetch_page_content("https://example.com"))
print("Type:", type(r))
print("Résultat:", str(r)[:500] if r else "None / vide")