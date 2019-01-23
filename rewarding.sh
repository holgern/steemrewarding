#!/bin/bash
cd /root/git/steemrewarding/
/usr/bin/python3.6 -u /root/git/steemrewarding/stream_blocks.py
/usr/bin/python3.6 -u /root/git/steemrewarding/apply_vote_rules.py
/usr/bin/python3.6 -u /root/git/steemrewarding/upvote_post_comments.py