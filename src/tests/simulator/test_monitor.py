from unittest.mock import MagicMock, patch
from phyelds.simulator import Simulator, Monitor
from phyelds.simulator.render import RenderMonitor

class MockMonitor(Monitor):
    def __init__(self, simulator):
        super().__init__(simulator)
        self.update_called = 0
        self.start_called = False
        self.finish_called = False

    def on_start(self):
        self.start_called = True

    def on_finish(self):
        self.finish_called = True

    def update(self):
        self.update_called += 1

def test_monitor_hooks():
    sim = Simulator()
    monitor = MockMonitor(sim)

    sim.schedule_event(1.0, lambda: None)
    sim.schedule_event(2.0, lambda: None)
    sim.run()

    assert monitor.start_called
    assert monitor.finish_called
    assert monitor.update_called == 2
