# -*- coding: utf-8 -*-
import langid
import logging
import pymongo
import os
import twitter
import sys
from datetime import datetime
from datetime import timedelta
from random import choice

logger = logging.getLogger(__name__)


class OrtograBot(object):
    """
    OrtograBot searches for certain orthographic errors on twitter and reports
    back to the user with the proper form.
    """

    def __init__(self, mongodb_url=None):
        """Setup MongoDB databse, Twitter API and rules"""
        mongodb_url = os.environ.get("MONGOHQ_URL", mongodb_url)
        client = pymongo.MongoClient(mongodb_url)
        self.db = client[mongodb_url.rsplit("/", 1)[1]]
        credentials = self.db.twitterCredentials.find_one()
        self.username = credentials["username"]
        self.api = twitter.Api(
            consumer_key=credentials["consumer_key"],
            consumer_secret=credentials["consumer_secret"],
            access_token_key=credentials["access_token_key"],
            access_token_secret=credentials["access_token_secret"]
        )
        self.rules = [
            {
                "search": u"tí",
                "message": u"ti nunca lleva tilde → "
                           u"http://buscon.rae.es/dpd/?key=ti&origen=REDPD",
                "lang": u"es",
            }
        ]

    def run_rule(self):
        """Run one random rule and reply to the twitter user if needed"""
        rule = choice(self.rules)
        results = self.api.GetSearch(rule["search"].encode("utf8"))
        for status_obj in results:
            if (langid.classify(status_obj.text)[0] != rule["lang"]
                    and self.username.lower() not in status_obj.text.lower()):
                continue
            post_time = datetime.strptime(status_obj.created_at,
                                          '%a %b %d %H:%M:%S +0000 %Y')
            now = datetime.utcnow()
            one_day_ago = now - timedelta(days=1)
            reply_to = {
                "status_id": status_obj.id,
                "screen_name": status_obj.user.screen_name,
                "post_time": post_time,
                "text": status_obj.text,
                "reply_time": now,
                "search": rule["search"],
                "lang": rule["lang"],
            }
            users_already_messaged = list(self.db.messaged.find({
                "screen_name": reply_to["screen_name"],
                "search": rule["search"],
                "lang": rule["lang"],
                "reply_time": {"$gte": one_day_ago}
            })).sort([('reply_time', pymongo.DESCENDING)])
            if not users_already_messaged:
                try:
                    reply_message = u"@{} {}".format(reply_to["screen_name"],
                                                     rule["message"])
                    self.api.PostUpdate(reply_message,
                                        in_reply_to_status_id=status_obj.id)
                    self.db.messaged.insert(reply_to, safe=True)
                    # We only reply to one user
                    break
                except Exception:
                    logger.error("Unexpected error: %s", sys.exc_info()[0:2])
