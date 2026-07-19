# Print on Demand (POD) Automation Pipeline

This repository contains the end-to-end Python automation pipeline for our Print on Demand business, heavily utilizing the Gemini API to ideate, generate, and process artwork.

## Core Scripts
- `research.py`: Analyzes current market trends and selects profitable niches (e.g., sarcastic introvert themes) from `niches.json`.
- `designer.py`: Takes the chosen niche, queries the Gemini API for highly detailed image generation prompts, and utilizes the Imagen model to generate the raw design assets.
- `remove_bg.py`: Automatically processes the generated images, removing backgrounds to make them print-ready for apparel.
- `upscale.py`: Enhances the resolution of the designs to meet the high DPI requirements for professional printing on platforms like Printify or Printful.
- `run_all.py`: The master orchestrator. Runs the entire pipeline sequentially (Research -> Design -> Background Removal -> Upscaling) and updates `designs/manifest.json` with the final assets and their generated titles/descriptions for the storefront.

## Workflow
1. Run `python run_all.py`
2. Wait for the pipeline to finish processing.
3. Check the `designs/` folder for transparent, upscaled, ready-to-upload PNG files.
4. Use `manifest.json` to copy the generated titles and descriptions for your Shopify store.
