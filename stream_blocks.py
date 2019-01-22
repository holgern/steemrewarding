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
from steemrewarding.command_storage import CommandTrx

from steemrewarding.version import version as rewardingversion
import dataset



def isfloat(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

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
    # voteRulesTrx = CommentVoteRulesTrx(db)
    # confStorage = ConfigurationDB(db)
    commandsTrx = CommandsTrx(db)
    
    conf_setup = confStorage.get()
    last_post_block = conf_setup["last_post_block"]

    print("stream new posts")
    authors_post = voteRulesTrx.get_authors_post() + ['rewarding']
    authors_comment = voteRulesTrx.get_authors_comment()

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
    print("deleting old posts")
    postTrx.delete_old_posts(6)
    # print("reading all authorperm")
    already_voted_posts = []
    flagged_posts = []
    start_block = b.get_current_block_num() - int(201600)
    stop_block = b.get_current_block_num()
    last_block_print = start_block
    
    latest_update = postTrx.get_latest_post()
    latest_block = postTrx.get_latest_block()
    if latest_block is not None:
        latest_update_block = latest_block
    elif latest_update is not None:
        latest_update_block = b.get_estimated_block_num(latest_update["created"])
    else:
        latest_update_block = start_block
    print("latest update %s - %d to %d" % (str(latest_update["created"]), latest_update_block, stop_block))
    
    # start_block = max([latest_update_block, start_block, last_post_block]) + 1
    start_block = max([latest_update_block, start_block]) + 1
    cnt = 0
    updated_accounts = []
    posts_dict = {}
    changed_member_data = []
    ops = None
    for ops in b.stream(start=start_block, stop=stop_block, opNames=["comment", "transfer"], max_batch_size=max_batch_size, threading=threading, thread_num=8):
        #print(ops)
        timestamp = ops["timestamp"]
        # timestamp = timestamp.replace(tzinfo=None)
            # continue
        if ops["type"] == "transfer" and ops["to"] == "rewarding":
            authorperm = op["memo"].split(",")[0]
            command = ",".join(op["memo"].split(",")[1:])
            commandsTrx.add({"authorperm": authorperm, "command": command, "member": ops["from"], "valid": True, "created": ops["timestamp"].replace(tzinfo=None), "in_progress": False,
                             "done": False, "block": ops["block_num"]})
            continue
        elif ops["type"] == "transfer":
            continue
        if ops["body"].find("$rewarding") < 0:
            command_found = False
        else:
            command_found = True

        if ops["block_num"] <= latest_update_block:
            continue
        if ops["block_num"] - last_block_print > 50:
            last_block_print = ops["block_num"]
            print("blocks left %d - post found: %d" % (ops["block_num"] - stop_block, len(posts_dict)))
        authorperm = construct_authorperm(ops)
        
        try:
            c = Comment(authorperm, steem_instance=stm)
        except:
            continue
        main_post = c.is_main_post()
        dt_created = c["created"]
        dt_created = dt_created.replace(tzinfo=None)        
        if not main_post and abs((c["created"] - ops['timestamp']).total_seconds()) < 9.0 and c.body.find("$rewarding") > -1:
            
            body = c.body
            start_index = body.find("$rewarding")
            stop_index = body[start_index:].find("!")
            stop_index2 = body[start_index:].find("\n")
            if stop_index >= 0:
                command = body[start_index + 11:start_index + stop_index]
            elif stop_index2 >= 0:
                command = body[start_index + 11:start_index + stop_index2]
            else:
                command = body[start_index + 11:]
            commandsTrx.add({"authorperm": authorperm, "command": command, "member": c["author"], "valid": True, "created": dt_created, "in_progress": False,
                             "done": False, "block": ops["block_num"]})
                
        already_voted = False
    
        #for v in c["active_votes"]:
        #    if v["voter"] in accounts:
        #        already_voted = True
                  

        if main_post:
            posts_dict[authorperm] = {"authorperm": authorperm, "author": ops["author"], "created": dt_created, "block": ops["block_num"],
                                      "main_post": main_post}
        
        if len(posts_dict) > 0:
            start_time = time.time()
            postTrx.add_batch(posts_dict)
            print("Adding %d post took %.2f seconds" % (len(posts_dict), time.time() - start_time))
            posts_dict = {}
            

        cnt += 1

    print("stream posts script run %.2f s" % (time.time() - start_prep_time))
