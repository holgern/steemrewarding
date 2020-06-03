from flask import Flask, jsonify, request, render_template, redirect, url_for, session, flash
from flask_wtf import FlaskForm
from flask_table import Table, Col, LinkCol, BoolCol, DatetimeCol
from flask_table.html import element
from flask_cors import CORS
import os
import ast
import json
import sys
from prettytable import PrettyTable
from datetime import datetime, timedelta
import pytz
import math
import random
import logging
import click
import dataset
import re
from functools import wraps
from beem.instance import set_shared_steem_instance, shared_steem_instance
from beem.amount import Amount
from beem.price import Price
from beem.account import Account
from beem.steem import Steem
from beem.comment import Comment
from beem.market import Market
from beem.block import Block
from beem.profile import Profile
from beem.wallet import Wallet
from beem.steemconnect import SteemConnect
from beem.asset import Asset
from beem.witness import Witness, WitnessesRankedByVote, WitnessesVotedByAccount
from beem.blockchain import Blockchain
from beem.utils import formatTimeString, construct_authorperm, formatTimedelta, addTzInfo, resolve_authorperm, derive_permlink
from beem.vote import AccountVotes, ActiveVotes
from beem import exceptions
from beem.version import version as __version__
from beem.asciichart import AsciiChart
from beem.transactionbuilder import TransactionBuilder
from beem.version import version as beem_version
from beembase import operations
from beem.transactionbuilder import TransactionBuilder
from timeit import default_timer as timer
from beembase import operations
from beemgraphenebase.account import PrivateKey, PublicKey, BrainKey
from beemgraphenebase.base58 import Base58
from beem.nodelist import NodeList
from beem.conveyor import Conveyor
from beem.rc import RC
from beem.constants import STEEM_VOTE_REGENERATION_SECONDS, STEEM_100_PERCENT, STEEM_1_PERCENT, STEEM_RC_REGEN_TIME
from beem.constants import state_object_size_info, resource_execution_time
from wtforms import Form, StringField, SelectField, validators, BooleanField, FloatField, IntegerField, TextAreaField
from steemrewarding.vote_rule_storage import VoteRulesTrx
from steemrewarding.trail_vote_rule_storage import TrailVoteRulesTrx
from steemrewarding.trail_downvote_rule_storage import TrailDownVoteRulesTrx
from steemrewarding.vote_log_storage import VoteLogTrx
from steemrewarding.pending_vote_storage import PendingVotesTrx
from steemrewarding.failed_vote_log_storage import FailedVoteLogTrx
from steemrewarding.account_storage import AccountsDB
from steemrewarding.version import version as rewardingversion
DEBUG = True
DEBUG = False

config_file = 'config.json'
with open(config_file) as json_data_file:
    config_data = json.load(json_data_file)

# instantiate the app
app = Flask(__name__, static_url_path='/static')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 1
app.config.from_object(__name__)
app.secret_key = config_data["flask_secret_key"]


# enable CORS
CORS(app)

stm = Steem()
nodelist = NodeList()

steemconnect = SteemConnect(client_id="beem.app", scope="login", get_refresh_token=False)


# print(config_data)
databaseConnector = config_data["databaseConnector"]
wallet_password = config_data["wallet_password"]
frontend = "https://steemit.com/"

def valid_age(post, hours=156):
    """
    Checks if post is within last twelve hours before payout.
    """
    if post.time_elapsed() > timedelta(hours=hours):
        return False
    return True


class ExternalURLCol(Col):
    def __init__(self, name, url_attr, frontend, **kwargs):
        self.url_attr = url_attr
        self.frontend = frontend
        super(ExternalURLCol, self).__init__(name, **kwargs)

    def td_contents(self, item, attr_list):
        text = self.from_attr_list(item, attr_list)
        url = self.from_attr_list(item, [self.url_attr])
        return element('a', {'href': self.frontend + url, 'target': "_blank", 'class': 'table'}, content=text)

class ExternalAuthorURLCol(Col):
    def __init__(self, name, url_attr, frontend, **kwargs):
        self.url_attr = url_attr
        self.frontend = frontend
        super(ExternalAuthorURLCol, self).__init__(name, **kwargs)

    def td_contents(self, item, attr_list):
        text = self.from_attr_list(item, attr_list)
        url = self.from_attr_list(item, [self.url_attr])
        return element('a', {'href': self.frontend + '@' + url, 'target': "_blank", 'class': 'table'}, content=text)


class Results(Table):
    edit = LinkCol('Edit', 'edit_rule', url_kwargs=dict(author='author', main_post='main_post'), allow_sort = False)
    copy = LinkCol('Copy', 'edit_rule', url_kwargs=dict(author='author', main_post='main_post', copy_rule='main_post'), allow_sort = False)
    delete = LinkCol('Delete', 'delete_rule', url_kwargs=dict(author='author', main_post='main_post'), allow_sort = False)
    
    author = ExternalAuthorURLCol('author', url_attr='author', attr='author', frontend=frontend, allow_sort = True)
    main_post = BoolCol('main post', allow_sort = False)
    enabled = BoolCol('enabled', allow_sort = False)
    
    vote_delay_min = Col('Vote delay [min]', allow_sort = True)
    maximum_vote_delay_min = Col('max. vote delay [min]', allow_sort = True)
    
    vote_weight = Col('vote weight [%]', allow_sort = True)
    vote_sbd = Col('vote sbd [$]', allow_sort = True)
    max_votes_per_day = Col('max. votes per day', allow_sort = True)
    max_votes_per_week = Col('max. votes per week', allow_sort = True)
    min_vp = Col('min. vp [%]', allow_sort = True)
    vp_scaler = Col('vp scaler', allow_sort = False)
    vote_when_vp_reached = BoolCol('vote when vp reached', allow_sort = False)
    vp_reached_order = Col('vp reached order', allow_sort = False)

    
    include_tags = Col('include tags', allow_sort = False)
    exclude_tags = Col('exclude tags', allow_sort = False)    
    minimum_word_count = Col('min. word count', allow_sort = False)
    include_apps = Col('include apps', allow_sort = False)
    exclude_apps = Col('exclude apps', allow_sort = False)

    include_text = Col('include text', allow_sort = False)
    exclude_text = Col('exclude text', allow_sort = False)
    note = Col('note', allow_sort = False)
    exclude_declined_payout = BoolCol('exclude declined payout', allow_sort = False)
    
    max_net_votes = Col('max net votes', allow_sort = False)
    max_pending_payout = Col('max pending payout [$]', allow_sort = False)    
    leave_comment = BoolCol('leave comment', allow_sort = False)
    disable_optimization = BoolCol('dis. opt.', allow_sort = False)
    allow_sort = True
    def sort_url(self, col_key, reverse=False):
        if col_key in ["author", "vote_weight", "vote_delay_min", "min_vp"]:
            direction = 'asc'
        else:
            direction = 'desc'
        return url_for('show_rules', sort=col_key, direction=direction)    




class TrailResults(Table):
    edit = LinkCol('Edit', 'edit_trail_rule', url_kwargs=dict(voter_to_follow='voter_to_follow'), allow_sort = False)
    copy = LinkCol('Copy', 'edit_trail_rule', url_kwargs=dict(voter_to_follow='voter_to_follow', copy_rule='enabled'), allow_sort = False)
    delete = LinkCol('Delete', 'delete_trail_rule', url_kwargs=dict(voter_to_follow='voter_to_follow'), allow_sort = False)
    voter_to_follow = Col('voter to follow')
    # account = Col('account')
    only_main_post = BoolCol('only main post', allow_sort = False)
    enabled = BoolCol('enabled', allow_sort = False)

    vote_weight_threshold = Col('vote weight threshold')
    vote_weight_scaler = Col('vote weight scaler [%]')
    vote_weight_offset = Col('vote weight offset [%]')
    
    minimum_vote_delay_min = Col('min. vote_delay [min]')
    maximum_vote_delay_min = Col('max. vote_delay [min]')    
  
    
    max_votes_per_day = Col('max votes per day')
    max_votes_per_week = Col('max votes per week')    
    
    min_vp = Col('min vp [%]')
    vp_scaler = Col('vp scaler', allow_sort = False)
    
    vote_when_vp_reached = BoolCol('vote when vp reached', allow_sort = False)
    vp_reached_order = Col('vp reached order', allow_sort = False)
    exclude_authors_with_vote_rule = BoolCol('exclude authors with vote rule', allow_sort = False)
    
    include_authors = Col('include authors', allow_sort = False)
    exclude_authors = Col('exclude authors', allow_sort = False)    
    include_tags = Col('include tags', allow_sort = False)
    exclude_tags = Col('exclude tags', allow_sort = False)
    note = Col('note', allow_sort = False)

    exclude_declined_payout = BoolCol('exclude declined payout', allow_sort = False)
    max_net_votes = Col('max. net votes', allow_sort = False)
    max_pending_payout = Col('max. pending payout [$]', allow_sort = False)

    # edit = LinkCol('Edit', 'edit', url_kwargs=dict(voter='voter'))
    allow_sort = True
    def sort_url(self, col_key, reverse=False):
        if col_key in ["voter_to_follow", "vote_weight", "minimum_vote_delay_min", "min_vp"]:
            direction = 'asc'
        else:
            direction = 'desc'
        return url_for('show_trail_rules', sort=col_key, direction=direction)    



class TrailDownVoteResults(Table):
    edit = LinkCol('Edit', 'edit_trail_downvote_rule', url_kwargs=dict(voter_to_follow='voter_to_follow'), allow_sort = False)
    copy = LinkCol('Copy', 'edit_trail_downvote_rule', url_kwargs=dict(voter_to_follow='voter_to_follow', copy_rule='enabled'), allow_sort = False)
    delete = LinkCol('Delete', 'delete_trail_downvote_rule', url_kwargs=dict(voter_to_follow='voter_to_follow'), allow_sort = False)
    voter_to_follow = Col('voter to follow')
    # account = Col('account')
    only_main_post = BoolCol('only main post', allow_sort = False)
    enabled = BoolCol('enabled', allow_sort = False)

    vote_weight_threshold = Col('downvote weight threshold')
    vote_weight_scaler = Col('downvote weight scaler [%]')
    vote_weight_offset = Col('downvote weight offset [%]')
    
    minimum_vote_delay_min = Col('min. vote_delay [min]')
    maximum_vote_delay_min = Col('max. vote_delay [min]')    
  
    
    max_votes_per_day = Col('max downvotes per day')
    max_votes_per_week = Col('max downvotes per week')    
    
    min_vp = Col('min down vp [%]')
    vp_scaler = Col('down vp scaler', allow_sort = False)
    
    vote_when_vp_reached = BoolCol('downvote when vp reached', allow_sort = False)
    vp_reached_order = Col('down vp reached order', allow_sort = False)
    exclude_authors_with_vote_rule = BoolCol('exclude authors with vote rule', allow_sort = False)
    
    include_authors = Col('include authors', allow_sort = False)
    exclude_authors = Col('exclude authors', allow_sort = False)    
    include_tags = Col('include tags', allow_sort = False)
    exclude_tags = Col('exclude tags', allow_sort = False)
    note = Col('note', allow_sort = False)

    exclude_declined_payout = BoolCol('exclude declined payout', allow_sort = False)
    max_net_votes = Col('max. net downvotes', allow_sort = False)
    max_pending_payout = Col('max. pending payout [$]', allow_sort = False)

    # edit = LinkCol('Edit', 'edit', url_kwargs=dict(voter='voter'))
    allow_sort = True
    def sort_url(self, col_key, reverse=False):
        if col_key in ["voter_to_follow", "vote_weight", "minimum_vote_delay_min", "min_vp"]:
            direction = 'asc'
        else:
            direction = 'desc'
        return url_for('show_trail_rules', sort=col_key, direction=direction)  
    

class VotesLog(Table):
    edit = LinkCol('Edit', 'edit_rule', url_kwargs=dict(author='author', main_post='main_post', voter_to_follow='voter_to_follow'), allow_sort = False)
    authorperm = ExternalURLCol('authorperm', url_attr='authorperm', attr='authorperm', frontend=frontend, allow_sort=False)
    author = ExternalAuthorURLCol('author', url_attr='author', attr='author', frontend=frontend)
    timestamp = Col('timestamp')
    vote_weight = Col('vote weight [%]')
    vote_delay_min = Col('vote delay [min]')
    voted_after_min = Col('voted after [min]')
    vp = Col('vp [%]')
    vote_when_vp_reached = BoolCol('vote when vp reached', allow_sort=False)
    performance = Col('curation performance [%]')
    best_vote_delay_min = Col('best vote delay [min]')
    best_performance = Col('best curation [%]')
    optimized_vote_delay_min = Col('new vote delay [min]')
    allow_sort = True
    def sort_url(self, col_key, reverse=False):
        if col_key in ["authorperm", "author", "vote_weight", "vote_delay_min", "voted_after_min"]:
            direction = 'asc'
        else:
            direction = 'desc'
        return url_for('show_vote_log', sort=col_key, direction=direction)


class FailedVotesLog(Table):
    authorperm = ExternalURLCol('authorperm', url_attr='authorperm', attr='authorperm', frontend=frontend)
    error = Col("error")
    timestamp = Col('timestamp')
    vote_weight = Col('vote weight')
    vote_delay_min = Col('vote delay min')
    min_vp = Col('vp min')
    vp = Col('vp')
    vote_when_vp_reached = BoolCol('vote when vp reached')

class SettingsForm(FlaskForm):

    upvote_comment = TextAreaField('upvote comment (placeholder for author: {{name}} and placeholder for voter is {{voter}})')
    optimize_vote_delay = BooleanField('optimize_vote_delay (When true, vote delay of time based vote rules will be optimized)', default=False)
    minimum_vote_delay = FloatField('minimum_vote_delay [min] (defines the minimum vote delay for vote delay optimization, only votes with an initial vote delay which is higher then minimum_vote_delay will be optimized)', default=3)
    maximum_vote_delay = FloatField('maximum_vote_delay [min] (defines the maximum vote delay for vote delay optimization, only votes with an initial vote delay which is lower then maximum_vote_delay will be optimized))', default=15)
    optimize_vote_delay_slope = FloatField('optimize_vote_delay_slope [%/min] (Changes the vote weight during optimization depending on the new vote delay. When it is set to 1 %/min, the weight is decreasing by 1% for every minute the delay is decreasing.)', default=0)
    optimize_threshold = FloatField('optimize_threshold [%] (A vote delay optimization is only performed when the best vote time differs from the set vote time more than this percentage )', default=5)
    optimize_ma_length = IntegerField('optimize_ma_length (Defines the moving average length, when set to 1, each optimal delay time overwrites direclty the vote delay)', default=20)
    rshares_divider = FloatField('rshares_divider (Defines the lower limit of rshares that are considered for curaiton optimization, vote_rshares > own_votershares / rshares_divider)', default=5)
    frontend = TextAreaField('Frontend-URL', default="https://steemit.com/")
    sliding_time_window = BooleanField('sliding_time_window (When true, votes for max_votes_per_day are counting for the last 24 hours, When False, votes for max_votes_per_day are counted from 0:0:0 UTC, some is done for max_votes_per_week)', default=True)
    pause_votes_below_vp = FloatField('Pause all votes when Vote power is below this value.', default=0.0)
    pause_down_votes_below_down_vp = FloatField('Pause all downvotes when DownVote power is below this value.', default=0.0)


class VoteForm(FlaskForm):

    authorperm = TextAreaField('authorperm')
    vote_delay_min = FloatField('vote_delay_min', default=5.0)
    vote_weight = FloatField('vote_weight', default=100.0)
    vote_when_vp_reached = BooleanField('vote_when_vp_reached (When true, posts/comments are upvoted when min_vp is reached)', default=True)
    min_vp = FloatField('min_vp [%] - minimum vote power', default=50.0)
    vote_sbd = FloatField('vote_sbd [$] (When vote_weight is zero, the vote weight is calculated based on the given amount)', default=0.0)
    vp_scaler = FloatField('vp_scaler [0-1] (When greater than 0, it can be used to adapt the vote weight to the vote power. vote weight = 100 - ((100-vp) *vp_scaler)).)', default=0.0)
    leave_comment = BooleanField('leave_comment (When true, a comment whith the text defined in settings is broadcasted)')
    vp_reached_order = IntegerField('vp_reached_order (defines the vote order for vote_when_vp_reached=True, 1 goes first)', default=1)
    max_net_votes = IntegerField('max_net_votes', default=-1)
    max_pending_payout = FloatField('max_pending_payout', default=-1.0) 

class RuleForm(FlaskForm):

    author = StringField('author (must not be empty!)')
    main_post = BooleanField('main_post (When True, only posts will be upvoted)', default=True)
    vote_delay_min = FloatField('vote_delay_min [minutes]', default=5.0)
    maximum_vote_delay_min = FloatField('maximum_vote_delay_min [minutes] - vote is skipped when older', default=9360.0)
    vote_weight = FloatField('vote_weight [%]', default=100.0)
    
    enabled = BooleanField('enabled', default=True)
    
    include_tags = TextAreaField('include_tags (when set, only posts with any of the given tags will be upvoted. Seperate tags with ,)')
    exclude_tags = TextAreaField('exclude_tags (when set, posts with any of the given tags will not be upvoted. use comma for seperation.')
    
    vote_sbd = FloatField('vote_sbd [$] (When vote_weight is zero, the vote weight is calculated based on the given amount)', default=0.0)
    max_votes_per_day = IntegerField('max_votes_per_day', default=-1)
    max_votes_per_week = IntegerField('max_votes_per_week', default=-1)
    vote_when_vp_reached = BooleanField('vote_when_vp_reached (When true, posts/comments are upvoted when min_vp is reached)')
    min_vp = FloatField('min_vp [%] - minimum vote power', default=90.0)
    vp_scaler = FloatField('vp_scaler [0-1] (When greater than 0, it can be used to adapt the vote weight to the vote power. vote weight = 100 - ((100-vp) *vp_scaler)).)', default=0.0)
    leave_comment = BooleanField('leave_comment (When true, a comment whith the text defined in settings is broadcasted)')
    minimum_word_count = IntegerField('minimum_word_count', default=0)
    include_apps = TextAreaField('include_apps (When set, only posts/comments which were created by any of the given apps are upvoted)')
    exclude_apps = TextAreaField('exclude_apps (When set, posts/comments which were created by any of the given apps are not upvoted)')
    exclude_declined_payout = BooleanField('exclude_declined_payout', default=True)
    vp_reached_order = IntegerField('vp_reached_order (defines the vote order for vote_when_vp_reached=True, 1 goes first)', default=1)
    max_net_votes = IntegerField('max_net_votes', default=-1)
    max_pending_payout = FloatField('max_pending_payout', default=-1.0)
    
    include_text = TextAreaField('include_text (When set, only posts/comments containing the given string are upvoted)')
    exclude_text = TextAreaField('exclude_text (When set, posts/comments containing the given string are not upvoted)')
    disable_optimization = BooleanField('disable_optimization (When true, the vote delay of this entry is not optimized')
    note = TextAreaField("Note (You can leave a note here, it has no influence to the rule)")

class TrailRuleForm(FlaskForm):

    voter_to_follow = StringField('vote to follow (must not be empty!)')
    # account = StringField("StringField")
    only_main_post = BooleanField('only_main_post (When True, only posts will be upvoted)', default=True)
    vote_weight_threshold = FloatField('vote_weight_threshold - skip votes with lower weight', default=0.0)
    
    vote_weight_scaler = FloatField('vote_weight_scaler [%] - scales the vote weight (e.g. 50% will halve the weight, 200% will double it)', default=50.0)
    vote_weight_offset = FloatField('vote_weight_offset [%] - the offset is added to the weight after scaling the vote', default=0.0)

    enabled = BooleanField('enabled', default=True)
    
    minimum_vote_delay_min = FloatField('minimum_vote_delay_min [minutes] - vote is delayed when earlier', default=5.0)
    maximum_vote_delay_min = FloatField('maximum_vote_delay_min [minutes] - vote is skipped when older', default=9360.0)    
    
    exclude_authors_with_vote_rule = BooleanField('exclude_authors_with_vote_rule - exclude all authors that have an enabled vote rule', default=False)
    
    include_authors = TextAreaField('include_authors - When set, only the given authors will be uvpoted. Use comma for seperation.')
    exclude_authors = TextAreaField('exclude_authors - When set, given authors will not be upvoted. Use comma for seperation.')    
    
    include_tags = TextAreaField('include_tags - When set, only the given tags will be uvpoted. Use comma for seperation.')
    exclude_tags = TextAreaField('exclude_tags - When set, given tags will not be upvoted. Use comma for seperation.')
    
    max_votes_per_day = IntegerField('max_votes_per_day', default=-1)
    max_votes_per_week = IntegerField('max_votes_per_week', default=-1)

    min_vp = FloatField('min_vp [%] - minimum vote power', default=90.0)
    vp_scaler = FloatField('vp_scaler  [0-1] - When greater than 0, it can be used to adapt the vote weight to the vote power. vote weight = 100 - ((100-vp) *vp_scaler)).', default=0.0)
    
    vote_when_vp_reached = BooleanField('vote_when_vp_reached (When true, posts/comments are upvoted when min_vp is reached)', default=True)
    vp_reached_order = IntegerField('vp_reached_order (defines the vote order for vote_when_vp_reached=True, 1 goes first)', default=1)
    
    exclude_declined_payout = BooleanField('exclude_declined_payout', default=True)
    max_net_votes = IntegerField('max_net_votes', default=-1)
    max_pending_payout = FloatField('max_pending_payout', default=-1.0)
    note = TextAreaField("Note (You can leave a note here, it has no influence to the rule)")


class TrailDownVoteRuleForm(FlaskForm):

    voter_to_follow = StringField('vote to follow (must not be empty!)')
    # account = StringField("StringField")
    only_main_post = BooleanField('only_main_post (When True, only posts will be upvoted)', default=True)
    vote_weight_threshold = FloatField('vote_weight_threshold - skip downvotes with lower weight', default=0.0)
    
    vote_weight_scaler = FloatField('vote_weight_scaler [%] - scales the downvote weight (e.g. 50% will halve the weight, 200% will double it)', default=50.0)
    vote_weight_offset = FloatField('vote_weight_offset [%] - the offset is added to the weight after scaling the vote', default=0.0)

    enabled = BooleanField('enabled', default=True)
    
    minimum_vote_delay_min = FloatField('minimum_vote_delay_min [minutes] - downvote is delayed when earlier', default=5.0)
    maximum_vote_delay_min = FloatField('maximum_vote_delay_min [minutes] - downvote is skipped when older', default=9360.0)    
    
    exclude_authors_with_vote_rule = BooleanField('exclude_authors_with_vote_rule - exclude all authors that have an enabled vote rule', default=False)
    
    include_authors = TextAreaField('include_authors - When set, only the given authors will be downvoted. Use comma for seperation.')
    exclude_authors = TextAreaField('exclude_authors - When set, given authors will not be downvoted. Use comma for seperation.')    
    
    include_tags = TextAreaField('include_tags - When set, only the given tags will be downvoted. Use comma for seperation.')
    exclude_tags = TextAreaField('exclude_tags - When set, given tags will not be downvoted. Use comma for seperation.')
    
    max_votes_per_day = IntegerField('max_votes_per_day', default=-1)
    max_votes_per_week = IntegerField('max_votes_per_week', default=-1)

    min_vp = FloatField('min_vp [%] - minimum downvote power', default=90.0)
    vp_scaler = FloatField('vp_scaler  [0-1] - When greater than 0, it can be used to adapt the downvote weight to the downvote power. vote weight = 100 - ((100-vp) *vp_scaler)).', default=0.0)
    
    vote_when_vp_reached = BooleanField('vote_when_vp_reached (When true, posts/comments are downvoted when min down vp is reached)', default=True)
    vp_reached_order = IntegerField('vp_reached_order (defines the down vote order for vote_when_vp_reached=True, 1 goes first)', default=1)
    
    exclude_declined_payout = BooleanField('exclude_declined_payout', default=True)
    max_net_votes = IntegerField('max_net_votes', default=-1)
    max_pending_payout = FloatField('max_pending_payout', default=-1.0)
    note = TextAreaField("Note (You can leave a note here, it has no influence to the rule)")


class PendingVotes(Table):
    authorperm = ExternalURLCol('authorperm', url_attr='authorperm', attr='authorperm', frontend=frontend)
    vote_weight = Col('vote weight')
    comment_timestamp = Col('comment timestamp')
    vote_delay_min = Col('vote delay min')
    maximum_vote_delay_min = Col('max vote delay min')
    created = Col('created')
    min_vp = Col('min vp')
    vote_when_vp_reached = Col('vote when vp reached')
    vp_reached_order = Col('vp reached order')
    max_net_votes = Col('max net votes')
    max_pending_payout = Col('max pending payout')
    max_votes_per_day = Col('max votes per day')
    max_votes_per_week = Col('max votes per week')
    vp_scaler = Col('vp scaler')
    leave_comment = Col('leave comment')
    delete = LinkCol('Delete', 'delete_vote', url_kwargs=dict(authorperm='authorperm', vote_when_vp_reached='vote_when_vp_reached'))


def set_form(form, rule):
    form.author.data = rule["author"]
    form.main_post.data = rule["main_post"]
    form.vote_delay_min.data = rule["vote_delay_min"]
    form.maximum_vote_delay_min.data =rule["maximum_vote_delay_min"]
    form.include_tags.data = rule["include_tags"]
    form.exclude_tags.data = rule["exclude_tags"]
    form.vote_weight.data = rule["vote_weight"]
    form.enabled.data = rule["enabled"]
    form.vote_sbd.data = rule["vote_sbd"]
    form.max_votes_per_day.data = rule["max_votes_per_day"]
    form.max_votes_per_week.data = rule["max_votes_per_week"]
    form.vote_when_vp_reached.data = rule["vote_when_vp_reached"]
    form.vp_reached_order.data = rule["vp_reached_order"]
    form.min_vp.data = rule["min_vp"]
    form.vp_scaler.data = rule["vp_scaler"]
    form.leave_comment.data = rule["leave_comment"]
    form.minimum_word_count.data = rule["minimum_word_count"]
    form.include_apps.data = rule["include_apps"]
    form.exclude_apps.data = rule["exclude_apps"]
    form.exclude_declined_payout.data = rule["exclude_declined_payout"]
    
    form.max_net_votes.data = rule["max_net_votes"]
    form.max_pending_payout.data = rule["max_pending_payout"]
    form.include_text.data = rule["include_text"]
    form.exclude_text.data = rule["exclude_text"]
    form.disable_optimization.data = rule["disable_optimization"]
    form.note.data = rule["note"]
    return form


def set_form_trail_votes(form, rule):
    form.voter_to_follow.data = rule["voter_to_follow"]
    form.only_main_post.data = rule["only_main_post"]
    form.vote_weight_threshold.data = rule["vote_weight_threshold"]
    form.include_authors.data = rule["include_authors"]
    form.exclude_authors.data = rule["exclude_authors"]
    form.min_vp.data = rule["min_vp"]
    form.vote_weight_scaler.data = rule["vote_weight_scaler"]
    form.vote_weight_offset.data = rule["vote_weight_offset"]
    form.max_votes_per_day.data = rule["max_votes_per_day"]
    form.max_votes_per_week.data = rule["max_votes_per_week"]
    form.vote_when_vp_reached.data = rule["vote_when_vp_reached"]
    form.vp_reached_order.data = rule["vp_reached_order"]
    form.exclude_authors_with_vote_rule.data = rule["exclude_authors_with_vote_rule"]
    form.include_tags.data = rule["include_tags"]
    form.exclude_tags.data = rule["exclude_tags"]
    form.exclude_declined_payout.data = rule["exclude_declined_payout"]
    form.minimum_vote_delay_min.data = rule["minimum_vote_delay_min"]
    form.maximum_vote_delay_min.data = rule["maximum_vote_delay_min"]
    form.enabled.data = rule["enabled"]
    form.max_net_votes.data = rule["max_net_votes"]
    form.max_pending_payout.data = rule["max_pending_payout"]
    form.vp_scaler.data = rule["vp_scaler"]
    form.note.data = rule["note"]
    return form

def set_form_trail_downvotes(form, rule):
    form.voter_to_follow.data = rule["voter_to_follow"]
    form.only_main_post.data = rule["only_main_post"]
    form.vote_weight_threshold.data = rule["vote_weight_threshold"]
    form.include_authors.data = rule["include_authors"]
    form.exclude_authors.data = rule["exclude_authors"]
    form.min_vp.data = rule["min_vp"]
    form.vote_weight_scaler.data = rule["vote_weight_scaler"]
    form.vote_weight_offset.data = rule["vote_weight_offset"]
    form.max_votes_per_day.data = rule["max_votes_per_day"]
    form.max_votes_per_week.data = rule["max_votes_per_week"]
    form.vote_when_vp_reached.data = rule["vote_when_vp_reached"]
    form.vp_reached_order.data = rule["vp_reached_order"]
    form.exclude_authors_with_vote_rule.data = rule["exclude_authors_with_vote_rule"]
    form.include_tags.data = rule["include_tags"]
    form.exclude_tags.data = rule["exclude_tags"]
    form.exclude_declined_payout.data = rule["exclude_declined_payout"]
    form.minimum_vote_delay_min.data = rule["minimum_vote_delay_min"]
    form.maximum_vote_delay_min.data = rule["maximum_vote_delay_min"]
    form.enabled.data = rule["enabled"]
    form.max_net_votes.data = rule["max_net_votes"]
    form.max_pending_payout.data = rule["max_pending_payout"]
    form.vp_scaler.data = rule["vp_scaler"]
    form.note.data = rule["note"]
    return form

def rule_dict_from_form(voter, form):
    """
    Save the changes to the database
    """

    rule = {"voter": voter, "author": form.author.data, "main_post": form.main_post.data,
            "vote_delay_min": form.vote_delay_min.data, "include_tags": form.include_tags.data,
            "exclude_tags": form.exclude_tags.data, "vote_weight": form.vote_weight.data,
            "maximum_vote_delay_min": form.maximum_vote_delay_min.data,
            "enabled": form.enabled.data, "vote_sbd": form.vote_sbd.data, "max_votes_per_day": form.max_votes_per_day.data,
            "max_votes_per_week": form.max_votes_per_week.data, 
            "vote_when_vp_reached": form.vote_when_vp_reached.data, "vp_reached_order": form.vp_reached_order.data, 
            "min_vp": form.min_vp.data, "vp_scaler": form.vp_scaler.data, "leave_comment": form.leave_comment.data,
            "minimum_word_count": form.minimum_word_count.data, "include_apps": form.include_apps.data, "exclude_apps": form.exclude_apps.data,
            "exclude_declined_payout": form.exclude_declined_payout.data, "max_net_votes": form.max_net_votes.data,
            "max_pending_payout": form.max_pending_payout.data, "include_text": form.include_text.data, "exclude_text": form.exclude_text.data,
            "disable_optimization": form.disable_optimization.data, "note": form.note.data}

    return rule


def trail_rule_dict_from_form(account, form):
    """
    Save the changes to the database
    """

    rule = {"account": account, "voter_to_follow": form.voter_to_follow.data, "only_main_post": form.only_main_post.data,
            "vote_weight_threshold": form.vote_weight_threshold.data, "include_authors": form.include_authors.data,
            "exclude_authors": form.exclude_authors.data, "min_vp": form.min_vp.data,
            "vote_when_vp_reached": form.vote_when_vp_reached.data, "vp_reached_order": form.vp_reached_order.data,
            "vote_weight_scaler": form.vote_weight_scaler.data, "vote_weight_offset": form.vote_weight_offset.data, "max_votes_per_day": form.max_votes_per_day.data,
            "max_votes_per_week": form.max_votes_per_week.data, "include_tags": form.include_tags.data,
            "exclude_tags": form.exclude_tags.data, "exclude_declined_payout": form.exclude_declined_payout.data,
            "minimum_vote_delay_min": form.minimum_vote_delay_min.data, "exclude_authors_with_vote_rule": form.exclude_authors_with_vote_rule.data,
            "maximum_vote_delay_min": form.maximum_vote_delay_min.data, "enabled": form.enabled.data, "max_net_votes": form.max_net_votes.data,
            "max_pending_payout": form.max_pending_payout.data, "vp_scaler": form.vp_scaler.data, "note": form.note.data}

    return rule

def trail_downvote_rule_dict_from_form(account, form):
    """
    Save the changes to the database
    """

    rule = {"account": account, "voter_to_follow": form.voter_to_follow.data, "only_main_post": form.only_main_post.data,
            "vote_weight_threshold": form.vote_weight_threshold.data, "include_authors": form.include_authors.data,
            "exclude_authors": form.exclude_authors.data, "min_vp": form.min_vp.data,
            "vote_when_vp_reached": form.vote_when_vp_reached.data, "vp_reached_order": form.vp_reached_order.data,
            "vote_weight_scaler": form.vote_weight_scaler.data, "vote_weight_offset": form.vote_weight_offset.data, "max_votes_per_day": form.max_votes_per_day.data,
            "max_votes_per_week": form.max_votes_per_week.data, "include_tags": form.include_tags.data,
            "exclude_tags": form.exclude_tags.data, "exclude_declined_payout": form.exclude_declined_payout.data,
            "minimum_vote_delay_min": form.minimum_vote_delay_min.data, "exclude_authors_with_vote_rule": form.exclude_authors_with_vote_rule.data,
            "maximum_vote_delay_min": form.maximum_vote_delay_min.data, "enabled": form.enabled.data, "max_net_votes": form.max_net_votes.data,
            "max_pending_payout": form.max_pending_payout.data, "vp_scaler": form.vp_scaler.data, "note": form.note.data}

    return rule

def vote_dict_from_form(voter, form):
    """
    Save the changes to the database
    """
    authorperm = form.authorperm.data
    author, permlink = resolve_authorperm(authorperm)
    authorperm = construct_authorperm(author, permlink)

    vote = {"voter": voter, "authorperm": authorperm, "vote_delay_min": form.vote_delay_min.data, 
            "vote_weight": form.vote_weight.data, "min_vp": form.min_vp.data, "vote_sbd": form.vote_sbd.data,
            "vote_when_vp_reached": form.vote_when_vp_reached.data, "vp_reached_order": form.vp_reached_order.data,
            }
    return vote

def settings_dict_from_form(account, form):
    """
    Save the changes to the database
    """
    upvote_comment = form.upvote_comment.data

    settings = {"name": account, "upvote_comment": upvote_comment, "optimize_vote_delay": form.optimize_vote_delay.data,
                "minimum_vote_delay": form.minimum_vote_delay.data, "maximum_vote_delay": form.maximum_vote_delay.data,
                "optimize_ma_length": form.optimize_ma_length.data, "optimize_threshold": form.optimize_threshold.data,
                "rshares_divider": form.rshares_divider.data, "frontend": form.frontend.data, "sliding_time_window": form.sliding_time_window.data,
                "optimize_vote_delay_slope": form.optimize_vote_delay_slope.data, "pause_votes_below_vp": form.pause_votes_below_vp.data,
                "pause_down_votes_below_down_vp": form.pause_down_votes_below_down_vp.data}
    return settings

def login(func):
    @wraps(func)
    def check_access_token(*args, **kwargs):
        access_token = request.args.get("access_token", None)
        if access_token is None and 'access_token' not in session:

            return render_template('please_login.html')
        elif access_token is None:
            access_token = session['access_token']
        else:
            session['access_token'] = access_token
        try:
          
            steemconnect.set_access_token(access_token)
            name = steemconnect.me()["name"]
        except:

            return render_template('please_login.html')        
        return func(*args, **kwargs)
    return check_access_token


@app.route('/')
@login
def main():
    name = steemconnect.me()["name"]
    try:
        acc = Account(name, steem_instance=stm)
    except:
        nodelist = NodeList()
        nodelist.update_nodes()
        stm = Steem(node=nodelist.get_nodes(), num_retries=5, call_num_retries=3, timeout=15)    
        acc = Account(name, steem_instance=stm)
    posting_auth = False
    for a in acc["posting"]["account_auths"]:
        if a[0] == "rewarding":
            posting_auth = True     
    return render_template('welcome.html', user=name, votepower=round(acc.vp, 2), recharged=acc.get_recharge_time_str(), post_auth=posting_auth, rewardingversion=rewardingversion)

@app.route('/logout')
def logout():
    name = ""
    if 'access_token' in session:
        session['access_token'] = None
        

        return render_template('please_login.html')
    
    return render_template('welcome.html', user=name)

@app.route('/welcome', methods=['GET'])
@login
def welcome():
    name = steemconnect.me()["name"]
    try:        
        acc = Account(name, steem_instance=stm)
    except:
        nodelist = NodeList()
        nodelist.update_nodes()
        stm = Steem(node=nodelist.get_nodes(), num_retries=5, call_num_retries=3, timeout=15)    
        acc = Account(name, steem_instance=stm)    
    posting_auth = False
    for a in acc["posting"]["account_auths"]:
        if a[0] == "rewarding":
            posting_auth = True    
    
    return render_template('welcome.html', user=name, votepower=round(acc.vp, 2), recharged=acc.get_recharge_time_str(), post_auth=posting_auth, rewardingversion=rewardingversion)

@app.route('/show_rules', methods=['GET'])
@login
def show_rules():
    sort = request.args.get('sort', 'author')
    reverse = (request.args.get('direction', 'asc') == 'desc')    
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    voteRulesTrx = VoteRulesTrx(db)
    try:
        rules = voteRulesTrx.get_posts(name)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        voteRulesTrx = VoteRulesTrx(db)
        rules = voteRulesTrx.get_posts(name)
    accountsTrx = AccountsDB(db)    
    setting = accountsTrx.get(name)
    if setting is None:
        frontend = "https://steemit.com/"
    else:
        frontend = setting["frontend"]
    try:
        sorted_rules = sorted(rules, key=lambda x: x[sort] or 0, reverse=reverse)
    except:
        sorted_rules = rules    
        
    table = Results(sorted_rules)
    table.author.frontend = frontend
    table.border = True
    return render_template('show_rules.html', table=table, user=name)    

@app.route('/show_trail_rules', methods=['GET'])
@login
def show_trail_rules():
    sort = request.args.get('sort', 'voter_to_follow')
    reverse = (request.args.get('direction', 'asc') == 'desc')      
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    trailVoteRulesTrx = TrailVoteRulesTrx(db)
 
    try:
        rules = trailVoteRulesTrx.get_rules_by_account(name)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        trailVoteRulesTrx = TrailVoteRulesTrx(db)
        rules = trailVoteRulesTrx.get_rules_by_account(name)
    try:
        sorted_rules = sorted(rules, key=lambda x: x[sort] or 0, reverse=reverse)
    except:
        sorted_rules = rules      
    table = TrailResults(sorted_rules)
    table.border = True
    table.table_id = "rules"
    table.classes  = ["display"] 
    return render_template('show_trail_rules.html', table=table, user=name)

@app.route('/show_trail_downvote_rules', methods=['GET'])
@login
def show_trail_downvote_rules():
    sort = request.args.get('sort', 'voter_to_follow')
    reverse = (request.args.get('direction', 'asc') == 'desc')      
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    trailDownVoteRulesTrx = TrailDownVoteRulesTrx(db)
 
    try:
        rules = trailDownVoteRulesTrx.get_rules_by_account(name)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        trailDownVoteRulesTrx = TrailDownVoteRulesTrx(db)
        rules = trailDownVoteRulesTrx.get_rules_by_account(name)
    try:
        sorted_rules = sorted(rules, key=lambda x: x[sort] or 0, reverse=reverse)
    except:
        sorted_rules = rules      
    table = TrailDownVoteResults(sorted_rules)
    table.border = True
    table.table_id = "rules"
    table.classes  = ["display"] 
    return render_template('show_trail_downvote_rules.html', table=table, user=name)


@app.route('/show_vote_log', methods=['GET'])
@login
def show_vote_log():
    
    sort = request.args.get('sort', 'timestamp')
    reverse = (request.args.get('direction', 'desc') == 'desc')
    
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    voteLogTrx = VoteLogTrx(db)

    try:
        logs = voteLogTrx.get_votes(name)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        voteLogTrx = VoteLogTrx(db)
        logs = voteLogTrx.get_votes(name)
    accountsTrx = AccountsDB(db)    
    setting = accountsTrx.get(name)
    if setting is None:
        frontend = "https://steemit.com/"
    else:
        frontend = setting["frontend"]    
    try:
        sorted_log = sorted(logs, key=lambda x: x[sort] or 0, reverse=reverse)
    except:
        sorted_log = logs
    table = VotesLog(sorted_log)
    table.authorperm.frontend = frontend
    table.author.frontend = frontend
    table.border = True
    return render_template('votes_log.html', table=table, user=name)


@app.route('/api/vote_log', methods=['GET', 'POST'])
def api_vote_log():
    if request.method == 'POST':
        json_data = request.get_json()
    else:
        json_data = request.args       
    access_token = json_data.get('access_token', None)
    sort = json_data.get('sort', 'timestamp')
    reverse = (json_data.get('direction', 'desc') == 'desc')
    if access_token is None:
        return jsonify([])
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        return jsonify([])
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    voteLogTrx = VoteLogTrx(db)

    try:
        logs = voteLogTrx.get_votes(name)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        voteLogTrx = VoteLogTrx(db)
        logs = voteLogTrx.get_votes(name)
    accountsTrx = AccountsDB(db)    
 
    try:
        sorted_log = sorted(logs, key=lambda x: x[sort] or 0, reverse=reverse)
    except:
        sorted_log = logs

    return jsonify(sorted_log)


@app.route('/api/vote_rules', methods=['GET', 'POST'])
def api_vote_rules():
    if request.method == 'POST':
        json_data = request.get_json()
    else:
        json_data = request.args        
    access_token = json_data.get('access_token', None)
    sort = json_data.get('sort', 'timestamp')
    reverse = (json_data.get('direction', 'desc') == 'desc')
    if access_token is None:
        return jsonify([])
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        return jsonify([])
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    voteRulesTrx = VoteRulesTrx(db)

    try:
        rules = voteRulesTrx.get_posts(name)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        voteRulesTrx = VoteRulesTrx(db)
        rules = voteRulesTrx.get_posts(name)
 
    try:
        sorted_rules = sorted(rules, key=lambda x: x[sort] or 0, reverse=reverse)
    except:
        sorted_rules = rules   

    return jsonify(sorted_rules)

@app.route('/api/new_trail_vote_rule', methods=['GET', 'POST'])
def api_new_trail_vote_rule():
    if request.method == 'POST':
        json_data = request.get_json()
    else:
        json_data = request.args    
    access_token = json_data.get('access_token', None)
    voter_to_follow = json_data.get("voter_to_follow", None)

    if access_token is None:
        return jsonify({})
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        return jsonify({})
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    trailVoteRulesTrx = TrailVoteRulesTrx(db)
    rule = {"voter_to_follow": voter_to_follow, "account": name}
    for key in json_data:
        if key in ["voter_to_follow", "account"]:
            continue
        if key not in ["only_main_post", "vote_weight_threshold", "include_authors", "exclude_authors", "min_vp", "vote_weight_scaler", "vote_weight_offset", "max_votes_per_day", "max_votes_per_week", "include_tags", "exclude_tags", "exclude_declined_payout", "minimum_vote_delay_min", "maximum_vote_delay_min", "enabled", "max_net_votes", "max_pending_payout", "vp_scaler", "scale_weight_to_voter_vp_diff", "vote_when_vp_reached", "vp_reached_order", "vote_sbd", "exclude_authors_with_vote_rule", "note", "vote_delay_scaler"]:
            continue
        value = json_data.get(key, None)
        if value == None:
            continue
        rule[key] = value
    
    trailVoteRulesTrx.add(rule)
    rule = trailVoteRulesTrx.get(voter_to_follow, name)    
        
    return jsonify(rule)

@app.route('/api/new_trail_downvote_rule', methods=['GET', 'POST'])
def api_new_trail_downvote_rule():
    if request.method == 'POST':
        json_data = request.get_json()
    else:
        json_data = request.args    
    access_token = json_data.get('access_token', None)
    voter_to_follow = json_data.get("voter_to_follow", None)

    if access_token is None:
        return jsonify({})
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        return jsonify({})
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    trailDownVoteRulesTrx = TrailDownVoteRulesTrx(db)
    rule = {"voter_to_follow": voter_to_follow, "account": name}
    for key in json_data:
        if key in ["voter_to_follow", "account"]:
            continue
        if key not in ["only_main_post", "vote_weight_threshold", "include_authors", "exclude_authors", "min_vp", "vote_weight_scaler", "vote_weight_offset", "max_votes_per_day", "max_votes_per_week", "include_tags", "exclude_tags", "exclude_declined_payout", "minimum_vote_delay_min", "maximum_vote_delay_min", "enabled", "max_net_votes", "max_pending_payout", "vp_scaler", "scale_weight_to_voter_vp_diff", "vote_when_vp_reached", "vp_reached_order", "vote_sbd", "exclude_authors_with_vote_rule", "note", "vote_delay_scaler"]:
            continue
        value = json_data.get(key, None)
        if value == None:
            continue
        rule[key] = value
    
    trailDownVoteRulesTrx.add(rule)
    rule = trailDownVoteRulesTrx.get(voter_to_follow, name)    
        
    return jsonify(rule)

@app.route('/api/new_vote_rule', methods=['GET', 'POST'])
def api_new_vote_rule():
    if request.method == 'POST':
        json_data = request.get_json()
    else:
        json_data = request.args    
    access_token = json_data.get('access_token', None)
    author = json_data.get('author', None)
    main_post = json_data.get('main_post', None)
    try:
        main_post = bool(main_post)
    except:
        return jsonify({})
    if access_token is None:
        return jsonify({})
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        return jsonify({})
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    voteRulesTrx = VoteRulesTrx(db)
    rule = {"author": author, "main_post": main_post, "voter": name}
    for key in json_data:
        if key in ["author", "main_post", "access_token", "voter"]:
            continue
        if key not in ["vote_delay_min", "vote_weight", "enabled", "vote_sbd", "max_votes_per_day", "max_votes_per_week", "include_tags", "exclude_tags", "vote_when_vp_reached", "min_vp", "vp_scaler", "leave_comment", "minimum_word_count", "include_apps", "exclude_apps", "exclude_declined_payout", "vp_reached_order", "max_net_votes", "max_pending_payout", "include_text", "exclude_text", "maximum_vote_delay_min", "disable_optimization", "note"]:
            continue
        value = json_data.get(key, None)
        if value == None:
            continue
        rule[key] = value
    voteRulesTrx.add(rule)
    rule = voteRulesTrx.get(name, author, main_post)
        
    return jsonify(rule)

@app.route('/api/delayed_vote', methods=['GET', 'POST'])
def api_delayed_vote():
    if request.method == 'POST':
        json_data = request.get_json()
    else:
        json_data = request.args    
    access_token = json_data.get('access_token', None)
    authorperm = json_data.get('authorperm', None)

    if access_token is None:
        return jsonify({})
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        return jsonify({})
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    pendingVotesTrx = PendingVotesTrx(db)
    
    try:
        authorperm = authorperm
        if authorperm.find("@") > 1:
            authorperm = authorperm[authorperm.find("@"):]
        c = Comment(authorperm, steem_instance=stm)
    except:
        return jsonify("Wrong authorperm!")    
    
    vote_dict = {"authorperm": authorperm, "voter": name}
    
    if not (c.is_pending() and valid_age(c)):
        stm.unlock(wallet_password)
        body = "The reward of this comment goes 100 %% to the author %s. This is done by setting the beneficiaries of this comment to 100 %%.\n\n" % (c["author"])
        comment_beneficiaries = [{"account": c["author"], "weight": 10000}]
        permlink = derive_permlink("rewarding %s" % c["author"], c["permlink"])
        stm.post("rewarding %s" % c["author"], body, author="rewarding", permlink=permlink, reply_identifier=c["authorperm"], beneficiaries=comment_beneficiaries)
        stm.wallet.lock()
        authorperm = construct_authorperm("rewarding", permlink)
        vote_dict["comment_timestamp"] = datetime.utcnow()
        vote_dict["authorperm"] = authorperm
    else:        
        vote_dict["comment_timestamp"] = c["created"].replace(tzinfo=None)
        vote_dict["exclude_declined_payout"] = False
    
    for key in json_data:
        if key in ["authorperm", "voter", "access_token", "comment_timestamp", "exclude_declined_payout"]:
            continue
        if key not in ["vote_weight", "vote_delay_min", "created", "min_vp", "vote_when_vp_reached", "vp_reached_order", "max_net_votes", "max_pending_payout", "max_votes_per_day", "max_votes_per_week", "vp_scaler", "leave_comment", "comment_command", "exclude_declined_payout", "maximum_vote_delay_min", "vote_sbd", "trail_vote", "vote_delay_scaler", "main_post", "voter_to_follow"]:
            continue
        value = json_data.get(key, None)
        if value == None:
            continue
        vote_dict[key] = value
    
    try:
        pendingVotesTrx.add(vote_dict)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        pendingVotesTrx = PendingVotesTrx(db)        
        pendingVotesTrx.add(vote_dict)    

    pending_votes = pendingVotesTrx.get_votes(name)
        
    return jsonify(pending_votes)


@app.route('/api/delete_vote_rule', methods=['GET', 'POST'])
def api_delete_vote_rule():
    if request.method == 'POST':
        json_data = request.get_json()
    else:
        json_data = request.args    
    access_token = json_data.get('access_token', None)
    author = json_data.get('author', None)
    main_post = json_data.get('main_post', None)
    try:
        main_post = bool(main_post)
    except:
        return jsonify({})
    if access_token is None:
        return jsonify({})
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        return jsonify({})
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    voteRulesTrx = VoteRulesTrx(db)

    voteRulesTrx.delete(name, author, main_post)
    rule = voteRulesTrx.get(name, author, main_post)
        
    return jsonify(rule)

@app.route('/api/delete_trail_vote_rule', methods=['GET', 'POST'])
def api_delete_trail_vote_rule():
    if request.method == 'POST':
        json_data = request.get_json()
    else:
        json_data = request.args    
    access_token = json_data.get('access_token', None)
    voter_to_follow = json_data.get("voter_to_follow", None)
    try:
        main_post = bool(main_post)
    except:
        return jsonify({})
    if access_token is None:
        return jsonify({})
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        return jsonify({})
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    trailVoteRulesTrx = TrailVoteRulesTrx(db)
    trailVoteRulesTrx.delete(voter_to_follow, name)
    rule = trailVoteRulesTrx.get(voter_to_follow, name)
    return jsonify(rule)

@app.route('/api/delete_trail_downvote_rule', methods=['GET', 'POST'])
def api_delete_trail_downvote_rule():
    if request.method == 'POST':
        json_data = request.get_json()
    else:
        json_data = request.args    
    access_token = json_data.get('access_token', None)
    voter_to_follow = json_data.get("voter_to_follow", None)
    try:
        main_post = bool(main_post)
    except:
        return jsonify({})
    if access_token is None:
        return jsonify({})
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        return jsonify({})
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    trailDownVoteRulesTrx = TrailDownVoteRulesTrx(db)
    trailDownVoteRulesTrx.delete(voter_to_follow, name)
    rule = trailDownVoteRulesTrx.get(voter_to_follow, name)
    return jsonify(rule)

@app.route('/api/edit_vote_rule', methods=['GET', 'POST'])
def api_edit_vote_rule():
    if request.method == 'POST':
        json_data = request.get_json()
    else:
        json_data = request.args
        
    access_token = json_data.get('access_token', None)
    author = json_data.get('author', None)
    main_post = json_data.get('main_post', None)
    if access_token is None:
        return jsonify([])
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        return jsonify([])
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    voteRulesTrx = VoteRulesTrx(db)

    try:
        rule = voteRulesTrx.get(name, author, main_post)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        voteRulesTrx = VoteRulesTrx(db)
        rule = voteRulesTrx.get(name, author, main_post)
 
    change_detected = False
    for key in rule:
        if key in ["author", "main_post", "voter"]:
            continue
        value = json_data.get(key, None)
        if value == None:
            continue
        change_detected = True
        rule[key] = value
    if change_detected:
        voteRulesTrx.update(rule)
        rule = voteRulesTrx.get(name, author, main_post)
        
    return jsonify(rule)


@app.route('/api/edit_trail_vote_rule', methods=['GET', 'POST'])
def api_edit_trail_vote_rule():
    if request.method == 'POST':
        json_data = request.get_json()
    else:
        json_data = request.args    
    access_token = json_data.get('access_token', None)
    voter_to_follow = json_data.get("voter_to_follow", None)
    if access_token is None:
        return jsonify([])
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        return jsonify([])
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    trailVoteRulesTrx = TrailVoteRulesTrx(db)

    try:
        rule = trailVoteRulesTrx.get(voter_to_follow, name)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        trailVoteRulesTrx = TrailVoteRulesTrx(db)
        rule = trailVoteRulesTrx.get(voter_to_follow, name)
 
    change_detected = False
    for key in rule:
        if key in ["voter_to_follow"]:
            continue
        value = json_data.get(key, None)
        if value == None:
            continue
        change_detected = True
        rule[key] = value
    if change_detected:
        trailVoteRulesTrx.update(rule)
        rule = trailVoteRulesTrx.get(voter_to_follow, name)
        
    return jsonify(rule)

@app.route('/api/trail_vote_rules', methods=['GET', 'POST'])
def api_trail_vote_rules():
    if request.method == 'POST':
        json_data = request.get_json()
    else:
        json_data = request.args        
    access_token = json_data.get('access_token', None)
    sort = json_data.get('sort', 'timestamp')
    reverse = (json_data.get('direction', 'desc') == 'desc')
    if access_token is None:
        return jsonify([])
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        return jsonify([])
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    trailVoteRulesTrx = TrailVoteRulesTrx(db)

    try:
        rules = trailVoteRulesTrx.get_rules_by_account(name)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        trailVoteRulesTrx = TrailVoteRulesTrx(db)
        rules = trailVoteRulesTrx.get_rules_by_account(name)
 
    try:
        sorted_rules = sorted(rules, key=lambda x: x[sort] or 0, reverse=reverse)
    except:
        sorted_rules = rules   

    return jsonify(sorted_rules)

@app.route('/api/edit_trail_downvote_rule', methods=['GET', 'POST'])
def api_edit_trail_downvote_rule():
    if request.method == 'POST':
        json_data = request.get_json()
    else:
        json_data = request.args    
    access_token = json_data.get('access_token', None)
    voter_to_follow = json_data.get("voter_to_follow", None)
    if access_token is None:
        return jsonify([])
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        return jsonify([])
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    trailDownVoteRulesTrx = TrailDownVoteRulesTrx(db)

    try:
        rule = trailVoteRulesTrx.get(voter_to_follow, name)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        trailDownVoteRulesTrx = TrailDownVoteRulesTrx(db)
        rule = trailDownVoteRulesTrx.get(voter_to_follow, name)
 
    change_detected = False
    for key in rule:
        if key in ["voter_to_follow"]:
            continue
        value = json_data.get(key, None)
        if value == None:
            continue
        change_detected = True
        rule[key] = value
    if change_detected:
        trailDownVoteRulesTrx.update(rule)
        rule = trailDownVoteRulesTrx.get(voter_to_follow, name)
        
    return jsonify(rule)

@app.route('/api/trail_downvote_rules', methods=['GET', 'POST'])
def api_trail_downvote_rules():
    if request.method == 'POST':
        json_data = request.get_json()
    else:
        json_data = request.args        
    access_token = json_data.get('access_token', None)
    sort = json_data.get('sort', 'timestamp')
    reverse = (json_data.get('direction', 'desc') == 'desc')
    if access_token is None:
        return jsonify([])
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        return jsonify([])
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    trailDownVoteRulesTrx = TrailDownVoteRulesTrx(db)

    try:
        rules = trailDownVoteRulesTrx.get_rules_by_account(name)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        trailDownVoteRulesTrx = TrailDownVoteRulesTrx(db)
        rules = trailDownVoteRulesTrx.get_rules_by_account(name)
 
    try:
        sorted_rules = sorted(rules, key=lambda x: x[sort] or 0, reverse=reverse)
    except:
        sorted_rules = rules   

    return jsonify(sorted_rules)


@app.route('/api/failed_vote_log', methods=['GET', 'POST'])
def api_failed_vote_log():
    if request.method == 'POST':
        json_data = request.get_json()
    else:
        json_data = request.args        
    access_token = json_data.get('access_token', None)
    sort = json_data.get('sort', 'timestamp')
    reverse = (json_data.get('direction', 'desc') == 'desc')
    if access_token is None:
        return jsonify([])
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        return jsonify([])
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    failedVoteLogTrx = FailedVoteLogTrx(db)

    try:
        logs = failedVoteLogTrx.get_votes(name, limit=100)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        failedVoteLogTrx = FailedVoteLogTrx(db)
        logs = failedVoteLogTrx.get_votes(name, limit=100)
    try:
        sorted_log = sorted(logs, key=lambda x: x[sort] or 0, reverse=reverse)
    except:
        sorted_log = logs   

    return jsonify(sorted_log)


@app.route('/api/pending_votes', methods=['GET', 'POST'])
def api_pending_votes():
    if request.method == 'POST':
        json_data = request.get_json()
    else:
        json_data = request.args        
    access_token = json_data.get('access_token', None)
    sort = json_data.get('sort', 'timestamp')
    reverse = (json_data.get('direction', 'desc') == 'desc')
    if access_token is None:
        return jsonify([])
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        return jsonify([])
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    pendingVotesTrx = PendingVotesTrx(db)

    try:
        votes = pendingVotesTrx.get_votes(name)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        pendingVotesTrx = PendingVotesTrx(db)
        votes = pendingVotesTrx.get_votes(name)
    try:
        sorted_votes = sorted(votes, key=lambda x: x[sort] or 0, reverse=reverse)
    except:
        sorted_votes = votes   

    return jsonify(sorted_votes)


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    if request.method == 'POST':
        json_data = request.get_json()
    else:
        json_data = request.args    
    access_token = json_data.get('access_token', None)
    

    if access_token is None:
        return jsonify([])
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        return jsonify([])
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    accountsTrx = AccountsDB(db)    

    try:
        setting = accountsTrx.get(name)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        accountsTrx = AccountsDB(db)    
        setting = accountsTrx.get(name)
    
    change_detected = False
    for key in setting:
        if key in ["name"]:
            continue
        value = json_data.get(key, None)
        if value == None:
            continue
        change_detected = True
        setting[key] = value
    if change_detected:
        accountsTrx.update(setting)
        setting = accountsTrx.get(name)

    return jsonify(setting)

@app.route('/show_failed_vote_log', methods=['GET'])
@login
def show_failed_vote_log():
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    failedVoteLogTrx = FailedVoteLogTrx(db)
   
    try:
        logs = failedVoteLogTrx.get_votes(name, limit=100)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        failedVoteLogTrx = FailedVoteLogTrx(db)
        logs = failedVoteLogTrx.get_votes(name, limit=100)
    accountsTrx = AccountsDB(db)    
    setting = accountsTrx.get(name)
    if setting is None:
        frontend = "https://steemit.com/"
    else:
        frontend = setting["frontend"]    
    table = FailedVotesLog(logs)
    table.authorperm.frontend = frontend
    table.border = True
    return render_template('failed_votes_log.html', table=table, user=name)

@app.route('/show_pending_votes', methods=['GET'])
@login
def show_pending_votes():
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    pendingVotesTrx = PendingVotesTrx(db)
    try:
        votes = pendingVotesTrx.get_votes(name)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        pendingVotesTrx = PendingVotesTrx(db)
        votes = pendingVotesTrx.get_votes(name)
    accountsTrx = AccountsDB(db)    
    setting = accountsTrx.get(name)  
    if setting is None:
        frontend = "https://steemit.com/"
    else:
        frontend = setting["frontend"]    
    table = PendingVotes(votes)
    table.authorperm.frontend = frontend
    table.border = True
    return render_template('pending_votes.html', table=table, user=name)

@app.route('/<community>/<author>/<permlink>', methods=['GET', 'POST'])
@login
def delayed_vote_link(community, author, permlink):
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    pendingVotesTrx = PendingVotesTrx(db)
    authorperm = author + '/' +permlink
    form = VoteForm(request.form)
    if request.method == 'POST': # and form.validate():
        # save the rule

        vote_dict = vote_dict_from_form(name, form)
        vote_dict["created"] = datetime.utcnow()
        try:
            authorperm = vote_dict["authorperm"]
            if authorperm.find("@") > 1:
                authorperm = authorperm[authorperm.find("@"):]
            c = Comment(authorperm, steem_instance=stm)
        except:
            return "Wrong authoerperm!"
        if not (c.is_pending() and valid_age(c)):
            stm.unlock(wallet_password)
            body = "The reward of this comment goes 100 %% to the author %s. This is done by setting the beneficiaries of this comment to 100 %%.\n\n" % (c["author"])
            comment_beneficiaries = [{"account": c["author"], "weight": 10000}]
            permlink = derive_permlink("rewarding %s" % c["author"], c["permlink"])
            stm.post("rewarding %s" % c["author"], body, author="rewarding", permlink=permlink, reply_identifier=c["authorperm"], beneficiaries=comment_beneficiaries)
            stm.wallet.lock()
            authorperm = construct_authorperm("rewarding", permlink)
            vote_dict["comment_timestamp"] = datetime.utcnow()
            vote_dict["authorperm"] = authorperm
        else:
            vote_dict["comment_timestamp"] = c["created"].replace(tzinfo=None)
        vote_dict["exclude_declined_payout"] = False
        try:
            pendingVotesTrx.add(vote_dict)
        except:
            db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
            pendingVotesTrx = PendingVotesTrx(db)        
            pendingVotesTrx.add(vote_dict)
        flash('Rule created successfully!')
        return redirect('/show_pending_votes')
    else:
        form.authorperm.data = authorperm

    return render_template('delayed_vote.html', form=form, user=name)        

@app.route('/delayed_vote', methods=['GET', 'POST'])
@login
def delayed_vote():
    """
    Add a new rule
    """
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    pendingVotesTrx = PendingVotesTrx(db)
    form = VoteForm(request.form)

    if request.method == 'POST': # and form.validate():
        # save the rule

        vote_dict = vote_dict_from_form(name, form)
        vote_dict["created"] = datetime.utcnow()
        try:
            authorperm = vote_dict["authorperm"]
            if authorperm.find("@") > 1:
                authorperm = authorperm[authorperm.find("@"):]
            c = Comment(authorperm, steem_instance=stm)
        except:
            return "Wrong authorperm!"
        if not (c.is_pending() and valid_age(c)):
            stm.unlock(wallet_password)
            body = "The reward of this comment goes 100 %% to the author %s. This is done by setting the beneficiaries of this comment to 100 %%.\n\n" % (c["author"])
            comment_beneficiaries = [{"account": c["author"], "weight": 10000}]
            permlink = derive_permlink("rewarding %s" % c["author"], c["permlink"])
            stm.post("rewarding %s" % c["author"], body, author="rewarding", permlink=permlink, reply_identifier=c["authorperm"], beneficiaries=comment_beneficiaries)
            stm.wallet.lock()
            authorperm = construct_authorperm("rewarding", permlink)
            vote_dict["comment_timestamp"] = datetime.utcnow()
            vote_dict["authorperm"] = authorperm
        else:        
            vote_dict["comment_timestamp"] = c["created"].replace(tzinfo=None)
            vote_dict["exclude_declined_payout"] = False
        try:
            pendingVotesTrx.add(vote_dict)
        except:
            db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
            pendingVotesTrx = PendingVotesTrx(db)        
            pendingVotesTrx.add(vote_dict)
        flash('Rule created successfully!')
        return redirect('/show_pending_votes')

    return render_template('delayed_vote.html', form=form, user=name)


@app.route('/settings', methods=['GET', 'POST'])
@login
def settings():
    """
    Add a new rule
    """
    
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    accountsTrx = AccountsDB(db)    
    form = SettingsForm(request.form)
    setting = None
    try:
        setting = accountsTrx.get(name)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        accountsTrx = AccountsDB(db)    
        setting = accountsTrx.get(name)
        
    if request.method == 'POST': # and form.validate():
        # save the rule

        settings_dict = settings_dict_from_form(name, form)
        frontend = settings_dict["frontend"]
        try:
            accountsTrx.upsert(vote_dict)
        except:
            db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
            accountsTrx = AccountsDB(db)        
            accountsTrx.upsert(settings_dict)
        flash('Settings stored successfully!')
        
        return redirect('/welcome')
    else:
        if setting:
            form.upvote_comment.data = setting["upvote_comment"]    
            form.optimize_vote_delay.data = setting["optimize_vote_delay"] 
            form.minimum_vote_delay.data = setting["minimum_vote_delay"] 
            form.maximum_vote_delay.data = setting["maximum_vote_delay"] 
            form.optimize_ma_length.data = setting["optimize_ma_length"]
            form.optimize_threshold.data = setting["optimize_threshold"]
            form.rshares_divider.data = setting["rshares_divider"]
            form.frontend.data = setting["frontend"]
            form.sliding_time_window.data = setting["sliding_time_window"]
            form.optimize_vote_delay_slope.data = setting["optimize_vote_delay_slope"]
            form.pause_votes_below_vp.data = setting["pause_votes_below_vp"]
            form.pause_down_votes_below_down_vp.data = setting["pause_down_votes_below_down_vp"]
        return render_template('settings.html', form=form, user=name)


@app.route('/new_trail_rule', methods=['GET', 'POST'])
@login
def new_trail_rule():
    """
    Add a new rule
    """
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    trailVoteRulesTrx = TrailVoteRulesTrx(db)
    form = TrailRuleForm(request.form)

    if request.method == 'POST': # and form.validate():
        # save the rule
        rule_dict = trail_rule_dict_from_form(name, form)
        try:
            trailVoteRulesTrx.add(rule_dict)
        except:
            db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
            trailVoteRulesTrx = TrailVoteRulesTrx(db)
            trailVoteRulesTrx.add(rule_dict)        
        flash('Trail Rule created successfully!')
        return redirect('/show_trail_rules')

    return render_template('new_trail_rule.html', form=form, user=name)

@app.route('/new_trail_downvote_rule', methods=['GET', 'POST'])
@login
def new_trail_downvote_rule():
    """
    Add a new rule
    """
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    trailDownVoteRulesTrx = TrailDownVoteRulesTrx(db)
    form = TrailDownVoteRuleForm(request.form)

    if request.method == 'POST': # and form.validate():
        # save the rule
        rule_dict = trail_downvote_rule_dict_from_form(name, form)
        try:
            trailDownVoteRulesTrx.add(rule_dict)
        except:
            db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
            trailDownVoteRulesTrx = TrailVoteRulesTrx(db)
            trailDownVoteRulesTrx.add(rule_dict)        
        flash('Trail Downvote Rule created successfully!')
        return redirect('/show_trail_downvote_rules')

    return render_template('new_trail_downvote_rule.html', form=form, user=name)


@app.route('/@<author>', methods=['GET', 'POST'])
@login
def new_rule_link(author):
    """
    Add a new rule
    """
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    voteRulesTrx = VoteRulesTrx(db)    
    form = RuleForm(request.form)

    if request.method == 'POST': # and form.validate():
        # save the rule
        rule_dict = rule_dict_from_form(name, form)
        try:
            voteRulesTrx.add(rule_dict)
        except:
            db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
            voteRulesTrx = VoteRulesTrx(db)
            voteRulesTrx.add(rule_dict)        
        flash('Rule created successfully!')
        return redirect('/show_rules')
    else:
        form.author.data = author

    return render_template('new_rule.html', form=form, user=name)


@app.route('/new_rule', methods=['GET', 'POST'])
@login
def new_rule():
    """
    Add a new rule
    """
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    voteRulesTrx = VoteRulesTrx(db)    
    form = RuleForm(request.form)

    if request.method == 'POST': # and form.validate():
        # save the rule
        rule_dict = rule_dict_from_form(name, form)
        try:
            voteRulesTrx.add(rule_dict)
        except:
            db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
            voteRulesTrx = VoteRulesTrx(db)
            voteRulesTrx.add(rule_dict)        
        flash('Rule created successfully!')
        return redirect('/show_rules')

    return render_template('new_rule.html', form=form, user=name)

@app.route('/edit_rule', methods=['GET', 'POST'])
@login
def edit_rule():
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    voteRulesTrx = VoteRulesTrx(db)     
    # access_token = request.args.get("access_token", None)
    author = request.args.get("author", None)
    main_post = request.args.get("main_post", None)
    copy_rule = request.args.get("copy_rule", None)
    voter_to_follow = request.args.get("voter_to_follow", None)
    if voter_to_follow is not None:
        return redirect('/edit_trail_rule?voter_to_follow=%s' % voter_to_follow)
    elif main_post is None or author is None:
        return redirect('/show_vote_log')
    if copy_rule is None or not copy_rule:
        helptext = "Editing author and/or main_post will delete the original rule and create a new rule with the new author/main_post flag."
    else:
        helptext = "Editing author and/or main_post will keep the original rule and create a new rule with the new author/main_post flag."
    try:
        rule = voteRulesTrx.get(name, author, main_post)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        voteRulesTrx = VoteRulesTrx(db)    
        rule = voteRulesTrx.get(name, author, main_post)
    if rule:
        form = RuleForm(formdata=request.form)
        if request.method == 'POST': # and form.validate():
            rule_dict = rule_dict_from_form(name, form)
            if rule_dict["author"] == "":
                return redirect('/show_rules')
            if rule_dict["author"][0] == '@':
                rule_dict["author"] = rule_dict["author"][1:]
            if len(rule_dict["author"]) > 16:
                return redirect('/show_rules')
            if rule_dict["author"] != author or rule_dict["main_post"] != main_post:
                if copy_rule is None or not copy_rule:
                    voteRulesTrx.delete(name, author, main_post)
                voteRulesTrx.add(rule_dict)
            else:
                voteRulesTrx.update(rule_dict)
            return redirect('/show_rules')
        else:
            form = set_form(form, rule)
        return render_template('edit_rule.html', form=form, helptext=helptext, user=name)

@app.route('/delete_rule', methods=['GET', 'POST'])
@login
def delete_rule():
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    voteRulesTrx = VoteRulesTrx(db)    
    author = request.args.get("author", None)
    main_post = request.args.get("main_post", None)
    try:
        rule = voteRulesTrx.get(name, author, main_post)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        voteRulesTrx = VoteRulesTrx(db)    
        rule = voteRulesTrx.get(name, author, main_post)
    if rule:
        form = RuleForm(formdata=request.form)
        if request.method == 'POST': # and form.validate():
            voteRulesTrx.delete(name, author, main_post)
            return redirect('/show_rules')
        else:
            form = set_form(form, rule)
        return render_template('delete_rule.html', form=form, user=name)

@app.route('/edit_trail_rule', methods=['GET', 'POST'])
@login
def edit_trail_rule():
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    trailVoteRulesTrx = TrailVoteRulesTrx(db)    
    voter_to_follow = request.args.get("voter_to_follow", None)
    copy_rule = request.args.get("copy_rule", None)
    if voter_to_follow is None:
        return redirect('/show_vote_log')
    if copy_rule is None or not copy_rule:
        helptext = "Editing voter_to_follow will delete the original rule and create a new rule with the new voter_to_follow."
    else:
        helptext = "Editing voter_to_follow will keep the original rule and create a new rule with the new voter_to_follow."
    
    try:
        rule = trailVoteRulesTrx.get(voter_to_follow, name)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        trailVoteRulesTrx = TrailVoteRulesTrx(db)    
        rule = trailVoteRulesTrx.get(voter_to_follow, name)
    if rule:
        form = TrailRuleForm(formdata=request.form)
        if request.method == 'POST': # and form.validate():
            rule_dict = trail_rule_dict_from_form(name, form)
            if rule_dict["voter_to_follow"] != voter_to_follow:
                if copy_rule is None or not copy_rule:
                    trailVoteRulesTrx.delete(voter_to_follow, name)
                trailVoteRulesTrx.add(rule_dict)
            else:            
                trailVoteRulesTrx.update(rule_dict)
            return redirect('/show_trail_rules')
        else:
            form = set_form_trail_votes(form, rule)
        return render_template('edit_trail_rule.html', form=form, helptext=helptext, user=name)

@app.route('/delete_trail_rule', methods=['GET', 'POST'])
@login
def delete_trail_rule():
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    trailVoteRulesTrx = TrailVoteRulesTrx(db)    
    voter_to_follow = request.args.get("voter_to_follow", None)
    try:
        rule = trailVoteRulesTrx.get(voter_to_follow, name)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        trailVoteRulesTrx = TrailVoteRulesTrx(db)
        rule = trailVoteRulesTrx.get(voter_to_follow, name)
    if rule:
        form = TrailRuleForm(formdata=request.form)
        if request.method == 'POST': # and form.validate():
            trailVoteRulesTrx.delete(voter_to_follow, name)
            return redirect('/show_trail_rules')
        else:
            form = set_form_trail_votes(form, rule)
        return render_template('delete_trail_rule.html', form=form, user=name)

@app.route('/edit_trail_downvote_rule', methods=['GET', 'POST'])
@login
def edit_trail_downvote_rule():
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    trailDownVoteRulesTrx = TrailDownVoteRulesTrx(db)    
    voter_to_follow = request.args.get("voter_to_follow", None)
    copy_rule = request.args.get("copy_rule", None)
    if voter_to_follow is None:
        return redirect('/show_vote_log')
    if copy_rule is None or not copy_rule:
        helptext = "Editing voter_to_follow will delete the original rule and create a new rule with the new voter_to_follow."
    else:
        helptext = "Editing voter_to_follow will keep the original rule and create a new rule with the new voter_to_follow."
    
    try:
        rule = trailDownVoteRulesTrx.get(voter_to_follow, name)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        trailDownVoteRulesTrx = TrailVoteRulesTrx(db)    
        rule = trailDownVoteRulesTrx.get(voter_to_follow, name)
    if rule:
        form = TrailDownVoteRuleForm(formdata=request.form)
        if request.method == 'POST': # and form.validate():
            rule_dict = trail_downvote_rule_dict_from_form(name, form)
            if rule_dict["voter_to_follow"] != voter_to_follow:
                if copy_rule is None or not copy_rule:
                    trailDownVoteRulesTrx.delete(voter_to_follow, name)
                trailDownVoteRulesTrx.add(rule_dict)
            else:            
                trailDownVoteRulesTrx.update(rule_dict)
            return redirect('/show_trail_downvote_rules')
        else:
            form = set_form_trail_downvotes(form, rule)
        return render_template('edit_trail_downvote_rule.html', form=form, helptext=helptext, user=name)

@app.route('/delete_trail_downvote_rule', methods=['GET', 'POST'])
@login
def delete_trail_downvote_rule():
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    trailDownVoteRulesTrx = TrailDownVoteRulesTrx(db)    
    voter_to_follow = request.args.get("voter_to_follow", None)
    try:
        rule = trailDownVoteRulesTrx.get(voter_to_follow, name)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        trailDownVoteRulesTrx = TrailDownVoteRulesTrx(db)
        rule = trailDownVoteRulesTrx.get(voter_to_follow, name)
    if rule:
        form = TrailDownVoteRuleForm(formdata=request.form)
        if request.method == 'POST': # and form.validate():
            trailDownVoteRulesTrx.delete(voter_to_follow, name)
            return redirect('/show_trail_downvote_rules')
        else:
            form = set_form_trail_votes(form, rule)
        return render_template('delete_trail_downvote_rule.html', form=form, user=name)

@app.route('/delete_vote', methods=['GET', 'POST'])
@login
def delete_vote():
    name = steemconnect.me()["name"]
    db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
    pendingVotesTrx = PendingVotesTrx(db)    
    authorperm = request.args.get("authorperm", None)
    vote_when_vp_reached = request.args.get("vote_when_vp_reached", None)
    try:
        pendingVotesTrx.delete(authorperm, name, vote_when_vp_reached)
    except:
        db = dataset.connect(databaseConnector, engine_kwargs={'pool_recycle': 3600})
        pendingVotesTrx = PendingVotesTrx(db)    
        pendingVotesTrx.delete(authorperm, name, vote_when_vp_reached)

    return redirect('show_pending_votes')

if __name__ == '__main__':
    app.run()