# -*- coding: utf-8 -*-
import codecs
import importlib
import time
import itertools

from anki.tags import TagManager

from functools import partial
from math import ceil, isqrt
from random import randint

import aqt.main
from anki.utils import splitFields, joinFields, stripHTML, intTime, fieldChecksum

from .morphemes import Location, Morpheme
from . import stats
from . import util
from .morphemes import MorphDb, AnkiDeck, getMorphemes
from .morphemizer import getMorphemizerByName
from .util import printf, mw, errorMsg, getFilter, getFilterByMidAndTags
from .preferences import get_preference as cfg
from .util_external import memoize

from .aleksej_main_penalty import get_depicts_penalty, get_language_set, get_fiction_penalty, get_language_penalty, get_language_prio_malus, get_role_penalty, get_other_penalty, priorityDb_toavoid, get_prio_penalty, get_combo_morphs_equiv

update_even_unchanged = True

# hack: typing is compile time anyway, so, nothing bad happens if it fails, the try is to support anki < 2.1.16
try:
    from aqt.pinnedmodules import typing  # pylint: disable=W0611 # See above hack comment
    from typing import Dict, Set
except ImportError:
    pass

# only for jedi-auto-completion
assert isinstance(mw, aqt.main.AnkiQt)


@memoize
def getFieldIndex(fieldName, mid):
    """
    Returns the index of a field in a model by its name.
    For example: we have the modelId of the card "Basic".
    The return value might be "1" for fieldName="Front" and
    "2" for fieldName="Back".
    """
    m = mw.col.models.get(mid)
    return next((f['ord'] for f in m['flds'] if f['name'] == fieldName), None)


def extractFieldData(field_name, fields, mid):
    # type: (str, str, str) -> str
    """
    :type field_name: The field name (like u'Expression')
    :type fields: A string containing all field data for the model (created by anki.utils.joinFields())
    :type mid: the modelId depicting the model for the "fields" data
    """
    idx = getFieldIndex(field_name, mid)
    return stripHTML(splitFields(fields)[idx])


@memoize
def getSortFieldIndex(mid):
    return mw.col.models.get(mid)['sortf']


def setField(mid, fs, k, v):  # nop if field DNE
    # type: (int, [str], str, str) -> None
    """
    :type mid: modelId
    :type fs: a list of all field data
    :type k: name of field to modify (for example u'Expression')
    :type v: new value for field
    """
    idx = getFieldIndex(k, mid)
#    try:
    if idx:
        fs[idx] = v
#    except IndexError:
#        print("IndexError.")
#        print("mid: {}".format(mid))
#        print("fs: {}".format(fs))
#        print("idx: {}".format(idx))
#        print("k: {}".format(k))
#        print("v: {}".format(v))


def mkAllDb(all_db=None):
    from . import config
    importlib.reload(config)
    t_0, db, TAG = time.time(), mw.col.db, mw.col.tags
    N_notes = db.scalar('select count() from notes')
    # for providing an error message if there is no note that is used for processing
    N_enabled_notes = 0
    mw.progress.start(label='Prep work for all.db creation',
                      max=N_notes, immediate=True)

    if not all_db:
        all_db = MorphDb()
    fidDb = all_db.fidDb()
    locDb = all_db.locDb(recalc=False)  # fidDb() already forces locDb recalc

    mw.progress.update(label='Generating all.db data')
    for i, (nid, mid, flds, guid, tags) in enumerate(db.execute('select id, mid, flds, guid, tags from notes')):
        if i % 500 == 0:
            mw.progress.update(value=i)

        C = partial(cfg, model_id=mid)

        note = mw.col.getNote(nid)
        note_cfg = getFilter(note)
        if note_cfg is None:
            continue
        morphemizer = getMorphemizerByName(note_cfg['Morphemizer'])

        N_enabled_notes += 1

        mats = [(0.5 if ivl == 0 and ctype == 1 else ivl) for ivl, ctype in
                db.execute('select ivl, type from cards where nid = :nid', nid=nid)]
        if C('ignore maturity'):
            mats = [0] * len(mats)
        ts, alreadyKnownTag = TAG.split(tags), cfg('Tag_AlreadyKnown')
        if alreadyKnownTag in ts:
            mats += [C('threshold_mature') + 1]

        for fieldName in note_cfg['Fields']:
            try:  # if doesn't have field, continue
                fieldValue = extractFieldData(fieldName, flds, mid)
            except KeyError:
                continue
            except TypeError:
                mname = mw.col.models.get(mid)['name']
                errorMsg('Failed to get field "{field}" from a note of model "{model}". Please fix your config.py '
                         'file to match your collection appropriately and ignore the following error.'.format(
                             model=mname, field=fieldName))
                raise

            loc = fidDb.get((nid, guid, fieldName), None)
            if not loc:
                loc = AnkiDeck(nid, fieldName, fieldValue, guid, mats)
                ms = getMorphemes(morphemizer, fieldValue, ts)
                if ms:  # TODO: this needed? should we change below too then?
                    locDb[loc] = ms
            else:
                # mats changed -> new loc (new mats), move morphs
                if loc.fieldValue == fieldValue and loc.maturities != mats:
                    newLoc = AnkiDeck(nid, fieldName, fieldValue, guid, mats)
                    locDb[newLoc] = locDb.pop(loc)
                # field changed -> new loc, new morphs
                elif loc.fieldValue != fieldValue:
                    newLoc = AnkiDeck(nid, fieldName, fieldValue, guid, mats)
                    ms = getMorphemes(morphemizer, fieldValue, ts)
                    locDb.pop(loc)
                    locDb[newLoc] = ms
        if i % 100 == 0:
            mw.progress.update(value=i, label='Creating all.db objects')

    if N_enabled_notes == 0:
        mw.progress.finish()
        errorMsg('There is no card that can be analyzed or be moved. Add cards or (re-)check your configuration under '
                 '"Tools -> MorphMan Preferences" or in "Anki/addons/morph/config.py" for mistakes.')
        return None

    printf('Processed all %d notes in %f sec' % (N_notes, time.time() - t_0))

    all_db.clear()
    all_db.addFromLocDb(locDb)
    if cfg('saveDbs'):
        mw.progress.update(label='Saving all.db to disk')
        all_db.save(cfg('path_all'))
        printf('Processed all %d notes + saved all.db in %f sec' %
               (N_notes, time.time() - t_0))
    mw.progress.finish()
    return all_db


def filterDbByMat(db, mat):
    """Assumes safe to use cached locDb"""
    newDb = MorphDb()
    for loc, ms in db.locDb(recalc=False).items():
        if loc.maturity > mat:
            newDb.addMsL(ms, loc)
    return newDb


def updateNotes(allDb):
    t_0, now, db = time.time(), intTime(), mw.col.db

    TAG = mw.col.tags  # type: TagManager
    ds, nid2mmi = [], {}
    N_notes = db.scalar('select count() from notes')
    mw.progress.start(label='Updating data', max=N_notes, immediate=True)
    fidDb = allDb.fidDb(recalc=True)
    loc_db = allDb.locDb(recalc=False)  # type: Dict[Location, Set[Morpheme]]

    # read tag names
    compTag, vocabTag, freshTag, notReadyTag, alreadyKnownTag, priorityTag, tooShortTag, tooLongTag, frequencyTag = tagNames = cfg(
        'Tag_Comprehension'), cfg('Tag_Vocab'), cfg('Tag_Fresh'), cfg('Tag_NotReady'), cfg(
        'Tag_AlreadyKnown'), cfg('Tag_Priority'), cfg('Tag_TooShort'), cfg('Tag_TooLong'), cfg('Tag_Frequency')
    TAG.register(tagNames)
    badLengthTag = cfg('Tag_BadLength')

    # handle secondary databases
    mw.progress.update(label='Creating seen/known/mature from all.db')
    seenDb = filterDbByMat(allDb, cfg('threshold_seen'))
    knownDb = filterDbByMat(allDb, cfg('threshold_known'))
    matureDb = filterDbByMat(allDb, cfg('threshold_mature'))
    mw.progress.update(label='Loading priority.db')
    priorityDb = MorphDb(cfg('path_priority'), ignoreErrors=True).db

    mw.progress.update(label='Loading frequency.txt')
    frequencyListPath = cfg('path_frequency')
    try:
        with codecs.open(frequencyListPath, encoding='utf-8') as f:
            # create a dictionary. key is word, value is its position in the file
            frequency_list = dict(zip(
                [line.strip().split('\t')[0] for line in f.readlines()],
                itertools.count(0)))

    except FileNotFoundError:
        frequency_list = []

    frequencyListLength = len(frequency_list)

    if cfg('saveDbs'):
        mw.progress.update(label='Saving seen/known/mature dbs')
        seenDb.save(cfg('path_seen'))
        knownDb.save(cfg('path_known'))
        matureDb.save(cfg('path_mature'))

    mw.progress.update(label='Updating notes')

    # prefetch cfg for fields
    field_focus_morph = cfg('Field_FocusMorph')
    field_unknown_count = cfg('Field_UnknownMorphCount')
    field_unmature_count = cfg('Field_UnmatureMorphCount')
    field_morph_man_index = cfg('Field_MorphManIndex')
    field_unknowns = cfg('Field_Unknowns')
    field_unmatures = cfg('Field_Unmatures')
    field_unknown_freq = cfg('Field_UnknownFreq')
    field_focus_morph_pos = cfg("Field_FocusMorphPos")

    max_good_due = 10000000      # any surplus will be reduced using a made-up formula
    max_editable_due = 99999999  # you can still increment it in the Browser, but not as digits.

    for i, (nid, mid, flds, guid, tags) in enumerate(db.execute('select id, mid, flds, guid, tags from notes')):
        ts = TAG.split(tags)
        if i % 500 == 0:
            mw.progress.update(value=i)

        C = partial(cfg, model_id=mid)

        notecfg = getFilterByMidAndTags(mid, ts)
        if notecfg is None or not notecfg['Modify']:
            continue

        # Get all morphemes for note
        morphemes = set()
        for fieldName in notecfg['Fields']:
            try:
                loc = fidDb[(nid, guid, fieldName)]
                morphemes.update(loc_db[loc])
            except KeyError:
                continue

        proper_nouns_known = cfg('Option_ProperNounsAlreadyKnown')

        # Determine un-seen/known/mature and i+N
        unseens, unknowns, unmatures, new_knowns = set(), set(), set(), set()
        for morpheme in morphemes:
            if proper_nouns_known and morpheme.isProperNoun():
                continue
            if not seenDb.matches(morpheme):
                unseens.add(morpheme)
            if not knownDb.matches(morpheme):
                unknowns.add(morpheme)
            if not matureDb.matches(morpheme):
                unmatures.add(morpheme)
                if knownDb.matches(morpheme):
                    new_knowns.add(morpheme)

        N, N_s, N_k, N_m, N_kp = 0, 0, 0, 0, 0

#        def worth_this_many_words(morpheme):
#            if " " in morpheme:
#                n = 0.75
#            else:
#                n = 1

        for morpheme_being_counted in morphemes:
            if not " " in morpheme_being_counted.base:
                N += 1

        for morpheme_being_counted in unseens:
            if N == 0:
                N += 1
            else:
                N_s += get_combo_morphs_equiv(morpheme_being_counted.base)

        for morpheme_being_counted in unknowns:
            if not " " in morpheme_being_counted.base:
                N_k += + 1
            else:
                N_kp += get_combo_morphs_equiv(morpheme_being_counted.base)

        for morpheme_being_counted in unmatures:
            if N_m == 0:
                N_m += 1
            else:
                N_m += get_combo_morphs_equiv(morpheme_being_counted.base)

#        # Determine MMI - Morph Man Index
#        N, N_s, N_k, N_m = len(morphemes), len(
#            unseens), len(unknowns), len(unmatures)
        N = ceil(N)
        N_s = ceil(N_s)
        N_k = ceil(N_k)
        N_m = ceil(N_m)

        # Bail early for lite update
        if N_k > 2 and C('only update k+2 and below'):
            continue


        # add bonus for morphs in priority.db and frequency.txt
        frequencyBonus = C('frequency.txt bonus')
        noPriorityPenalty = C('no priority penalty')
        reinforceNewVocabWeight = C('reinforce new vocab weight')
        priorityDbWeight = C('priority.db weight')
        isPriority = False
        isFrequency = False

        focusMorph = None

        # непонятно, но похоже, что он складывает все frequency подходящих unknowns
        F_k = 0
        usefulness_of_this_unknown_morph = 0
        best_focus_morph_from_unknowns_usefulness = 0
        best_focus_morph_from_unknowns = None
        for this_unknown in unknowns:
            F_k += allDb.frequency(this_unknown)
            if this_unknown in priorityDb:
                if priorityDb_toavoid(this_unknown):
                    isPriority = True
                    usefulness_of_this_unknown_morph += priorityDbWeight
            this_unknownString = this_unknown.base
            try:
                this_unknownIndex = frequency_list[this_unknownString]
                isFrequency = True

                # The bigger this number, the lower mmi would become
                usefulness_of_this_unknown_morph += int(round( frequencyBonus * (1 - this_unknownIndex / frequencyListLength) ))
                if usefulness_of_this_unknown_morph > best_focus_morph_from_unknowns_usefulness:
                    best_focus_morph_from_unknowns_usefulness = usefulness_of_this_unknown_morph
                    best_focus_morph_from_unknowns = this_unknown

            except KeyError:
                pass
            if N_k == 1:
                if " " not in this_unknown.base:
                    break

        best_focus_morph_from_unmatures_usefulness = 0
        best_focus_morph_from_unmatures = None
        for this_unmature in unmatures:
            this_unmatureString = this_unmature.base
            usefulness_of_this_unmature_morph = 0
            try:
                this_unmatureIndex = frequency_list[this_unmatureString]
                isFrequency = True

                # The bigger this number, the lower mmi would become
                usefulness_of_this_unmature_morph += int(round( frequencyBonus * (1 - this_unmatureIndex / frequencyListLength) ))
                if usefulness_of_this_unmature_morph > best_focus_morph_from_unmatures_usefulness:
                    best_focus_morph_from_unmatures_usefulness = usefulness_of_this_unmature_morph
                    best_focus_morph_from_unmatures = this_unmature

            except KeyError:
                pass

        usefulness_of_this_morph = 0
        focusMorph_unknown_with_space = None
        focusMorph_unmature_with_space = None
        if best_focus_morph_from_unknowns:
            focusMorph = best_focus_morph_from_unknowns
            usefulness_of_this_morph = usefulness_of_this_unknown_morph
            if best_focus_morph_from_unmatures and usefulness_of_this_unmature_morph > usefulness_of_this_morph:
                usefulness_of_this_morph = (usefulness_of_this_unknown_morph + usefulness_of_this_unmature_morph) / 2
        elif best_focus_morph_from_unmatures:
            focusMorph = best_focus_morph_from_unmatures
            usefulness_of_this_morph = usefulness_of_this_unmature_morph
        elif unknowns:
            for this_unknown in unknowns:
                if ' ' not in this_unknown.base:
                    focusMorph = this_unknown
                    break
                else:
                    focusMorph_unknown_with_space = this_unknown
        if focusMorph is None and unmatures:
            for this_unmature in unmatures:
                if ' ' not in this_unmature.base:
                    focusMorph = this_unmature
                    break
                else:
                    focusMorph_unmature_with_space = this_unmature
        if focusMorph is None:
            if focusMorph_unknown_with_space is not None:
                focusMorph = focusMorph_unknown_with_space
            elif focusMorph_unmature_with_space is not None:
                focusMorph = focusMorph_unmature_with_space


        # average frequency of unknowns (ie. how common the word is within your collection)
        F_k_avg = F_k // (N_k + N_kp) if (N_k + N_kp) > 0 else F_k
        usefulness_of_this_morph += F_k_avg

        # add bonus for studying recent learned knowns (reinforce)
        for morpheme in new_knowns:
            locs = knownDb.getMatchingLocs(morpheme)
            if locs:
                ivl = min(1, max(loc.maturity for loc in locs))
                # TODO: maybe average this so it doesnt favor long sentences
                usefulness_of_this_morph += reinforceNewVocabWeight // ivl

#        if any(morpheme.pos == '動詞' for morpheme in unknowns):  # FIXME: this isn't working???
#            usefulness_of_this_morph += C('verb bonus')

        uselessness_penalty = 399999 - min(599999, usefulness_of_this_morph)
#        uselessness = 99999 - min(99999, uselessness)

        itagset = {tag.lower() for tag in ts}

        is_immediate = False
        is_important = False
        is_urgent = False
        if "mm_imp" in ts and "вв-неваж" not in ts:
            is_important = True
        if "аа-безотлагательно" in ts:
            is_urgent = True
            is_immediate = True
        if "mm_urg" in ts and "аа-несроч" not in ts:
            is_urgent = True

        mname = mw.col.models.get(mid)['name']

        prio_penalty = get_prio_penalty(mname, ts, is_immediate, is_important, is_urgent)
        if prio_penalty is None:
            print("prio penalty is None")
            prio_penalty = 0
        role_penalty = get_role_penalty(ts, itagset)
        if role_penalty is None:
            print("role penalty is None")
            role_penalty = 0

        language_set = get_language_set(itagset)
        language_penalty = get_language_penalty(itagset, language_set, is_immediate, is_important,
            is_urgent)
        language_prio_malus = get_language_prio_malus(itagset, language_set, is_immediate,
            is_important, is_urgent)
        if language_penalty is None:
            print("language penalty is None")
            language_penalty = 1
        if language_prio_malus is None:
            print("language prio malus is None")
            language_prio_malus = 0

        # difference from optimal length range (too little context vs long sentence)
        # calculate mmi
        if mname == "IR3":
#            if N_k > 100 or N_m > 300:
#                continue
            min_gsl = 3
            max_gsl = 500
            lendiff_penalty = 133
        elif mname.startswith("C-Clz-pron"):
            min_gsl = 1
            max_gsl = 4
            lendiff_penalty = 40000
        elif mname.startswith("movies2anki"):
#            if N_k > 20 or N_m > 30:
#                continue
            min_gsl = 1
            max_gsl = 4
            lendiff_penalty = 80000
        else:
#            if N_k > 15 or N_m > 45:
#                continue
            min_gsl = C('min good sentence length')
            max_gsl = C('max good sentence length')
            lendiff_penalty = 10000

        lendiff_penalty *= language_penalty

        lenDiffRaw = min(N - min_gsl,
                         max(0, N - max_gsl))
#        lenDiffRaw = min(N - C('min good sentence length'),
#                         max(0, N - C('max good sentence length')))
        lenDiff = min(50, abs(lenDiffRaw))

        len_penalty = lendiff_penalty / 20

        other_penalty = get_other_penalty(itagset, ts, mname, language_prio_malus, N_m)

        depicts_penalty = get_depicts_penalty(itagset)
        if depicts_penalty is None:
            print("depicts penalty is None")

        fiction_penalty = get_fiction_penalty(itagset, is_immediate, is_important, is_urgent)
        if fiction_penalty is None:
            print("fiction penalty is None")

        other_penalty += fiction_penalty

        del fiction_penalty

        # apply penalty for cards that aren't prioritized for learning
        if not (isPriority or isFrequency):
            uselessness_penalty += noPriorityPenalty

        def limit_mmi(mmi):
            if mmi < (max_good_due + 1):
                return mmi
            else:
                lowered_overmuch = max_good_due + isqrt(mmi - max_good_due)
                if lowered_overmuch <= max_editable_due:
                    return lowered_overmuch
                else:
                    return max_editable_due

        standard_penalty = lendiff_penalty * lenDiff + len_penalty * N + uselessness_penalty
        my_penalty = prio_penalty + role_penalty + language_penalty * 10000 + language_prio_malus + depicts_penalty + other_penalty
        del lendiff_penalty, prio_penalty, role_penalty, language_prio_malus, depicts_penalty, other_penalty

        unknown_value = 30000 + 35000 * language_penalty
        if mname.startswith("movies2anki"):
            unknown_value *= 10
        del language_penalty,
        mmi = int(round(unknown_value * (N_k + N_kp) + standard_penalty + my_penalty))
        del standard_penalty, my_penalty

        if C('set due based on mmi'):
                nid2mmi[nid] = limit_mmi(mmi)

        do_update = True
#        if mname == "IR3":
#            max_due_to_update = 800000
#        else:
#            max_due_to_update = 10000000
#            max_due_to_update = 600000
#                db.execute('select ivl, type from cards where nid = :nid', nid=nid)]
        for (cid, due) in db.execute('select id, due from cards where type = 0 and nid = :nid', nid=nid):
            if nid in nid2mmi:  # owise it was disabled
                due_ = nid2mmi[nid]
#                if limit_mmi(due) > max_due_to_update and due_ > max_due_to_update:
#                    do_update = False
        if do_update is False:
            continue

        # Fill in various fields/tags on the note based on cfg
        fs = splitFields(flds)

        # clear any 'special' tags, the appropriate will be set in the next few lines
        ts = [t for t in ts if t not in (
            notReadyTag, compTag, vocabTag, freshTag)]

        # determine card type
        if N_m == 0:  # sentence comprehension card, m+0
            ts.append(compTag)
            if focusMorph:
                setField(mid, fs, field_focus_morph, focusMorph.base)
        elif N_k == 1:  # new vocab card, k+1
            ts.append(vocabTag)
            setField(mid, fs, field_focus_morph, focusMorph.base)
            setField(mid, fs, field_focus_morph_pos, focusMorph.pos)
        elif N_k > 1:  # M+1+ and K+2+
            ts.append(notReadyTag)
            if focusMorph:
                setField(mid, fs, field_focus_morph, focusMorph.base)
        elif unknowns == 1 and N_m == 0:  # 0 unknown words, 1 unknown pair
            ts.append(vocabTag)
            setField(mid, fs, field_focus_morph, focusMorph.base)
            setField(mid, fs, field_focus_morph_pos, focusMorph.pos)
        elif N_kp >= 1:  # 0 unknown words, many unknown pairs
            ts.append(notReadyTag)
            if focusMorph:
                setField(mid, fs, field_focus_morph, focusMorph.base)
        elif N_kp > 0:  # a couple unknown pairs
            if focusMorph:
                setField(mid, fs, field_focus_morph, focusMorph.base)
            pass
        elif N_m == 1:  # we have k+0, and m+1, so this card does not introduce a new vocabulary -> card for newly learned morpheme
            ts.append(freshTag)
            if not focusMorph:
                focusMorph = next(iter(unmatures))
            setField(mid, fs, field_focus_morph, focusMorph.base)
            setField(mid, fs, field_focus_morph_pos, focusMorph.pos)
        else:  # only case left: we have k+0, but m+2 or higher, so this card does not introduce a new vocabulary -> card for newly learned morpheme
            ts.append(freshTag)
            if focusMorph:
                setField(mid, fs, field_focus_morph, focusMorph.base)
                setField(mid, fs, field_focus_morph_pos, focusMorph.pos)
            # XXX: стираем все MorphMan_FocusMorph! Медленно?
#            else:
#                setField(mid, fs, field_focus_morph, '')

        # set type agnostic fields
        setField(mid, fs, field_unknown_count, '%d' % N_k)
        setField(mid, fs, field_unmature_count, '%d' % N_m)
        setField(mid, fs, field_morph_man_index, '%d' % mmi)
        setField(mid, fs, field_unknowns, ', '.join(u.base for u in unknowns))
        setField(mid, fs, field_unmatures,
                 ', '.join(u.base for u in unmatures))
        setField(mid, fs, field_unknown_freq, '%d' % F_k_avg)

        # remove deprecated tag
        if badLengthTag is not None and badLengthTag in ts:
            ts.remove(badLengthTag)

        # other tags
        if priorityTag in ts:
            ts.remove(priorityTag)
        if isPriority:
            ts.append(priorityTag)

        if frequencyTag in ts:
            ts.remove(frequencyTag)
        if isFrequency:
            ts.append(frequencyTag)

        if tooShortTag in ts:
            ts.remove(tooShortTag)
        if lenDiffRaw < 0:
            ts.append(tooShortTag)

        if tooLongTag in ts:
            ts.remove(tooLongTag)
        if lenDiffRaw > 0:
            ts.append(tooLongTag)

        # remove unnecessary tags
        if not cfg('Option_SetNotRequiredTags'):
            unnecessary = [priorityTag, tooShortTag, tooLongTag]
            ts = [tag for tag in ts if tag not in unnecessary]

        # update sql db
        tags_ = TAG.join(TAG.canonify(ts))
        flds_ = joinFields(fs)
        if flds != flds_ or tags != tags_ or update_even_unchanged:  # only update notes that have changed
            csum = fieldChecksum(fs[0])
            sfld = stripHTML(fs[getSortFieldIndex(mid)])
            ds.append(
                {'now': now, 'tags': tags_, 'flds': flds_, 'sfld': sfld, 'csum': csum, 'usn': mw.col.usn(), 'nid': nid})

    mw.progress.update(label='Updating anki database...')
    mw.col.db.executemany(
        'update notes set tags=:tags, flds=:flds, sfld=:sfld, csum=:csum, mod=:now, usn=:usn where id=:nid', ds)

    # Now reorder new cards based on MMI
    mw.progress.update(label='Updating new card ordering...')
    ds = []

    # "type = 0": new cards
    # "type = 1": learning cards [is supposed to be learning: in my case no learning card had this type]
    # "type = 2": review cards
    for (cid, nid, due) in db.execute('select id, nid, due from cards where type = 0', nid=nid):
#    for (cid, nid, due) in db.execute('select id, nid, due from cards where type = 0'):
        if nid in nid2mmi:  # owise it was disabled
            due_ = nid2mmi[nid]
            if due != due_:  # only update cards that have changed
                ds.append({'now': now, 'due': due_,
                           'usn': mw.col.usn(), 'cid': cid})

    mw.col.db.executemany(
        'update cards set due=:due, mod=:now, usn=:usn where id=:cid', ds)
    mw.reset()

    printf('Updated notes in %f sec' % (time.time() - t_0))
    mw.progress.finish()
    return knownDb


def main():
    # load existing all.db
    mw.progress.start(label='Loading existing all.db', immediate=True)
    t_0 = time.time()
    cur = util.allDb(reload=True) if cfg('loadAllDb') else None
    printf('Loaded all.db in %f sec' % (time.time() - t_0))
    mw.progress.finish()

    # update all.db
    allDb = mkAllDb(cur)
    # there was an (non-critical-/non-"exception"-)error but error message was already displayed
    if not allDb:
        mw.progress.finish()
        return

    # merge in external.db
    mw.progress.start(label='Merging ext.db', immediate=True)
    ext = MorphDb(cfg('path_ext'), ignoreErrors=True)
    allDb.merge(ext)
    mw.progress.finish()

    # update notes
    knownDb = updateNotes(allDb)

    # update stats and refresh display
    stats.updateStats(knownDb)
    mw.toolbar.draw()

    # set global allDb
    util._allDb = allDb
