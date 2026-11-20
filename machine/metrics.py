"""Sales feedback loop (read-only): Printify orders -> revenue by design/niche -> recommendation."""
import collections, json, requests
import engine

def main():
    e = engine.ENV
    h = {"Authorization": f"Bearer {e['PRINTIFY_API_KEY']}"}
    r = requests.get(f"https://api.printify.com/v1/shops/{e['PRINTIFY_SHOP_ID']}/orders.json?limit=50", headers=h, timeout=30)
    orders = r.json().get("data", []) if r.status_code == 200 else []
    by = collections.Counter()
    for o in orders:
        for li in o.get("line_items", []):
            by[li.get("metadata", {}).get("title", "?").split(" | ")[0]] += li.get("quantity", 1)
    out = {"orders": len(orders), "units_by_design": dict(by.most_common()),
           "recommendation": (f"Double down on: {by.most_common(1)[0][0]} — generate 3 variants + 5 more pins."
                              if by else "No orders yet: keep posting; judge after ~200 pin impressions/design.")}
    (engine.Path(__file__).parent / "metrics.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
