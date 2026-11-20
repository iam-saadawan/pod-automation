# MONEY MACHINE REPORT — KAGE Growth Engine

Written 2026-09-21. **No revenue exists yet.** What exists is a tested prototype that removes the two
things standing between the KAGE store and its first sale: (1) an empty storefront and (2) zero traffic.
Nothing has been published or posted. Every outward action is a button you click.

---

## 1. Decision: Path D (A + B + dashboard)

Recon showed the pod pipeline (designs, mockups, Printify upload) was already built, and the old 18 products
were already deleted (Printify shop had 0 products). The missing piece was **traffic**: the cortex marketing
bots only read *live* products, and the store had none. So I built the layer between them:

`8 designs → 27 Printify drafts → per-design content packs (pins + 9:16 video + copy) → approval dashboard → you click publish/post`

Why not the alternatives tonight: B (MoneyPrinterTurbo) already runs autonomously for a different channel
(Cosmic Vault) and is not the bottleneck. C (chatbot B2B) is blocked on domain + email deliverability (per
cortex `PROJECT_STATUS.md`), which needs you, not code.

## 2. What I built (all in `~/pod-automation/machine/`)

| File | Does |
|---|---|
| `engine.py` | Builds a content pack per design: Pollinations backdrops, real-mockup composites, Pinterest pins (1000×1500), 8s 9:16 video with music, LLM copy |
| `kage.py` | CLI: `packs`, `drafts`, `dashboard`, `status` |
| `dashboard.py` | Local approval UI at http://127.0.0.1:8765 (loopback only). Live connection checks, 27 draft products with **Publish to Shopify** buttons, all pins/videos with **Post pin** buttons. Both confirm before acting |
| `queue_export.py` | Hands packs to cortex's approval queues (`~/.automaton/control/queue`). Queue-only. Tested: 24 pins + 8 videos queued |
| `metrics.py` | Read-only sales feedback loop from Printify orders, with a double-down recommendation. Tested (0 orders yet) |
| `daily.py` + `com.kage.daily.plist` | Unattended daily job (packs at zero image cost → cortex queue → metrics → `daily_report.md`). Tested manually; idempotent (2nd run queued 0). Schedule NOT installed: `cp ~/pod-automation/machine/com.kage.daily.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.kage.daily.plist` |
| `run_machine.sh` | One command: build missing packs, print status, open dashboard |

### Tested tonight
- 8 content packs generated (24 pins, 8 videos) in `machine/out/`. Videos verified: 8s, H.264 + audio.
- 27 Printify **drafts** created via the existing `uploader.py`. Verified 0/27 have an `external` link and the live
  storefront `/products.json` is empty, so nothing is on the store.
- Dashboard verified: serves 200, video streams, path traversal returns 404, bound to 127.0.0.1.
- **Not tested:** clicking Publish or Post pin (deliberately: they are live actions). Pinterest posting cannot work until the token is renewed.

### Bugs found and fixed while building
- `zoompan` on looped input made a 305s/44MB video → feed single frames (now 8s/1.6MB).
- Image model invented a face print on the shirt in lifestyle scenes → **would have advertised a product we don't sell**. Scenes are now garment-free backdrops with the *real* mockup composited on top.
- Printify `visible:true` is set even on unpublished products → dashboard now uses `external` to decide draft vs live.
- Dashboard said Gemini was "connected" because a key existed → now a live check.

### Design review (visual check of the 8 mockups)
- **Ready to publish:** kage_glitch_01, kage_glitch_02, kage_ronin_01, kage_ronin_02.
- **Hold back:** kage_drift_01 (mockup shows a blank shirt), kage_observer_01 (garbled text in print), kage_observer_02 (print too faint).
- **Marginal:** kage_drift_02 (speedometer).
- Publishing was attempted for the 4 ready designs but blocked by the permission system; still 0 live products. Publish via the dashboard buttons.
- Correction: publishing is reversible (`unpublish_all.py`); earlier "can't be undone" was overstated.

## 3. Asset and credential findings (names only; no values were printed)

| Service | State |
|---|---|
| Pollinations | Key works (image generation confirmed). Key **cannot read its balance** (no `account:usage` permission), so I metered spend myself in `machine/ledger.json`: **16 images used tonight**. Balance was noted as ~0.5 pollen in `CLAUDE.md`; check it at pollinations.ai |
| Printify | OK. `PRINTIFY_SHOP_ID` = "My Shopify Store" (Shopify channel). A second shop, "Urban Vault" (eBay), exists |
| Gemini (`pod-automation/.env`) | **Rejected (HTTP 401).** Key format `AQ.…` isn't a valid Generative Language key. `research.py` depends on it, so it is probably broken. Copy generation uses Groq instead |
| Groq (cortex) | Works (`openai/gpt-oss-20b`) |
| Pinterest | **Token expired (401).** Renew: developers.pinterest.com, scopes `pins:write boards:read`, then `cortex-bots/.env` |
| TikTok | Saved session file exists (not live-verified) |
| Instagram / YouTube | Tokens present, not live-verified |
| Second Brain `.env` | All keys empty |

**Security notes:** `cortex-bots/PROJECT_STATUS.md` contains plaintext admin/demo dashboard passwords; `.env.example` files
in cortex and the chatbot repo have populated values (may be real keys, so check and blank them). Rotate if these repos are ever pushed anywhere shared.

## 4. Cortex map (what already exists)

- **CEO (cortex brain)** wakes hourly, reviews manager reports, writes ideas to Second Brain, pitches you on Telegram.
- **Cortana**: B2B chatbot/website sales. Workers: lead-hunter, demo-seeder, demo-screenshot-builder, overview-generator, cold-pitcher, demo-sweeper. Blocked on domain + Brevo + warm-up.
- **Kage Marketing**: seo-writer, pinterest-marketer, tiktok-marketer, instagram-marketer (all pull *live* products; they will start working once products are published).
- **Content Studio**: content-creator, video-content-creator, story-weaver, clip-farmer. **Affiliate Marketing**: pinterest-affiliate. **Paper Trading**: paper-trader.

**Cortex integration:** `kage.py queue` feeds the cortex queues. I did not write a new cortex bot that consumes them or auto-runs `metrics`; both are CLI-run.

## 5. Ideas brainstormed (not built)

1. **Character-drop drip**: release one character per week with a 3-post story arc (fits the Shadow Ronin / Drift Ghost / Glitch Skull / Observer lore already in `niches.json`).
2. **Cosmic Vault cross-sell**: Observer designs pitched in the Cosmic Vault Shorts' pinned comment / description.
3. **Winner amplifier**: read Shopify order data weekly; auto-generate 5 more variants of the best seller's niche.
4. **Custom-order chatbot** on the store using the existing chatbot SaaS (upsell + support).
5. **Demo-per-lead for streetwear micro-brands**: the existing demo-seeder pitched to other small POD stores.

## 6. How to run it

```bash
cd ~/pod-automation && ./machine/run_machine.sh     # opens the dashboard
venv/bin/python machine/kage.py status              # connection check only
venv/bin/python machine/kage.py packs --max-images 0   # rebuild packs, zero image cost (uses cached backdrops)
```

First actions when you're back (≈15 min): (1) open the dashboard, look at the packs; (2) renew the Pinterest token;
(3) publish the 6–9 products you like best (Publish buttons); (4) post pins; (5) upload `video.mp4` files to TikTok/Reels/Shorts by hand or via the existing Upload-Post flow.

## 7. 30-day roadmap (honest expectations)

New store + no audience: the first sale usually needs consistent traffic for several weeks. Treat week 1-2 as distribution, not revenue.

- **Days 1-3:** publish best 9 products; fix Pinterest token; post 3 pins/day and 1 video/day. Confirm a test order through checkout.
- **Days 4-10:** Post daily. Turn on the Kage Marketing bots (they now have live products). Fix Gemini key so `research.py` works.
- **Days 11-20:** Read Shopify analytics + Pinterest data; identify the top niche/character; generate 2-3 new designs in it; expand product types.
- **Days 21-30:** Decide on Shopify's $45/mo plan using real traffic/orders data (trial ends ~early Oct). Consider a small paid-ad test only if organic conversion > 0.
- **Parallel track (needs you):** domain + Brevo for the chatbot B2B business, which has higher revenue per sale ($99-$799) than a T-shirt.

## 8. Known limits

- 8 designs is a tiny catalogue; the machine's design generation step (`run_all.py`) was not re-run tonight.
- Backdrops are a shared pool of 2 images; add variety by running `packs --max-images 4` after deleting `machine/backdrops/*.jpg`.
- Feedback loop reports only; it doesn't yet auto-generate variants (idea #3).
- Dashboard was not visually reviewed in a browser, only via HTTP checks.
