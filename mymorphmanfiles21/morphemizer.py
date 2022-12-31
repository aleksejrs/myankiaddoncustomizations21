#!/usr/bin/python3
import re

from typing import Dict, Iterator, List, Optional, Set

from .morphemes import Morpheme
from .deps.zhon.hanzi import characters
from .mecab_wrapper import getMorphemesMecab
from .deps.jieba import posseg

#from .aleksej_morphemizer_code import getMorphemesFromExpr_Aleksej_general
#from .aleksej_morphemizer_data import *

from .aleksej_morphemizer_data import BAD_BASE_FORMS_EVEN_FOR_PAIRS_DE, \
                                      BAD_BASE_FORMS_CASE_INSENS_DE, BAD_BASE_FORMS_CASE_SENS_DE
from .aleksej_morphemizer_data import ENDING_DICT_DE, ENDING_DICT_CUR_SET_DE, \
                                      FULLWORD_DICT_DE, TRANSLATION_TABLE_DE

from .aleksej_morphemizer_data import BAD_BASE_FORMS_EVEN_FOR_PAIRS_EN, \
                                      BAD_BASE_FORMS_CASE_INSENS_EN, BAD_BASE_FORMS_CASE_SENS_EN
from .aleksej_morphemizer_data import ENDING_DICT_EN, ENDING_DICT_CUR_SET_EN, \
                                      FULLWORD_DICT_EN, TRANSLATION_TABLE_EN

from .aleksej_morphemizer_data import BAD_BASE_FORMS_EVEN_FOR_PAIRS_EO, \
                                      BAD_BASE_FORMS_CASE_INSENS_EO, BAD_BASE_FORMS_CASE_SENS_EO
from .aleksej_morphemizer_data import ENDING_DICT_EO, ENDING_DICT_CUR_SET_EO, \
                                      FULLWORD_DICT_EO, TRANSLATION_TABLE_EO

from .aleksej_morphemizer_data import BAD_BASE_FORMS_EVEN_FOR_PAIRS_ES, BAD_BASE_FORMS_CASE_INSENS_ES, BAD_BASE_FORMS_CASE_SENS_ES
from .aleksej_morphemizer_data import ENDING_DICT_ES, ENDING_DICT_CUR_SET_ES, FULLWORD_DICT_ES, TRANSLATION_TABLE_ES

from .aleksej_morphemizer_data import BAD_BASE_FORMS_EVEN_FOR_PAIRS_RU, BAD_BASE_FORMS_CASE_INSENS_RU, BAD_BASE_FORMS_CASE_SENS_RU
from .aleksej_morphemizer_data import ENDING_DICT_RU, ENDING_DICT_CUR_SET_RU, FULLWORD_DICT_RU, TRANSLATION_TABLE_RU

from .aleksej_morphemizer_data import BAD_BASE_FORMS_EVEN_FOR_PAIRS_TOTAL, BAD_BASE_FORMS_CASE_INSENS_TOTAL, BAD_BASE_FORMS_CASE_SENS_TOTAL
from .aleksej_morphemizer_data import ENDING_DICT_TOTAL, ENDING_DICT_CUR_SET_TOTAL, FULLWORD_DICT_TOTAL, TRANSLATION_TABLE_TOTAL

from .aleksej_morphemizer_data import CLOZE_MARKS, PAIRS_WORDSEPARATOR
from .aleksej_morphemizer_extra import morphemizer_extra_processing

PRIMARY_PUNCTUATION_REGEXP=r"\b[^\s{}«»\"]+"
SECONDARY_PUNCTUATION_STRING = ".,;:!?()+-*×/—− "

####################################################################################################
# Base Class
####################################################################################################

class Morphemizer:
    def getMorphemesFromExpr(self, expression):
        # type: (str) -> List[Morpheme]
        """
        The heart of this plugin: convert an expression to a list of its morphemes.
        """
        return []

    def getDescription(self):
        # type: () -> str
        """
        Returns a single line, for which languages this Morphemizer is.
        """
        return 'No information available'

    def getName(self):
        # type: () -> str
        return self.__class__.__name__


####################################################################################################
# Morphemizer Helpers
####################################################################################################

def getAllMorphemizers():
    # type: () -> List[Morphemizer]
    AleksejMorphemizers: List[Morphemizer] = [
        SpaceMorphemizerAleksej(),
        SpaceMorphemizerAleksejDe(),
        SpaceMorphemizerAleksejEn(),
        SpaceMorphemizerAleksejEo(),
        SpaceMorphemizerAleksejEs(),
        SpaceMorphemizerAleksejRu(),
        ]
    return [SpaceMorphemizer(), MecabMorphemizer(), JiebaMorphemizer(), CjkCharMorphemizer()] + AleksejMorphemizers


def getMorphemizerByName(name):
    # type: (str) -> Optional[Morphemizer]
    for m in getAllMorphemizers():
        if m.getName() == name:
            return m
    return None


####################################################################################################
# Mecab Morphemizer
####################################################################################################

space_char_regex = re.compile(' ')

class MecabMorphemizer(Morphemizer):
    """
    Because in japanese there are no spaces to differentiate between morphemes,
    a extra tool called 'mecab' has to be used.
    """

    def getMorphemesFromExpr(self, expression):
        # Remove simple spaces that could be added by other add-ons and break the parsing.
        if space_char_regex.search(expression):
            expression = space_char_regex.sub('', expression)

        return getMorphemesMecab(expression)

    def getDescription(self):
        return 'Japanese'


####################################################################################################
# Space Morphemizer
####################################################################################################


class SpaceMorphemizer(Morphemizer):
    """
    Morphemizer for languages that use spaces (English, German, Spanish, ...). Because it is
    a general-use-morphemizer, it can't generate the base form from inflection.
    """

    def getMorphemesFromExpr(self, e):
        str_lower = str.lower
        word_list = [
            str_lower(word) for word in re.findall(r"\b[^\s\d()]+\b", e, re.UNICODE)
            ]
        return [Morpheme(word, word, word, word, 'UNKNOWN', 'UNKNOWN') for word in word_list]

    def getDescription(self):
        return 'Language w/ Spaces'

####################################################################################################
# Space Morphemizer, modified by Aleksej
####################################################################################################




class SpaceMorphemizerAleksej_parent(Morphemizer):
    """
    Morphemizer for languages that use spaces (English, German, Spanish, ...).
    Modified by Aleksej to extract word pairs and replace some words to
    their base forms.
    """

    def getMorphemesFromExpr(self, e: str) -> List[Morpheme]:

#        fullword_dict: Dict[str, str] = self.get_fullword_dict()
#        print(f"getMorphemesFromExpr: e: {e}")
#        print(f"getMorphemesFromExpr: self.fullword_dict: {self.fullword_dict}")
#        ending_dict_cur_set: Set[str] = self.get_ending_dict_cur_set()
#        ending_dict: Dict[str, str] = self.get_ending_dict()
        BAD_BASE_FORMS_EVEN_FOR_PAIRS: Set[str] = self.get_bad_base_forms_even_for_pairs()
        BAD_BASE_FORMS_CASE_INSENS: Set[str] = self.get_bad_base_forms_case_insensitive()
        BAD_BASE_FORMS_CASE_SENS: Set[str] = self.get_bad_base_forms_case_sensitive()
        TRANSLATION_TABLE: Dict[str, str] = self.get_translation_table()

        e = e.lower()
        translation_string = str.maketrans("ſ:{}", "s   ")
        e = e.translate(translation_string)
        # remove cloze syntax. Does not work (c1 etc are kept)?!
        # even the :: are kept?!
        for i in range(0,5):
            if '{' not in e:
                break
            e = re.sub("\{\{c\\d+::(?P<hidden>.*)::(?P<hint>.*)\}\}(?P<therest>.*)", " \\g<hint> \\g<therest> \\g<hidden>", string=e)
#        e = re.sub("{{c\d+::(?P<hidden>.*)::(?P<hint>.*)}}", "\g<hidden> \g<hint>", string=e)
        e = re.sub("\{\{c\\d+::(?P<hidden>.*)\}\}", "\\g<hidden>", string=e)
        e = re.sub("::", " ", string=e)
        e = re.sub("(?P<month>jan(uary)?|feb(ruary)?|mar(ch)?|june?|july?|aug(ust)?|sep(t(ember)?)?|oct(ober?)|nov(ember)?|dec(ember)?)\\.? (?P<date>\\d{1,2})(st|nd|rd|th)?, (?P<year>\\d{4})",
                   "\\g<date> \\g<month> \\g<year>)", string=e)
        e = re.sub("(?P<prechar>([^d]|^))(?P<year>1\\d\\d\\d)-01-(?P<date>)", "\\g<prechar>\\g<date> january \\g<year>", string=e)
        e = re.sub("(?P<prechar>([^d]|^))(?P<year>1\\d\\d\\d)-02-(?P<date>)", "\\g<prechar>\\g<date> february \\g<year>", string=e)
        e = re.sub("(?P<prechar>([^d]|^))(?P<year>1\\d\\d\\d)-03-(?P<date>)", "\\g<prechar>\\g<date> march \\g<year>", string=e)
        e = re.sub("(?P<prechar>([^d]|^))(?P<year>1\\d\\d\\d)-04-(?P<date>)", "\\g<prechar>\\g<date> april \\g<year>", string=e)
        e = re.sub("(?P<prechar>([^d]|^))(?P<year>1\\d\\d\\d)-05-(?P<date>)", "\\g<prechar>\\g<date> may \\g<year>", string=e)
        e = re.sub("(?P<prechar>([^d]|^))(?P<year>1\\d\\d\\d)-06-(?P<date>)", "\\g<prechar>\\g<date> june \\g<year>", string=e)
        e = re.sub("(?P<prechar>([^d]|^))(?P<year>1\\d\\d\\d)-07-(?P<date>)", "\\g<prechar>\\g<date> july \\g<year>", string=e)
        e = re.sub("(?P<prechar>([^d]|^))(?P<year>1\\d\\d\\d)-08-(?P<date>)", "\\g<prechar>\\g<date> august \\g<year>", string=e)
        e = re.sub("(?P<prechar>([^d]|^))(?P<year>1\\d\\d\\d)-09-(?P<date>)", "\\g<prechar>\\g<date> september \\g<year>", string=e)
        e = re.sub("(?P<prechar>([^d]|^))(?P<year>1\\d\\d\\d)-10-(?P<date>)", "\\g<prechar>\\g<date> october \\g<year>", string=e)
        e = re.sub("(?P<prechar>([^d]|^))(?P<year>1\\d\\d\\d)-11-(?P<date>)", "\\g<prechar>\\g<date> november \\g<year>", string=e)
        e = re.sub("(?P<prechar>([^d]|^))(?P<year>1\\d\\d\\d)-12-(?P<date>)", "\\g<prechar>\\g<date> december \\g<year>", string=e)
        # remove character names from the beginning
        e = morphemizer_extra_processing(e)
#        e = e.replace(" of the ", " of_englisharticle_")
#        e = e.replace(" of a ", " of_englisharticle_")
#        e = e.replace(" of an ", " of_englisharticle_")
#        e = e.replace(" on the ", " of_englisharticle_")
#        e = e.replace(" on a ", " of_englisharticle_")
#        e = e.replace(" on an ", " of_englisharticle_")
#        e = e.replace(" with the ", " of_englisharticle_")
#        e = e.replace(" with a ", " of_englisharticle_")
#        e = e.replace(" with an ", " of_englisharticle_")
        e = e.replace(" of the ", "_of the_")
        e = e.replace(" of a ",   "_of a_")
        e = e.replace(" of an ",  "_of an_")
        e = e.replace(" on the ", "_on the_")
        e = e.replace(" on a ",   "_on a_")
        e = e.replace(" on an ",  "_on an_")
        e = re.sub("\\bin the ", "in_the_", string=e)
        e = re.sub("\\bin the ", "in_the_", string=e)
        e = re.sub("\\bin a ",   "in_a_", string=e)
        e = re.sub("\\bin an ",  "in_an_", string=e)
        e = re.sub("\\bat the ", "at_the_", string=e)
        e = re.sub("\\bat a ",   "at_a_", string=e)
        e = re.sub("\\bat an ",  "at_an_", string=e)
        e = e.replace(" with the ", "_with the_")
        e = e.replace(" with a ",   "_with a_")
        e = e.replace(" with an ",  "_with an_")
        e = e.replace(" off the ", "_off the_")
        e = e.replace(" off a ",   "_off a_")
        e = e.replace(" off an ",  "_off an_")
        e = re.sub("\\bto the ", "to_the_", string=e)
        e = re.sub("\\bto a ",   "to_a_", string=e)
        e = re.sub("\\bto an ",  "to_an_", string=e)
        e = e.replace(" from the ", "_from the_")
        e = e.replace(" from a ",   "_from a_")
        e = e.replace(" from an ",  "_from an_")
        e = re.sub("\\bthe ", "the_", string=e)
        e = re.sub("\\ba ",   "a_", string=e)
        e = re.sub("\\ban ",  "an_", string=e)
        e = re.sub("\\byou can\\b", "you_can", string=e)
        e = re.sub("\\bi have\\b",  "i_have", string=e)
        e = re.sub("\\bbe ",        "be_", string=e)
        e = re.sub("\\byou all\\b",        "you_all", string=e)
#        e = e.replace(" you all ",   " you_all ")
#        e = e.replace(" on the ", " of_englisharticle_")
#        e = e.replace(" on a ", " of_englisharticle_")
#        e = e.replace(" on an ", " of_englisharticle_")
#        e = e.replace(" with the ", " of_englisharticle_")
#        e = e.replace(" with a ", " of_englisharticle_")
#        e = e.replace(" with an ", " of_englisharticle_")
#        e = e.replace(" the ", " englisharticle_")
#        e = e.replace(" of the ", " of_the ")
#        e = e.replace(" of an ",  " of_an ")
#        e = e.replace(" of a ",   " of_a ")
#        e = e.replace(" on the ", " on_the ")
#        e = e.replace(" on an ",  " on_an ")
#        e = e.replace(" on a ",   " on_a ")
#        e = e.replace(" with the ", " with_the ")
#        e = e.replace(" with a ",   " with_a ")
#        e = e.replace(" in the ", " in_the ")
#        e = e.replace(" in an ",  " in_an ")
#        e = e.replace(" in a ",   " in_a ")
#        e = e.replace(" at the ", " at_the ")
#        e = e.replace(" at an ",  " at_an ")
#        e = e.replace(" at a ",   " at_a ")

        def split_expr_and_correct_case(expr):
            # type: (str) -> List[str]


            # \n\r in the character class doesn't work.
            word_list_firstsplit: List[str] = re.findall(PRIMARY_PUNCTUATION_REGEXP, expr, re.UNICODE)
#            word_list_firstsplit = [
#                # Not word.lower(), because capitalization is grammar in German.
#                # Lowercasing the rest of the word though.
#    # XXX: temporarily actually lower() for perfomance reasons
#                word_firstsplit
#                # Digits are allowed to let dates and math in. Obvious
#                # punctuation and cloze deletion is not.
#                for word_firstsplit in re.findall(r"\b[^\s,;()/]+\b", e, re.UNICODE)
#            ]

    #            if None in word_list_firstsplit:
    #                raise TypeError(f"word_list_firstsplit contains Nones: {word_list_firstsplit}")
#        def correct_case_of_list(word_list):
#            # type: [str] -> [str]
#            str_lower = str.lower
#            return (str_lower(word) for word in word_list)

#            word_list_no_cloze_dcolons: List[str] = []
#            str_startswith = str.startswith
#            str_find = str.find
#            str_split = str.split
#            list_append = list.append
#            for word_firstsplit in word_list_firstsplit:
#                word_no_start_dcolon: str = word_firstsplit
#                while str_startswith(word_firstsplit, "::"):
#                    word_no_start_dcolon = word_no_start_dcolon[2:]
#                if str_find(word_no_start_dcolon, "::") != -1:
#                    word_no_cloze_dcolon, nextword_no_cloze_dcolon = str_split(word_no_start_dcolon, "::", 1)
#                    list_append(word_list_no_cloze_dcolons, word_no_cloze_dcolon)
#                    list_append(word_list_no_cloze_dcolons, nextword_no_cloze_dcolon)
#                else:
#                    list_append(word_list_no_cloze_dcolons, word_no_start_dcolon)
    #                if word_no_start_dcolon:
    #                    del word_no_start_dcolon
    #            del word_list_firstsplit

    #            if None in word_list_no_cloze_dcolons:
    #                raise TypeError(f"There are Nones in word_list_no_cloze_dcolons: {word_list_no_cloze_dcolons}")

            return word_list_firstsplit


    # XXX: probably TOO slow:
    #        def correct_case_of_word(word):
    #            if len(word) == 1:
    #                word_correct_case = word.lower()
    #            else:
    #                first_letter, lowercase_nonfirst_letters = word[0], word[1:].lower()
    #                for cyrillic_letter in cyrillic_letters:
    #                    if cyrillic_letter in lowercase_nonfirst_letters:
    #                        first_letter = first_letter.lower()
    #                        break
    #                word_correct_case = (
    #                    first_letter + lowercase_nonfirst_letters
    #                )
    #            return word_correct_case

        def get_pair_morphemes(words):
            # type: (List[str]) -> List[Morpheme]
            """Take a list of words and return a list of pairs as morphs."""

#            pair_string_list = map(pair_join, zip(words[:-1], words[1:]))
#            pair_list_original = zip(words[:-1], words[1:])
#            pair_string_list = map(pair_join, pair_list_original)
#            pair_string_list = map(PAIRS_WORDSEPARATOR.join, pair_list_original)
#            pair_string_list = [
#                PAIRS_WORDSEPARATOR.join(pair) for pair in pair_list_original
#            ]
            firstwords = words[:-1]
            secondwords = words[1:]
            secondwords_without_trailing_punctuation = [word.rstrip(SECONDARY_PUNCTUATION_STRING) for word in secondwords]
            pair_tuples = zip(firstwords, secondwords_without_trailing_punctuation)
            pairs = map(PAIRS_WORDSEPARATOR.join, pair_tuples)
            return [ Morpheme(pair, pair, pair, pair, "PAIR", "UNKNOWN") for pair in pairs ]

        def get_base_form(word: str) -> str:

#            s = self.stemmer_en.stemWord(word)
#            if s != word:
#                return s
#            s = self.stemmer_ru.stemWord(word)
#            if s != word:
#                return s
#            s = self.stemmer_de.stemWord(word)
#            if s != word:
#                return s
#            s = self.stemmer_es.stemWord(word)
#            if s != word:
#                return s

            try:
                return self.fullword_dict[word]
            except KeyError:
                str_endswith = str.endswith
                if word.endswith(tuple(self.ending_dict)):
                    # twice as fast as just the loop below
                    for cur_ending in self.ending_dict_cur_set:
                        if str_endswith(word, cur_ending):
                            return ''.join([word[: -len(cur_ending)], self.ending_dict[cur_ending]])
                else:
                    return word
            return word

        def remove_bad_base_forms(words: List[str]) -> List[str]:
            words_no_bad_base_forms: List[str] = [
                word
                for word in words
                if (
                    word not in BAD_BASE_FORMS_CASE_SENS
# XXX: note the removal of word.lower() for speed!
                    and word not in BAD_BASE_FORMS_CASE_INSENS
#                    and word.lower() not in BAD_BASE_FORMS_CASE_INSENS
                )
            ]
            return words_no_bad_base_forms

        def translate(word: str):
            """Replace the word with its English equivalent (if available)."""
            try:
                return TRANSLATION_TABLE[word]
            except KeyError:
                return word

        word_list_in_correct_case: List[str] = split_expr_and_correct_case(e)
        del e
#        word_list_after_splitting = split_expr(e)
#        word_list_in_correct_case = correct_case_of_list(word_list_after_splitting)
#        word_list_in_correct_case = word_list_after_splitting
    #        del word_list_after_splitting
    #        if None in word_list_after_splitting:
    #            raise TypeError(f"word_list_after_splitting contains Nones: {word_list_after_splitting}")
        str_startswith = str.startswith

        word_list_no_bad_originals: List[str] = [
            word
            for word in word_list_in_correct_case
            if not str_startswith(word, ("http://", "https://"))
        ]
        word_list_no_bad_originals: List[str] = [
            word for word in word_list_no_bad_originals if not word in CLOZE_MARKS
            ]


        base_forms: Iterator[str] = map(get_base_form, word_list_no_bad_originals)
        del word_list_no_bad_originals

        # Remove base forms that are unacceptable even for pairs
        base_forms_no_very_bad_base_forms: List[str] = [
            base_form
            for base_form in base_forms
            if base_form not in BAD_BASE_FORMS_EVEN_FOR_PAIRS
        ]
        del base_forms


        translated_base_forms: List[str] = list(map(translate, base_forms_no_very_bad_base_forms))
        pair_morphemes: List[Morpheme] = get_pair_morphemes(translated_base_forms)

        translated_base_forms = [word.strip(SECONDARY_PUNCTUATION_STRING) for word in translated_base_forms]

        base_forms_without_bad_base_forms: List[str] = remove_bad_base_forms(translated_base_forms)
        del BAD_BASE_FORMS_CASE_SENS
        del BAD_BASE_FORMS_CASE_INSENS
        del BAD_BASE_FORMS_EVEN_FOR_PAIRS
        del TRANSLATION_TABLE
        del translated_base_forms

        word_morphemes: List[Morpheme] = [
            Morpheme(word, word, word, word, "UNKNOWN", "UNKNOWN")
            for word in base_forms_without_bad_base_forms]
        del base_forms_without_bad_base_forms

        result = word_morphemes + pair_morphemes
        del word_morphemes, pair_morphemes
        return result

    def getDescription(self):
        return "Language w/ Spaces, modified by Aleksej"

class SpaceMorphemizerAleksej(SpaceMorphemizerAleksej_parent):

#    def get_fullword_dict(self):
    def __init__(self):

#        print("total")
        SpaceMorphemizerAleksej.fullword_dict = FULLWORD_DICT_TOTAL
        SpaceMorphemizerAleksej.ending_dict = ENDING_DICT_TOTAL
        SpaceMorphemizerAleksej.ending_dict_cur_set = ENDING_DICT_CUR_SET_TOTAL
#
#        from .deps.snowballstemmer import stemmer
#        SpaceMorphemizerAleksej.stemmer_en = stemmer('english')
#        SpaceMorphemizerAleksej.stemmer_ru = stemmer('russian')
#        SpaceMorphemizerAleksej.stemmer_de = stemmer('german')
#        SpaceMorphemizerAleksej.stemmer_es = stemmer('spanish')
#self.fullword_dict = FULLWORD_DICT_TOTAL
#        return FULLWORD_DICT_TOTAL

    def get_ending_dict(self):
        return ENDING_DICT_TOTAL

    def get_ending_dict_cur_set(self):
        #XXX: probably actually a list
        return ENDING_DICT_CUR_SET_TOTAL

    def get_bad_base_forms_even_for_pairs(self):
        return BAD_BASE_FORMS_EVEN_FOR_PAIRS_TOTAL

    def get_bad_base_forms_case_insensitive(self):
        return BAD_BASE_FORMS_CASE_INSENS_TOTAL

    def get_bad_base_forms_case_sensitive(self):
        return BAD_BASE_FORMS_CASE_SENS_TOTAL

    def get_translation_table(self):
        return TRANSLATION_TABLE_TOTAL


#    def correct_case_of_list(self, word_list_after_splitting):
#        return [word.lower() for word in word_list_after_splitting]

    def getDescription(self):
        return "Language w/ Spaces, modified by Aleksej, total"

class SpaceMorphemizerAleksejEn(SpaceMorphemizerAleksej_parent):
    def __init__(self):
#        print("en")
        SpaceMorphemizerAleksejEn.fullword_dict = FULLWORD_DICT_EN
        SpaceMorphemizerAleksejEn.ending_dict = ENDING_DICT_EN
        SpaceMorphemizerAleksejEn.ending_dict_cur_set = ENDING_DICT_CUR_SET_EN
#        self.fullword_dict = FULLWORD_DICT_EN
#        ending_dict = ENDING_DICT_EN
#        ending_dict_cur_set = ENDING_DICT_EN_CUR_SET

    def get_fullword_dict(self):
        self.fullword_dict = FULLWORD_DICT_EN
#        return FULLWORD_DICT_EN

    def get_ending_dict(self):
        return ENDING_DICT_EN

    def get_ending_dict_cur_set(self):
        return ENDING_DICT_CUR_SET_EN

    def get_bad_base_forms_even_for_pairs(self):
        return BAD_BASE_FORMS_EVEN_FOR_PAIRS_EN

    def get_bad_base_forms_case_insensitive(self):
        return BAD_BASE_FORMS_CASE_INSENS_EN

    def get_bad_base_forms_case_sensitive(self):
        return BAD_BASE_FORMS_CASE_SENS_EN

#    def correct_case_of_list(self, word_list_after_splitting):
#        return [word.lower() for word in word_list_after_splitting]

    def get_translation_table(self):
        return TRANSLATION_TABLE_EN


    def getDescription(self) -> str:
        return "Language w/ Spaces, modified by Aleksej, English"

class SpaceMorphemizerAleksejDe(SpaceMorphemizerAleksej_parent):
    def __init__(self):
#        print("de")
        SpaceMorphemizerAleksejDe.fullword_dict = FULLWORD_DICT_DE
        SpaceMorphemizerAleksejDe.ending_dict = ENDING_DICT_DE
        SpaceMorphemizerAleksejDe.ending_dict_cur_set = ENDING_DICT_CUR_SET_DE
#        self.fullword_dict = FULLWORD_DICT_DE
#        ending_dict = ENDING_DICT_DE
#        ending_dict_cur_set = ENDING_DICT_DE_CUR_SET

    def get_fullword_dict(self):
        self.fullword_dict = FULLWORD_DICT_DE
#        return FULLWORD_DICT_DE

    def get_ending_dict(self):
        return ENDING_DICT_DE

    def get_ending_dict_cur_set(self):
        return ENDING_DICT_CUR_SET_DE

    def get_bad_base_forms_even_for_pairs(self):
        return BAD_BASE_FORMS_EVEN_FOR_PAIRS_DE

    def get_bad_base_forms_case_insensitive(self):
        return BAD_BASE_FORMS_CASE_INSENS_DE
    
    def get_bad_base_forms_case_sensitive(self):
        return BAD_BASE_FORMS_CASE_SENS_DE

    def correct_case_of_list(self, word_list_after_splitting):
        return word_list_after_splitting

    def get_translation_table(self):
        return TRANSLATION_TABLE_DE

    def getDescription(self):
        return "Language w/ Spaces, modified by Aleksej, German"

class SpaceMorphemizerAleksejRu(SpaceMorphemizerAleksej_parent):
    def __init__(self):
#        print("ru")
        SpaceMorphemizerAleksejRu.fullword_dict = FULLWORD_DICT_RU
        SpaceMorphemizerAleksejRu.ending_dict = ENDING_DICT_RU
        SpaceMorphemizerAleksejRu.ending_dict_cur_set = ENDING_DICT_CUR_SET_RU
#       self.fullword_dict = FULLWORD_DICT_RU
#        ending_dict = ENDING_DICT_RU
#        ending_dict_cur_set = ENDING_DICT_RU_CUR_SET

    def get_fullword_dict(self):
        self.fullword_dict = FULLWORD_DICT_RU
        return FULLWORD_DICT_RU

    def get_ending_dict(self):
        return ENDING_DICT_RU

    def get_ending_dict_cur_set(self):
        return ENDING_DICT_CUR_SET_RU

    def get_bad_base_forms_even_for_pairs(self):
        return BAD_BASE_FORMS_EVEN_FOR_PAIRS_RU

    def get_bad_base_forms_case_insensitive(self):
        return BAD_BASE_FORMS_CASE_INSENS_RU

    def get_bad_base_forms_case_sensitive(self):
        return BAD_BASE_FORMS_CASE_SENS_RU

    def get_translation_table(self):
        return TRANSLATION_TABLE_RU


#    def correct_case_of_list(self, word_list_after_splitting):
#        return [word.lower() for word in word_list_after_splitting]

    def getDescription(self):
        return "Language w/ Spaces, modified by Aleksej, Russian"

class SpaceMorphemizerAleksejEs(SpaceMorphemizerAleksej_parent):
    def __init__(self):
#        print("es")
        self.fullword_dict = FULLWORD_DICT_ES
        SpaceMorphemizerAleksejEs.ending_dict = ENDING_DICT_ES
        SpaceMorphemizerAleksejEs.ending_dict = ENDING_DICT_ES
        SpaceMorphemizerAleksejEs.ending_dict_cur_set = ENDING_DICT_CUR_SET_ES
#        ending_dict = ENDING_DICT_EN
#        ending_dict_cur_set = ENDING_DICT_EN_CUR_SET

    def get_fullword_dict(self):
        return FULLWORD_DICT_ES

    def get_ending_dict(self):
        return ENDING_DICT_ES

    def get_ending_dict_cur_set(self):
        return ENDING_DICT_CUR_SET_ES

    def get_bad_base_forms_even_for_pairs(self):
        return BAD_BASE_FORMS_EVEN_FOR_PAIRS_ES

    def get_bad_base_forms_case_insensitive(self):
        return BAD_BASE_FORMS_CASE_INSENS_ES

    def get_bad_base_forms_case_sensitive(self):
        return BAD_BASE_FORMS_CASE_SENS_ES

    def get_translation_table(self):
        return TRANSLATION_TABLE_ES

#    def correct_case_of_list(self, word_list_after_splitting):
#        return [word.lower() for word in word_list_after_splitting]

    def getDescription(self) -> str:
        return "Language w/ Spaces, modified by Aleksej, Spanish"

class SpaceMorphemizerAleksejEo(SpaceMorphemizerAleksej_parent):
    def __init__(self):
#        print("eo")
        self.fullword_dict = FULLWORD_DICT_EO
#        ending_dict = ENDING_DICT_EO
#        ending_dict_cur_set = ENDING_DICT_EO_CUR_SET

    def get_fullword_dict(self):
        return FULLWORD_DICT_EO

    def get_ending_dict(self):
        return ENDING_DICT_EO

    def get_ending_dict_cur_set(self):
        return ENDING_DICT_CUR_SET_EO

    def get_bad_base_forms_even_for_pairs(self):
        return BAD_BASE_FORMS_EVEN_FOR_PAIRS_EO

    def get_bad_base_forms_case_insensitive(self):
        return BAD_BASE_FORMS_CASE_INSENS_EO

    def get_bad_base_forms_case_sensitive(self):
        return BAD_BASE_FORMS_CASE_SENS_EO

#    def correct_case_of_list(self, word_list_after_splitting):
#        return [word.lower() for word in word_list_after_splitting]

    def get_translation_table(self):
        return TRANSLATION_TABLE_EO

    def getDescription(self) -> str:
        return "Language w/ Spaces, modified by Aleksej, Esperanto"

####################################################################################################
# CJK Character Morphemizer
####################################################################################################

class CjkCharMorphemizer(Morphemizer):
    """
    Morphemizer that splits sentence into characters and filters for Chinese-Japanese-Korean logographic/idiographic
    characters.
    """

    def getMorphemesFromExpr(self, e):
        return [Morpheme(character, character, character, character, 'CJK_CHAR', 'UNKNOWN') for character in
                re.findall('[%s]' % characters, e)]

    def getDescription(self):
        return 'CJK Characters'


####################################################################################################
# Jieba Morphemizer (Chinese)
####################################################################################################

class JiebaMorphemizer(Morphemizer):
    """
    Jieba Chinese text segmentation: built to be the best Python Chinese word segmentation module.
    https://github.com/fxsjy/jieba
    """

    def getMorphemesFromExpr(self, e):
        # remove all punctuation
        e = u''.join(re.findall('[%s]' % characters, e))
        return [Morpheme(m.word, m.word, m.word, m.word, m.flag, u'UNKNOWN') for m in
                posseg.cut(e)]  # find morphemes using jieba's POS segmenter

    def getDescription(self):
        return 'Chinese'
