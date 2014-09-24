from google.appengine.ext import ndb


class Day(ndb.Model):
    day_id = ndb.DateTimeProperty(required=True, indexed=True)

    @classmethod
    def did_we_get_day_yet(cls, day_id):
        return len(Day.query(Day.day_id == day_id).fetch(1)) > 0


class GameCache(ndb.Model):
    home_team_runs = ndb.IntegerProperty(required=True, indexed=False)
    away_team_runs = ndb.IntegerProperty(required=True, indexed=False)
    inning = ndb.IntegerProperty(required=True, indexed=False)
    top_inning = ndb.StringProperty(required=True, indexed=False, choices=['Y', 'N'])  # Yes / No
    status = ndb.StringProperty(required=True, indexed=False, choices=['I', 'F'])  # In-Progress / Finished
    refresh_time = ndb.DateTimeProperty(required=True, indexed=False)


class GameInfo(ndb.Model):
    day = ndb.DateTimeProperty(required=True, indexed=True)
    home_team = ndb.StringProperty(required=True, indexed=True)
    away_team = ndb.StringProperty(required=True, indexed=True)
    start_time = ndb.DateTimeProperty(required=True, indexed=False)
    start_time_display = ndb.StringProperty(required=True, indexed=False)
    game_day_data_url = ndb.StringProperty(required=True, indexed=False)
    game_day_url = ndb.StringProperty(required=True, indexed=False)
    delete_time = ndb.DateTimeProperty(required=True, indexed=True)
    cache_key = ndb.KeyProperty(default=None, indexed=False, kind=GameCache)
