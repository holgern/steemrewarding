# This Python file uses the following encoding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from builtins import bytes, int, str
from future.utils import python_2_unicode_compatible
from datetime import date, datetime, timedelta
import time


def isfloat(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

def valid_age(post, hours=156):
    """
    Checks if post is within last twelve hours before payout.
    """
    if post.time_elapsed() > timedelta(hours=hours):
        return False
    return True


def upvote_comment(c_comment, acc_vote_name, acc_vote_weight):
    already_voted = False
    vote_sucessfull = False
    for v in c_comment["active_votes"]:
        if acc_vote_name == v["voter"]:
            already_voted = True
    cnt = 0
    while not (vote_sucessfull or already_voted) and cnt < 5:
        try:
            c_comment.upvote(weight=acc_vote_weight, voter=acc_vote_name)
            time.sleep(4)
            c_comment.refresh()
            for v in c_comment["active_votes"]:
                if acc_vote_name == v["voter"]:
                    vote_sucessfull = True
        except:
            print("retry to vote %s" % c_comment["authorperm"])
        cnt += 1
    return vote_sucessfull
