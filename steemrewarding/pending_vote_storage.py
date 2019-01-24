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


class PendingVotesTrx(object):
    """ This is the trx storage class
    """
    __tablename__ = 'pending_votes'

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

    def get_latest_command(self):
        table = self.db[self.__tablename__]
        ret = table.find_one(order_by='-created')
        if ret is None:
            return None
        return ret

    def get_votes(self, voter):
        table = self.db[self.__tablename__]
        votes = []
        for vote in table.find(voter=voter, order_by='-created'):
            votes.append(vote)
        return votes

    def get_command_list_timed(self):
        table = self.db[self.__tablename__]
        posts = []
        for post in table.find(vote_when_vp_reached=False, order_by='created'):
            posts.append(post)
        return posts

    def get_command_list_vp_reached(self):
        table = self.db[self.__tablename__]
        posts = []
        for post in table.find(vote_when_vp_reached=True, order_by='vp_reached_order'):
            posts.append(post)
        return posts

    def delete(self, authorperm, voter):
        """ Delete a data set

           :param int ID: database id
        """
        table = self.db[self.__tablename__]
        table.delete(authorperm=authorperm, voter=voter)

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


