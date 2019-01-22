# steemrewarding
Automatic upvote service for STEEM

## Installation of packages for Ubuntu 18.04

```
sudo apt-get install postgresql postgresql-contrib python3-pip libicu-dev build-essential libssl-dev python3-dev
```

## Installation of python packages
```
pip3 install beem dataset psycopg2-binary secp256k1prp
```


## Setup of the postgresql database

Set a password and a user for the postgres database:

```
su postgres
psql -c "\password"
createdb rewarding
```