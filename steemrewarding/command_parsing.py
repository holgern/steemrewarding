# This Python file uses the following encoding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from builtins import bytes, int, str
from future.utils import python_2_unicode_compatible
from datetime import date, datetime, timedelta
import time
from beem.account import Account
from .utils import isfloat


def parse_command(command, stm):
    command_args = command.replace('  ', ' ').split(" ")[1:]
    beneficiaries = []
    beneficiaries_accounts = []
    upvote = None
    authorperm = None
    vote_percentage = None
    vote_sbd = None
    tip_sbd = None
    vote_delay_min = 15.0
    bounty_delay_days = 6.5
    bounty_vote_percentage = None
    bounty_vote_sbd = None
    number = []
    symbols = []
    keywords = []
    beneficiaries_sum = 0
    next_is_beneficiares = False
    next_is_tip = False
    next_is_bounty = False
    verbose = "normal"
    next_is_vote = False
    abort_command = False
    for arg in command_args:
        if arg in ["set", "and", "upvote", "with", "vote", "in", "after", "at", "abort", "skip", "stop",
                   "silent", "follow", "resteem", "verbose", "tip", "bounty", "release", "subscribe", "random"]:
            keywords.append(arg)
            if arg == "set":
                next_is_beneficiares = True
                next_is_vote = False
                next_is_tip = False
                next_is_bounty = False
            elif arg == "tip":
                next_is_beneficiares = False
                next_is_vote = False
                next_is_tip = True
                next_is_bounty = False
                tip_sbd = 0.01
            elif arg in ["vote", "upvote"]:
                next_is_vote = True
                next_is_beneficiares = False
                next_is_tip = False
                next_is_bounty = False
            elif arg == "bounty":
                next_is_bounty = True
                next_is_vote = False
                next_is_beneficiares = False
                next_is_tip = False                            
            elif arg == "abort":
                abort_command = True
            elif arg in ["stop", "skip"]:
                continue
            elif arg in ["silent", "verbose"]:
                verbose = arg
            else:
                next_is_beneficiares = False
                next_is_vote = False       
                next_is_tip = False
            continue
        elif arg.find('@') > -1 or next_is_beneficiares:
            next_is_beneficiares = False
            for w in arg.split(","):
                if len(w) == 0:
                    next_is_beneficiares = True
                    continue                            
                account_name = w.strip().split(":")[0]
                if account_name[0] == "@":
                    account_name = account_name[1:]
                a = Account(account_name, steem_instance=stm)
                if a["name"] in beneficiaries_accounts:
                    continue
                
                if w.find(":") == -1:
                    percentage = -1
                    
                else:
                    percentage = w.strip().split(":")[1]
                    if "%" in percentage:
                        percentage = percentage.strip().split("%")[0].strip()
                    percentage = float(percentage)
                    beneficiaries_sum += percentage
                beneficiaries.append({"account": a["name"], "weight": int(percentage * 100)})
                
                beneficiaries_accounts.append(a["name"])
            missing = 0
            for bene in beneficiaries:
                if bene["weight"] < 0:
                    missing += 1
            index = 0
            for bene in beneficiaries:
                if bene["weight"] < 0:
                    beneficiaries[index]["weight"] = int((int(100 * 100) - int(beneficiaries_sum * 100)) / missing)
                index += 1
        elif isfloat(arg):
            number.append(arg)
        elif arg == "%" and len(number) > 0:
            if next_is_bounty:
                bounty_vote_percentage = float(number[-1])
            else:
                vote_percentage = float(number[-1])
            symbols.append("%")
            del number[-1]
        elif arg == "$" and len(number) > 0 and not next_is_tip:
            if next_is_bounty:
                bounty_vote_sbd = float(number[-1])
            else:
                vote_sbd = float(number[-1])
            symbols.append("$")
            del number[-1]
        elif arg == "$" and len(number) > 0 and next_is_tip:
            tip_sbd = float(number[-1])
            del number[-1]
            next_is_tip = False
        elif arg in ["min", "mins", "minutes"] and len(number) > 0:
            vote_delay_min = float(number[-1])
            symbols.append(arg)
            del number[-1]
        elif arg in ["day", "days", "d"] and len(number) > 0:
            bounty_delay_days = float(number[-1])
            vote_delay_min = float(number[-1]) * 24 * 60
            symbols.append(arg)
            del number[-1]
        elif arg in ["h", "hours", "hour"] and len(number) > 0:
            bounty_delay_days = float(number[-1])
            vote_delay_min = float(number[-1]) * 60
            symbols.append(arg)
            del number[-1]            
        elif arg in ["sec", "second", "seconds"] and len(number) > 0:
            bounty_delay_days = float(number[-1])
            vote_delay_min = float(number[-1]) / 60
            symbols.append(arg)
            del number[-1]
        elif arg.find('%') > -1 and arg.find('@') == -1:
            if next_is_bounty:
                bounty_vote_percentage = float(arg.strip().split("%")[0].strip())
            else:
                vote_percentage = float(arg.strip().split("%")[0].strip())
            symbols.append('%')
        elif arg.find('$') > -1 and arg.find('@') == -1 and arg.find('%') == -1 and not next_is_tip:
            if next_is_bounty:
                bounty_vote_sbd = float(arg.strip().split("$")[0].strip())
            else:
                vote_sbd = float(arg.strip().split("$")[0].strip())
            symbols.append('$')
        elif arg.find('$') > -1 and arg.find('@') == -1 and arg.find('%') == -1 and next_is_tip:
            tip_sbd = float(arg.strip().split("$")[0].strip())
            next_is_tip = False
        elif arg.find('min') > -1 and arg.find('%') == -1  and arg.find('$') == -1:
            vote_delay_min = float(arg.strip().split("min")[0].strip())
            symbols.append('min')
        elif arg.find('mins') > -1 and arg.find('%') == -1  and arg.find('$') == -1:
            vote_delay_min = float(arg.strip().split("mins")[0].strip())
            symbols.append('min')
        elif arg.find('minutes') > -1 and arg.find('%') == -1  and arg.find('$') == -1:
            vote_delay_min = float(arg.strip().split("minutes")[0].strip())
            symbols.append('min')
        elif arg.find('days') > -1 and arg.find('%') == -1  and arg.find('$') == -1:
            bounty_delay_days = float(arg.strip().split("days")[0].strip())
            symbols.append('days')
        elif arg.find('day') > -1 and arg.find('%') == -1  and arg.find('$') == -1:
            bounty_delay_days = float(arg.strip().split("day")[0].strip())
            symbols.append('days') 
        else:
            break
    if len(number) == 1 and len(command_args) == 1:
        if next_is_bounty:
            bounty_vote_percentage = float(number[0])
        else:
            vote_percentage = float(number[0])
    elif len(number) == 1 and len(command_args) > 1 and len(symbols) == 1:
        if symbols[0] in ["%", "$"] and not next_is_bounty:
            vote_delay_min = float(number[-1])
        elif symbols[0] in ["%", "$"] and next_is_bounty:
            bounty_delay_days = float(number[-1])
        else:
            if next_is_bounty:
                bounty_vote_percentage = float(number[-1])
            else:
                vote_percentage = float(number[-1])
    ret = {"vote_percentage": vote_percentage, "bounty_vote_percentage": bounty_vote_percentage, "vote_sbd": vote_sbd, "bounty_vote_sbd": bounty_vote_sbd, 
              "vote_delay_min": vote_delay_min, "tip_sbd": tip_sbd, "bounty_delay_days": bounty_delay_days, "beneficiaries": beneficiaries}
    return ret
