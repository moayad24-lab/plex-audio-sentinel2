"""Orchestration: discovery, baseline state, and per-file processing."""
import logging

from .core import Summary, build_output_map, discover, process
from .state import State, StateError, default_state_path


def run(cfg, dry_run=False, proc=None, logger=None):
    """Scan cfg.media_path and process only source paths not yet recorded in state.

    First real run: every discovered source media path is recorded into the
    durable state file (the baseline) and nothing is processed, so existing
    library files are never touched. Later runs: only paths absent from the
    state are probed and processed. A path is recorded as seen once it was
    converted or skipped as ineligible; conversion errors are never recorded,
    so failed files are retried on the next run.

    Only source media paths are ever tracked: the output folder
    (cfg.output_path) is excluded from discovery even when nested under the
    media root, so generated companions are never considered new sources. The
    collision-safe source -> companion mapping is attached to cfg.output_names
    for core.process to use.

    proc(path, cfg, dry_run=False) returns "converted", "would-convert",
    "skipped", or "error"; it defaults to core.process and can be injected
    for tests. run() always passes its own dry_run flag through to proc, so
    an injected processor must accept the dry_run keyword (a default of
    False keeps simple fakes compatible).
    """
    log = logger or logging.getLogger(__name__)
    proc = proc or process
    state_path = cfg.state_file or default_state_path(cfg.media_path)
    output_dir = (cfg.output_path or "").strip()
    sources = sorted(discover(cfg.media_path, cfg.extensions, exclude_dir=output_dir or None))
    if output_dir:
        cfg.output_names = build_output_map(sources, output_dir, cfg.media_path)
    summary = Summary(scanned=len(sources))

    try:
        state = State.load(state_path)
    except FileNotFoundError:
        state = None
    except StateError:
        raise

    if state is None:
        if dry_run:
            summary.new = summary.scanned
            log.warning(
                "no state file at %s; the first real run will record a baseline "
                "of %d file(s) and convert nothing",
                state_path, summary.scanned,
            )
            return summary
        state = State(state_path)
        state.mark_many(sources)
        state.save()
        summary.baseline_created = True
        summary.ignored = summary.scanned
        log.info(
            "baseline created: recorded %d source media file(s) in %s; "
            "0 conversions performed (existing library files are never processed)",
            summary.scanned, state_path,
        )
        return summary

    dirty = False
    for path in sources:
        if state.contains(path):
            summary.ignored += 1
            continue
        summary.new += 1
        result = proc(path, cfg, dry_run=dry_run)
        if result in ("converted", "would-convert"):
            summary.converted += 1
        elif result == "skipped":
            summary.skipped += 1
        else:
            summary.errors += 1
        if not dry_run and result in ("converted", "skipped"):
            state.mark(path)
            dirty = True
    if not dry_run and dirty:
        state.save()
    return summary
