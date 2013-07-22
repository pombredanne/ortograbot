from apscheduler.scheduler import Scheduler

from bot import OrtograBot

sched = Scheduler()


@sched.interval_schedule(minutes=5)
def rules_job():
    """Launch the main job very minute"""
    OrtograBot().run_rule()

sched.start()

while True:
    pass
