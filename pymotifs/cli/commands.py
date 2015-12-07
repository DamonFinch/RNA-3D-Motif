import random
import logging

import click

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pymotifs.cli import setup
from pymotifs.cli.params import FILE
from pymotifs.cli.params import DATE
from pymotifs.cli.params import PDB

from pymotifs import models as mod
from pymotifs import config as conf
from pymotifs.dispatcher import Dispatcher


def run(ctx, name, ids, config=None, engine=None, **kwargs):
    if kwargs.get('seed', None) is not None:
        random.seed(kwargs['seed'])

    setup.expand_stage_pattern(name, 'recalculate', kwargs)

    if not ids:
        ids = setup.pdbs(config, kwargs)

    mod.reflect(engine)

    logger = logging.getLogger(__name__)
    dispatcher = Dispatcher(name, config, sessionmaker(engine), **kwargs)
    try:
        dispatcher(ids, **kwargs)
    except Exception as err:
        click.secho("Pipeline failed", fg='red', err=True)
        logger.exception(err)
        ctx.exit(1)


@click.group(short_help="Interface to update pipeline",
             context_settings={'help_option_names': ['-h', '--help']})
@click.option('--config', default='conf/motifatlas.json', type=FILE,
              help="JOSN configuration file")
@click.option('--log-file', type=click.Path(dir_okay=False, resolve_path=True),
              help="Logging filename")
@click.option('--log-level', default='debug',
              type=click.Choice(['debug', 'info', 'warning', 'error']),
              help="Logging level to use")
@click.option('--log-mode', default='a', type=click.Choice(['w', 'a']),
              help='Mode to open the  logging file')
@click.option('--email/--no-email', default=False, help='Send email')
@click.version_option('2.0.0')
@click.pass_context
def cli(ctx, **options):
    """A tool for running parts of the update pipeline.

    This allows users run either the whole or parts of the update pipeline. It
    offers fine grained control over what gets run and how.
    """
    setup.logs(options)
    ctx.objs = options
    config = conf.load(options['config'])
    ctx.objs.update({
        'config': config,
        'engine': create_engine(config['db']['uri'])
    })


@cli.command('run', short_help="Run stage(s)")
@click.option('--dry-run', is_flag=True, help="Alter nothing while running")
@click.option('--skip-dependencies', is_flag=True, help='Skip stage(s)')
@click.option('--skip-stage', multiple=True, help='Stage to skip')
@click.option('--seed', type=int, help="Set the random seed")
@click.option('--recalculate', multiple=True,
              help="Recalculate data for the given stage(s)")
@click.option('--all', is_flag=True, help="Use all RNA containing PDBS")
@click.option('--known', is_flag=True, help="Use only downloaded files")
@click.option('--after-date', default=None,
              type=DATE, help='Get PDBs from after the date')
@click.option('--before-date', default=None,
              type=DATE, help='Get PDBs from before the date')
@click.option('--exclude', multiple=True, type=PDB,
              help='Excluded PDB(s)')
@click.option('--ignore-time', is_flag=True, help='Ignore time for rerunning')
@click.argument('name')
@click.argument('ids', nargs=-1, type=PDB)
@click.pass_context
def do(ctx, name, ids, **kwargs):
    """Run specific stages in the pipeline.

    This accepts a stage to run and a list of PDB ids to import. It determines
    which if any dependencies must be run and runs them all.
    """
    kwargs.update(ctx.parent.objs)
    run(ctx, name, ids, **kwargs)


@cli.command(short_help='Populate a database')
@click.pass_context
def bootstrap(ctx, **kwargs):
    """Poupluate a testing database.

    To test this pipeline working copy of the database is needed. This command
    will populate a database with some default data for testing. The config
    file used MUST contain a pdbs section, with the list of pdbs to get data
    for. For an example look at `conf/bootstrap.json.txt`. This will not import
    and distance data.
    """
    kwargs['exclude'] = kwargs.get('exclude', [])
    kwargs['exclude'].append('units.distances')
    kwargs['seed'] = 1
    config = ctx.parent.objs['config']
    kwargs.update(ctx.parent.objs)
    run(ctx, 'update', config.pop('pdbs'), **kwargs)


@cli.group(short_help="Run commands for 2d diagrams")
@click.pass_context
def ss(ctx):
    """Commands dealing with importing 2D diagrams
    """
    ctx.objs = ctx.parent.objs
    return ctx


@ss.command('import', short_help='Import a 2D diagram')
@click.option('--ss-name', default=None, type=str, help='Name for the diagram')
@click.option('--recalculate', multiple=True,
              help="Recalculate data for the given stage(s)")
@click.argument('filename', metavar='F', type=FILE)
@click.pass_context
def ss_import(ctx, **kwargs):
    """Import a 2D diagram.

    This will parse the secondary structure diagram in the given file and
    import it. The file should be a post script file from the gutell lab. It
    parses their style of postcript files and no others.
    """
    kwargs.update(ctx.parent.objs)
    run(ctx, 'ss.positions', None, **kwargs)


@ss.command('align', short_help='Align a 2D to a chain')
@click.option('--ss-name', default=None, type=str, help='Name for the diagram')
@click.option('--recalculate', multiple=True,
              help="Recalculate data for the given stage(s)")
@click.option('--skip-dependencies', is_flag=True,
              help='Skip running any dependencies')
@click.argument('pdb', type=PDB)
@click.argument('chain')
@click.argument('filename', type=FILE)
@click.pass_context
def ss_align(ctx, pdb, **kwargs):
    """Align a chain to a secondary structure.

    This will determine the expermental sequence of the given chain and then
    align it to the secondary structure in the given file. The 2D will be
    imported as needed. Doing one such import can allow the inference of
    positions across many structures since experimental sequences are often
    reused.
    """
    kwargs.update(ctx.parent.objs)
    run(ctx, 'ss.position_mapping', [pdb], **kwargs)
