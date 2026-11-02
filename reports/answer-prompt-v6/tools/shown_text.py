"""One pure R0–R5 display function; move byte for byte on adoption."""


def shown_text(raw, question, *, finished=True, details=False):
    """Reconstruct releases in unit order, independent of chunk boundaries.

    unfinished calls hold an open unit, including ambiguous final ASCII punctuation.
    details adds only policy state/offsets; the ordinary result stays text and flags.
    Offsets are Python character offsets in raw (cut_at is in the answer part).
    """
    import unicodedata
    from collections import Counter

    import regex

    def citation_free(value):
        return regex.sub(r"\[\s*\d+(?:\s*[,;–-]\s*\d+)*\s*\]", lambda m: " " * len(m[0]), value)

    def words(value):
        return list(regex.finditer(r"\p{L}[\p{L}\p{M}\p{N}]*|\p{N}+", value))

    def normal(value):
        return unicodedata.normalize("NFKC", value).casefold()

    # ISO/Unicode script property identifiers, not a vocabulary. Newer identifiers
    # unsupported by an older regex database are ignored; such letters abstain.
    scripts = """LATIN BOPOMOFO GREEK COPTIC CYRILLIC ARMENIAN HEBREW ARABIC SYRIAC
    THAANA NKO SAMARITAN MANDAIC DEVANAGARI BENGALI GURMUKHI GUJARATI ORIYA TAMIL
    TELUGU KANNADA MALAYALAM SINHALA THAI LAO TIBETAN MYANMAR GEORGIAN HANGUL ETHIOPIC
    CHEROKEE CANADIANABORIGINAL OGHAM RUNIC TAGALOG HANUNOO BUHID TAGBANWA KHMER
    MONGOLIAN LIMBU TAILE NEWTAILUE BUGINESE TAITHAM BALINESE SUNDANESE BATAK LEPCHA
    OLCHIKI BRAILLE GLAGOLITIC TIFINAGH HAN HIRAGANA KATAKANA YI LISU VAI BAMUM
    SYLOTINAGRI PHAGSPA SAURASHTRA KAYAHLI REJANG JAVANESE CHAM TAIVIET MEETEIMAYEK
    LINEARB LYCIAN CARIAN OLDITALIC GOTHIC OLDPERMIC UGARITIC OLDPERSIAN DESERET
    SHAVIAN OSMANYA OSAGE ELBASAN CAUCASIANALBANIAN VITHKUQI TODHRI LINEARA CYPRIOT
    IMPERIALARAMAIC PALMYRENE NABATAEAN HATRAN PHOENICIAN LYDIAN SIDETIC
    MEROITICHIEROGLYPHS MEROITICCURSIVE KHAROSHTHI OLDSOUTHARABIAN OLDNORTHARABIAN
    MANICHAEAN AVESTAN INSCRIPTIONALPARTHIAN INSCRIPTIONALPAHLAVI PSALTERPAHLAVI
    OLDTURKIC OLDHUNGARIAN HANIFIROHINGYA GARAY YEZIDI OLDSOGDIAN SOGDIAN OLDUYGHUR
    CHORASMIAN ELYMAIC BRAHMI KAITHI SORASOMPENG CHAKMA MAHAJANI SHARADA KHOJKI
    MULTANI KHUDAWADI GRANTHA TULUTIGALARI NEWA TIRHUTA SIDDHAM MODI TAKRI AHOM DOGRA
    WARANGCITI DIVESAKURU NANDINAGARI ZANABAZARSQUARE SOYOMBO PAUCINHAU SUNUWAR
    BHAIKSUKI MARCHEN MASARAMGONDI GUNJALAGONDI TOLONGSIKI MAKASAR KAWI CUNEIFORM
    CYPROMINOAN EGYPTIANHIEROGLYPHS ANATOLIANHIEROGLYPHS GURUNGKHEMA MRO TANGSA
    BASSAVAH PAHAWHHMONG KIRATRAI MEDEFAIDRIN BERIAERFE MIAO TANGUT NUSHU
    KHITANSMALLSCRIPT DUPLOYAN SIGNWRITING NYIAKENGPUACHUEHMONG TOTO WANCHO
    NAGMUNDARI OLONAL TAIYO MENDEKIKAKUI ADLAM KATAKANAORHIRAGANA""".split()

    def language(value, share=0.60):
        value = citation_free(value)
        value = regex.sub(
            r'"[^"]*"|“[^”]*”|«[^»]*»|‘[^’]*’|「[^」]*」|『[^』]*』|(?<!\w)\x27[^\x27]*\x27(?!\w)',
            "",
            value,
        )

        def identifier(match):
            token = match[0]
            letters = regex.findall(r"\p{L}", token)
            drop = (
                "_" in token
                or regex.search(r"\p{N}", token)
                or regex.search(r"\p{Ll}\p{Lu}", token)
                or (len(letters) >= 2 and all(c.isupper() for c in letters))
            )
            return "" if drop else token

        value = regex.sub(r"[\p{L}\p{M}\p{N}_]+", identifier, value)
        letters = "".join(regex.findall(r"\p{L}", value))
        if len(letters) >= 12:
            for script in scripts:
                try:
                    count = len(regex.findall(r"\p{Script=" + script + "}", letters))
                except regex.error:
                    continue
                if count / len(letters) >= share:
                    return script, len(letters)
        return None, len(letters)

    state = dict(
        text="",
        flags=[],
        stop=False,
        answer_open=None,
        unit_ends=[],
        release_at=None,
        cut_at=None,
        answer_end=None,
        prefix_whole_disagreement=False,
    )

    def result():
        return state if details else {k: state[k] for k in ("text", "flags")}

    opening = regex.search(r"<answer>", raw, regex.I)
    if opening is None:
        if finished:
            state.update(flags=["parse"], stop=True)
        return result()
    offset = opening.end()
    state["answer_open"] = offset
    tail = raw[offset:]
    # Only tags defined by the prompt terminate an unclosed answer.
    close = regex.search(r"</?(?:answer|evidence)>", tail, regex.I)
    ended = finished or close is not None
    text = tail[: close.start()] if close else tail
    if close is None:
        # A split prompt tag is not answer text; hold it until it can be classified.
        partial = regex.search(r"<[^<>]*$", text)
        if partial and any(
            t.startswith(partial[0].lower())
            for t in ("<answer>", "</answer>", "<evidence>", "</evidence>")
        ):
            text = text[: partial.start()]
    if ended:
        state["answer_end"] = offset + len(text)
    expected, _ = language(question)
    whole, _ = language(text)
    whole_fails = expected is not None and whole is not None and expected != whole
    # Include the lookahead character in the availability offset for ASCII ends.
    units = []
    for match in regex.finditer(r"[。！？]|[\r\n]|[.!?](?=\s)", text):
        end = match.end()
        available = end + (1 if match[0] in ".!?" else 0)
        units.append((end, offset + available))
    if ended and (not units or units[-1][0] < len(text)):
        units.append((len(text), offset + len(text)))
    clean = citation_free(text)
    seen, counts, previous, scanned, released = set(), Counter(), 0, 0, 0
    for end, available in units:
        state["unit_ends"].append(available)
        prefix = text[:end]
        actual, letters = language(prefix)
        key = tuple(normal(w[0]) for w in words(clean[previous:end]))
        cut = None
        if len(key) >= 4 and key in seen:
            beginning = regex.search(r"\S", clean[previous:end])
            cut = previous + beginning.start()
        if len(key) >= 4:
            seen.add(key)
        tokens = words(clean[:end])
        for index in range(scanned, max(0, len(tokens) - 7)):
            gram = tuple(normal(w[0]) for w in tokens[index : index + 8])
            counts[gram] += 1
            if counts[gram] == 3:
                cut = min(cut, tokens[index].start()) if cut is not None else tokens[index].start()
                break
        scanned = max(0, len(tokens) - 7)
        previous = end
        mismatch = expected is not None and actual is not None and expected != actual
        if state["release_at"] is not None and mismatch:
            state.update(flags=["language_after_release"], stop=True)
        elif (
            state["release_at"] is None
            and letters >= 40
            and mismatch
            and language(prefix, 0.90)[0] not in (None, expected)
        ):
            state.update(flags=["language"], stop=True)
        elif cut is not None:
            state.update(flags=["repeat"], stop=True, cut_at=cut)
            # A release is irrevocable, including a cut within an earlier unit.
            candidate = text[: max(released, cut)].strip()
            script, _ = language(candidate)
            if state["release_at"] is None and expected and script and script != expected:
                state["flags"].append("language")
            else:
                state["text"] = candidate
                if candidate and state["release_at"] is None:
                    state["release_at"] = available
        elif (
            state["release_at"] is not None
            or expected is None
            or (letters >= 40 and actual == expected)
        ):
            state["text"] = prefix.strip()
            released = end
            if state["text"] and state["release_at"] is None:
                state["release_at"] = available
        if state["stop"]:
            break
    if ended and not state["stop"]:
        state["stop"] = True
        if not text.strip():
            state["flags"] = ["parse"]
        elif state["release_at"] is None:
            if whole_fails:
                state["flags"] = ["language"]
            else:
                state["text"] = text.strip()
                state["release_at"] = offset + len(text)
    state["prefix_whole_disagreement"] = bool(
        (state["release_at"] is not None and whole_fails)
        or ("language" in state["flags"] and not whole_fails)
    )
    return result()
