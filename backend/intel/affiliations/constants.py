"""Thresholds for the affiliation database, set from real zKill samples."""

# How far back an investigation reads, in calendar months (this one too).
WINDOW_MONTHS = 24
# zKill returns 200 mails a page; one page per month is the sample.
ZKILL_PAGE_SIZE = 200
# zKill asks for about one request a second.
ZKILL_SLEEP_SECONDS = 1.1
# Bigger mails are blobs and structure bashes: everyone is on them.
MAX_ATTACKERS = 60
# NPC corporations (militias, starter corps) are 1,000,000 to 1,999,999.
FIRST_PLAYER_CORPORATION_ID = 2_000_000

# Evidence rows below this are dropped: a single shared kill is noise.
MIN_SHARED_ROW = 2

# A group is re-read this long after its last investigation, if still seen.
REINVESTIGATE_DAYS = 30
# A failed investigation is retried after this long.
RETRY_FAILED_HOURS = 6
# Sightings before a group is queued. A group in a Local report is queued
# at once (each report counts this many).
QUEUE_AFTER_SIGHTINGS = 3
LOCAL_REPORT_SIGHTINGS = 3
# Investigations per scheduled run (each is about 50 zKill requests).
INVESTIGATIONS_PER_RUN = 3

# Scoring looks at the whole window and at the last year, and keeps the
# stronger lean: Scary Wormhole People had Snuffed Out on 20% of its kills
# over two years but 25% over the last one.
RECENT_MONTHS = 12
# A group needs this many sampled kills before it is judged.
MIN_KILLS = 25
# A pet was on the partner's side of at least this share of its kills...
# (Scary Wormhole People, run by TDSIN, had Snuffed Out on 25% of its kills
# in each of 12 months; Snuffed Out had it on 1.5% of its own.)
PET_SHARE = 0.20
# ...in at least this many months...
MIN_MONTHS_TOGETHER = 3
# ...and leans on the partner at least this much more than the reverse.
PET_ASYMMETRY = 2.0
# More kills against each other than this share of the shared ones rules a
# link out (third parties on the same brawl, not friends). Real pets show
# some (lowsec brawls, awoxers): 5-13% in the Snuffed Out sample. Below the
# cut, each point of it lowers the confidence.
MAX_AGAINST_SHARE = 0.20
MAX_AGAINST_FLOOR = 2
# Shared kills mostly flown for the same militia are militia allies, which
# Local already shows by faction; they are not suggested as a bloc.
MILITIA_SHARE = 0.6
# A character outside the bloc on this many of its sampled kills, across
# this many months, is a suggested associate.
ASSOCIATE_SHARED = 6
ASSOCIATE_MONTHS = 3
# Inferred affiliations with no evidence for this many months have ended.
ENDED_AFTER_MONTHS = 6
# A main's pets are a small share of its kills, so the partners it flies
# with most are queued right after its investigation, whatever their share.
QUEUE_TOP_PARTNERS = 10
PARTNER_PRIORITY = 10
# "Investigate now" from the intel team jumps the queue.
MANUAL_PRIORITY = 100
