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


class BroadcastVoteTrx(object):
    """ This is the trx storage class
    """
    __tablename__ = 'broadcast_vote'

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

    def update_processed(self, voter, authorperm, trx, valid, expired):
        """ Change share_age depending on timestamp

        """
        table = self.db[self.__tablename__]
        data = dict(voter=voter, authorperm=authorperm, trx=trx, valid=valid, expired=expired)
        table.update(data, ["authorperm", "voter"])

    def update(self, data):
        """ Change share_age depending on timestamp

        """
        table = self.db[self.__tablename__]
        table.update(data, ["authorperm", "voter"])

    def get_unprocessed(self, voter, authorperm):
        table = self.db[self.__tablename__]
        return table.find_one(voter=voter, authorperm=authorperm, valid=True, expired=False, trx=None, order_by='expiration')

    def get_all_unexpired(self, timestamp):
        table = self.db[self.__tablename__]
        ret = []
        for data in table.find(valid=True, expired=False, expiration = {'<': timestamp}):
            ret.append(data)
        return ret

    def get_all_expired(self):
        table = self.db[self.__tablename__]
        ret = []
        for data in table.find(valid=True, expired=False, trx=None):
            ret.append(data)
        return ret

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
