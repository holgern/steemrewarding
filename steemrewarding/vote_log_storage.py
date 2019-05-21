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
from datetime import datetime, timedelta, date
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


class VoteLogTrx(object):
    """ This is the trx storage class
    """
    __tablename__ = 'vote_log'

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

    def update(self, data):
        """ Add a new data set

        """
        table = self.db[self.__tablename__]
        table.update(data, ["authorperm", "voter"])

    def get(self, authorperm, voter):
        table = self.db[self.__tablename__]
        return table.find_one(authorperm=authorperm, voter=voter)

    def get_votes(self, voter, hours=168):
        table = self.db[self.__tablename__]
        # today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        date_before = datetime.utcnow() - timedelta(hours=hours)
        votes = []
        for v in table.find(table.table.columns.timestamp > date_before, voter=voter, order_by='-timestamp'):
            votes.append(v)
        return votes
    
    def get_log_list(self):
        table = self.db[self.__tablename__]
        logs = []
        for v in table.find(order_by='last_update'):
            logs.append(v)
        return logs        

    def get_oldest_log(self, vote_delay_optimized=False, min_age=15):
        table = self.db[self.__tablename__]
        date_before = datetime.utcnow() - timedelta(minutes=min_age)
        return table.find_one(table.table.columns.timestamp < date_before, is_pending=True, vote_delay_optimized=vote_delay_optimized, order_by='last_update')    

    def get_votes_per_day(self, voter, author, sliding_window=True):
        table = self.db[self.__tablename__]
        
        if sliding_window:
            date_24h_before = datetime.utcnow() - timedelta(hours=24)
        else:
            date_24h_before = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        votes = 0
        for v in table.find(table.table.columns.timestamp > date_24h_before, author=author, voter=voter):
            votes += 1
        return votes

    def get_votes_per_week(self, voter, author, sliding_window=True):
        table = self.db[self.__tablename__]
        if sliding_window:
            date_168h_before = datetime.utcnow() - timedelta(hours=168)
        else:
            date_168h_before = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=168)
        votes = 0
        for v in table.find(table.table.columns.timestamp > date_168h_before, author=author, voter=voter):
            votes += 1
        return votes

    def delete_old_logs(self, days=7):
        table = self.db[self.__tablename__]
        del_logs = []
        for log in table.find(order_by='timestamp'):
            if (datetime.utcnow() - log["timestamp"]).total_seconds() - log["voted_after_min"] * 60 > 60 * 60 * 24 * days:
                del_logs.append(log)
        for log in del_logs:
            table.delete(authorperm=log["authorperm"], voter=log["voter"])

    def delete(self, ID):
        """ Delete a data set

           :param int ID: database id
        """
        table = self.db[self.__tablename__]
        table.delete(id=ID)

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
