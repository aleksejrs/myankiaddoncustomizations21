# -*- coding: utf-8 -*-
# Copyright: (C) 2018-2020 Lovac42
# Support: https://github.com/lovac42/Cardistry
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html


from aqt import mw
from .setting import settings

from .cardistry_penalty import cardistry_penalty, median_penalty

def getYoungCardCnt(did):
    "count lrn or burried only, no suspended"

    opts = settings.conf.get("scan_options", {})
    sd = opts.get("scan_days", 5) - 1 #reduce by 1 to include today
    scan_days = mw.col.sched.today + sd
    scan_ease = opts.get("scan_ease", 4000)
    scan_timeavg = opts.get("scan_timeavg", 9999)
    matured_ivl = opts.get("matured_ivl", 21)

    incFilter = opts.get("inc_filtered_decks", False)
    sql_odid='or odid = %d'%did if incFilter else ''

    due_soon=mw.col.db.list("""
Select id from cards where
type in (1,2,3) and queue in (1,2,3,4,-2,-3)
and due <= ?
and (did = ? %s)"""%sql_odid,
scan_days, did)
    total_penalty = float(0)
    for card_due_soon in due_soon:

        total_card_penalty = cardistry_penalty(cid=card_due_soon, scan_days=scan_days, normalize=True)
#        print(" -> total_card_penalty: {}".format(total_card_penalty))
        total_penalty += total_card_penalty
#        if total_card_penalty > 2:
#            print(total_card_penalty)
#    if overlong_times != 0:
#        print(overlong_times)
#    if cnt != 0:
#        print(cnt)
#    print(total_penalty)
    return (int(total_penalty)) or 0  # x outstanding ÷ y (prop:due<6)
#    return (int(total_penalty * 0.70202818)) or 0  # x outstanding ÷ y (prop:due<6)




def getNewCardCnt(did):
    "count new or burried only, no suspended"

    opts = settings.conf.get("scan_options", {})
    incFilter = opts.get("inc_filtered_decks", False)
    sql_odid='or odid = %d'%did if incFilter else ''

    cnt=mw.col.db.first("""
Select count() from cards where
type = 0 and queue in (0,-2,-3)
and (did = ? %s)"""%sql_odid,did)[0]

    return cnt or 0

