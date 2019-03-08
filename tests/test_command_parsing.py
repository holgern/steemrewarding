from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import unittest
from datetime import datetime, date, timedelta
from beem import Steem
from steemrewarding.command_parsing import parse_command


class Testcases(unittest.TestCase):
    def test_vote_command(self):
        stm = Steem()
        ret = parse_command("$rewarding upvote 76% in 45mins", stm)
        self.assertEqual(ret["vote_delay_min"], 45)
        self.assertEqual(ret["vote_percentage"], 76)

        ret = parse_command("$rewarding upvote 87%", stm)
        self.assertEqual(ret["vote_delay_min"], 15)
        self.assertEqual(ret["vote_percentage"], 87)
        
        ret = parse_command("$rewarding 60% \n", stm)
        self.assertEqual(ret["vote_delay_min"], 15)
        self.assertEqual(ret["vote_percentage"], 60)
        
        ret = parse_command("$rewarding 100% 80min", stm)
        self.assertEqual(ret["vote_delay_min"], 80)
        self.assertEqual(ret["vote_percentage"], 100)        
        
        ret = parse_command("$rewarding 55% 14", stm)
        self.assertEqual(ret["vote_delay_min"], 14)
        self.assertEqual(ret["vote_percentage"], 55)        

        ret = parse_command("$rewarding 7% 15min", stm)
        self.assertEqual(ret["vote_delay_min"], 15)
        self.assertEqual(ret["vote_percentage"], 7)  

        ret = parse_command("$rewarding upvote 43 % after 11 min", stm)
        self.assertEqual(ret["vote_delay_min"], 11)
        self.assertEqual(ret["vote_percentage"], 43)    
        
        ret = parse_command("$rewarding 0.01$", stm)
        self.assertEqual(ret["vote_delay_min"], 15)
        self.assertEqual(ret["vote_sbd"], 0.01)        
        
        ret = parse_command("$rewarding 0.01$ tip 0.01$", stm)
        self.assertEqual(ret["vote_delay_min"], 15)
        self.assertEqual(ret["vote_sbd"], 0.01)
        self.assertEqual(ret["tip_sbd"], 0.01)

        ret = parse_command("$rewarding 10% 2days", stm)
        self.assertEqual(ret["vote_delay_min"], 2 * 24 * 60)
        self.assertEqual(ret["vote_percentage"], 10)

        ret = parse_command("$rewarding 10% 2hours", stm)
        self.assertEqual(ret["vote_delay_min"], 2 * 60)
        self.assertEqual(ret["vote_percentage"], 10)

        ret = parse_command("$rewarding 10% 60seconds", stm)
        self.assertEqual(ret["vote_delay_min"], 1)
        self.assertEqual(ret["vote_percentage"], 10)
        
    def test_vote_command(self):
        stm = Steem()
        ret = parse_command("$rewarding set nonameslefttouse:70, steemnsfw", stm)
        self.assertEqual(ret["beneficiaries"], [{"account": "nonameslefttouse", "weight": 7000}, {"account": "steemnsfw", "weight": 3000}])
