# This Python file uses the following encoding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from builtins import bytes, int, str
from future.utils import python_2_unicode_compatible
from datetime import date, datetime, timedelta
import time
import math


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

def upvote_comment_without_check(c_comment, acc_vote_name, acc_vote_weight, retry_count=5):
    already_voted = False
    for v in c_comment["active_votes"]:
        if acc_vote_name == v["voter"]:
            already_voted = True
    if acc_vote_weight <0.01:
        return None
    cnt = 0
    reply = None
    while not already_voted and cnt <= retry_count:
        try:
            reply = c_comment.upvote(weight=acc_vote_weight, voter=acc_vote_name)
            already_voted = True
        except Exception as inst:
            print("retry to vote %s from %s with %.2f" % (c_comment["authorperm"], acc_vote_name, acc_vote_weight))
            print(type(inst))
            print(inst)
            time.sleep(3)
            c_comment.refresh()
            for v in c_comment["active_votes"]:
                if acc_vote_name == v["voter"]:
                    already_voted = True            
          
        cnt += 1
    return reply

def upvote_comment(c_comment, acc_vote_name, acc_vote_weight, retry_count=5):
    already_voted = False
    vote_sucessfull = False
    for v in c_comment["active_votes"]:
        if acc_vote_name == v["voter"]:
            already_voted = True
    cnt = 0
    if acc_vote_weight < 0.01:
        return False
    while not (vote_sucessfull or already_voted) and cnt <= retry_count:
        try:
            c_comment.upvote(weight=acc_vote_weight, voter=acc_vote_name)
            time.sleep(1)
            c_comment.refresh()
            for v in c_comment["active_votes"]:
                if acc_vote_name == v["voter"]:
                    vote_sucessfull = True
        except Exception as inst:
            print("retry to vote %s from %s with %.2f" % (c_comment["authorperm"], acc_vote_name, acc_vote_weight))
            print(type(inst))
            print(inst)
            time.sleep(3)
            c_comment.refresh()
            for v in c_comment["active_votes"]:
                if acc_vote_name == v["voter"]:
                    vote_sucessfull = True            
          
        cnt += 1
    return vote_sucessfull

def split_string(string):
    if string.find(",") == -1 and string.strip().find(" ") > -1:
        string = string.strip().split(" ")
    elif string.find(",") == -1 and string.strip().find(";") > -1:
        string = string.strip().split(";")
    else:
        string = string.split(",")
    return string

def tags_included(include_tags, tags):
    tags_included = True
    if tags is None:
        return False
    if include_tags is not None and include_tags != "":
        tags_included = False
        include_tags = split_string(include_tags)
         
        for tag in include_tags:
            if tag.find("&") == -1:
                if tag.lower().strip() in tags:
                    tags_included = True
            elif not tags_included:
                tags_included = True
                for t in tag.split("&"):
                    if t.lower().strip() not in tags:
                        tags_included = False
    return tags_included


def tags_excluded(exclude_tags, tags):
    tags_excluded = True
    if exclude_tags is not None and exclude_tags != "":
        tags_excluded = True
        exclude_tags = split_string(exclude_tags)    

        for tag in exclude_tags:
            if tag.find("&") == -1:
                if tag.lower().strip() in tags:
                    tags_excluded = False
            elif tags_excluded:
                tags_excluded = False
                for t in tag.split("&"):
                    if t.lower().strip() not in tags:
                        tags_excluded = True           
    return tags_excluded


def string_excluded(exclude_rule, string):
    if exclude_rule is not None and exclude_rule != "":
        exclude_rule = split_string(exclude_rule)

        excluded = True
        for s in exclude_rule:
            if s.lower().strip() == string:
                excluded = False
        return excluded
    return True


def string_included(include_rule, string):
    if include_rule is not None and include_rule != "":
        include_rule = split_string(include_rule)
        include = False
        for s in include_rule:
            if s.lower().strip() == string:
                include = True
        return include
    return True

def approx_sqrt_v1(x):
    if x <= 1:
        return x
    # mantissa_bits, leading_1, mantissa_mask are independent of x
    msb_x = x.bit_length() - 1
    msb_z = msb_x >> 1
    msb_x_bit = 1 << msb_x
    msb_z_bit = 1 << msb_z
    mantissa_mask = msb_x_bit-1

    mantissa_x = x & mantissa_mask
    if (msb_x & 1) != 0:
        mantissa_z_hi = msb_z_bit
    else:
        mantissa_z_hi = 0
    mantissa_z_lo = mantissa_x >> (msb_x - msb_z)
    mantissa_z = (mantissa_z_hi | mantissa_z_lo) >> 1
    result = msb_z_bit | mantissa_z
    return result

def curation_performance(rshares_before, rshares_vote, rshares_after):
    return (approx_sqrt_v1(rshares_before + rshares_vote) - approx_sqrt_v1(rshares_before)) / (approx_sqrt_v1(rshares_before + rshares_vote + rshares_after))
