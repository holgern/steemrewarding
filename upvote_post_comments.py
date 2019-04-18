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
from steemrewarding.failed_vote_log_storage import FailedVoteLogTrx
from steemrewarding.utils import isfloat, upvote_comment, valid_age
from steemrewarding.version import version as rewardingversion
from steemrewarding.account_storage import AccountsDB
from steemrewarding.version import version as rewarding_version
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
        posting_auth_acc = config_data["posting_auth_acc"]

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
    failedVoteLogTrx = FailedVoteLogTrx(db)
    accountsTrx = AccountsDB(db)

    conf_setup = confStorage.get()
    # last_post_block = conf_setup["last_post_block"]

    nodes = NodeList()
    # nodes.update_nodes(weights={"block": 1})
    try:
        nodes.update_nodes()
    except:
        print("could not update nodes")
    
    node_list = nodes.get_nodes()
    stm = Steem(node=node_list, num_retries=5, call_num_retries=3, timeout=15, nobroadcast=nobroadcast) 
    stm.wallet.unlock(wallet_password)
    vote_count = 0
    delete_pending_votes = []
    for pending_vote in pendingVotesTrx.get_command_list_timed():
        # print("time vote %.2f s - %d votes" % (time.time() - start_prep_time, vote_count))
        if (pending_vote["vote_weight"] is None or pending_vote["vote_weight"] <= 0) and (pending_vote["vote_sbd"] is None or float(pending_vote["vote_sbd"]) <= 0):
            voter_acc = Account(pending_vote["voter"], steem_instance=stm)
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "vote_weight was set to zero. (%s %% and %s $)" % (pending_vote["vote_weight"], pending_vote["vote_sbd"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": pending_vote["vote_weight"], "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})                  
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})            
            continue

            
        age_min = (datetime.utcnow() - pending_vote["comment_timestamp"]).total_seconds() / 60
        maximum_vote_delay_min = pending_vote["maximum_vote_delay_min"]
        if maximum_vote_delay_min < 0:
            maximum_vote_delay_min = 9360
        if age_min > maximum_vote_delay_min:
            voter_acc = Account(pending_vote["voter"], steem_instance=stm)
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "post is older than %.2f min." % (maximum_vote_delay_min),
                                  "timestamp": datetime.utcnow(), "vote_weight": pending_vote["vote_weight"], "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})              
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue

        if age_min < pending_vote["vote_delay_min"]:
            continue
        voter_acc = Account(pending_vote["voter"], steem_instance=stm)
        if voter_acc.sp < 0.1:
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "Could not vot %s, as Steem Power is almost zero." % (pending_vote["authorperm"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": pending_vote["vote_weight"], "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})                  
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            print("Could not process %s" % pending_vote["authorperm"])
            continue            
        try:
            c = Comment(pending_vote["authorperm"], steem_instance=stm)
        except:
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "Could not process %s" % (pending_vote["authorperm"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": pending_vote["vote_weight"], "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})                  
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            print("Could not process %s" % pending_vote["authorperm"])
            continue
        
        vote_weight = pending_vote["vote_weight"]
        if vote_weight is None or vote_weight <= 0:        
            vote_weight = voter_acc.get_vote_pct_for_SBD(float(pending_vote["vote_sbd"])) / 100.
            if vote_weight > 100:
                vote_weight = 100
            elif vote_weight == 0:
                failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "vote_weight was set to zero.",
                                      "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                      "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})                  
                delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
                continue                
        if not valid_age(c):
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "post is older than 6.5 days.",
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})                  
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue                
        age_min = (addTzInfo(datetime.utcnow()) - c["created"]).total_seconds() / 60
        if age_min < pending_vote["vote_delay_min"]:
            continue
        if pending_vote["max_net_votes"] >= 0 and pending_vote["max_net_votes"] < c["net_votes"]:
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "The number of post/comment votes (%d) is higher than max_net_votes (%d)." % (c["net_votes"], pending_vote["max_net_votes"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})                
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue
        if pending_vote["max_pending_payout"] >= 0 and pending_vote["max_pending_payout"] < float(c["pending_payout_value"]):
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "The pending payout of post/comment votes (%.2f) is higher than max_pending_payout (%.2f)." % (float(c["pending_payout_value"]), pending_vote["max_pending_payout"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})                    
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue
        # check for max votes per day/week
        author, permlink = resolve_authorperm(pending_vote["authorperm"])
        votes_24h_before = voteLogTrx.get_votes_per_day(pending_vote["voter"], author)
        if pending_vote["max_votes_per_day"] > -1 and votes_24h_before >= pending_vote["max_votes_per_day"]:
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "The author was already upvoted %d in the last 24h (max_votes_per_day is %d)." % (votes_24h_before, pending_vote["max_votes_per_day"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})                
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue
        author, permlink = resolve_authorperm(pending_vote["authorperm"])
        votes_168h_before = voteLogTrx.get_votes_per_week(pending_vote["voter"], author)
        if pending_vote["max_votes_per_week"] > -1 and votes_168h_before >= pending_vote["max_votes_per_week"]:
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "The author was already upvoted %d in the last 7 days (max_votes_per_week is %d)." % (votes_168h_before, pending_vote["max_votes_per_week"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})                  
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue               
        
        if voter_acc.vp < pending_vote["min_vp"]:
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "Voting power is %.2f %%, which is to low. (min_vp is %.2f %%)" % (voter_acc.vp, pending_vote["min_vp"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})                  
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue       
        posting_auth = False
        for a in voter_acc["posting"]["account_auths"]:
            if a[0] == posting_auth_acc:
                posting_auth = True
        if voter_acc["name"] == posting_auth_acc:
            posting_auth = True

        already_voted = False
        for v in c["active_votes"]:
            if voter_acc["name"] == v["voter"]:
                already_voted = True
        
        if not posting_auth or already_voted:
            if already_voted:
                error_msg = "already voted."
            else:
                error_msg = "posting authority is missing"
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": error_msg,
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue
        
        if pending_vote["vp_scaler"] > 0:
            vote_weight *= 1 - ((100 - voter_acc.vp) / 100 * pending_vote["vp_scaler"])
        if vote_weight <= 0:
            error_msg = "Vote weight is zero or below zero (%.2f %%)" % vote_weight
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": error_msg,
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue            
        sucess = upvote_comment(c, voter_acc["name"], vote_weight)

        if sucess:
            vote_count += 1
            if pending_vote["leave_comment"]:
                try:
                    settings = accountsTrx.get(voter_acc["name"])
                    if settings is not None and "upvote_comment" in settings:
                        json_metadata = {'app': 'rewarding/%s' % (rewarding_version)}
                        reply_body = settings["upvote_comment"]
                        reply_body = reply_body.replace("{{name}}", "@%s" % c["author"] ).replace("{{voter}}", "@%s" % voter_acc["name"])
                        c.reply(reply_body, author=voter_acc["name"], meta=json_metadata)
                except:
                    print("Could not leave comment!")
            voteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "author": c["author"],
                            "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                            "voted_after_min": age_min, "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"],
                            "last_update": datetime.utcnow()})
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue

    for pending_vote in delete_pending_votes:
        pendingVotesTrx.delete(pending_vote["authorperm"], pending_vote["voter"], pending_vote["vote_when_vp_reached"])
    delete_pending_votes = []
    
    print("time vote %.2f s - %d votes" % (time.time() - start_prep_time, vote_count))
    
    for pending_vote in pendingVotesTrx.get_command_list_vp_reached():
        if (pending_vote["vote_weight"] is None or pending_vote["vote_weight"] <= 0) and (pending_vote["vote_sbd"] is None or float(pending_vote["vote_sbd"]) <= 0):
            voter_acc = Account(pending_vote["voter"], steem_instance=stm)
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "vote_weight was set to zero.",
                                  "timestamp": datetime.utcnow(), "vote_weight": 0, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})                  
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue
        voter_acc = Account(pending_vote["voter"], steem_instance=stm)
        if voter_acc.sp < 0.1:
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "Could not vot %s, as Steem Power is almost zero." % (pending_vote["authorperm"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": pending_vote["vote_weight"], "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})                  
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            print("Could not process %s" % pending_vote["authorperm"])
            continue            
        age_min = (datetime.utcnow() - pending_vote["comment_timestamp"]).total_seconds() / 60
        maximum_vote_delay_min = pending_vote["maximum_vote_delay_min"]
        if maximum_vote_delay_min > 0 and age_min > maximum_vote_delay_min:
            voter_acc = Account(pending_vote["voter"], steem_instance=stm)
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "post is older than %.2f min." % (maximum_vote_delay_min),
                                  "timestamp": datetime.utcnow(), "vote_weight": pending_vote["vote_weight"], "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})              
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue            
        if pending_vote["max_net_votes"] < 0 and pending_vote["max_pending_payout"] < 0:
            if voter_acc.vp < pending_vote["min_vp"]:
                continue
            if age_min < pending_vote["vote_delay_min"]:
                continue
            
        vote_weight = pending_vote["vote_weight"]
        if vote_weight <= 0:        
            vote_weight = voter_acc.get_vote_pct_for_SBD(float(pending_vote["vote_sbd"])) / 100.
            if vote_weight > 100:
                vote_weight = 100
            elif vote_weight == 0:
                failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "vote_weight was set to zero.",
                                      "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                      "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})                  
                delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
                continue        
        try:
            c = Comment(pending_vote["authorperm"], steem_instance=stm)
        except:
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "Could not process %s" % (pending_vote["authorperm"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})                  
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})            
            print("Could not process %s" % pending_vote["authorperm"])
            continue
        if not valid_age(c):
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "post is older than 6.5 days.",
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})               
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue
        if pending_vote["max_net_votes"] >= 0 and pending_vote["max_net_votes"] < c["net_votes"]:
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "The number of post/comment votes (%d) is higher than max_net_votes (%d)." % (c["net_votes"], pending_vote["max_net_votes"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})                
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue
        if pending_vote["max_pending_payout"] >= 0 and pending_vote["max_pending_payout"] < float(c["pending_payout_value"]):
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "The pending payout of post/comment votes (%.2f) is higher than max_pending_payout (%.2f)." % (float(c["pending_payout_value"]), pending_vote["max_pending_payout"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})            
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue        
        
        if pending_vote["max_net_votes"] >= 0 or pending_vote["max_pending_payout"] >= 0:
            if voter_acc.vp < pending_vote["min_vp"]:
                continue
            if age_min < pending_vote["vote_delay_min"]:
                continue


        author, permlink = resolve_authorperm(pending_vote["authorperm"])
        votes_24h_before = voteLogTrx.get_votes_per_day(pending_vote["voter"], author)
        if pending_vote["max_votes_per_day"] > -1 and votes_24h_before >= pending_vote["max_votes_per_day"]:
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "The author was already upvoted %d in the last 24h (max_votes_per_day is %d)." % (votes_24h_before, pending_vote["max_votes_per_day"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})              
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue
        author, permlink = resolve_authorperm(pending_vote["authorperm"])
        votes_168h_before = voteLogTrx.get_votes_per_week(pending_vote["voter"], author)
        if pending_vote["max_votes_per_week"] > -1 and votes_168h_before >= pending_vote["max_votes_per_week"]:
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "The author was already upvoted %d in the last 7 days (max_votes_per_week is %d)." % (votes_168h_before, pending_vote["max_votes_per_week"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})            
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue        
        posting_auth = False
        for a in voter_acc["posting"]["account_auths"]:
            if a[0] == posting_auth_acc:
                posting_auth = True
        if voter_acc["name"] == posting_auth_acc:
            posting_auth = True        

        already_voted = False
        for v in c["active_votes"]:
            if voter_acc["name"] == v["voter"]:
                already_voted = True        
                
        if not posting_auth or already_voted:
            if already_voted:
                error_msg = "already voted."
            else:
                error_msg = "posting authority is missing"
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": error_msg,
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})            
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"] })
            continue
        if pending_vote["vp_scaler"] > 0:
            vote_weight *= 1 - ((100 - voter_acc.vp) / 100 * pending_vote["vp_scaler"])
        if vote_weight <= 0:
            error_msg = "Vote weight is zero or below zero (%.2f %%)" % vote_weight
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": error_msg,
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue
        sucess = upvote_comment(c, voter_acc["name"], vote_weight)
        if sucess:
            vote_count += 1
            if pending_vote["leave_comment"]:
                try:
                    settings = accountsTrx.get(voter_acc["name"])
                    if settings is not None and "upvote_comment" in settings:
                        json_metadata = {'app': 'rewarding/%s' % (rewarding_version)}
                        reply_body = settings["upvote_comment"]
                        reply_body = reply_body.replace("{{name}}", "@%s" % c["author"] ).replace("{{voter}}", "@%s" % voter_acc["name"])
                        c.reply(reply_body, author=voter_acc["name"], meta=json_metadata)
                except:
                    print("Could not leave comment!")
            # add vote to log
            voteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "author": c["author"],
                            "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                            "voted_after_min": age_min, "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"],
                            "last_update": datetime.utcnow()})            
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
        continue                        
    
    for pending_vote in delete_pending_votes:
        pendingVotesTrx.delete(pending_vote["authorperm"], pending_vote["voter"], pending_vote["vote_when_vp_reached"])
    delete_pending_votes = []
    print("upvote posts script run %.2f s - %d votes were broadcasted" % (time.time() - start_prep_time, vote_count))
