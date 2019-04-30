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
from steemrewarding.account_storage import AccountsDB
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
    accountsDB = AccountsDB(db)

    conf_setup = confStorage.get()
    # last_post_block = conf_setup["last_post_block"]

    nodes = NodeList()
    try:
        nodes.update_nodes()
    except:
        print("could not update nodes")
    
    node_list = nodes.get_nodes()
    if "https://api.steemit.com" in node_list:
        node_list.remove("https://api.steemit.com")
    stm = Steem(node=node_list, num_retries=5, call_num_retries=3, timeout=15, nobroadcast=nobroadcast) 
    b = Blockchain(steem_instance = stm)
    updated_vote_log = []
    voteLogTrx.delete_old_logs(14)
    for n in range(16):
        if n < 4:
            vote_log = voteLogTrx.get_oldest_log(vote_delay_optimized=True)
            
            update_age = (datetime.utcnow() - vote_log["last_update"]).total_seconds() / 60
            if update_age < 60:
                vote_log = voteLogTrx.get_oldest_log()
        else:
            vote_log = voteLogTrx.get_oldest_log()
        if vote_log is None:
            vote_log = voteLogTrx.get_oldest_log()        
        if vote_log is not None:
            authorperm = vote_log["authorperm"]
            # print(vote_log["authorperm"])
            try:
                c = Comment(authorperm, steem_instance=stm)
            except:
                print("Could not process %s" % authorperm)
                vote_log["last_update"] = datetime.utcnow()
                vote_log["performance"] = 0
                voteLogTrx.update(vote_log)                
                continue
            try:
                curation_rewards_SBD = c.get_curation_rewards(pending_payout_SBD=True)
                
            except:
                print("Could not calc curation rewards for %s (stm: %s)" % (c["authorperm"], stm))
                vote_log["last_update"] = datetime.utcnow()
                voteLogTrx.update(vote_log)
                continue
            
            age_days = (addTzInfo(datetime.utcnow()) - c["created"]).total_seconds() / 60 / 60 / 24
            if age_days > 6.5:
                if vote_log["vote_delay_optimized"]:
                    vote_log["vote_delay_optimized"] = False
                    voteLogTrx.update(vote_log)                
                continue
            
            performance = 0
            rshares = 0
            for vote in c["active_votes"]:
                if vote["voter"] != vote_log["voter"]:
                    continue
                rshares = int(vote["rshares"])
                vote_SBD = stm.rshares_to_sbd(rshares)
                curation_SBD = curation_rewards_SBD["active_votes"][vote["voter"]]
                if vote_SBD > 0:
                    performance = (float(curation_SBD) / vote_SBD * 100)
            
            acc_data = accountsDB.get(vote_log["voter"])
            vote_delay_diff = vote_log["voted_after_min"] - vote_log["vote_delay_min"]  
            if acc_data is not None:
                minimum_vote_delay = acc_data["minimum_vote_delay"]
                maximum_vote_delay = acc_data["maximum_vote_delay"]
                rshares_divider = acc_data["rshares_divider"]
                if rshares_divider <= 0:
                    rshares_divider = 5
            else:
                minimum_vote_delay = 0
                maximum_vote_delay = 6.5 * 24 * 60
                rshares_divider = 5
            best_performance = 0
            best_vote_delay_min = 0
            for v in c["active_votes"]:
                v_SBD = stm.rshares_to_sbd(int(v["rshares"]))
                
                if v_SBD > 0 and int(v["rshares"]) > rshares / rshares_divider:
                    
                    p = float(curation_rewards_SBD["active_votes"][v["voter"]]) / v_SBD * 100
                    if p > best_performance:
                        best_performance = p
                        best_vote_delay_min = ((v["time"]) - c["created"]).total_seconds() / 60

            if acc_data is not None and acc_data["optimize_vote_delay"] and abs(vote_delay_diff) < 1.0 and not vote_log["trail_vote"]:

                optimize_threshold = 1 + (acc_data["optimize_threshold"] / 100)
                optimize_ma_length = acc_data["optimize_ma_length"]
                vote_not_optimized = vote_log["optimized_vote_delay_min"] is None
                age_min = (addTzInfo(datetime.utcnow()) - c["created"]).total_seconds() / 60 
                vote_rule = voteRulesTrx.get(vote_log["voter"], c["author"], c.is_main_post())
                if vote_rule is not None and not vote_rule["disable_optimization"] and age_min > maximum_vote_delay + 1 and vote_not_optimized:
                    vote_delay_min = vote_rule["vote_delay_min"]
                    old_vote_delay_min = vote_rule["vote_delay_min"]
                    vote_log["vote_delay_optimized"] = True
                    if best_performance > performance * optimize_threshold and vote_delay_min <= maximum_vote_delay + 0.1 and vote_delay_min >= minimum_vote_delay -0.1:
                        if optimize_ma_length > 1:
                            vote_delay_min = (vote_delay_min * (optimize_ma_length - 1) + best_vote_delay_min) / optimize_ma_length
                        else:
                            vote_delay_min = best_vote_delay_min
                        if vote_delay_min > maximum_vote_delay:
                            vote_delay_min = maximum_vote_delay
                        elif vote_delay_min < minimum_vote_delay:
                            vote_delay_min = minimum_vote_delay
                        vote_weight = vote_log["vote_weight"]
                        if acc_data["optimize_vote_delay_slope"] != 0 and vote_log["vote_weight"] > 0:
                            vote_weight = vote_weight + (vote_delay_min - old_vote_delay_min) * acc_data["optimize_vote_delay_slope"]
                            if vote_weight < 0:
                                vote_weight = 0
                            if vote_weight > 100:
                                vote_weight = 100
                            
                        print("optimize vote %s" % c["authorperm"])
                        voteRulesTrx.update({"voter": vote_log["voter"], "author": c["author"], "main_post": c.is_main_post(),
                                             "vote_delay_min": vote_delay_min, "vote_weight": vote_weight})
                        vote_log["optimized_vote_delay_min"] = vote_delay_min
                        vote_log["vote_delay_optimized"] = False
                elif vote_rule is not None and not vote_rule["disable_optimization"] and vote_not_optimized:
                    vote_log["vote_delay_optimized"] = True
                else:
                    vote_log["vote_delay_optimized"] = False
            else:
                vote_log["vote_delay_optimized"] = False
            
            if best_vote_delay_min > 0:
                vote_log["best_vote_delay_min"] = best_vote_delay_min
            if best_performance  > 0:
                vote_log["best_performance"] = best_performance
            if rshares > 0:
                vote_log["vote_rshares"] = rshares
            vote_log["last_update"] = datetime.utcnow()
            if performance > 0:
                vote_log["performance"] = performance
            voteLogTrx.update(vote_log)
        

    print("calc curation perf script run %.2f s" % (time.time() - start_prep_time))
