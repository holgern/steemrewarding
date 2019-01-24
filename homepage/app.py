from flask import Flask, jsonify, request, render_template, redirect, url_for, session, flash
from flask_wtf import FlaskForm
from flask_table import Table, Col, LinkCol
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
from beem.utils import formatTimeString, construct_authorperm, formatTimedelta, addTzInfo, resolve_authorperm
from beem.vote import AccountVotes, ActiveVotes
from beem import exceptions
from beem.version import version as __version__
from beem.asciichart import AsciiChart
from beem.transactionbuilder import TransactionBuilder
from beem.version import version as beem_version
from beem.steemconnect import SteemConnect
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
from wtforms import Form, StringField, SelectField, validators, BooleanField, FloatField, IntegerField
from steemrewarding.vote_rule_storage import VoteRulesTrx
from steemrewarding.vote_log_storage import VoteLogTrx
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

steemconnect = SteemConnect(client_id="beem.app", scope="login", get_refresh_token=False)


# print(config_data)
databaseConnector = config_data["databaseConnector"]


def valid_age(post, hours=156):
    """
    Checks if post is within last twelve hours before payout.
    """
    if post.time_elapsed() > timedelta(hours=hours):
        return False
    return True



class Results(Table):
    voter = Col('voter')
    author = Col('author')
    main_post = Col('main_post')
    vote_delay_min = Col('Vote delay min')
    include_tags = Col('include tags')
    exclude_tags = Col('exclude tags')
    vote_weight = Col('vote_weight')
    enabled = Col('enabled')
    vote_sbd = Col('vote_sbd')
    max_votes_per_day = Col('max votes per day')
    max_votes_per_week = Col('max votes per week')
    vote_when_vp_reached = Col('vote when vp reached')
    min_vp = Col('min vp')
    vp_scaler = Col('vp scaler')
    leave_comment = Col('leave comment')
    minimum_word_count = Col('minimum word count')
    include_apps = Col('include apps')
    exclude_apps = Col('exclude apps')
    exclude_declined_payout = Col('exclude declined payout')
    vp_reached_order = Col('vp reached order')
    max_net_votes = Col('max net votes')
    max_pending_payout = Col('max pending payout')
    include_text = Col('include text')
    exclude_text = Col('exclude text')
    edit = LinkCol('Edit', 'edit_rule', url_kwargs=dict(author='author', main_post='main_post'))
    delete = LinkCol('Delete', 'delete_rule', url_kwargs=dict(author='author', main_post='main_post'))
    # edit = LinkCol('Edit', 'edit', url_kwargs=dict(voter='voter'))


class VotesLog(Table):
    voter = Col('voter')
    authorperm = Col('authorperm')
    author = Col('author')
    timestamp = Col('timestamp')
    vote_weight = Col('vote weight')
    vote_delay_min = Col('vote delay min')
    voted_after_min = Col('voted after min')
    vp = Col('vp')
    vote_when_vp_reached = Col('vote when vp reached')

class RuleForm(FlaskForm):

    author = StringField('author')
    main_post = BooleanField('main_post', default=True)
    vote_delay_min = FloatField('vote_delay_min', default=15.0)
    include_tags = StringField('include_tags')
    exclude_tags = StringField('exclude_tags')
    
    vote_weight = FloatField('vote_weight', default=100.0)
    enabled = BooleanField('enabled', default=True)
    vote_sbd = FloatField('vote_sbd', default=0.0)
    max_votes_per_day = IntegerField('max_votes_per_day', default=-1)
    max_votes_per_week = IntegerField('max_votes_per_week', default=-1)
    vote_when_vp_reached = BooleanField('vote_when_vp_reached')
    min_vp = FloatField('min_vp', default=90.0)
    vp_scaler = FloatField('vp_scaler', default=0.0)
    leave_comment = BooleanField('leave_comment')
    minimum_word_count = IntegerField('minimum_word_count', default=0)
    include_apps = StringField('include_apps')
    exclude_apps = StringField('exclude_apps')
    exclude_declined_payout = BooleanField('exclude_declined_payout', default=True)
    vp_reached_order = IntegerField('vp_reached_order', default=1)
    max_net_votes = IntegerField('max_net_votes', default=-1)
    max_pending_payout = FloatField('max_pending_payout', default=-1.0)
    
    include_text = StringField('include_text')
    exclude_text = StringField('exclude_text')


def set_form(form, rule):
    form.author.data = rule["author"]
    form.main_post.data = rule["main_post"]
    form.vote_delay_min.data = rule["vote_delay_min"]
    form.include_tags.data = rule["include_tags"]
    form.exclude_tags.data = rule["exclude_tags"]
    form.vote_weight.data = rule["vote_weight"]
    form.enabled.data = rule["enabled"]
    form.vote_sbd.data = rule["vote_sbd"]
    form.max_votes_per_day.data = rule["max_votes_per_day"]
    form.max_votes_per_week.data = rule["max_votes_per_week"]
    form.vote_when_vp_reached.data = rule["vote_when_vp_reached"]
    form.min_vp.data = rule["min_vp"]
    form.vp_scaler.data = rule["vp_scaler"]
    form.leave_comment.data = rule["leave_comment"]
    form.minimum_word_count.data = rule["minimum_word_count"]
    form.include_apps.data = rule["include_apps"]
    form.exclude_apps.data = rule["exclude_apps"]
    form.exclude_declined_payout.data = rule["exclude_declined_payout"]
    form.vp_reached_order.data = rule["vp_reached_order"]
    form.max_net_votes.data = rule["max_net_votes"]
    form.max_pending_payout.data = rule["max_pending_payout"]
    form.include_text.data = rule["include_text"]
    form.exclude_text.data = rule["exclude_text"]
    return form

def rule_dict_from_form(voter, form):
    """
    Save the changes to the database
    """

    rule = {"voter": voter, "author": form.author.data, "main_post": form.main_post.data,
            "vote_delay_min": form.vote_delay_min.data, "include_tags": form.include_tags.data,
            "exclude_tags": form.exclude_tags.data, "vote_weight": form.vote_weight.data,
            "enabled": form.enabled.data, "vote_sbd": form.vote_sbd.data, "max_votes_per_day": form.max_votes_per_day.data,
            "max_votes_per_week": form.max_votes_per_week.data, "vote_when_vp_reached": form.vote_when_vp_reached.data,
            "min_vp": form.min_vp.data, "vp_scaler": form.vp_scaler.data, "leave_comment": form.leave_comment.data,
            "minimum_word_count": form.minimum_word_count.data, "include_apps": form.include_apps.data, "exclude_apps": form.exclude_apps.data,
            "exclude_declined_payout": form.exclude_declined_payout.data, "vp_reached_order": form.vp_reached_order.data, "max_net_votes": form.max_net_votes.data,
            "max_pending_payout": form.max_pending_payout.data, "include_text": form.include_text.data, "exclude_text": form.exclude_text.data}

    return rule


@app.route('/')
def main():
    access_token = request.args.get("access_token", None)
    if access_token is None and 'access_token' not in session:
        login_url = steemconnect.get_login_url(
            "https://steemrewarding.com/welcome",
        )        
        return "Please login! <a href='%s'>Login with SteemConnect</a>" % login_url        
    elif access_token is None:
        access_token = session['access_token']
    else:
        session['access_token'] = access_token
    try:
      
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        login_url = steemconnect.get_login_url(
            "https://steemrewarding.com/welcome",
        )        
        return "Please login! <a href='%s'>Login with SteemConnect</a>" % login_url
    # return name

    return render_template('welcome.html', user=name)

@app.route('/logout')
def logout():
       
    if 'access_token' in session:
        session['access_token'] = None

        login_url = steemconnect.get_login_url(
            "https://steemrewarding.com/welcome",
        )        
        return "Logout successfull! <a href='%s'>Login with SteemConnect</a>" % login_url

    return render_template('welcome.html', user=name)

@app.route('/welcome', methods=['GET'])
def welcome():
    access_token = request.args.get("access_token", None)
    if access_token is None and 'access_token' not in session:
        login_url = steemconnect.get_login_url(
            "https://steemrewarding.com/welcome",
        )        
        return "Please login! <a href='%s'>Login with SteemConnect</a>" % login_url        
    elif access_token is None:
        access_token = session['access_token']
    else:
        session['access_token'] = access_token
    try:
      
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        login_url = steemconnect.get_login_url(
            "https://steemrewarding.com/welcome",
        )        
        return "Please login! <a href='%s'>Login with SteemConnect</a>" % login_url
    # return name

    return render_template('welcome.html', user=name)

@app.route('/show_rules', methods=['GET'])
def show_rules():
    access_token = request.args.get("access_token", None)
    if access_token is None and 'access_token' not in session:
        login_url = steemconnect.get_login_url(
            "https://steemrewarding.com/welcome",
        )        
        return "Please login! <a href='%s'>Login with SteemConnect</a>" % login_url        
    elif access_token is None:
        access_token = session['access_token']
    else:
        session['access_token'] = access_token
    try:
      
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        login_url = steemconnect.get_login_url(
            "https://steemrewarding.com/welcome",
        )        
        return "Please login! <a href='%s'>Login with SteemConnect</a>" % login_url
    # return name
    db = dataset.connect(databaseConnector)
    voteRulesTrx = VoteRulesTrx(db)
    rules = voteRulesTrx.get_posts(name)
    table = Results(rules)
    table.border = True
    return render_template('show_rules.html', table=table)    

@app.route('/show_vote_log', methods=['GET'])
def show_vote_log():
    access_token = request.args.get("access_token", None)
    if access_token is None and 'access_token' not in session:
        login_url = steemconnect.get_login_url(
            "https://steemrewarding.com/welcome",
        )        
        return "Please login! <a href='%s'>Login with SteemConnect</a>" % login_url        
    elif access_token is None:
        access_token = session['access_token']
    else:
        session['access_token'] = access_token
    try:
      
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        login_url = steemconnect.get_login_url(
            "https://steemrewarding.com/welcome",
        )        
        return "Please login! <a href='%s'>Login with SteemConnect</a>" % login_url
    # return name
    db = dataset.connect(databaseConnector)
    voteLogTrx = VoteLogTrx(db)
    logs = voteLogTrx.get_votes(name)
    table = VotesLog(logs)
    table.border = True
    return render_template('votes_log.html', table=table)

@app.route('/new_rule', methods=['GET', 'POST'])
def new_rule():
    """
    Add a new rule
    """
    
    access_token = request.args.get("access_token", None)
 
    # access_token = session['access_token']
    try:
        if access_token is None:
            access_token = session['access_token']           
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        login_url = steemconnect.get_login_url(
            "https://steemrewarding.com/welcome",
        )        
        return "Please login! <a href='%s'>Login with SteemConnect</a>" % login_url    
    form = RuleForm(request.form)

    if request.method == 'POST': # and form.validate():
        # save the rule
        db = dataset.connect(databaseConnector)
        voteRulesTrx = VoteRulesTrx(db)           
        rule_dict = rule_dict_from_form(name, form)
        voteRulesTrx.add(rule_dict)        
        flash('Rule created successfully!')
        return redirect('/show_rules')

    return render_template('new_rule.html', form=form)

@app.route('/edit_rule', methods=['GET', 'POST'])
def edit_rule():
    access_token = session['access_token']
    # access_token = request.args.get("access_token", None)
    author = request.args.get("author", None)
    main_post = request.args.get("main_post", None)
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        login_url = steemconnect.get_login_url(
            "https://steemrewarding.com/welcome",
        )        
        return "Please login! <a href='%s'>Login with SteemConnect</a>" % login_url
    db = dataset.connect(databaseConnector)
    voteRulesTrx = VoteRulesTrx(db)    
    rule = voteRulesTrx.get(name, author, main_post)
    if rule:
        form = RuleForm(formdata=request.form)
        if request.method == 'POST': # and form.validate():
            rule_dict = rule_dict_from_form(name, form)
            voteRulesTrx.update(rule_dict)
            return redirect('/show_rules')
        else:
            form = set_form(form, rule)
        return render_template('edit_rule.html', form=form)

@app.route('/delete_rule', methods=['GET', 'POST'])
def delete_rule():
    access_token = session['access_token']
    # access_token = request.args.get("access_token", None)
    author = request.args.get("author", None)
    main_post = request.args.get("main_post", None)
    try:
        steemconnect.set_access_token(access_token)
        name = steemconnect.me()["name"]
    except:
        login_url = steemconnect.get_login_url(
            "https://steemrewarding.com/welcome",
        )        
        return "Please login! <a href='%s'>Login with SteemConnect</a>" % login_url
    db = dataset.connect(databaseConnector)
    voteRulesTrx = VoteRulesTrx(db)    
    rule = voteRulesTrx.get(name, author, main_post)
    if rule:
        form = RuleForm(formdata=request.form)
        if request.method == 'POST': # and form.validate():
            voteRulesTrx.delete(name, author, main_post)
            return redirect('/show_rules')
        else:
            form = set_form(form, rule)
        return render_template('delete_rule.html', form=form)


if __name__ == '__main__':
    app.run()