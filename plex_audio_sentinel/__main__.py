import argparse, logging, sys
from .config import Config
from .integrations import refresh_plex, send_telegram
from .runner import run
from .state import StateError

def main(argv=None):
    p=argparse.ArgumentParser(description="Scan a Plex media path and create stereo AC-3 companion files for multichannel audio. The first real run records a baseline of every discovered source file and converts nothing; later runs only process files added after the baseline.")
    p.add_argument("command", choices=("scan","process"), nargs="?", default="scan")
    p.add_argument("--dry-run", action="store_true", help="inspect only; never write state or media (default for scan)")
    p.add_argument("--config", action="store_true", help="validate environment and exit")
    p.add_argument("-v","--verbose",action="store_true")
    args=p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    try: cfg=Config.from_env().validate()
    except ValueError as e: p.error(str(e))
    if args.config:
        print(f"Configuration valid (state file: {cfg.state_file}, output path: {cfg.output_path})"); return 0
    dry=args.dry_run or args.command == "scan"
    try:
        # runner.run propagates dry_run to core.process itself.
        summary=run(cfg, dry_run=dry, logger=logging.getLogger(__name__))
    except StateError as e:
        print(f"error: {e}", file=sys.stderr); return 1
    except Exception as e:
        logging.error("run failed: %s", e); return 1
    print(summary.text())
    if not dry and summary.converted:
        try: refresh_plex(cfg.plex_url,cfg.plex_token,cfg.plex_section)
        except Exception as e: logging.error("Plex refresh failed: %s",e); summary.errors += 1
    try: send_telegram(cfg.telegram_token,cfg.telegram_chat_id,summary.text())
    except Exception as e: logging.error("Telegram report failed: %s",e); summary.errors += 1
    return 1 if summary.errors else 0
if __name__ == "__main__": sys.exit(main())
