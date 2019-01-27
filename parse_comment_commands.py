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
from steemrewarding.command_parsing import parse_command

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
    commandsTrx = CommandsTrx(db)
    confStorage = ConfigurationDB(db)
    pendingVotesTrx = PendingVotesTrx(db)
    
    conf_setup = confStorage.get()
    last_command = conf_setup["last_command"]
    if last_command is None:
        last_command = datetime(1970,1,1,0,0,0)
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
    
    
    for command in commandsTrx.get_command_list(last_command):
        command_string = command["command"]
        last_command = command["created"]
        params = parse_command("$rewarding " + command_string, stm)
        vote_delay_min = params["vote_delay_min"]
        vote_weight = params["vote_percentage"]
        
        c_comment = Comment(command["authorperm"], steem_instance=stm)
        voter = c_comment["author"]
        
        if c_comment.is_main_post():
            c = c_comment
        else:
            c = Comment(construct_authorperm(c_comment["parent_author"], c_comment["parent_permlink"]), steem_instance=stm)
        authorperm = c["authorperm"]
        
        if command["valid"]:
            pending_vote = {"authorperm": authorperm, "voter": voter, "vote_weight": vote_weight, "comment_timestamp": c["created"].replace(tzinfo=None),
                            "vote_delay_min": vote_delay_min, "created": datetime.utcnow(), "min_vp": 0, "vote_when_vp_reached": False,
                            "vp_reached_order": 1, "max_net_votes": -1, "max_pending_payout": -1,
                            "max_votes_per_day": -1, "max_votes_per_week": -1, "vp_scaler": 0, "leave_comment": False}
            pendingVotesTrx.add(pending_vote)
            pendingVotesTrx.add({"authorperm": c_comment["authorperm"], "voter": "rewarding", "vote_weight": 5, "comment_timestamp": c_comment["created"].replace(tzinfo=None),
                                 "vote_delay_min": 0, "created": datetime.utcnow(), "min_vp": 0, "vote_when_vp_reached": False,
                                 "vp_reached_order": 1, "max_net_votes": -1, "max_pending_payout": -1,
                                 "max_votes_per_day": -1, "max_votes_per_week": -1, "vp_scaler": 0, "leave_comment": False})

    confStorage.update({"last_command": last_command})
    print("command parse script run %.2f s" % (time.time() - start_prep_time))
