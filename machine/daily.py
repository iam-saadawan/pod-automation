"""Daily unattended job (no live actions): rebuild missing packs at zero image cost,
queue new ones for cortex approval, refresh sales metrics, write machine/daily_report.md."""
import time
import engine, queue_export, metrics

def main():
    engine.build_all(max_images=0)
    queue_export.export()
    metrics.main()
    m = (engine.Path(__file__).parent / "metrics.json").read_text()
    (engine.Path(__file__).parent / "daily_report.md").write_text(f"# KAGE daily {time.strftime('%Y-%m-%d %H:%M')}\n\n```json\n{m}\n```\n")

if __name__ == "__main__":
    main()
