# This Python file uses the following encoding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from builtins import bytes
from builtins import object
from beemgraphenebase.py23 import py23_bytes, bytes_types
from sqlalchemy.dialects.postgresql import insert as pg_insert
import shutil
import time
import os
import json
import sqlite3
from appdirs import user_data_dir
from datetime import datetime, timedelta
from beem.utils import formatTimeString, addTzInfo
import logging
from binascii import hexlify
import random
import hashlib
import dataset
from sqlalchemy import and_
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())

timeformat = "%Y%m%d-%H%M%S"


class TrailDownVoteRulesTrx(object):
    """ This is the trx storage class
    """
    __tablename__ = 'trail_downvote_rules'

    def __init__(self, db):
        self.db = db

    def exists_table(self):
        """ Check if the database table exists
        """

        if len(self.db.tables) == 0:
            return False
        if self.__tablename__ in self.db.tables:
            return True
        else:
            return False
 
    def add(self, data):
        """ Add a new data set

        """
        table = self.db[self.__tablename__]
        table.upsert(data, ["voter_to_follow", "account"])
 
    def update(self, data):
        """ Add a new data set

        """
        table = self.db[self.__tablename__]
        table.update(data, ["voter_to_follow", "account"])

    def add_batch(self, data):
        """ Add a new data set

        """
        table = self.db[self.__tablename__]
        self.db.begin()
        if isinstance(data, list):
            #table.insert_many(data, chunk_size=chunk_size)
            for d in data:
                table.upsert(d, ["voter_to_follow", "account"])
        else:
            
            for d in data:
                table.upsert(data[d], ["voter_to_follow", "account"])            
            
        self.db.commit()

    def update_batch(self, data):
        """ Add a new data set

        """
        table = self.db[self.__tablename__]
        self.db.begin()
        if isinstance(data, list):
            for d in data:
                table.update(d, ["voter_to_follow", "account"])
        else:
            for d in data:
                table.update(data[d], ["voter_to_follow", "account"])            
        self.db.commit()

    def get_trail_voters(self):
        table = self.db[self.__tablename__]
        data = [] 
        for v in table.find():
            if v["voter_to_follow"] not in data:
                data.append(v["voter_to_follow"])
        return data


    def get_accounts(self):
        table = self.db[self.__tablename__]
        data = [] 
        for v in table.all():
            if v["account"] not in data:
                data.append(v["account"])
        return data

    def get(self, voter_to_follow, account):
        table = self.db[self.__tablename__]
        return table.find_one(voter_to_follow=voter_to_follow, account=account)

    def get_rules(self, voter_to_follow):
        table = self.db[self.__tablename__]
        data = [] 
        for v in table.find(voter_to_follow=voter_to_follow):
            data.append(v)
        return data

    def get_rules_by_account(self, account):
        table = self.db[self.__tablename__]
        data = [] 
        for v in table.find(account=account):
            data.append(v)
        return data
    
    def delete(self, voter_to_follow, account):
        """ Delete a data set

           :param int ID: database id
        """
        table = self.db[self.__tablename__]
        table.delete(voter_to_follow=voter_to_follow, account=account)

    def wipe(self, sure=False):
        """Purge the entire database. No data set will survive this!"""
        if not sure:
            log.error(
                "You need to confirm that you are sure "
                "and understand the implications of "
                "wiping your wallet!"
            )
            return
        else:
            table = self.db[self.__tablename__]
            table.drop
