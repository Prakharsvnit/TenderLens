"""Download the two public demo RFPs from their official city websites into data/rfps/."""
import sys
import urllib.request
from pathlib import Path

RFPS = {
    "belle-isle-rfp-2026-04.pdf": "https://www.belleislefl.gov/sites/default/files/fileattachments/finance/page/10736/rfp_2026-04_information_technology_services_final.pdf",
    "dawsonville-25-rfp-001.pdf": "https://dawsonville-ga.gov/sites/default/files/fileattachments/city_clerk/page/10387/25-rfp-001_it_managed_services_final.pdf",
}

DEST = Path(__file__).resolve().parent.parent / "data" / "rfps"


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    for name, url in RFPS.items():
        target = DEST / name
        if target.exists():
            print(f"exists  {target}")
            continue
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
        if not data.startswith(b"%PDF"):
            print(f"error   {name}: response is not a PDF", file=sys.stderr)
            return 1
        target.write_bytes(data)
        print(f"saved   {target} ({len(data) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
