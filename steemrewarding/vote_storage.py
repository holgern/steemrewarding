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


class VotesTrx(object):
    """ This is the trx storage class
    """
    __tablename__ = 'votes'

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
        table.upsert(data, ["authorperm", "voter"])
        self.db.commit()

    def add_batch(self, data):
        """ Add a new data set

        """
        table = self.db[self.__tablename__]
        
        if isinstance(data, list):
            #table.insert_many(data, chunk_size=chunk_size)
            for d in data:
                table.upsert(d, ["authorperm", "voter"])
        else:
            self.db.begin()
            for d in data:
                table.upsert(data[d], ["authorperm", "voter"])            
            
        self.db.commit()

    def update_batch(self, data):
        """ Add a new data set

        """
        table = self.db[self.__tablename__]
        self.db.begin()
        if isinstance(data, list):
            for d in data:
                table.update(d, ["authorperm", "voter"])
        else:
            for d in data:
                table.update(data[d], ["authorperm", "voter"])            
        self.db.commit()

    def update_processed(self, authorperm, processed):
        """ Change share_age depending on timestamp

        """
        table = self.db[self.__tablename__]
        data = dict(authorperm=authorperm, processed=processed)
        table.update(data, ['authorperm', "voter"])

    def get_latest_vote(self):
        table = self.db[self.__tablename__]
        ret = table.find_one(order_by='-timestamp')
        if ret is None:
            return None
        return ret

    def get_latest_block(self):
        table = self.db[self.__tablename__]
        ret = table.find_one(order_by='-timestamp')
        if ret is None:
            return None
        return ret["block"]

    def get_voter_votes(self, voter):
        table = self.db[self.__tablename__]
        posts = []
        for post in table.find(voter=voter, order_by='timestamp'):
            posts.append(post)
        return posts

    def get_authorperm_votes(self, authorperm):
        table = self.db[self.__tablename__]
        posts = []
        for post in table.find(authorperm=authorperm, order_by='timestamp'):
            posts.append(post)
        return posts

    def get_vote(self, authorperm, voter):
        table = self.db[self.__tablename__]
        posts = None
        for post in table.find(authorperm=authorperm, voter=voter):
            posts = post
        return posts

    def get_votes_list(self):
        table = self.db[self.__tablename__]
        posts = []
        for post in table.find(order_by='timestamp'):
            posts.append(post)
        return posts

    def get_authorperm_list(self):
        table = self.db[self.__tablename__]
        posts = []
        for post in table.find(order_by='timestamp'):
            posts.append(post["authorperm"])
        return posts

    def get_votes_list(self, start_timestamp):
        table = self.db[self.__tablename__]
        votes = []
        for vote in table.find(table.table.columns.timestamp >  start_timestamp, order_by='timestamp'):
            votes.append(vote)
        return votes

    def delete_old_votes(self, days):
        table = self.db[self.__tablename__]
        del_votes = []
        for post in table.find(order_by='timestamp'):
            if (datetime.utcnow() - post["timestamp"]).total_seconds() > 60 * 60 * 24 * days:
                del_votes.append(post)
        for vote in del_votes:
            table.delete(authorperm=vote["authorperm"], voter=vote["voter"])

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
