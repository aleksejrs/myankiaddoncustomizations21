from aqt import mw
from math import log
#from .setting import settings
from .aleksej_target import get_bonus_and_params, get_languages

median_penalty = 1
#median_penalty = 0.406055765    # over 5 days on 2022-01-25

def cardistry_penalty(cid, scan_days, normalize):
    scan_timeavg = 13
#        print("cardistry_penalty: cid {}".format(cid))
    c = mw.col.getCard(cid)

    note = mw.col.getNote(c.nid)
    itagset = {tag.lower() for tag in note.tags}
    # average review time
    shortivl_penalty = 1
    this_avgtime = mw.col.db.scalar(
        "select avg(time)/1000.0 from revlog where cid = ?", cid)
    if this_avgtime is None:
        avgtime_penalty = 1
    else:
#        if (this_avgtime is not None) and (this_avgtime > scan_timeavg):
        if this_avgtime <= 239:
            assumed_avgtime = this_avgtime
        else:
            assumed_avgtime = 300

        # рисование вряд ли может занять меньше минуты
        if 'hard-answerisdrawing' in itagset and assumed_avgtime < 60:
            assumed_avgtime = 60
        avgtime_penalty = float(assumed_avgtime) / float(scan_timeavg)  #- 1.0

    if 'mm_toolong' in itagset:
        avgtime_penalty *= 1.01

    if avgtime_penalty < 0.7:
        avgtime_penalty = 0.7

    def add_to_target_min_logarithmic(ivl):
        return 2.46939 - 0.281854 * log(5.71041 * ivl - 0.232888)
#    print("queue: ", c.queue, "ivl: ", c.ivl)
#    if c.queue != -1:    # new card?   // wrong. Review cards are queue 3, learn are queue 2
#        shortivl_penalty = 1
    if c.ivl == 0:
        shortivl_penalty = 4
    elif c.ivl < 0:
        shortivl_penalty = 5
    elif c.ivl <= 5:
        shortivl_penalty = float(8 / float(c.ivl))
        if shortivl_penalty > 4:
            shortivl_penalty = 4
    else:
        shortivl_penalty = add_to_target_min_logarithmic(c.ivl)
#        elif c.ivl == 0:
#            shortivl_penalty = 3
#        elif c.ivl <= 5:
#            shortivl_penalty = float(5.0 / float(c.ivl))
#            if shortivl_penalty > 3:
#                shortivl_penalty = 3
#        elif c.ivl <= 7:
#            shortivl_penalty = 1
#        elif c.ivl <= 10:
#            shortivl_penalty = 0.95
#        elif c.ivl <= 14:
#            shortivl_penalty = 0.9
#        elif c.ivl <= 21:
#            shortivl_penalty = 0.8
#        elif c.ivl <= 61:
#            shortivl_penalty = 0.7
#        elif c.ivl <= 100:
#            shortivl_penalty = 0.6
#        elif c.ivl <= 200:
#            shortivl_penalty = 0.5
#        elif c.ivl <= 365:
#            shortivl_penalty = 0.4
#        elif c.ivl <= 800:
#            shortivl_penalty = 0.3
#        elif c.ivl <= 1000:
#            shortivl_penalty = 0.15
#        elif c.ivl <= 2000:
#            shortivl_penalty = 0.08
#        elif c.ivl <= 3000:
#            shortivl_penalty = 0.04
#        else:
#            shortivl_penalty = 0.02
#        shortivls += shortivl_penalty

    try:
        lowease_penalty = 3558 / c.factor
    except:
        lowease_penalty = 1

    autoEaseFactor_bonus, target_min, target_max = get_bonus_and_params(c)
    autoEaseFactor_multiplier = 1.00 + autoEaseFactor_bonus * 0.7

#        if 'morphman_important' in itagset:
#            importance_multiplier = 1.01
#        else:
#            importance_multiplier = 0.99001
#        if 'morphman_urgent' in itagset:
#            urgency_multiplier = 1.01
#        else:
#            urgency_multiplier = 0.99001

#        print("Ivl: {}, pen: {}".format(c.ivl, shortivl_penalty))
#        print("Avg time: {}, pen: {}".format(this_avgtime, avgtime_penalty))
#        print("Ease: {}, pen: {}".format(c.factor, lowease_penalty))
#    if c.ivl < 6:
#        print(shortivl_penalty, avgtime_penalty, lowease_penalty, autoEaseFactor_multiplier)
    total_card_penalty = shortivl_penalty * avgtime_penalty * lowease_penalty * autoEaseFactor_multiplier  # * importance_multiplier * urgency_multiplier
    if normalize:
        total_card_penalty = total_card_penalty / median_penalty
    return (total_card_penalty)

