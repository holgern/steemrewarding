from beem.utils import formatTimeString, resolve_authorperm, construct_authorperm, addTzInfo
from beem.nodelist import NodeList
from beem.comment import Comment
from beem import Steem
from beem.account import Account
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
from steemrewarding.vote_log_storage import VoteLogTrx
from steemrewarding.utils import isfloat, upvote_comment, valid_age
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
        wallet_password = config_data["wallet_password"]

    start_prep_time = time.time()
    db = dataset.connect(databaseConnector)
    # Create keyStorage
    
    nobroadcast = False
    # nobroadcast = True    

    postTrx = PostsTrx(db)
    voteRulesTrx = VoteRulesTrx(db)
    confStorage = ConfigurationDB(db)
    pendingVotesTrx = PendingVotesTrx(db)
    voteLogTrx = VoteLogTrx(db)

    conf_setup = confStorage.get()
    # last_post_block = conf_setup["last_post_block"]

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
    stm.wallet.unlock(wallet_password)
    b = Blockchain(steem_instance = stm)
    
    # print("reading all authorperm")
    delete_vote_commands = []
    for vote_command in pendingVotesTrx.get_command_list_timed():
        # print(vote_command)
        age_min = (datetime.utcnow() - vote_command["comment_timestamp"]).total_seconds() / 60
        if age_min > vote_command["vote_delay_min"] + 3:
            delete_vote_commands.append({"authorperm": vote_command["authorperm"], "voter": vote_command["voter"]})
            continue

        if age_min > vote_command["vote_delay_min"] and vote_command["vote_weight"] > 0:
            c = Comment(vote_command["authorperm"], steem_instance=stm)
            if not valid_age(c):
                delete_vote_commands.append({"authorperm": vote_command["authorperm"], "voter": vote_command["voter"]})
                continue                
            age_min = (addTzInfo(datetime.utcnow()) - c["created"]).total_seconds() / 60
            if age_min < vote_command["vote_delay_min"]:
                continue
            if vote_command["max_net_votes"] > -1 and vote_command["max_net_votes"] < c["net_votes"]:
                delete_vote_commands.append({"authorperm": vote_command["authorperm"], "voter": vote_command["voter"]})
                continue
            if vote_command["max_pending_payout"] > -1 and vote_command["max_pending_payout"] < float(c["pending_payout"]):
                delete_vote_commands.append({"authorperm": vote_command["authorperm"], "voter": vote_command["voter"]})
                continue
            # check for max votes per day/week
            votes_24h_before = voteLogTrx.get_votes_per_day(vote_command["voter"])
            if vote_command["max_votes_per_day"] > -1 and vote_command["max_votes_per_day"] <= votes_24h_before:
                delete_vote_commands.append({"authorperm": vote_command["authorperm"], "voter": vote_command["voter"]})
                continue
            votes_168h_before = voteLogTrx.get_votes_per_week(vote_command["voter"])
            if vote_command["max_votes_per_week"] > -1 and vote_command["max_votes_per_week"] <= votes_168h_before:
                delete_vote_commands.append({"authorperm": vote_command["authorperm"], "voter": vote_command["voter"]})
                continue               
            voter_acc = Account(vote_command["voter"], steem_instance=stm)
            if voter_acc.vp < vote_command["min_vp"]:
                delete_vote_commands.append({"authorperm": vote_command["authorperm"], "voter": vote_command["voter"]})
                continue       
            posting_auth = False
            for a in voter_acc["posting"]["account_auths"]:
                if a[0] == "rewarding":
                    posting_auth = True

            already_voted = False
            for v in c["active_votes"]:
                if voter_acc["name"] == v["voter"]:
                    already_voted = True
            
            if not posting_auth or already_voted:
                delete_vote_commands.append({"authorperm": vote_command["authorperm"], "voter": vote_command["voter"]})
                continue
            
            
            
            sucess = upvote_comment(c, voter_acc["name"], vote_command["vote_weight"])

            if sucess:
                if vote_command["leave_comment"]:
                    print("leave comment")
                voteLogTrx.add({"authorperm": vote_command["authorperm"], "voter": vote_command["voter"], "author": c["author"],
                                "timestamp": datetime.utcnow(), "vote_weight": vote_command["vote_weight"], "vote_delay_min": vote_command["vote_delay_min"],
                                "voted_after_min": age_min, "vp": voter_acc.vp, "vote_when_vp_reached": vote_command["vote_when_vp_reached"]})
                delete_vote_commands.append({"authorperm": vote_command["authorperm"], "voter": vote_command["voter"]})
                continue
    
    for vote_command in delete_vote_commands:
        pendingVotesTrx.delete(vote_command["authorperm"], vote_command["voter"])
    delete_vote_commands = []

    for vote_command in pendingVotesTrx.get_command_list_vp_reached():
        if vote_command["vote_weight"] == 0:
            continue
        voter_acc = Account(vote_command["voter"], steem_instance=stm)
        age_min = (datetime.utcnow() - vote_command["comment_timestamp"]).total_seconds() / 60
        if voter_acc.vp < vote_command["min_vp"]:
            continue
        c = Comment(vote_command["authorperm"], steem_instance=stm)
        if not valid_age(c):
            delete_vote_commands.append({"authorperm": vote_command["authorperm"], "voter": vote_command["voter"]})
            continue
        if vote_command["max_net_votes"] > -1 and vote_command["max_net_votes"] < c["net_votes"]:
            delete_vote_commands.append({"authorperm": vote_command["authorperm"], "voter": vote_command["voter"]})
            continue
        if vote_command["max_pending_payout"] > -1 and vote_command["max_pending_payout"] < float(c["pending_payout"]):
            delete_vote_commands.append({"authorperm": vote_command["authorperm"], "voter": vote_command["voter"]})
            continue
        votes_24h_before = voteLogTrx.get_votes_per_day(vote_command["voter"])
        if vote_command["max_votes_per_day"] > -1 and vote_command["max_votes_per_day"] <= votes_24h_before:
            delete_vote_commands.append({"authorperm": vote_command["authorperm"], "voter": vote_command["voter"]})
            continue
        votes_168h_before = voteLogTrx.get_votes_per_week(vote_command["voter"])
        if vote_command["max_votes_per_week"] > -1 and vote_command["max_votes_per_week"] <= votes_168h_before:
            delete_vote_commands.append({"authorperm": vote_command["authorperm"], "voter": vote_command["voter"]})
            continue        
        posting_auth = False
        for a in voter_acc["posting"]["account_auths"]:
            if a[0] == "rewarding":
                posting_auth = True

        already_voted = False
        for v in c["active_votes"]:
            if voter_acc["name"] == v["voter"]:
                already_voted = True        
                
        if not posting_auth or already_voted:
            delete_vote_commands.append({"authorperm": vote_command["authorperm"], "voter": vote_command["voter"]})
            continue
        sucess = upvote_comment(c, voter_acc["name"], vote_command["vote_weight_vp_full"])
        if sucess:
            if vote_command["leave_comment"]:
                print("leave comment")
            # add vote to log
            voteLogTrx.add({"authorperm": vote_command["authorperm"], "voter": vote_command["voter"], "author": c["author"],
                            "timestamp": datetime.utcnow(), "vote_weight": vote_command["vote_weight"], "vote_delay_min": vote_command["vote_delay_min"],
                            "voted_after_min": age_min, "vp": voter_acc.vp, "vote_when_vp_reached": vote_command["vote_when_vp_reached"]})            
            delete_vote_commands.append({"authorperm": vote_command["authorperm"], "voter": vote_command["voter"]})
        continue                        
    
    for vote_command in delete_vote_commands:
        pendingVotesTrx.delete(vote_command["authorperm"], vote_command["voter"])
    delete_vote_commands = []
    print("upvote posts script run %.2f s" % (time.time() - start_prep_time))
