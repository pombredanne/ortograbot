from apscheduler.scheduler import Scheduler

from bot import OrtograBot

sched = Scheduler()


@sched.interval_schedule(minutes=30)
def rules_job():
    """Launch the main job"""
    OrtograBot().run_rule()

sched.start()

while True:
    pass
