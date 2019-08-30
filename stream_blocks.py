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
import sys
import math
import dataset
import random
from datetime import date, datetime, timedelta
from dateutil.parser import parse
from beem.constants import STEEM_100_PERCENT 
from steemrewarding.post_storage import PostsTrx
from steemrewarding.command_storage import CommandsTrx
from steemrewarding.vote_rule_storage import VoteRulesTrx
from steemrewarding.trail_vote_rule_storage import TrailVoteRulesTrx
from steemrewarding.config_storage import ConfigurationDB
from steemrewarding.vote_storage import VotesTrx
from steemrewarding.utils import isfloat
from steemrewarding.version import version as rewardingversion
from steemrewarding.broadcast_vote_storage import BroadcastVoteTrx
from steemrewarding.pending_vote_storage import PendingVotesTrx
import dataset
from nltk.tokenize import RegexpTokenizer



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
    voteTrx = VotesTrx(db)
    commandsTrx = CommandsTrx(db)
    trailVoteRuleTrx = TrailVoteRulesTrx(db)
    broadcastVoteTrx = BroadcastVoteTrx(db)
    pendingVotesTrx = PendingVotesTrx(db)
    
    
    conf_setup = confStorage.get()
    last_streamed_block = conf_setup["last_streamed_block"]

    print("stream new posts")
    authors_list_posts = voteRulesTrx.get_authors()
    authors_list_comments = voteRulesTrx.get_authors(main_post=False)
    voter_list = trailVoteRuleTrx.get_trail_voters()
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
    
    tokenizer = RegexpTokenizer(r'\w+')
 
    node_list = nodes.get_nodes(normal=normal, appbase=appbase, wss=wss, https=https)

    stm = Steem(node=node_list, num_retries=5, call_num_retries=3, timeout=15, nobroadcast=nobroadcast) 
    print("user node %s" % str(stm))
    b = Blockchain(mode="head", steem_instance = stm)
    print("deleting old posts and votes")
    postTrx.delete_old_posts(6)
    voteTrx.delete_old_votes(8)
    broadcastVoteTrx.delete_old_votes(7)
    pendingVotesTrx.delete_old_votes(7)
    print("Parsing new blocks")
    # print("reading all authorperm")
    already_voted_posts = []
    flagged_posts = []
    if last_streamed_block == 0:
        start_block = b.get_current_block_num() - int(201600)
    else:
        start_block = last_streamed_block + 1
    stop_block = b.get_current_block_num()
    last_block_print = start_block

    cnt = 0
    updated_accounts = []
    posts_dict = {}
    changed_member_data = []
    ops = None
    for ops in b.stream(start=start_block, stop=stop_block, opNames=["comment", "transfer", "vote", "custom_json"], max_batch_size=max_batch_size, threading=threading, thread_num=8):
        #print(ops)
        timestamp = ops["timestamp"]
        # timestamp = timestamp.replace(tzinfo=None)
            # continue
        last_streamed_block = ops["block_num"]
        if ops["type"] == "transfer" and ops["to"] == "rewarding":
            authorperm = ops["memo"].split(",")[0]
            command = ",".join(ops["memo"].split(",")[1:])
            commandsTrx.add({"authorperm": authorperm, "command": command, "account": ops["from"], "valid": True, "created": ops["timestamp"].replace(tzinfo=None), "in_progress": False,
                             "done": False, "block": ops["block_num"]})
            continue
        elif ops["type"] == "transfer":
            continue
        elif ops["type"] == "vote":
            authorperm = construct_authorperm(ops["author"], ops["permlink"])
            unprocessed_vote = broadcastVoteTrx.get_unprocessed(ops["voter"], authorperm)
            if unprocessed_vote is not None:
                broadcastVoteTrx.update_processed(ops["voter"], authorperm, ops["trx_id"], True, False)
                
            timestamp = ops["timestamp"].replace(tzinfo=None)
            weight = ops["weight"] / STEEM_100_PERCENT * 100
            voteTrx.add({"authorperm": authorperm, "voter": ops["voter"], "block": ops["block_num"], "timestamp": timestamp, "weight": weight})
            continue
        elif ops["type"] == "custom_json":
            if ops['id'] not in ["rewarding"]:
                continue
            try:
                json_data = json.loads(ops['json'])
                if isinstance(json_data, str):
                    json_data = json.loads(json_data)                 
            except:
                print("Skip json: %s" % str(ops['json']))
                continue
            if len(ops['required_posting_auths']) > 0:
                user = ops['required_posting_auths'][0]
            elif len(ops['required_auths']) > 0:
                user = ops['required_auths'][0]
            else:
                print("Cannot parse transaction, as user could not be determined!")
                continue 
            continue
        if ops["body"].find("$rewarding") < 0:
            command_found = False
        else:
            command_found = True
        if ops["author"] not in authors_list_posts + authors_list_comments and not command_found:
            continue

        if ops["block_num"] - last_block_print > 50:
            last_block_print = ops["block_num"]
            print("blocks left %d - post found: %d" % (ops["block_num"] - stop_block, len(posts_dict)))
        authorperm = construct_authorperm(ops)
        
        
        cnt = 0
        c = None
        while c is None and cnt < 5:
            cnt += 1
            try:
                if cnt <= 2:
                    c = Comment(authorperm, use_tags_api=False, steem_instance=stm)
                else:
                    c = Comment(authorperm, use_tags_api=True, steem_instance=stm)
                    
                c.refresh()
            except Exception as e:
                print(e)
                nodelist = NodeList()
                nodelist.update_nodes()
                stm = Steem(node=nodelist.get_nodes(), num_retries=5, call_num_retries=3, timeout=15, nobroadcast=nobroadcast) 
                #stm.rpc.next()
                print("Switch to %s" % str(stm))
                #time.sleep(1)
        if cnt == 5:
            print("Could not read %s" % (authorperm))
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
            commandsTrx.add({"authorperm": authorperm, "command": command, "account": c["author"], "valid": True, "created": dt_created, "in_progress": False,
                             "done": False, "block": ops["block_num"]})
                
        already_voted = False
    
        #for v in c["active_votes"]:
        #    if v["voter"] in accounts:
        #        already_voted = True
        if main_post and ops["author"] in authors_list_posts or not main_post and ops["author"] in authors_list_comments:
            app = None
            json_metadata = c.json_metadata
            if isinstance(json_metadata, str):
                try:
                    json_metadata = json.loads(json_metadata)
                except:
                    continue
            if "app" in json_metadata:
                app = json_metadata["app"]
                if isinstance(app, dict) and "name" in app:
                    app = app["name"]
                elif isinstance(app, dict):
                    app = ""
            word_count = len(tokenizer.tokenize(c.body))
            net_votes = 0 #len(c.get_votes())
            vote_rshares = 0
            #for v in c.get_votes():
            #    vote_rshares += int(v["rshares"])
            tags = ""
            if "tags" in c and c["tags"] is not None:
                for t in c["tags"]:
                    if t is not None and len(tags) == 0:
                        tags = t
                    elif t is not None and len(tags) > 0:
                        tags += "," + t
            if len(tags) > 512:
                continue
            posts_dict[authorperm] = {"authorperm": authorperm, "author": ops["author"], "created": dt_created, "block": ops["block_num"],
                                      "main_post": main_post, "tags": tags, "app": app, "decline_payout": int(c["max_accepted_payout"]) == 0,
                                      "word_count": word_count, "net_votes": net_votes, "vote_rshares": vote_rshares, "pending_payout_value": 0,
                                      "update": datetime.utcnow()}
        
        if len(posts_dict) > 0:
            start_time = time.time()
            #print(posts_dict)
            postTrx.add_batch(posts_dict)
            # print("Adding %d post took %.2f seconds" % (len(posts_dict), time.time() - start_time))
            posts_dict = {}
            

        cnt += 1
    if stop_block >= start_block:
        confStorage.update({"last_streamed_block": last_streamed_block})
    print("stream posts script run %.2f s" % (time.time() - start_prep_time))
