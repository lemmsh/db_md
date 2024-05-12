#!/bin/bash

mkdir -p $HOME/.config/systemd/user/
cp systemd/* $HOME/.config/systemd/user/
systemctl --user daemon-reload


## make scripts /usr/bin/mdbot-test and /usr/bin/mdbot 
## which will export the TELEGRAM_CHAT_ID and TELEGRAM_TOKEN
## and run the dbmdbot.py, passing the input parameters
## todo: make dbmdbot accepting a configuration file

