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

## Prepare the postgres database
```
psql -d rewarding -a -f sql/rewarding.sql
```

## Config file for accessing the database and the beem wallet
A `config.json` file must be stored in the main directory and in the homepage directory where the `app.py` file is.
```
{
        "databaseConnector": "postgresql://postgres:password@localhost/rewarding",
        "wallet_password": "abc",
        "flask_secret_key": "abc"
}
```

## Running the scripts
```
chmod a+x rewarding.sh
./rewarding.sh
```
or copy the systemd service file to /etc/systemd/system and start it by
```
systemctl start rewarding
```


