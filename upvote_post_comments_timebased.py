from beem.utils import formatTimeString, resolve_authorperm, construct_authorperm, addTzInfo
from beem.nodelist import NodeList
from beem.comment import Comment
from beem import Steem
from beem.account import Account
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
from steemrewarding.broadcast_vote_storage import BroadcastVoteTrx
from steemrewarding.utils import isfloat, upvote_comment, valid_age, upvote_comment_without_check
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
        voting_round_sec = config_data["voting_round_sec"]

    start_prep_time = time.time()
    db = dataset.connect(databaseConnector)
    # Create keyStorage
    print("Start upvote_post_comments_timebased.py")
    nobroadcast = False
    # nobroadcast = True    

    postTrx = PostsTrx(db)
    votesTrx = VotesTrx(db)
    voteRulesTrx = VoteRulesTrx(db)
    confStorage = ConfigurationDB(db)
    pendingVotesTrx = PendingVotesTrx(db)
    voteLogTrx = VoteLogTrx(db)
    failedVoteLogTrx = FailedVoteLogTrx(db)
    accountsTrx = AccountsDB(db)
    broadcastVoteTrx = BroadcastVoteTrx(db)

    conf_setup = confStorage.get()
    # last_post_block = conf_setup["last_post_block"]

    nodes = NodeList()
    # nodes.update_nodes(weights={"block": 1})
    try:
        nodes.update_nodes()
    except:
        print("could not update nodes")
    
    node_list = nodes.get_nodes(exclude_limited=False)
    stm = Steem(node=node_list, num_retries=5, call_num_retries=3, timeout=15, nobroadcast=nobroadcast) 
    stm.wallet.unlock(wallet_password)
    
    last_voter = None

    print("Start apply new timebased votes")
    voter_counter = 0
    delete_pending_votes = []
    rc_sp_to_low_account_list = []
    vote_counter = 0
    vote_count = 0
    for pending_vote in pendingVotesTrx.get_command_list_timed():
        settings = None
        voter_acc = None
        author, permlink = resolve_authorperm(pending_vote["authorperm"])
        
        if pending_vote["voter"] in rc_sp_to_low_account_list:
            continue
        age_min = (datetime.utcnow() - pending_vote["comment_timestamp"]).total_seconds() / 60
        maximum_vote_delay_min = pending_vote["maximum_vote_delay_min"]        
        
        if age_min < pending_vote["vote_delay_min"] - voting_round_sec / 2.0 / 60 - 3:
            # print("%s is not ready yet - %.2f min should be %.2f" % (pending_vote["authorperm"], age_min, pending_vote["vote_delay_min"]))
            continue        
        
        if settings is None:
            settings = accountsTrx.get(pending_vote["voter"])
        if settings is None:
            voter_acc = Account(pending_vote["voter"], steem_instance=stm)
            print("update %s - did not exists" % pending_vote["voter"])
            posting_auth = False
            for a in voter_acc["posting"]["account_auths"]:
                if a[0] == posting_auth_acc:
                    posting_auth = True
            if pending_vote["voter"] == posting_auth_acc:
                posting_auth = True            
            
            accountsTrx.upsert({"name": pending_vote["voter"], "vp_update":datetime.utcnow(), "vp": voter_acc.vp, "down_vp": voter_acc.get_downvoting_power(),
                                "sp": voter_acc.sp, "rc": voter_acc.get_rc_manabar()["current_mana"] / 1e9, "last_update": datetime.utcnow(),
                                "posting_auth_acc": posting_auth})
            pause_votes_below_vp = 0 
            settings = accountsTrx.get(pending_vote["voter"])

        elif settings["sp"] is None or settings["vp"] is None or settings["last_update"] is None or settings["rc"] is None or settings["posting_auth_acc"] is None:
            print("update %s - None" % pending_vote["voter"])
            voter_acc = Account(pending_vote["voter"], steem_instance=stm)
            posting_auth = False
            for a in voter_acc["posting"]["account_auths"]:
                if a[0] == posting_auth_acc:
                    posting_auth = True
            if pending_vote["voter"] == posting_auth_acc:
                posting_auth = True               
            accountsTrx.upsert({"name": pending_vote["voter"], "vp_update":datetime.utcnow(), "vp": voter_acc.vp, "down_vp": voter_acc.get_downvoting_power(),
                                "sp": voter_acc.sp, "rc": voter_acc.get_rc_manabar()["current_mana"] / 1e9, "last_update": datetime.utcnow(),
                                "posting_auth_acc": posting_auth})
            settings = accountsTrx.get(pending_vote["voter"])
        elif (datetime.utcnow() - settings["last_update"]).total_seconds() / 60 > 1:
            print("update %s - last update was before %f s" % (pending_vote["voter"], (datetime.utcnow() - settings["last_update"]).total_seconds()))
            voter_acc = Account(pending_vote["voter"], steem_instance=stm)
            posting_auth = False
            for a in voter_acc["posting"]["account_auths"]:
                if a[0] == posting_auth_acc:
                    posting_auth = True
            if pending_vote["voter"] == posting_auth_acc:
                posting_auth = True   
                
            accountsTrx.upsert({"name": pending_vote["voter"], "vp_update":datetime.utcnow(), "vp": voter_acc.vp, "down_vp": voter_acc.get_downvoting_power(),
                                "sp": voter_acc.sp, "rc": voter_acc.get_rc_manabar()["current_mana"] / 1e9, "last_update": datetime.utcnow(),
                                "posting_auth_acc": posting_auth})
            settings = accountsTrx.get(pending_vote["voter"])

        if pending_vote["vote_weight"] > 0:
            
            pause_votes_below_vp = settings["pause_votes_below_vp"]
            vp = settings["vp"]
        else:
            pause_votes_below_vp = settings["pause_down_votes_below_down_vp"]
            vp = settings["down_vp"]
        vp_update = settings["last_update"]
        if vp_update is not None:
            diff_in_seconds = ((datetime.utcnow()) - (vp_update)).total_seconds()
            regenerated_vp = diff_in_seconds * 10000 / 432000 / 100
            vp = vp + regenerated_vp
            #down_vp = down_vp + regenerated_vp
            if vp > 100:
                vp = 100
            #if down_vp > 100:
            #    down_vp = 100
        
        if vp < pause_votes_below_vp:
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "Voting is paused (VP = %.2f %%, which below pause_votes_below_vp of %.2f %%)" % (vp, pause_votes_below_vp),
                                  "timestamp": datetime.utcnow(), "vote_weight": pending_vote["vote_weight"], "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": settings["vp"], "down_vp": settings["down_vp"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"],
                                  "main_post": pending_vote["main_post"]})                  
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue        
        
        # print("time vote %.2f s - %d votes" % (time.time() - start_prep_time, vote_count))
        if (pending_vote["vote_weight"] is None or pending_vote["vote_weight"] == 0) and (pending_vote["vote_sbd"] is None or float(pending_vote["vote_sbd"]) <= 0):
            # voter_acc = Account(pending_vote["voter"], steem_instance=stm)
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "vote_weight was set to zero. (%s %% and %s $)" % (pending_vote["vote_weight"], pending_vote["vote_sbd"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": pending_vote["vote_weight"], "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": settings["vp"], "down_vp": settings["down_vp"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"],
                                  "main_post": pending_vote["main_post"]})                  
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})            
            continue


        if maximum_vote_delay_min < 0:
            maximum_vote_delay_min = 9360
        if age_min > maximum_vote_delay_min + voting_round_sec / 60:
            # voter_acc = Account(pending_vote["voter"], steem_instance=stm)
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "post is older than %.2f min." % (maximum_vote_delay_min),
                                  "timestamp": datetime.utcnow(), "vote_weight": pending_vote["vote_weight"], "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": settings["vp"], "down_vp": settings["down_vp"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"],
                                  "main_post": pending_vote["main_post"]})              
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue


        

        
        voter_counter += 1
        # voter_acc = Account(pending_vote["voter"], steem_instance=stm)
        if settings["sp"] < 0.1:
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "Could not vot %s, as Steem Power is almost zero." % (pending_vote["authorperm"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": pending_vote["vote_weight"], "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": settings["vp"], "down_vp": settings["down_vp"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"],
                                  "main_post": pending_vote["main_post"]})                  
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            print("Could not process %s - sp < 0.1" % pending_vote["authorperm"])
            rc_sp_to_low_account_list.append(pending_vote["voter"])
            continue
        if settings["rc"] < 0.5:
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "Could not vot %s, as RC is almost zero." % (pending_vote["authorperm"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": pending_vote["vote_weight"], "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": settings["vp"], "down_vp": settings["down_vp"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"],
                                  "main_post": pending_vote["main_post"]})                  
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            print("Could not process %s - rc to low" % pending_vote["authorperm"])
            rc_sp_to_low_account_list.append(pending_vote["voter"])
            continue          

        
        vote_weight = pending_vote["vote_weight"]
        if vote_weight is None or vote_weight == 0:
            voter_acc = Account(pending_vote["voter"], steem_instance=stm)
            vote_weight = voter_acc.get_vote_pct_for_SBD(float(pending_vote["vote_sbd"])) / 100.
            if vote_weight > 100:
                vote_weight = 100
            elif vote_weight < 0.01:
                failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "vote_weight was set to zero.",
                                      "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                      "min_vp": pending_vote["min_vp"], "vp": voter_acc.vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"],
                                      "main_post": pending_vote["main_post"]})                  
                delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
                continue
        age_hour = ((datetime.utcnow()) - pending_vote["created"]).total_seconds() / 60 / 60
        if age_hour > 156:
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "post is older than 6.5 days.",
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": settings["vp"], "down_vp": settings["down_vp"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"],
                                  "main_post": pending_vote["main_post"]})                  
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue                
        
        if vp < pending_vote["min_vp"]:
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "Voting power is %.2f %%, which is to low. (min_vp is %.2f %%)" % (vp, pending_vote["min_vp"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": settings["vp"], "down_vp": settings["down_vp"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"],
                                  "main_post": pending_vote["main_post"]})                  
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue    
        
        if pending_vote["max_votes_per_day"] > -1:
            if settings is None:
                settings = accountsTrx.get(pending_vote["voter"])
            if settings is not None:
                sliding_time_window = settings["sliding_time_window"]
            else:
                sliding_time_window = True
            votes_24h_before = voteLogTrx.get_votes_per_day(pending_vote["voter"], author, sliding_time_window)
            if votes_24h_before >= pending_vote["max_votes_per_day"]:
                failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "The author was already upvoted %d in the last 24h (max_votes_per_day is %d)." % (votes_24h_before, pending_vote["max_votes_per_day"]),
                                      "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                      "min_vp": pending_vote["min_vp"], "vp": settings["vp"], "down_vp": settings["down_vp"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"],
                                      "main_post": pending_vote["main_post"]})                
                delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
                continue        
        
        if pending_vote["max_votes_per_week"] > -1:
            if settings is None:
                settings = accountsTrx.get(pending_vote["voter"])
            if settings is not None:
                sliding_time_window = settings["sliding_time_window"]            
            else:
                sliding_time_window = True
            votes_168h_before = voteLogTrx.get_votes_per_week(pending_vote["voter"], author, sliding_time_window)
            if votes_168h_before >= pending_vote["max_votes_per_week"]:
                failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "The author was already upvoted %d in the last 7 days (max_votes_per_week is %d)." % (votes_168h_before, pending_vote["max_votes_per_week"]),
                                      "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                      "min_vp": pending_vote["min_vp"], "vp": settings["vp"], "down_vp": settings["down_vp"],"vote_when_vp_reached": pending_vote["vote_when_vp_reached"],
                                      "main_post": pending_vote["main_post"]})                  
                delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
                continue      
            
        
        if pending_vote["vp_scaler"] > 0:
            vote_weight *= 1 - ((100 - vp) / 100 * pending_vote["vp_scaler"])

        if abs(vote_weight) < 0.02:
            error_msg = "Vote weight is zero or below zero (%.2f %%)" % vote_weight
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": error_msg,
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": settings["vp"], "down_vp": settings["down_vp"],"vote_when_vp_reached": pending_vote["vote_when_vp_reached"],
                                  "main_post": pending_vote["main_post"]})
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue           
            
        cnt = 0
        c = None
        while c is None and cnt < 5:
            cnt += 1
            try:
                if False and pending_vote["max_pending_payout"] >= 0:
                    c = Comment(pending_vote["authorperm"], use_tags_api=True, steem_instance=stm)
                else:
                    c = Comment(pending_vote["authorperm"], use_tags_api=False, steem_instance=stm)
                c.refresh()
            except:
                nodelist = NodeList()
                nodelist.update_nodes()
                stm = Steem(node=nodelist.get_nodes(), num_retries=5, call_num_retries=3, timeout=15, nobroadcast=nobroadcast) 
                time.sleep(1)
        if cnt == 5:
            print("Could not read %s" % (pending_vote["authorperm"]))
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "Could not process %s" % (pending_vote["authorperm"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": pending_vote["vote_weight"], "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"],
                                  "main_post": pending_vote["main_post"]})                  
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            print("Could not process %s" % pending_vote["authorperm"])
            continue      

        votes_list = votesTrx.get_authorperm_votes(pending_vote["authorperm"])

        try:
            
            if pending_vote["max_net_votes"] >= 0 and pending_vote["max_net_votes"] < len(votes_list):
                failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "The number of post/comment votes (%d) is higher than max_net_votes (%d)." % (len(votes_list), pending_vote["max_net_votes"]),
                                      "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                      "min_vp": pending_vote["min_vp"], "vp": vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"],
                                      "main_post": pending_vote["main_post"]})                
                delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
                continue
        except:
            continue
        if False and pending_vote["max_pending_payout"] >= 0 and pending_vote["max_pending_payout"] < float(c["pending_payout_value"]):
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": "The pending payout of post/comment votes (%.2f) is higher than max_pending_payout (%.2f)." % (float(c["pending_payout_value"]), pending_vote["max_pending_payout"]),
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"],
                                  "main_post": pending_vote["main_post"]})                    
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue
        # check for max votes per day/week
        

        
           
        

        
           


        already_voted = False
        for v in votes_list:
            if pending_vote["voter"] == v["voter"]:
                already_voted = True
        
        if not settings["posting_auth_acc"] or already_voted:
            if already_voted:
                error_msg = "already voted."
            else:
                error_msg = "posting authority is missing"
            failedVoteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "error": error_msg,
                                  "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                  "min_vp": pending_vote["min_vp"], "vp": vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"],
                                  "main_post": pending_vote["main_post"]})
            delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
            continue
        
         
        # sucess = upvote_comment(c, pending_vote["voter"], vote_weight)
        
        
        
        
        
        
        if False:
            
        
            reply_message = upvote_comment_without_check(c, pending_vote["voter"], vote_weight)
            if reply_message is not None:
                vote_count += 1
                if pending_vote["leave_comment"]:
                    try:
                        if settings is None:
                            settings = accountsTrx.get(pending_vote["voter"])
                        if settings is not None and "upvote_comment" in settings and settings["upvote_comment"] is not None:
                            json_metadata = {'app': 'rewarding/%s' % (rewarding_version)}
                            reply_body = settings["upvote_comment"]
                            reply_body = reply_body.replace("{{name}}", "@%s" % c["author"] ).replace("{{voter}}", "@%s" % pending_vote["voter"])
                            c.reply(reply_body, author=pending_vote["voter"], meta=json_metadata)
                    except:
                        print("Could not leave comment!")
                voteLogTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "author": c["author"],
                                "timestamp": datetime.utcnow(), "vote_weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"],
                                "voted_after_min": age_min, "vp": vp, "vote_when_vp_reached": pending_vote["vote_when_vp_reached"],
                                "trail_vote": pending_vote["trail_vote"], "main_post": pending_vote["main_post"],
                                "voter_to_follow": pending_vote["voter_to_follow"]})
                expiration = formatTimeString(reply_message["expiration"]).replace(tzinfo=None)
                delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
                
            else:
                expiration = datetime.utcnow()

        broadcastVoteTrx.add({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"],
                              "weight": vote_weight, "vote_delay_min": pending_vote["vote_delay_min"], "min_vp": pending_vote["min_vp"],
                              "vote_when_vp_reached": pending_vote["vote_when_vp_reached"], "main_post": pending_vote["main_post"], 
                              "author": c["author"], "voted_after_min": 0, "created": datetime.utcnow(), "vp": settings["vp"], "down_vp": settings["down_vp"],
                              "maximum_vote_delay_min": pending_vote["maximum_vote_delay_min"], "comment_timestamp": pending_vote["comment_timestamp"],
                              "trail_vote": pending_vote["trail_vote"], "voter_to_follow": pending_vote["voter_to_follow"], "leave_comment": pending_vote["leave_comment"],
                              "vote_timestamp": pending_vote["comment_timestamp"] + timedelta(seconds=pending_vote["vote_delay_min"]/60),
                              "max_votes_per_day": pending_vote["max_votes_per_day"], "max_votes_per_week": pending_vote["max_votes_per_week"]})            
        delete_pending_votes.append({"authorperm": pending_vote["authorperm"], "voter": pending_vote["voter"], "vote_when_vp_reached": pending_vote["vote_when_vp_reached"]})
        
    for pending_vote in delete_pending_votes:
        pendingVotesTrx.delete(pending_vote["authorperm"], pending_vote["voter"], pending_vote["vote_when_vp_reached"])
    delete_pending_votes = []
    print("%d voter have been checked!" % voter_counter)
    print("time vote %.2f s - %d votes" % (time.time() - start_prep_time, vote_count))

