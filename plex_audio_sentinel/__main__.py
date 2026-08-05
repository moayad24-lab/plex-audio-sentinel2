import argparse, logging, sys
from .config import Config
from .core import Summary, discover, process
from .integrations import refresh_plex, send_telegram

def main(argv=None):
    p=argparse.ArgumentParser(description="Scan a Plex media path and create stereo AC-3 companion files for multichannel audio.")
    p.add_argument("command", choices=("scan","process"), nargs="?", default="scan")
    p.add_argument("--dry-run", action="store_true", help="inspect only; do not replace media (default for scan)")
    p.add_argument("--config", action="store_true", help="validate environment and exit")
    p.add_argument("-v","--verbose",action="store_true")
    args=p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    try: cfg=Config.from_env().validate()
    except ValueError as e: p.error(str(e))
    if args.config: print("Configuration valid"); return 0
    dry=args.dry_run or args.command == "scan"
    summary=Summary()
    for path in discover(cfg.media_path,cfg.extensions):
        summary.scanned += 1; result=process(path,cfg,dry)
        if result in ("skipped",): summary.skipped += 1
        elif result in ("converted","would-convert"): summary.converted += 1
        else: summary.errors += 1
    print(summary.text())
    if not dry and summary.converted:
        try: refresh_plex(cfg.plex_url,cfg.plex_token,cfg.plex_section)
        except Exception as e: logging.error("Plex refresh failed: %s",e); summary.errors += 1
    try: send_telegram(cfg.telegram_token,cfg.telegram_chat_id,summary.text())
    except Exception as e: logging.error("Telegram report failed: %s",e); summary.errors += 1
    return 1 if summary.errors else 0
if __name__ == "__main__": sys.exit(main())
