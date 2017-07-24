#! /bin/sh -
date >> /opt/crashlog.log
pgrep -fl otto.py >> /opt/crashlog.log || /usr/bin/python /opt/otto_robotto/otto.py > /opt/stdout.log



