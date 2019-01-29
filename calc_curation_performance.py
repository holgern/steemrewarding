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
    b = Blockchain(steem_instance = stm)
    updated_vote_log = []
    voteLogTrx.delete_old_logs(7)
    for n in range(4):
        vote_log = voteLogTrx.get_oldest_log()
        if vote_log is not None:
            authorperm = vote_log["authorperm"]
            c = Comment(authorperm, steem_instance=stm)
            curation_rewards_SBD = c.get_curation_rewards(pending_payout_SBD=True)
            performance = 0
            for vote in c["active_votes"]:
                if vote["voter"] != vote_log["voter"]:
                    continue
                vote_SBD = stm.rshares_to_sbd(int(vote["rshares"]))
                curation_SBD = curation_rewards_SBD["active_votes"][vote["voter"]]
                if vote_SBD > 0:
                    performance = (float(curation_SBD) / vote_SBD * 100)
            vote_log["last_update"] = datetime.utcnow()
            vote_log["performance"] = performance
            voteLogTrx.update(vote_log)
        

    print("calc curation perf script run %.2f s" % (time.time() - start_prep_time))
