from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    "esi_cleanup_callbackredirect": {
        "task": "esi.tasks.cleanup_callbackredirect",
        "schedule": crontab(minute=0, hour="*/4"),
    },
    "esi_cleanup_token": {
        "task": "esi.tasks.cleanup_token",
        "schedule": crontab(minute=0, hour=0),
    },
    # "eveonline_update_corporations": {
    #     "task": "eveonline.tasks.update_corporations",
    #     "schedule": crontab(hour="*/1"),
    # },
    # "eveonline_update_characters": {
    #     "task": "eveonline.tasks.update_characters",
    #     "schedule": crontab(hour="*/8"),
    # },
}
