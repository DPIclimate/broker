import importlib.util
import logging
from pathlib import Path
import sqlalchemy as sqla
import subprocess

# Only imported for the side-effect of setting up the logging system.
import util.LoggingUtil

import quality


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def load_plugins(plugin_dir):
    """
    Load all Python files from a directory as plugins.

    Args:
        plugin_dir: Path to the directory containing plugin files

    Returns:
        dict: Dictionary mapping plugin names to loaded modules
    """
    logger.info(f'Searching for plugins at {plugin_dir}')

    plugins = {}

    if not plugin_dir.exists():
        logger.error(f"Plugin directory {plugin_dir} does not exist")
        return plugins

    for filepath in plugin_dir.glob("*.py"):
        if filepath.name == "__init__.py":
            continue

        module_name = filepath.stem
        spec = importlib.util.spec_from_file_location(module_name, filepath)

        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
                plugins[module_name] = module
                logger.info(f"Loaded plugin: {module_name}")
            except Exception as e:
                logger.error(f"Failed to load {module_name}: {e}")

    return plugins


if __name__ == "__main__":
    logger.info('Running daily checks')
    current_path = Path(__file__)
    current_dir = current_path.parent
    plugins = load_plugins(current_dir / current_path.stem)

    # Access loaded plugins
    module_names = [mn for mn in plugins.keys()]
    module_names.sort()

    logger.info(module_names)

    # FIXME: Should be done in __init__.py? Either that or dev moved from there to here.
    with quality.iota_engine.connect() as conn:
        dev_name_results = conn.execute(sqla.text(quality.location_dev_name_qry))
        for uid, dev_name, last_seen in dev_name_results:
            quality.devs[uid] = (dev_name, last_seen)

    for name in module_names:
        module = plugins[name]

        if hasattr(module, "run_check"):
            logger.info(f'Calling {name}')
            module.run_check()

    logger.info(quality.emit_report)
    logger.info(quality.report_root.parent)

    if quality.emit_report:
        fn_prefix = quality.report_date.strftime('%Y%m%d')
        md_name = Path(f"/tmp/{fn_prefix}_report.md")
        html_name = md_name.with_suffix(".html")
        pdf_name = md_name.with_suffix(".pdf")

        logger.info(f'Writing markdown report: {md_name}')

        quality.report_root.parent.visit(None)
        print(quality.markdown)

        with open(md_name, 'wt') as fp:
            fp.write(quality.markdown)

        logger.info(f'Converting to HTML report: {html_name}')
        subprocess.run(['pandoc', '-f', 'markdown', '-t', 'html', '-s', '-o', html_name, md_name])

        logger.info(f'Converting to PDF report: {pdf_name}')
        subprocess.run(['pandoc', '-f', 'markdown', '-t', 'pdf', '-s', '-o', pdf_name, md_name])
