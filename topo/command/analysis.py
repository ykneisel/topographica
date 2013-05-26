"""
User-level analysis commands, typically for processing existing SheetViews.

Most of this file consists of commands that accept SheetViews as
input, process the data in these SheetViews to create new SheetViews
with the analysed data.

For instance, the temporal_measurement command take a measurement
command as input, uses it to generate SheetViews over time which it
collapses into a new spatiotemporal SheetView with the name of the
original sheetviews prefixed by 'ST'.

Some of the commands are ordinary Python functions, but the rest are
ParameterizedFunctions, which act like Python functions but support
Parameters with defaults, bounds, inheritance, etc.  These commands
are usually grouped together using inheritance so that they share a
set of parameters and some code, and only the bits that are specific
to that particular plot or analysis appear below.  See the
superclasses for the rest of the parameters and code.
"""

import math
import param
import topo
from topo.base.sheet import Sheet
 # For backward compatibility. Would be nice to generate a depracation warning.
from topo.command.measurement import *
from topo.command.measurement import Feature  # Why is this not handled by *?


class temporal_measurement(param.Parameterized):
    """
    Initialize using: temporal_measurement(<measurement command>, <steps>)
    Run by calling with arguments for the supplied <measurement command>.
    """

    measurement_command = param.Parameter( default=None, doc="""
         The measurement command that will be called to generate
         SheetViews over time. Must not be instantiated and must be a
         subclass of PatternPresentingCommand.""")

    collapse_views = param.Boolean(default=True, doc="""
        If True, multiple SheetView over time are collapsed into a
        single SheetView starting with prefix. If False, all the
        timestamped SheetViews are left in the sheet_view
        dictionary.""")


    prefix = param.String(default='Temporal', doc="""
        The prefix given to the SheetViews that are generated over
        time. If collapse_views is True, the sheetviews with this
        prefix are collapsed into a single sheetview starting with
        this prefix.""")


    duration = param.Number(default=100, doc="""
       The duration over which the measurement is to be repeated.""")

    time_density = param.Number(default=1.0, doc="""
       The interval that elapses between measurements.""")

    def __init__(self, measurement_command, duration, **kwargs):

        super(temporal_measurement, self).__init__(measurement_command=measurement_command,
                                                      duration=duration, **kwargs)
        self._prefix_map = {}
        self._padding = None

    def __call__(self, *args, **kwargs):
        """
        Run the specified measurement_command over time using the
        *args and **kwargs specified.
        """
        if not issubclass(self.measurement_command, PatternPresentingCommand):
            raise ValueError('A PatternPresentingCommand Class is required.')

        steps = int(math.floor(self.duration / self.time_density))
        self._padding = len(str(steps))
        self._prefix_map = {}

        topo.sim.run(0.0)
        prefix_formatter = (self.prefix + '%%0%dd:') % self._padding

        topo.sim.state_push()

        for step in range(steps):
            timestamped_prefix = prefix_formatter % step
            self.measurement_command.sheet_views_prefix = timestamped_prefix
            step_duration = topo.sim.convert_to_time_type(self.time_density)
            timestamp = step * step_duration
            self._prefix_map[timestamped_prefix] = timestamp

            if self.measurement_command is measure_response:
                self.measurement_command.duration = step_duration
                self.measurement_command.instance()(*args, **dict(kwargs, restore_state=False, restore_events=False))
            else:
                self.measurement_command.duration = timestamp
                self.measurement_command.instance()(*args, **kwargs)

        topo.sim.state_pop()

        if self.collapse_views: self._collapse_views()


    def _collapse_views(self):
        """
        Collapses the timestamped SheetViews into a single SheetView
        with the specified prefix.
        """
        sheets = [s for s in topo.sim.objects(Sheet).values() if hasattr(s, 'sheet_views')]
        for sheet in sheets:
            viewnames = sheet.sheet_views.keys()
            striplen = len(self.prefix) + self._padding + 1
            basenames = set(name[striplen:] for name in viewnames if name.startswith(self.prefix))
            for basename in basenames:
                sorted_keys = sorted(name for name in viewnames if name.endswith(basename) and name!=basename)
                views = [sheet.sheet_views.pop(key) for key in sorted_keys]
                timestamps  = [self._prefix_map[key[:-len(basename)]] for key in sorted_keys]
                collapsed_view = views[0]
                for data, timestamp in zip([v.view()[0] for v in views[1:]], timestamps[1:]):
                    collapsed_view.record(data, timestamp)
                sheet.sheet_views[self.prefix + basename] = collapsed_view
