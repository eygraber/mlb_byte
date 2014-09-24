#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from google.appengine.ext import ndb
from google.appengine.api import urlfetch

import datetime
import json
import logging
import webapp2

import models


class InitHandler(webapp2.RequestHandler):
    SCOREBOARD_URL_TEMPLATE = "http://gd2.mlb.com/components/game/mlb/" \
                              "year_{year}/month_{month}/day_{day}/miniscoreboard.json"
    GAMEDAY_DATA_URL_TEMPLATE = "http://gd2.mlb.com/{game_data_dir}/linescore.json"
    GAME_DAY_URL_TEMPLATE = "http://mlb.com/mlb/gameday/index.jsp?gid={id}"

    @classmethod
    def convert_game_time_to_utc_time(cls, game_time, ampm):
        return datetime.datetime.strptime(game_time + " " + ampm, "%Y/%m/%d %I:%M %p")

    def get(self):
        override_current_vals = bool(self.request.get("override_current_vals", False))

        now = datetime.datetime.now() - datetime.timedelta(hours=7)
        now_even = datetime.datetime.now().replace(hour=0,
                                                   minute=0,
                                                   second=0,
                                                   microsecond=0)
        delete_time = now_even + datetime.timedelta(days=2)

        year = now.strftime('%Y')
        month = now.strftime('%m')
        day = now.strftime('%d')
        url = self.SCOREBOARD_URL_TEMPLATE.format(year=year, month=month, day=day)

        day_id = datetime.datetime(year=int(year), month=int(month), day=int(day))
        if models.Day.did_we_get_day_yet(day_id) and not override_current_vals:
            logging.info("We already got this day's games")
            self.response.write("We already got this day's games")
            return

        result = urlfetch.fetch(url)
        if result.status_code == 200:
            sched = json.loads(result.content)
            if not 'data' in sched or not 'games' in sched['data'] or not 'game' in sched['data']['games']:
                logging.error("Missing some required params in today's schedule - {sched}"
                              .format(json.dumps(sched)))
                self.response.write("Missing some required params in today's schedule - {sched}"
                                    .format(json.dumps(sched)))
                return

            games = sched['data']['games']['game']
            game_models = [self.get_game(game, now_even, delete_time) for game in games]
            ndb.put_multi(game_models)
            models.Day(day_id=day_id).put()
            self.response.write("Success")
        else:
            self.response.write("There was an error getting the game schedule! - {code} {message}"
                                .format(code=result.status_code, message=result.content))

    @classmethod
    def get_game(cls, game, now_even, delete_time):
        if not 'home_team_name' in game or not 'away_team_name' in game or not 'home_time' in game or not \
                'home_ampm' in game or not 'home_time_zone' in game or not 'time_date' in game or not \
                'game_data_directory' in game or not 'id' in game:
            logging.error("Missing required params for a game")
            return None

        return models.GameInfo(home_team=game['home_team_name'],
                               away_team=game['away_team_name'],
                               start_time_display="{time}{ampm} {tz}"
                                                  .format(time=game['home_time'],
                                                          ampm=game['home_ampm'],
                                                          tz=game['home_time_zone']),
                               start_time=cls.convert_game_time_to_utc_time(game['time_date'],
                                                                            game['home_ampm']),
                               game_day_data_url=cls.GAMEDAY_DATA_URL_TEMPLATE
                                                  .format(game_data_dir=game['game_data_directory']),
                               game_day_url=cls.GAME_DAY_URL_TEMPLATE
                                               .format(id=game['id']
                                                       .replace("/", "_")
                                                       .replace("-", "_")),
                               day=now_even,
                               delete_time=delete_time)


app = webapp2.WSGIApplication([
    ('/admin/init_day', InitHandler)
], debug=True)
