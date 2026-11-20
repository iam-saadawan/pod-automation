# KAGE — POD Automation Pipeline

*Last updated: 2026-09-09*

## What This Is

This is the **KAGE** print-on-demand automation project. It generates designs via AI, removes backgrounds, uploads to Printify, and syncs to a Shopify store.

**Store:** https://jmxvzh-87.myshopify.com/
**Brand:** KAGE (影 = shadow, Japanese) — dark streetwear, anime-inspired, character-driven
**Tagline:** "WEAR THE SHADOW"
**Status:** LIVE (18 products currently — all need to be deleted and replaced with new pipeline output)

## Before Any Task, Load Context

1. `/Users/saad/Second Brain/clients/kage/profile.md` — brand profile, stack, blockers
2. `/Users/saad/Second Brain/clients/kage/rules.md` — hard rules (IP, pricing, specs)
3. `/Users/saad/Second Brain/clients/kage/preferences.md` — design style preferences
4. `/Users/saad/Second Brain/skills/SKILL_BIBLE_print_on_demand.md` — Flux prompting, rembg fixes, print specs
5. `/Users/saad/Second Brain/skills/SKILL_BIBLE_shopify_seo.md` — listing copy guidelines

## The Stack

| Component | Details |
|-----------|---------|
| **Shopify Store** | https://jmxvzh-87.myshopify.com/ |
| **Shopify Theme** | "Kage" theme — dark background (#0D0F14), warm white text (#F6F1E7), gold accent (#FFD23F) |
| **Theme on disk** | `/Users/saad/copy-of-urban-vault-theme/` |
| **Printify Provider** | Monster Digital (ID 29) — 73 products available |
| **Image Generation** | Pollinations.ai (Flux) — using existing 0.5 Pollens balance. Migrate to fal.ai / Replicate later when exhausted. |
| **Background Removal** | rembg with isnet-general-use model |
| **Shopify Trial** | ~25 days left on $1.10/mo trial, then $45/mo. Evaluate at that point. |

## Pipeline Architecture

```
research.py → niches.json → designer.py → designs/ → uploader.py → Printify → Shopify
```

### Core Pipeline Files
| File | Purpose |
|------|---------|
| `research.py` | AI-powered niche research + concept generation. Uses Gemini API + eBay/Google trend scraping |
| `niches.json` | Working state: niche definitions + design concepts with image prompts |
| `designer.py` | Generates images via Pollinations Flux, removes backgrounds via rembg, quality checks |
| `uploader.py` | Uploads designs to Printify, creates draft products with variants |
| `run_all.py` | Chains: research → designer → uploader |

### Helper/Utility Scripts
| File | Purpose |
|------|---------|
| `publish_all.py` | Force-publishes all Printify products to Shopify |
| `publish_drafts.py` | Publishes only draft products |
| `unpublish_all.py` | Unpublishes all products |
| `slow_sync.py` | Publishes with 20s delays to avoid Shopify rate limits |
| `list_products.py` | Lists all Printify products |
| `check_status.py` | Checks product sync status |
| `check_printify_product.py` | Inspects a single product |
| `force_sync_one.py` | Force-syncs one product to Shopify |
| `find_blueprint.py` | Searches Printify blueprints |
| `list_colors.py` | Lists available colors for a blueprint |
| `get_shop_id.py` | Gets Printify shop ID |
| `remove_bg.py` | Standalone background removal tool |
| `upscale.py` | Image upscaling (Real-ESRGAN style) |
| `test_poll.py` | Tests Pollinations API |

## Available Product Types (Monster Digital, Provider 29)

### Currently In Use
| Product | Blueprint ID | Price |
|---------|-------------|-------|
| Unisex Heavy Cotton Tee | 6 | $22.99 |
| Unisex Heavy Blend™ Hoodie | 77 | $39.99 |

### Planned Additions
| Product | Blueprint ID | Suggested Price |
|---------|-------------|----------------|
| Crewneck Sweatshirt | 49 | $34.99 |
| Jersey Tank Top | 39 | $19.99 |
| Long Sleeve Tee | 41 | $27.99 |
| Oversized Boxy Tee | 1382 | $24.99 |
| Canvas Tote Bag | 1313 | $14.99 |

### Other Available (not yet used)
Mugs (478, 479), Women's tees (14, 88, 2053, 3043), Youth (81, 157, 417, 420), Zip hoodies (66, 445), Garment-dyed (706, 1296, 1298, 1476), and 50+ more. Full list via `find_blueprint.py`.

## Environment Variables (.env)
```
PRINTIFY_API_KEY=...
PRINTIFY_SHOP_ID=28133194
BLUEPRINT_ID=6
PRINT_PROVIDER_ID=29
GEMINI_API_KEY=...
POLLINATIONS_API_KEY=...
# TODO: Add FAL_AI_KEY after signup at https://fal.ai
```

## ⚠️ PENDING OVERHAUL — READ THIS FIRST

**The entire pipeline is about to be overhauled.** Here's what needs to happen:

### 1. Delete All Existing Products
- All 18 current products use the old "Urban Vault" branding and have rembg quality issues
- Create `cleanup.py` to delete all via Printify API
- Start fresh with the new pipeline

### 2. Image API: Pollinations.ai First (0.5 Pollens remaining)
- User currently has 0.5 Pollens (~$0.50) on Pollinations.ai.
- Generate initial flagship drops with Pollinations.ai.
- When Pollens run out, migrate to fal.ai / Replicate as needed.

### 3. Smart Color Matching (Kill the rembg Problem)
Two modes per design concept in `niches.json`:

| Mode | What It Does |
|------|-------------|
| `"matched"` | Generate design on a colored background (black, navy, etc). **Skip rembg entirely**. Only list on matching shirt color. Premium quality, design looks like part of the shirt. |
| `"transparent"` | Keep current flow: white bg → rembg → transparent PNG. Works on any shirt color. Use for clean vector/logo designs only. |

**Color distribution per niche (6-8 concepts):**
- 2-3 on black bg → Black shirts
- 1-2 on navy/charcoal bg → Navy/Dark Heather shirts
- 1 on forest/maroon bg → accent color variety
- 1-2 transparent → universal (any color)

### 4. Premium 3D-Style AI Mockups
After creating each product, generate 4 premium mockup images via Pollinations:
1. **Floating 3D render** — shirt floating in mid-air, dramatic shadows, dark gradient bg
2. **Dark studio flat-lay** — folded on matte black surface, spotlight, minimal
3. **Ghost mannequin** — invisible form, dark backdrop, rim lighting
4. **Close-up detail** — tight crop on print, fabric texture, shallow DOF

Upload mockups as additional Printify product images to replace generic flat-lays.

### 5. Multi-Niche System
Replace single-niche `niches.json` with 5 niches:
- 🎌 **Anime & Manga** — dark anime, cel-shaded, Japanese streetwear
- 🚗 **JDM & Automotive** — drift culture, midnight racing, clean line art
- 🎮 **Retro Gaming** — dark pixel art, glitch aesthetic (not cute cartoon)
- 🌌 **Cosmic & Space** — sci-fi, nebula colors (cross-promote with Cosmic Vault YouTube)
- 💀 **Dark & Horror** — kawaii horror, skull art, yokai, tattoo flash

### 6. Expanded Product Types
Each design → 2-3 product types automatically:
- Bold anime/dark art → Tee + Hoodie + Oversized Boxy
- Minimal logos → Tee + Crewneck + Tank
- Cosmic/detailed → Tee + Long Sleeve + Tote Bag
- 30 designs × 2-3 products each = 60-90 products

### 7. Shopify Collections
Create automated collections based on product tags:
- `anime-manga` → Anime & Manga
- `jdm-auto` → JDM & Automotive
- `retro-gaming` → Retro Gaming
- `cosmic-space` → Cosmic & Space
- `dark-horror` → Dark & Horror

Update nav: HOME | ANIME | JDM | GAMING | COSMIC | DARK

### 8. Brand Updates
- All descriptions: "Urban Vault" → "KAGE"
- Tagline: "WEAR YOUR OBSESSION" → "WEAR THE SHADOW"
- Update `research.py` creative director persona

## New Files To Create
- `cleanup.py` — deletes all existing Printify products
- `mockup_generator.py` — generates premium 3D-style mockup images via Pollinations

## Files To Modify
- `niches.json` — multi-niche structure with bg_mode, bg_color, shirt_colors, product_types
- `designer.py` — Pollinations API, bg_mode branching, skip rembg for matched designs
- `uploader.py` — smart color selection, multi-product types, mockup upload, niche tags
- `research.py` — KAGE branding, multi-niche awareness

## Related Projects
- `/Users/saad/MoneyPrinterTurbo/` — "The Cosmic Vault" YouTube automation (space/science videos)
- `/Users/saad/copy-of-urban-vault-theme/` — Shopify theme files on disk
- `/Users/saad/AI chat bot for businesses/` — Pathway2Care NDIS chatbot (separate project)
