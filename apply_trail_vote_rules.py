from beem.utils import formatTimeString, resolve_authorperm, construct_authorperm, addTzInfo
from beem.nodelist import NodeList
from beem.comment import Comment
from beem import Steem
from datetime import datetime, timedelta
from beem.instance import set_shared_steem_instance
from beem.blockchain import Blockchain
import time 
import json
import os
import math
import dataset
import random
from datetime import date, datetime, timedelta
from dateutil.parser import parse
from beem.constants import STEEM_100_PERCENT 
from steemrewarding.vote_storage import VotesTrx
from steemrewarding.command_storage import CommandsTrx
from steemrewarding.vote_rule_storage import VoteRulesTrx
from steemrewarding.pending_vote_storage import PendingVotesTrx
from steemrewarding.config_storage import ConfigurationDB
from steemrewarding.trail_vote_rule_storage import TrailVoteRulesTrx
from steemrewarding.utils import isfloat, tags_included, tags_excluded, string_included, string_excluded
from steemrewarding.version import version as rewardingversion
import dataset



if __name__ == "__main__":
    config_file = 'config.json'
    if not os.path.isfile(config_file):
        raise Exception("config.json is missing!")
    else:
        with open(config_file) as json_data_file:
            config_data = json.load(json_data_file)
        # print(config_data)
        databaseConnector = config_data["databaseConnector"]

    start_prep_time = time.time()
    db = dataset.connect(databaseConnector)
    # Create keyStorage
    
    nobroadcast = False
    # nobroadcast = True    

    votesTrx = VotesTrx(db)
    trailVoteRulesTrx = TrailVoteRulesTrx(db)
    voteRulesTrx = VoteRulesTrx(db)
    confStorage = ConfigurationDB(db)
    pendingVotesTrx = PendingVotesTrx(db)
    
    conf_setup = confStorage.get()
    last_vote = conf_setup["last_vote"]
    if last_vote is None:
        last_vote = datetime(1970,1,1,0,0,0)
    if True:
        max_batch_size = 50
        threading = False
        wss = False
        https = True
        normal = False
        appbase = True
    elif False:
        max_batch_size = None
        threading = True
        wss = True
        https = False
        normal = True
        appbase = True
    else:
        max_batch_size = None
        threading = False
        wss = True
        https = True
        normal = True
        appbase = True        

    nodes = NodeList()
    # nodes.update_nodes(weights={"block": 1})
    try:
        nodes.update_nodes()
    except:
        print("could not update nodes")
    
    node_list = nodes.get_nodes(normal=normal, appbase=appbase, wss=wss, https=https)
    if "https://api.steemit.com" in node_list:
        node_list.remove("https://api.steemit.com")    
    stm = Steem(node=node_list, num_retries=5, call_num_retries=3, timeout=15, nobroadcast=nobroadcast) 
    
    pendingVotesTrx.delete_old_votes(6.4)
    
    for vote in votesTrx.get_votes_list(last_vote):
        authorperm = vote["authorperm"]
        voter = vote["voter"]
        weight = vote["weight"]
        last_vote = vote["timestamp"]
        rules = trailVoteRulesTrx.get_rules(voter)
        if len(rules) == 0:
            continue
        fitting_rules = []
        post = Comment(authorperm, steem_instance=stm)
        for rule in rules:
            # print(rule)
            if not string_included(rule["include_authors"], post["author"]):
                continue
            if not string_excluded(rule["exclude_authors"], post["author"]):
                continue

            if not tags_included(rule["include_tags"], post["tags"]):
                continue
            if not tags_excluded(rule["exclude_tags"], post["tags"]):
                continue
            if rule["only_main_post"] and post.is_comment():
                continue
            if rule["exclude_authors_with_vote_rule"]:
                vote_rule = voteRulesTrx.get(rule["account"], post["author"], not post.is_comment())
                if vote_rule is not None and vote_rule["enabled"]:
                    continue
            if rule["exclude_declined_payout"] and int(post["max_accepted_payout"]) == 0:
                continue
  
            fitting_rules.append(rule)
        
        if len(fitting_rules) == 0:
            continue
        voters = []
        for v in post["active_votes"]:
            voters.append(v["voter"])
        
        not_processed_rules = []
        for r in fitting_rules:
            voter = r["account"]
            if voter in voters:
                continue
            not_processed_rules.append(r)
        if len(not_processed_rules) == 0:
            continue
        
        print("vote %s - rules %d" % (authorperm, len(not_processed_rules)))
        for rule in not_processed_rules:
                
            if rule["enabled"]:
                vote_weight = rule["vote_weight_scaler"] * weight / 100 + rule["vote_weight_offset"]
                if vote_weight > 100:
                    vote_weight = 100
                if vote_weight < 0:
                    vote_weight = 0
                pending_vote = {"authorperm": authorperm, "voter": rule["account"], "vote_weight": vote_weight, "comment_timestamp": post["created"].replace(tzinfo=None),
                                "vote_delay_min": rule["minimum_vote_delay_min"], "created": datetime.utcnow(), "min_vp": rule["min_vp"], "vote_when_vp_reached": rule["vote_when_vp_reached"],
                                "vp_reached_order": rule["vp_reached_order"], "max_net_votes": rule["max_net_votes"], "max_pending_payout": rule["max_pending_payout"],
                                "max_votes_per_day": rule["max_votes_per_day"], "max_votes_per_week": rule["max_votes_per_week"], "vp_scaler": rule["vp_scaler"], "leave_comment": False,
                                "maximum_vote_delay_min": rule["maximum_vote_delay_min"], "vote_sbd": rule["vote_sbd"], "vote_delay_scaler": rule["vote_delay_scaler"],
                                "trail_vote": True, "voter_to_follow": rule["voter_to_follow"]}
                pendingVotesTrx.add(pending_vote)

    confStorage.update({"last_vote": last_vote})
    print("check votes script run %.2f s" % (time.time() - start_prep_time))
