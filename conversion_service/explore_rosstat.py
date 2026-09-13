import re
import requests
import warnings

warnings.filterwarnings("ignore")
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"}
r = requests.get(
    "https://rosstat.gov.ru/compendium/document/50798",
    headers=headers,
    verify=False,
    timeout=30,
)
html = r.text

pattern = re.compile(r'<div class="toggle-card__title">(.*?)</div>', re.DOTALL)
titles = [(m.start(), m.group(1).strip()) for m in pattern.finditer(html)]

# Print all titles with their byte representations to understand what we're dealing with
with open("titles_bytes.txt", "w", encoding="utf-8") as f:
    for i, (pos, t) in enumerate(titles):
        f.write(f"[{i}] pos={pos}: {repr(t)}\n")
        f.write(f"     bytes: {t.encode('utf-8').hex()}\n")

print("Written to titles_bytes.txt")

# Also test matching approach: check what "оценке" looks like
# The word "оценке" in UTF-8: о=d0be, ц=d186, е=d0b5, н=d0bd, к=d0ba, е=d0b5
target_bytes = bytes.fromhex("d0bed186d0b5d0bdd0bad0b5")  # оценке
target_word = target_bytes.decode("utf-8")
print(f"Target word: {target_word!r}")

for i, (pos, t) in enumerate(titles):
    if target_word in t:
        print(f"  Found in [{i}]: {t!r}")
