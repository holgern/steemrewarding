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


class AccountsDB(object):
    """ This is the accounts storage class
    """
    __tablename__ = 'accounts'

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

    def get(self, name):
        """ Returns the public keys stored in the database
        """
        table = self.db[self.__tablename__]
        return table.find_one(name=name)
    
    def upsert(self, data):
        """ Add a new data set
    
        """
        table = self.db[self.__tablename__]
        table.upsert(data, ["name"])
        self.db.commit()


    def update(self, data):
        """ Change share_age depending on timestamp
    
        """
        table = self.db[self.__tablename__]
        table.update(data, ['name'])
    
    def delete(self, account):
        """ Delete a data set
    
           :param int ID: database id
        """
        table = self.db[self.__tablename__]
        table.delete(account=account)
    
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