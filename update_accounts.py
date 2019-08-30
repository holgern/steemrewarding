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
    
    last_voter = None

    print("Start to update accounts")
    voter_counter = 0
    updated_accounts_names = []
    updated_accounts = []
    rc_sp_to_low_account_list = []
    vote_counter = 0
    vote_count = 0
    
    for pending_vote in pendingVotesTrx.get_command_list_timed():
        settings = None
        if pending_vote["voter"] in updated_accounts:
            continue
        updated_accounts_names.append(pending_vote["voter"])
        updated_accounts.append(pending_vote)

    for pending_vote in pendingVotesTrx.get_command_list_vp_reached():
        settings = None
        if pending_vote["voter"] in updated_accounts:
            continue
        updated_accounts_names.append(pending_vote["voter"])
        updated_accounts.append(pending_vote)
            
    for pending_vote in updated_accounts:
        
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
            voter_counter += 1
            accountsTrx.upsert({"name": pending_vote["voter"], "vp_update":datetime.utcnow(), "vp": voter_acc.vp, "down_vp": voter_acc.get_downvoting_power(),
                                "sp": voter_acc.sp, "rc": voter_acc.get_rc_manabar()["current_mana"] / 1e9, "last_update": datetime.utcnow(),
                                "posting_auth_acc": posting_auth})
            pause_votes_below_vp = 0 

        elif settings["sp"] is None or settings["vp"] is None or settings["last_update"] is None or settings["rc"] is None or settings["posting_auth_acc"] is None:
            print("update %s - None" % pending_vote["voter"])
            voter_acc = Account(pending_vote["voter"], steem_instance=stm)
            posting_auth = False
            for a in voter_acc["posting"]["account_auths"]:
                if a[0] == posting_auth_acc:
                    posting_auth = True
            if pending_vote["voter"] == posting_auth_acc:
                posting_auth = True      
            voter_counter += 1
            accountsTrx.upsert({"name": pending_vote["voter"], "vp_update":datetime.utcnow(), "vp": voter_acc.vp, "down_vp": voter_acc.get_downvoting_power(),
                                "sp": voter_acc.sp, "rc": voter_acc.get_rc_manabar()["current_mana"] / 1e9, "last_update": datetime.utcnow(),
                                "posting_auth_acc": posting_auth})
        elif (datetime.utcnow() - settings["last_update"]).total_seconds() / 60 > 0.5:
            print("update %s - last update was before %f s" % (pending_vote["voter"], (datetime.utcnow() - settings["last_update"]).total_seconds()))
            voter_acc = Account(pending_vote["voter"], steem_instance=stm)
            posting_auth = False
            for a in voter_acc["posting"]["account_auths"]:
                if a[0] == posting_auth_acc:
                    posting_auth = True
            if pending_vote["voter"] == posting_auth_acc:
                posting_auth = True   
            voter_counter += 1
            accountsTrx.upsert({"name": pending_vote["voter"], "vp_update":datetime.utcnow(), "vp": voter_acc.vp, "down_vp": voter_acc.get_downvoting_power(),
                                "sp": voter_acc.sp, "rc": voter_acc.get_rc_manabar()["current_mana"] / 1e9, "last_update": datetime.utcnow(),
                                "posting_auth_acc": posting_auth})
        
                
    print("%d accounts have been updated!" % voter_counter)
    print("time vote %.2f s " % (time.time() - start_prep_time))

