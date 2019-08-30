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
from beem.transactionbuilder import TransactionBuilder
from beembase import operations
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
    
    nobroadcast = False
    # nobroadcast = True    

    postTrx = PostsTrx(db)
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

    voter_this_round = {}
    vote_count = 0
    rc_sp_to_low_account_list = []
    
    vote_ops = []
    
    for vote in broadcastVoteTrx.get_all_expired():
        if vote["voter"] in voter_this_round: # and (datetime.utcnow() - voter_this_round[vote["voter"]]).total_seconds() < 3:
            # print("Skip %s for this round" % vote["voter"])
            continue
        author, permlink = resolve_authorperm(vote["authorperm"])
        
        if vote["voter"] in rc_sp_to_low_account_list:
            continue        
        
        settings = accountsTrx.get(vote["voter"])
        
        if settings is None:
            voter_acc = Account(vote["voter"], steem_instance=stm)
            print("update %s - did not exists" % vote["voter"])
            posting_auth = False
            for a in voter_acc["posting"]["account_auths"]:
                if a[0] == posting_auth_acc:
                    posting_auth = True
            if vote["voter"] == posting_auth_acc:
                posting_auth = True            
            
            accountsTrx.upsert({"name": vote["voter"], "vp_update":datetime.utcnow(), "vp": voter_acc.vp, "down_vp": voter_acc.get_downvoting_power(),
                                "sp": voter_acc.sp, "rc": voter_acc.get_rc_manabar()["current_mana"] / 1e9, "last_update": datetime.utcnow(),
                                "posting_auth_acc": posting_auth})
            pause_votes_below_vp = 0 
            settings = accountsTrx.get(vote["voter"])

        elif settings["sp"] is None or settings["vp"] is None or settings["last_update"] is None or settings["rc"] is None or settings["posting_auth_acc"] is None:
            print("update %s - None" % vote["voter"])
            voter_acc = Account(vote["voter"], steem_instance=stm)
            posting_auth = False
            for a in voter_acc["posting"]["account_auths"]:
                if a[0] == posting_auth_acc:
                    posting_auth = True
            if vote["voter"] == posting_auth_acc:
                posting_auth = True               
            accountsTrx.upsert({"name": vote["voter"], "vp_update":datetime.utcnow(), "vp": voter_acc.vp, "down_vp": voter_acc.get_downvoting_power(),
                                "sp": voter_acc.sp, "rc": voter_acc.get_rc_manabar()["current_mana"] / 1e9, "last_update": datetime.utcnow(),
                                "posting_auth_acc": posting_auth})
            settings = accountsTrx.get(vote["voter"])
        elif (datetime.utcnow() - settings["last_update"]).total_seconds() / 60 > 1:
            print("update %s - last update was before %f s" % (vote["voter"], (datetime.utcnow() - settings["last_update"]).total_seconds()))
            voter_acc = Account(vote["voter"], steem_instance=stm)
            posting_auth = False
            for a in voter_acc["posting"]["account_auths"]:
                if a[0] == posting_auth_acc:
                    posting_auth = True
            if vote["voter"] == posting_auth_acc:
                posting_auth = True   
                
            accountsTrx.upsert({"name": vote["voter"], "vp_update":datetime.utcnow(), "vp": voter_acc.vp, "down_vp": voter_acc.get_downvoting_power(),
                                "sp": voter_acc.sp, "rc": voter_acc.get_rc_manabar()["current_mana"] / 1e9, "last_update": datetime.utcnow(),
                                "posting_auth_acc": posting_auth})
            settings = accountsTrx.get(vote["voter"])

                
        pause_votes_below_vp = settings["pause_votes_below_vp"]
        vp = settings["vp"]
        down_vp = settings["down_vp"]
        vp_update = settings["last_update"]
        if vp_update is not None:
            diff_in_seconds = ((datetime.utcnow()) - (vp_update)).total_seconds()
            regenerated_vp = diff_in_seconds * 10000 / 432000 / 100
            vp = vp + regenerated_vp  
            down_vp = down_vp + regenerated_vp
            if vp > 100:
                vp = 100
            if down_vp > 100:
                down_vp = 100
        
        
        if settings["rc"] < 0.5:
            rc_sp_to_low_account_list.append(vote["voter"])
            continue
        if settings["sp"] < 0.1:
            rc_sp_to_low_account_list.append(vote["voter"])
            continue 
        if settings["pause_votes_below_vp"] is not None and vp < settings["pause_votes_below_vp"] and vote["weight"] > 0:
            continue         
        if vp < vote["min_vp"] and vote["weight"] > 0:
            continue
        if down_vp < vote["min_vp"] and vote["weight"] < 0:
            continue
        
        if vote["comment_timestamp"] is not None:
            
            age_min = (datetime.utcnow() - vote["comment_timestamp"]).total_seconds() / 60
        else:
            age_min = 60
        maximum_vote_delay_min = vote["maximum_vote_delay_min"]
        if maximum_vote_delay_min is not None and maximum_vote_delay_min < 0:
            maximum_vote_delay_min = 9360
        if maximum_vote_delay_min is not None and age_min > maximum_vote_delay_min + voting_round_sec / 60:          
            failedVoteLogTrx.add({"authorperm": vote["authorperm"], "voter": vote["voter"], "error": "post is older than %.2f min." % (maximum_vote_delay_min),
                                  "timestamp": datetime.utcnow(), "vote_weight": vote["weight"], "vote_delay_min": vote["vote_delay_min"],
                                  "min_vp": vote["min_vp"], "vp": vote["vp"], "vote_when_vp_reached": vote["vote_when_vp_reached"],
                                  "main_post": vote["main_post"]})   
            broadcastVoteTrx.delete(vote["authorperm"], vote["voter"])            
            continue
        if not vote["vote_when_vp_reached"] and age_min < vote["vote_delay_min"]:
            continue
        
        if abs(vote["weight"]) < 0.01:
            failedVoteLogTrx.add({"authorperm": vote["authorperm"], "voter": vote["voter"], "error": "vote weight is below 0.01%%.",
                                  "timestamp": datetime.utcnow(), "vote_weight": vote["weight"], "vote_delay_min": vote["vote_delay_min"],
                                  "min_vp": vote["min_vp"], "vp": vote["vp"], "vote_when_vp_reached": vote["vote_when_vp_reached"],
                                  "main_post": vote["main_post"]})   
            broadcastVoteTrx.delete(vote["authorperm"], vote["voter"])               
            continue        
        
        if vote["max_votes_per_day"]  is not None and vote["max_votes_per_day"] > -1:
            if settings is None:
                settings = accountsTrx.get(vote["voter"])
            if settings is not None:
                sliding_time_window = settings["sliding_time_window"]
            else:
                sliding_time_window = True
            votes_24h_before = voteLogTrx.get_votes_per_day(vote["voter"], author, sliding_time_window)
            if votes_24h_before >= vote["max_votes_per_day"]:
                failedVoteLogTrx.add({"authorperm": vote["authorperm"], "voter": vote["voter"], "error": "The author was already upvoted %d in the last 24h (max_votes_per_day is %d)." % (votes_24h_before, vote["max_votes_per_day"]),
                                      "timestamp": datetime.utcnow(), "vote_weight": vote["weight"], "vote_delay_min": vote["vote_delay_min"],
                                      "min_vp": vote["min_vp"], "vp": vp, "vote_when_vp_reached": vote["vote_when_vp_reached"],
                                      "main_post": vote["main_post"]})                
                continue        
        
        if vote["max_votes_per_week"] is not None and vote["max_votes_per_week"] > -1:
            if settings is None:
                settings = accountsTrx.get(vote["voter"])
            if settings is not None:
                sliding_time_window = settings["sliding_time_window"]            
            else:
                sliding_time_window = True
            votes_168h_before = voteLogTrx.get_votes_per_week(vote["voter"], author, sliding_time_window)
            if votes_168h_before >= vote["max_votes_per_week"]:
                failedVoteLogTrx.add({"authorperm": vote["authorperm"], "voter": vote["voter"], "error": "The author was already upvoted %d in the last 7 days (max_votes_per_week is %d)." % (votes_168h_before, vote["max_votes_per_week"]),
                                      "timestamp": datetime.utcnow(), "vote_weight": vote["weight"], "vote_delay_min": vote["vote_delay_min"],
                                      "min_vp": vote["min_vp"], "vp": vp, "vote_when_vp_reached": vote["vote_when_vp_reached"],
                                      "main_post": vote["main_post"]})                  
                continue        
        
        if vote["retry_count"] >= 5:
            failedVoteLogTrx.add({"authorperm": vote["authorperm"], "voter": vote["voter"], "error": "tried 5 times to vote...",
                                  "timestamp": datetime.utcnow(), "vote_weight": vote["weight"], "vote_delay_min": vote["vote_delay_min"],
                                  "min_vp": vote["min_vp"], "vp": vote["vp"], "vote_when_vp_reached": vote["vote_when_vp_reached"],
                                  "main_post": vote["main_post"]})   
            broadcastVoteTrx.delete(vote["authorperm"], vote["voter"])        
            continue
        
        if vote["expiration"] is not None and (datetime.utcnow() - vote["expiration"]).total_seconds() < 30:
            continue



        
        voter_this_round[vote["voter"]] = datetime.utcnow()
        if True:
            vote_ops.append({"weight": vote["weight"], "authorperm": vote["authorperm"], "voter": vote["voter"], "retry_count": vote["retry_count"],
                             "voted_after_min": age_min, "vote_delay_min": vote["vote_delay_min"]})
            vote_count += 1
        else:
            try:
                if vote["trail_vote"]:
                    print("trail voter %s votes %s" % (vote["voter"], vote["authorperm"]))
                else:
                    print("voter %s votes %s after %.2f min (%.2f min)" % (vote["voter"], vote["authorperm"], age_min, vote["vote_delay_min"]))
                reply_message = stm.vote(vote["weight"], vote["authorperm"], vote["voter"])
                vote_count += 1
                expiration = formatTimeString(reply_message["expiration"]).replace(tzinfo=None)
                
            except Exception as e:
                expiration = datetime.utcnow()
                print("Vote failed: %s" % str(e))
            
            broadcastVoteTrx.update({"voter": vote["voter"], "authorperm": vote["authorperm"], "retry_count": vote["retry_count"] + 1,
                                     "voted_after_min": age_min, "expiration": expiration})                
        last_voter = vote["voter"]
            
    print("Building vote list: %d - %.2f s" % (len(vote_ops), time.time() - start_prep_time))
    if len(vote_ops) > 0:
        tx = TransactionBuilder(steem_instance=stm)
    else:
        tx = None
    ops = []
    broadcasted_votes = []
    for vote in vote_ops:
        
        print("broadcast voter %s votes %s" % (vote["voter"], vote["authorperm"]))
        author, permlink = resolve_authorperm(vote["authorperm"])
        op = operations.Vote(**{"voter": vote["voter"],
                                "author": author,
                                "permlink": permlink,
                                "weight": int(vote["weight"] * 100)})
        ops.append(op)      
        broadcasted_votes.append(vote)
        if len(ops) > 5:
            try:
                print("Broadcasting %d votes" % len(ops))
                tx.appendOps(ops)
                # tx.appendMissingSignatures()
                tx.appendSigner("rewarding", "posting")
                tx.sign()
                reply_message = tx.broadcast()
                # print(reply_message)
                ops = []
                #if vote["trail_vote"]:
                #    print("trail voter %s votes %s" % (vote["voter"], vote["authorperm"]))
                #else:
                #    print("voter %s votes %s after %.2f min (%.2f min)" % (vote["voter"], vote["authorperm"], age_min, vote["vote_delay_min"]))
                # reply_message = stm.vote(vote["weight"], vote["authorperm"], vote["voter"])
                # vote_count += 1
                expiration = formatTimeString(reply_message["expiration"]).replace(tzinfo=None)
            except Exception as e:
                expiration = datetime.utcnow()
                print("Vote failed: %s" % str(e))
                for vote in broadcasted_votes:
                    try:
                        reply_message = stm.vote(vote["weight"], vote["authorperm"], vote["voter"])
                    except Exception as e:
                        expiration = datetime.utcnow()
                        print("Vote failed: %s" % str(e))
                    broadcastVoteTrx.update({"voter": vote["voter"], "authorperm": vote["authorperm"], "retry_count": vote["retry_count"] + 1,
                                             "voted_after_min": vote["voted_after_min"], "expiration": expiration})                    
                broadcasted_votes = []
                ops = []
            for vote in broadcasted_votes:
                
                broadcastVoteTrx.update({"voter": vote["voter"], "authorperm": vote["authorperm"], "retry_count": vote["retry_count"] + 1,
                                         "voted_after_min": vote["voted_after_min"], "expiration": expiration})
            broadcasted_votes = []
    
    
    if len(ops) > 0:
        try:
            
            tx.appendOps(ops)
            # tx.appendMissingSignatures()
            tx.appendSigner("rewarding", "posting")
            tx.sign()
            reply_message = tx.broadcast()
            # print(reply_message)
            ops = []
            #if vote["trail_vote"]:
            #    print("trail voter %s votes %s" % (vote["voter"], vote["authorperm"]))
            #else:
            #    print("voter %s votes %s after %.2f min (%.2f min)" % (vote["voter"], vote["authorperm"], age_min, vote["vote_delay_min"]))
            # reply_message = stm.vote(vote["weight"], vote["authorperm"], vote["voter"])
            # vote_count += 1
            expiration = formatTimeString(reply_message["expiration"]).replace(tzinfo=None)
        except Exception as e:
            expiration = datetime.utcnow()
            print("Vote failed: %s" % str(e))
            for vote in broadcasted_votes:
                try:
                    reply_message = stm.vote(vote["weight"], vote["authorperm"], vote["voter"])
                except Exception as e:
                    expiration = datetime.utcnow()
                    print("Vote failed: %s" % str(e))
                broadcastVoteTrx.update({"voter": vote["voter"], "authorperm": vote["authorperm"], "retry_count": vote["retry_count"] + 1,
                                         "voted_after_min": vote["voted_after_min"], "expiration": expiration})                    
            broadcasted_votes = []
            ops = []
        for vote in broadcasted_votes:
            
            broadcastVoteTrx.update({"voter": vote["voter"], "authorperm": vote["authorperm"], "retry_count": vote["retry_count"] + 1,
                                     "voted_after_min": vote["voted_after_min"], "expiration": expiration})
        broadcasted_votes = []    
    
    vote_ops = []
    if True:
        print("Write vote log")
        for vote in broadcastVoteTrx.get_vote_without_votelog():
            if vote["trx"] is None:
                continue
            author, permlink = resolve_authorperm(vote["authorperm"])
            voted_after_min = vote["voted_after_min"]
            vote_delay_min = vote["vote_delay_min"]
            vp = vote["vp"]
            vote_when_vp_reached = vote["vote_when_vp_reached"]
            trail_vote = vote["trail_vote"]
            if voted_after_min is None:
                voted_after_min = 0
            if vp is None:
                vp = 0
            if vote_delay_min is None:
                vote_delay_min = 0
            if vote_when_vp_reached is None:
                vote_when_vp_reached = False
            if trail_vote is None:
                trail_vote = False
                
            voteLogTrx.add({"authorperm": vote["authorperm"], "voter": vote["voter"], "author": author,
                            "timestamp": datetime.utcnow(), "vote_weight":  vote["weight"], "vote_delay_min": vote_delay_min,
                            "voted_after_min": voted_after_min, "vp": vp, "vote_when_vp_reached": vote_when_vp_reached,
                            "trail_vote": trail_vote, "main_post": vote["main_post"],
                            "voter_to_follow": vote["voter_to_follow"]})
            broadcastVoteTrx.update({"voter": vote["voter"], "authorperm": vote["authorperm"], "vote_log_added": True})
        print("write comments")
        comment_written = False
        for vote in broadcastVoteTrx.get_vote_with_comment():
            if vote["trx"] is None:
                continue
            
            
            if vote["voter"] in rc_sp_to_low_account_list:
                continue                
            
            settings = accountsTrx.get(vote["voter"])
            if settings is None:
                broadcastVoteTrx.update({"voter": vote["voter"], "authorperm": vote["authorperm"], "leave_comment": False})
                continue
            if "upvote_comment" not in settings:
                broadcastVoteTrx.update({"voter": vote["voter"], "authorperm": vote["authorperm"], "leave_comment": False})
                continue
            if settings["upvote_comment"] is None:
                broadcastVoteTrx.update({"voter": vote["voter"], "authorperm": vote["authorperm"], "leave_comment": False})
                continue
            if comment_written:
                continue
            # print(vote)
            
            voter_acc = Account(vote["voter"], steem_instance=stm)
            print("RC: %f" % (voter_acc.get_rc_manabar()["current_mana"] / 1e9))
            if voter_acc.get_rc_manabar()["current_mana"] / 1e9 < 1.6:
                rc_sp_to_low_account_list.append(vote["voter"])
                broadcastVoteTrx.update({"voter": vote["voter"], "authorperm": vote["authorperm"], "comment_broadcasted": True})
                continue
            try:
                c = Comment(vote["authorperm"], use_tags_api=False, steem_instance=stm)
            except:
                broadcastVoteTrx.update({"voter": vote["voter"], "authorperm": vote["authorperm"], "comment_broadcasted": True})
                continue
         
            try:
                
                json_metadata = {'app': 'rewarding/%s' % (rewarding_version)}
                reply_body = settings["upvote_comment"]
                reply_body = reply_body.replace("{{name}}", "@%s" % c["author"] ).replace("{{voter}}", "@%s" % vote["voter"])
                c.reply(reply_body, author=vote["voter"], meta=json_metadata)
                print("Broadcasted comment for %s " % vote["authorperm"])
                comment_written = True
                broadcastVoteTrx.update({"voter": vote["voter"], "authorperm": vote["authorperm"], "comment_broadcasted": True})
            except Exception as e:
                print("Could not leave comment! - %s" % str(e))    
    print("expired vote script run %.2f s - %d votes were broadcasted" % (time.time() - start_prep_time, vote_count))
