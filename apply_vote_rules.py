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
from steemrewarding.post_storage import PostsTrx
from steemrewarding.command_storage import CommandsTrx
from steemrewarding.vote_rule_storage import VoteRulesTrx
from steemrewarding.pending_vote_storage import PendingVotesTrx
from steemrewarding.config_storage import ConfigurationDB
from steemrewarding.vote_storage import VotesTrx
from steemrewarding.utils import isfloat, tags_included, tags_excluded
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

    postTrx = PostsTrx(db)
    voteRulesTrx = VoteRulesTrx(db)
    confStorage = ConfigurationDB(db)
    pendingVotesTrx = PendingVotesTrx(db)
    
    conf_setup = confStorage.get()
    last_processed_timestamp = conf_setup["last_processed_timestamp"]
    if last_processed_timestamp is None:
        last_processed_timestamp = datetime(1970,1,1,0,0,0)
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
    stm = Steem(node=node_list, num_retries=5, call_num_retries=3, timeout=15, nobroadcast=nobroadcast) 
    
    
    for post in postTrx.get_posts_list(last_processed_timestamp):
        authorperm = post["authorperm"]
        author = post["author"]
        main_post = post["main_post"]
        last_processed_timestamp = post["created"]
        rules = voteRulesTrx.get_rules(author, main_post)
        if len(rules) == 0:
            continue
        c = Comment(authorperm, steem_instance=stm)
        voters = []
        for v in c["active_votes"]:
            voters.append(v["voter"])
        
        not_processed_rules = []
        for r in rules:
            voter = r["voter"]
            if voter in voters:
                continue
            not_processed_rules.append(r)
        if len(not_processed_rules) == 0:
            continue
        
        print("vote %s - rules %d" % (authorperm, len(not_processed_rules)))
        for rule in not_processed_rules:
            # print(rule)
            if not tags_included(rule["include_tags"], c["tags"]):
                continue
            if not tags_excluded(rule["exclude_tags"], c["tags"]):
                continue
            
            if post["word_count"] < rule["minimum_word_count"]:
                continue
            if rule["exclude_declined_payout"] and post["decline_payout"]:
                continue
            if rule["include_apps"] is not None and rule["include_apps"] != "":
                include_apps = rule["include_apps"].split(",")
                apps_included = True
                for app in include_apps:
                    if app.lower().strip() not in post["app"].split("/")[0]:
                        apps_included = False
                if not apps_included:
                    continue
                
            if rule["exclude_apps"] is not None and rule["exclude_apps"] != "":
                exclude_apps = rule["exclude_apps"].split(",")
                apps_excluded = True
                for app in exclude_apps:
                    if app.lower().strip() in post["app"].split("/")[0]:
                        apps_excluded = False
                if not apps_excluded:
                    continue            
        
            if rule["enabled"]:
                pending_vote = {"authorperm": authorperm, "voter": rule["voter"], "vote_weight": rule["vote_weight"], "comment_timestamp": c["created"].replace(tzinfo=None),
                                "vote_delay_min": rule["vote_delay_min"], "created": datetime.utcnow(), "min_vp": rule["min_vp"], "vote_when_vp_reached": rule["vote_when_vp_reached"],
                                "vp_reached_order": rule["vp_reached_order"], "max_net_votes": rule["max_net_votes"], "max_pending_payout": rule["max_pending_payout"],
                                "max_votes_per_day": rule["max_votes_per_day"], "max_votes_per_week": rule["max_votes_per_week"], "vp_scaler": rule["vp_scaler"], "leave_comment": rule["leave_comment"]}
                pendingVotesTrx.add(pending_vote)

    confStorage.update({"last_processed_timestamp": last_processed_timestamp})
    print("check posts script run %.2f s" % (time.time() - start_prep_time))
